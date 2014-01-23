import gzip
import lxml.etree as ET
import os
import requests
from xml.etree import cElementTree
import zlib

PAGESTART=25
PAGELIMIT=50
SIZE=5*1024*1024
XMLTEMPLATE = 'output/oed-vol1_p%d.xml'
HTMLTEMPLATE = 'output/oed-vol1_p%04d.html'
HEADER = ['<?xml version="1.0" encoding="UTF-8"?>',
#    '<document version="1.0" producer="LuraDocument XML Exporter for ABBYY FineReader" pagesCount="1"',
#    'xmlns="http://www.abbyy.com/FineReader_xml/FineReader6-schema-v1.xml" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.abbyy.com/FineReader_xml/FineReader6-schema-v1.xml http://www.abbyy.com/FineReader_xml/FineReader6-schema-v1.xml">',
    ]
FILENAME = 'https://ia600401.us.archive.org/7/items/oed01arch/oed01arch_abbyy.gz'


xslt = ET.parse('abbyy2hocr.xsl')
transform = ET.XSLT(xslt)

def mergeblocks(dom):
        '''
        Sort text blocks by column and merge those where the columns
        were split up into multiple blocks.  
        '''
        blocks = dom.findall(".//div[@class='ocr_carea column']")
        print 'Found %d blocks' % len(blocks)
        cols=[[] for i in range(3)]
        pl = pt = pr = pb = 1500
        lastcenter = -2000
        for block in blocks:
                bbox = block.attrib['title'].split('bbox')[1]
                l,t,r,b = map(int,bbox.strip().split(' '))
                if l < pl:
                        pl = l
                if t < pt:
                        pt = t
                if r > pr:
                        pr = r
                if b > pb:
                        pb = b
                # Nominal column width is ~720-750 pixels
                w = r-l
                # Full column height is ~3045-3115 pixels
                h = b-t
                # Nominal column centers 415, 1170, 1920 or 725, 1480, 2230
                # (ie 300 px offset on facing pages)
                c = l+(w)/2
                print "%d\t%d\t%d\t%d\t%d\t%d\t%d" % (l,r,t,b,c,w,h)
                # Sort by column & then by Y position before merging
                # ** need to watch for overlapping bboxes ie bad segmentation**
                # make sure candidates to be merged are the same shape & adjacent
                if (abs(lastcenter - c) < 100):
                        print("merging")
                        lastblock.extend(block.findall("*"))
                        # TODO: update bounding box?
                        block.find("..").remove(block)
                        block.clear
                else:
                        lastcenter = c
                        lastblock = block
        pw = pr - pl
        ph = pb - pt
        print "Page bounding box: %d\t%d\t%d\t%d" % (pl,pt,pw,ph)
        blocks = dom.findall(".//div[@class='ocr_carea column']")
        print 'Finally remaining %d blocks' % len(blocks)

def numberandlink(dom,pagenum):
        nxt = dom.find(".//a[@id='next']")
        prev = dom.find(".//a[@id='prev']")
        nxt.attrib['href'] = HTMLTEMPLATE.split('/')[-1] % (pagenum+1)
        prev.attrib['href'] = HTMLTEMPLATE.split('/')[-1] % (pagenum-1)
        return dom

def postprocess(dom):
        '''
        Post-process our HTML in an attempt to improve it
        '''
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
