'''
Parse ABBY FineReader XML and generate hOCR preview to help visualize contents.

We currently merge text blocks which have been inappropriately split, but probably
need to resegment the entire page from scratch because we also have some
overlapping text blocks that can't be dealt with in a simple-minded fashion.  Paragraph
boundaries are also wonky and should probably be ignored, working from lines instead.

Page characteristics:
- layouts for left and right pages are offset due to gutter
- 3 column layout with vertical rules between columns
- page header has first word, page number, last word centered at head of each of three columns
  (ABBY recognizes the larger font, but with a size anywhere from 9.0-10.5)
- no page footer, but signature marks at bottom of some pages
  (e.g. "22-2" on pg. 171, "VOL. I." left and "23" right on pg 177)
- entries can be split across columns/pages
- entry format is described in detail on pp xix-xxiii with pronunciation key on pg. xxv and other
  symbols & abbreviations on pg. xxvi
- order: word main form (pronunciation) , subordinate words, part(s) of speech, [etymology],
      definition(s) & quotations(s)
  - main word form - bold, title case, larger font, possibly preceded by dagger ( = obsolete)
    or double vertical bar ( = not naturalized)
    (dagger often recognized as lower case 't', double vertical bar occasionally recognized as 'II' 'I!')
    stress mark is "turned period" (ie uppper dot), usually recognized as apostrophe in word
    (needs to be removed for searchable/natural form of word)
  - pronunciation - diacritics & ligatures not being recognized. custom alphabet described pg xxv
  - parts of speech - in italics, generally well recognized
  - etymology - language code, followed by word in italics.  variable quality recognition, but
    probably constrained enough syntax to be able to recover fair amount of info
  - if there are multiple definitions, they are numbered with large bold arabic numbers
    (font info not picked up by OCR, but probably can parse based on structure/layout since
    numbers are at beginning of line, sequential starting at 1)
  - each definition is follow by (optional) list of quotation.  Quotations are in a slightly smaller font.
    Each quto is in a slightly smaller font and of the format: year in bold, author name in small caps,
    title (abbrev.) in italics, quote
  - small caps indicates a cross reference wherever it occurs - ideally should be hyperlinked
- main words occur in alphabetical order (duh!)
'''
from collections import Counter
import gzip
import lxml.etree as ET
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.collections import PatchCollection
import numpy as np
from operator import itemgetter
import os
import requests
import shutil
#from xml.etree import cElementTree
#import zlib

DEBUG = False
PAGESTART = 26  # 351  # 26
PAGELIMIT = 1275
SIZE = 5 * 1024 * 1024
XMLTEMPLATE = 'output/oed-vol1_p%d.xml'
HTMLTEMPLATE = 'output/oed-vol1_p%04d.html'
IATEMPLATE = 'https://archive.org/stream/oed01arch#page/%d/mode/1up'
HEADER = ['<?xml version="1.0" encoding="UTF-8"?>',
          # '<document version="1.0" producer="LuraDocument XML Exporter for ABBYY FineReader" pagesCount="1"',
          # 'xmlns="http://www.abbyy.com/FineReader_xml/FineReader6-schema-v1.xml" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.abbyy.com/FineReader_xml/FineReader6-schema-v1.xml http://www.abbyy.com/FineReader_xml/FineReader6-schema-v1.xml">',
          ]
FILENAME = 'https://ia600401.us.archive.org/7/items/oed01arch/oed01arch_abbyy.gz'


class BoundingBox():
        left = 0
        top = 0
        right = 0
        bottom = 0

        def __init__(self, bbox):
            self.left = bbox[0]
            self.top = bbox[1]
            self.right = bbox[2]
            self.bottom = bbox[3]

        def inner(self, b2):
                '''
                Checks two bounding boxes to see if either completely contains
                the other.  If a completely contained box is found, that inner box
                is returned, otherwise None is returned.
                '''
                if self.contains(b2):
                        return b2
                if b2.contains(self):
                        return self
                return None

        def contains(self,b2):
                '''
                Returns True if b2 is contained by b1
                '''
                # top, left, bottom, right - 0,0 in upper left
                return b2.left >= left and b2.top >= top and b2.bottom <= bottom and b2.right <= b1.right

        def intersects(self,b2):
                '''
                Tests two bounding boxes to see if they intersect (or touch). Returns True
                if they do and false if they don't.
                '''
                return not (self.left >= b2.right or b2.left >= self.right
                            or self.top >= b2.bottom or b2.top >= self.bottom)

        def width(self):
                return self.right - self.left
        def height(self):
                return self.bottom - self.top
        def centerx(self):
                return self.left+self.width()/2

        def union(self,b2):
                return BoundingBox(min(self.left,b2.left), min(self.top,b2.top),
                                       max(self.right,b2.right), max(self.bottom, b2.bottom) )

        def maximize(self,b2):
                '''
                Maximize our bounding box with the other boxes bounds.
                '''
                self.left = min(self.left,b2.left)
                self.top = min(self.top,b2.top)
                self.right = max(self.right,b2.right)
                self.bottom = max(self.bottom, b2.bottom)

        def column(self, cols):
            '''
            Return the column index for the bounding because, given a list
            of column left margins.
            '''
            if self.right < cols[0]:
                # in the left margin
                return -1
            for i in range(1, len(cols)):
                if self.left < cols[i] - 10:
                    return i-1
            return len(cols)-1

        def __str__(self):
                return "bbox %d %d %d %d" % (self.left, self.top, self.right, self.bottom)

        def __repr__(self):
                return "%s %d %d" % (str(self), self.width(), self.height())


def bound_box(block):
        # TODO: refactor to return BoundingBox object
        bbox = block.attrib['title'].split('bbox')[1]
        return map(int, bbox.strip().split(' '))


def extendblock(block1, block2):
        '''
        Merge contents of block2 into block1
        '''
        bb1 = BoundingBox(bound_box(block1))
        bb2 = BoundingBox(bound_box(block2))
        if DEBUG:
            print("merging two blocks: %s, %s" % (bb1, bb2))
        block1.extend(block2.findall("*"))
        bb1.maximize(bb2)
        block1.attrib['title'] = str(bb1)
        if DEBUG:
            print("resulting block: %s" % bb1)
        removeblock(block2)


def removeblock(block):
        block.find("..").remove(block)
        block.clear


def blocktop(block):
    bbox = BoundingBox(bound_box(block))
    return bbox.top


def mergeblocks(dom, columns):
        '''
        Sort text blocks by column and merge those where the columns
        were split up into multiple blocks.

        TODO: This doesn't handle horizontal splits, only vertical splits.
        '''
        cols = [[] for i in range(3)]
        page_bb = BoundingBox([1500, 1500, 1500, 1500]) # Starting page bounding box - center point of page
        blocks = dom.xpath(".//div[contains(concat(' ',@class,' '),' ocr_carea ')]")
        if DEBUG:
            print 'Found %d blocks' % len(blocks)
        if len(blocks) <= 3:
            return
        bboxes = []
        for i in range(len(blocks)):
                block = blocks[i]
                bbox = BoundingBox(bound_box(block))
                bboxes.append(bbox)
                page_bb.maximize(bbox)

                col = bbox.column(columns)
                # TODO: Filter / warn on runts
                if col < 0:
                    removeblock(block)
                    print 'Removed ', repr(bbox)
                else:
                    cols[col].append(block)
                    if DEBUG:
                        print col, columns, repr(bbox)

        # Graphical display of our bounding boxes for debugging
        if DEBUG:
            fig, ax = plt.subplots()
            ax.axis([0, 2700, 3600, 0])
            patches = []

            # add a rectangle for each bounding box
            for bb in bboxes:
                rect = mpatches.Rectangle([bb.left, bb.top],
                                          bb.right - bb.left,
                                          bb.bottom - bb.top, ec="none")
                patches.append(rect)

            colors = np.linspace(0, 1, len(patches))
            collection = PatchCollection(patches, cmap=plt.cm.hsv, alpha=0.3)
            collection.set_array(np.array(colors))
            ax.add_collection(collection)

            plt.subplots_adjust(left=0, right=1, bottom=0, top=1)

            plt.show(block=True)

        # ** need to watch for overlapping bboxes ie bad segmentation**

        # Sort columns by Y position and merge adjacent boxes
        for col in cols:
            if len(col) == 1:
                continue
            lastcenter = -2000
            lastblock = None
            for block in sorted(col, key = lambda b: BoundingBox(bound_box(b)).top):
                bbox = BoundingBox(bound_box(block))

                # Nominal column width is ~720-750 pixels
                w = bbox.width()
                # Full column height is ~3045-3115 pixels
                h = bbox.height()

                # TODO: take runts out of flow (position absolutely?)

                # Nominal column centers 415, 1170, 1920 or 725, 1480, 2230
                # (ie 300 px offset on facing pages)
                c = bbox.centerx()
                #print "%s\t%d\t%d\t%d" % (bbox,c,w,h)

                # TODO: Sort by column & then by Y position before merging?

                # make sure candidates to be merged are the same shape & adjacent
                if DEBUG:
                    print 'Center delta: ', lastcenter - c, w, h, c, lastcenter
                # TODO: Remove this sanity check since they should be in right cols?
                if (abs(lastcenter - c) < 450):
                        extendblock(lastblock, block)
                else:
                        lastcenter = c
                        lastblock = block

        pw = page_bb.width()
        ph = page_bb.height()
        print "Page: %s" % (repr(page_bb))
        blocks = dom.xpath(".//div[contains(concat(' ',@class,' '),' ocr_carea ')]")
        if DEBUG:
            print 'Final block count:  %d' % len(blocks)
        if len(blocks) != 3:
                print '  * wrong # blocks on this page: %d' % len(blocks)
                for bbox in bboxes:
                        print bbox
                if DEBUG:
                    assert False

def numberandlink(dom,pagenum):
	# TODO Add link to page image at Internet Archives
        nxt = dom.find(".//a[@id='next']")
        prev = dom.find(".//a[@id='prev']")
        orig = dom.find(".//a[@id='orig']")
        relativetemplate = HTMLTEMPLATE.split('/')[-1]
        nxt.attrib['href'] = relativetemplate % (pagenum+1)
        prev.attrib['href'] = relativetemplate % (pagenum-1)
        orig.attrib['href'] = IATEMPLATE % (pagenum-24)
        return dom


def findcolumns(dom):
        '''
        Look at line beginning & ending coordinates to compute column gutters.
        Returns a 3-tuple of X page coordinates.

        TODO: Although this information is currently used as input to the block
        merging method, it's becoming clear that we should probably just ignore
        the page segmentation and construct the columns de novo from the line
        information that we have available.  Part of this process will be merging
        not only lines, but their containing paragraphs when a line/block has been
        split horizontally by mistake.
        '''

        lines = dom.findall(".//span[@class='ocr_line']")
        if len(lines) < 30:
            return
        leftcounter = Counter()
        rightcounter = Counter()
        total = 0
        for line in lines:
                # TODO: Check for lines which span multiple columns
                # TODO: Compute bounds of entire text area here too?
                bbox = line.attrib['title'].strip().split(' ')[1:]
                left = int(bbox[0])
                right = int(bbox[2])
                width = right - left
                total += width
                leftcounter[left] += 1
                rightcounter[right] += 1
        print 'Average width: ', total / len(lines)

        # TODO: Need a better algorithm here which takes into account density to handle outliers

        # Find right column's left edge
        last = None
        for k, v in sorted(leftcounter.items(), key=itemgetter(0), reverse=True):
                if last and last - k > 200:
                        # if we're up to the next column, return previous value
                        col3 = last - COLMARGIN
                        break
                if k < 2400 and v > 1:
                        last = k

        # Left column is easy
        col1 = int(sorted(leftcounter.items(), key=itemgetter(0))[0][0])
        if col1 > COLMARGIN:
            col1 -= COLMARGIN
        else:
            col1 = 0

        # Middle column
        last = None
        triggered = False
        col2 = -1
        for k, v in sorted(leftcounter.items(), key=itemgetter(0)):
            if v > 2:  # threshold low frequency bins
                if last:
                    if DEBUG:
                        pass
                        print "Mid col left/delta: ", k, k-last
                    if triggered:
                        if k - last < 10:
                            col2 = last - COLMARGIN
                            if DEBUG:
                                print 'Col 2 left = ', col2
                            break
                    elif k - last > 100:
                        triggered = True
                last = k

        # Workaround for pathological case - should never happen, but does!
        # TODO: should bail in the case of a page with no recognizable content
        if col2 == -1:
            col2 = (col3 - col1) / 2 + col1

        print "Columns: ", col1, col2, col3
        #print "Column left edge frequency: "
        #for k,v in leftcounter.most_common(20):
        #       print k,v
        columnlines = [[],[],[]]
        for line in lines:
                left = int(line.attrib['title'].strip().split(' ')[1])
                if left >= col3:
                        columnlines[2].append(line)
                elif left <= col2:
                        columnlines[0].append(line)
                else:
                        columnlines[1].append(line)
        totallines = len(lines)
        print "Total lines: ", totallines

        # Visualization of line start/end histogram for debugging
        if DEBUG and True:
            plt.axis([0, 2700, 0, 45])
            xsorted = sorted(leftcounter.items(), key=itemgetter(0))
            xvals, counts = zip(*xsorted)  # unzip our values for plot
            plt.bar(xvals, counts, 10)
            xsorted = sorted(rightcounter.items(), key=itemgetter(0))
            xvals, counts = zip(*xsorted)  # unzip our values for plot
            plt.bar(xvals, counts, 10, color='green')
            plt.bar([col1, col2, col3], [40]*3, color='red',
                    linestyle='dotted', width=10)
            plt.show(block=True)

        # Sanity check line counts
        for i in range(3):
            if DEBUG:
                print "Col %d lines" % i, len(columnlines[i])
            if len(columnlines[i]) * 1.0 / totallines < 0.25:
                    print '*** short column %d %d' % (i, len(columnlines[i]))
                    if DEBUG:
                        assert False
            columnlines[i].sort(key=lambda line:  int(line.attrib['title'].strip().split(' ')[2]))

        # Print top and bottom of page
        print("First words: %s\t%s\t%s" % tuple([unicode(columnlines[i][0].xpath("string()")) for i in range(3)]))
        # TODO: Validate & strip head words & page numbers
        print("Last words: %s\t%s\t%s" % tuple([unicode(columnlines[i][-1].xpath("string()")) for i in range(3)]))
        # TODO: Look for and remove signature marks - VOL. I. in col #1
        # 999 in col 3 (at the bottom of every 8th page - img 33/pg 9 is #2 & img 41/pg 17 is #3)

        return col1, col2, col3

def postprocess(dom):
        '''
        Post-process our HTML in an attempt to improve it
        '''
        columns = findcolumns(dom)
        if columns:
            print "Columns: ", columns

            # merge multiple blocks in a column
            mergeblocks(dom, columns)

        # strip headwords & page number after validating no missing pages
        # strip trailing signature marks

        # fix leading symbols t -> dagger & II -> ||
        # (perhaps do this as part of semantic markup)

        # apply semantic markup to entries

        # concatenate hyphenated words

        return dom

def download(remote,local):
    print 'Downloading %s to %s' % (remote, local)
    r = requests.get(remote, stream=True)
    if r.status_code == 200:
        with open(local, 'wb') as f:
            for chunk in r.iter_content():
                f.write(chunk)
    else:
        print 'Download failed with status code %d' % r.status_code

def processfile(filename):
    localfile = 'input/'+filename.split('/')[-1]
    if not os.path.exists(localfile):
        download(filename,localfile)

    xslt = ET.parse('abbyy2hocr.xsl')
    transform = ET.XSLT(xslt)

    shutil.copyfile('3column.css','output/3column.css')

    # Old code to just read a few MB over the network & decompress it
    #    r = requests.get(f, stream=True)
    #    buf = r.raw.read(SIZE)
    #    zd = zlib.decompressobj(16+zlib.MAX_WBITS)
    #    lines = zd.decompress(buf).split('\n')

    print 'Opening %s' % localfile
    pagenum = 0
    linenum = 0
    with gzip.open(localfile, 'rb') as f:
        for line in f:
                linenum += 1
                if line.startswith('<page'):
                    pagenum += 1
                    if pagenum < PAGESTART:
                            continue
                    if pagenum > PAGELIMIT:
                        break
                    xml = list(HEADER)
                    while not line.startswith('</page'):
                        xml.append(line)
                        linenum += 1
                        line = f.next()
                    xml.append(line)
            #        xml.append('</document>')

            # Our extracted XML file if it's interesting for debugging
                    #with file(XMLTEMPLATE % pagenum, 'w') as of:
                    #    of.write('\n'.join(xml))

                    dom = ET.fromstring('\n'.join(xml))

                    # Transform to hOCR
                    newdom = transform(dom)

                    newdom = postprocess(newdom)

		    # number page and add next/previous page link
                    newdom = numberandlink(newdom, pagenum)

                    print 'Writing page %d - %d XML lines processed' % (pagenum,linenum)
                    with file(HTMLTEMPLATE % pagenum, 'w') as of:
                        of.write(ET.tostring(newdom, pretty_print=True))

def main():
    processfile(FILENAME)

main()
