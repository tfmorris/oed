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
'''
from collections import Counter
import gzip
import lxml.etree as ET
from operator import itemgetter
import os
import requests
import shutil
from xml.etree import cElementTree
import zlib

PAGESTART=26
PAGELIMIT=500
SIZE=5*1024*1024
XMLTEMPLATE = 'output/oed-vol1_p%d.xml'
HTMLTEMPLATE = 'output/oed-vol1_p%04d.html'
HEADER = ['<?xml version="1.0" encoding="UTF-8"?>',
#    '<document version="1.0" producer="LuraDocument XML Exporter for ABBYY FineReader" pagesCount="1"',
#    'xmlns="http://www.abbyy.com/FineReader_xml/FineReader6-schema-v1.xml" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.abbyy.com/FineReader_xml/FineReader6-schema-v1.xml http://www.abbyy.com/FineReader_xml/FineReader6-schema-v1.xml">',
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

        def __str__(self):
                return "bbox %d %d %d %d" % (self.left, self.top, self.right, self.bottom)

        def __repr__(self):
                return "%s %d %d" % (str(self), self.width(), self.height())
        
def bound_box(block):
        bbox = block.attrib['title'].split('bbox')[1]
        return map(int,bbox.strip().split(' '))


def extendblock(block1, block2):
        '''
        Merge contents of block2 into block1
        '''
        bb1 = BoundingBox(bound_box(block1))
        bb2 = BoundingBox(bound_box(block2))
        #print("merging two blocks: %s, %s" % (bb1,bb2))
        block1.extend(block2.findall("*"))
        bb1.maximize(bb2)
        block1.attrib['title']=str(bb1)
        #print("resulting block: %s" % bb1)
        block2.find("..").remove(block2)
        block2.clear
        
def mergeblocks(dom):
        '''
        Sort text blocks by column and merge those where the columns
        were split up into multiple blocks.  
        '''
        cols=[[] for i in range(3)]
        page_bb = BoundingBox([1500,1500,1500,1500]) # Starting page bounding box - center point of page
        lastcenter = -2000
        blocks = dom.findall(".//div[@class='ocr_carea column']")
        #print 'Found %d blocks' % len(blocks)
        bboxes = []
        for i in range(len(blocks)):
                block = blocks[i]
                bbox = BoundingBox(bound_box(block))
                bboxes.append(bbox)
                page_bb.maximize(bbox)

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
                # ** need to watch for overlapping bboxes ie bad segmentation**
                
                # make sure candidates to be merged are the same shape & adjacent
                if (abs(lastcenter - c) < 100):
                       extendblock(lastblock,block)
                else:
                        lastcenter = c
                        lastblock = block
        pw = page_bb.width()
        ph = page_bb.height()
        print "Page: %s" % (repr(page_bb))
        blocks = dom.findall(".//div[@class='ocr_carea column']")
        #print 'Finally remaining %d blocks' % len(blocks)
        if len(blocks) > 3:
                print '  * too many blocks on this page: %d' % len(blocks)
                for bbox in bboxes:
                        print bbox

def numberandlink(dom,pagenum):
        nxt = dom.find(".//a[@id='next']")
        prev = dom.find(".//a[@id='prev']")
        nxt.attrib['href'] = HTMLTEMPLATE.split('/')[-1] % (pagenum+1)
        prev.attrib['href'] = HTMLTEMPLATE.split('/')[-1] % (pagenum-1)
        return dom

def findcolumns(dom):
        lines = dom.findall(".//span[@class='ocr_line']")
        leftcounter = Counter()
        for line in lines:
                left = int(line.attrib['title'].strip().split(' ')[1])
                leftcounter[left] +=1
        last = None
        # Find right column's left edge
        for k,v in sorted(leftcounter.items(), key=itemgetter(0), reverse=True):
                if last and last-k > 200:
                        col3 = last
                        break
                if k < 2000:
                        last = k
        # Left column is easy
        col1 = int(sorted(leftcounter.items(), key=itemgetter(0))[0][0])
        last = None
        # Middle column 
        for k,v in sorted(leftcounter.items(), key=itemgetter(0)):
                if last and k-last > 300:
                        col2 = k
                        break
                last = k
        print "Columns: ", col1, col2, col3
        for k,v in leftcounter.most_common(20):
               print k,v
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
        print totallines
        for i in range(3):
            print len(columnlines[i])
            if len(columnlines[i]) * 1.0 / totallines < 0.25:
                    print '*** short column'
                    print xyzzy
            columnlines[i].sort(key=lambda line:  int(line.attrib['title'].strip().split(' ')[2]))
        print("%s\t%s\t%s" % tuple([unicode(columnlines[i][0].xpath("string()")) for i in range(3)]))
        print("%s\t%s\t%s" % tuple([unicode(columnlines[i][-1].xpath("string()")) for i in range(3)]))

        return col1, col2, col3

def postprocess(dom):
        '''
        Post-process our HTML in an attempt to improve it
        '''
        columns = findcolumns(dom)
        print "Columns: ", columns
        mergeblocks(dom)

        # merge multiple blocks in a column

        # strip headwords

        # fix leading symbols t -> dagger & II -> ||

        # apply semantic markup to entries

        # concatenate hyphenated words

        # number page and add next/previous page link
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
            #        with file(XMLTEMPLATE % pagenum, 'w') as of:
            #            of.write('\n'.join(xml))

                    dom = ET.fromstring('\n'.join(xml))

                    # Transform to hOCR
                    newdom = transform(dom)

                    newdom = postprocess(newdom)
                    newdom = numberandlink(newdom, pagenum)

                    print 'Writing page %d - %d XML lines processed' % (pagenum,linenum)
                    with file(HTMLTEMPLATE % pagenum, 'w') as of:
                        of.write(ET.tostring(newdom, pretty_print=True))

def main():
    processfile(FILENAME)

main()
