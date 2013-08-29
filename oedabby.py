import lxml.etree as ET
import requests
from xml.etree import cElementTree
import zlib

PAGELIMIT=30
SIZE=5*1024*1024
XMLTEMPLATE = 'output/oed-vol1_p%d.xml'
HTMLTEMPLATE = 'output/oed-vol1_p%d.html'
HEADER = ['<?xml version="1.0" encoding="UTF-8"?>',
#    '<document version="1.0" producer="LuraDocument XML Exporter for ABBYY FineReader" pagesCount="1"',
#    'xmlns="http://www.abbyy.com/FineReader_xml/FineReader6-schema-v1.xml" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.abbyy.com/FineReader_xml/FineReader6-schema-v1.xml http://www.abbyy.com/FineReader_xml/FineReader6-schema-v1.xml">',
    ]


xslt = ET.parse('abbyy2hocr.xsl')
transform = ET.XSLT(xslt)

f = 'https://ia600401.us.archive.org/7/items/oed01arch/oed01arch_abbyy.gz'
r = requests.get(f, stream=True)

zd = zlib.decompressobj(16+zlib.MAX_WBITS)
buf = r.raw.read(SIZE)

pagenum = 0
linenum = 0
lines = zd.decompress(buf).split('\n')
while linenum < len(lines):
    linenum += 1
    line = lines[linenum]
    if line.startswith('<page'):
        pagenum += 1
        if pagenum > PAGELIMIT:
            break
        xml = list(HEADER)
        while not line.startswith('</page'):
            xml.append(line)
            linenum += 1
            line = lines[linenum]
        xml.append(line)
#        xml.append('</document>')
        
# Our extracted XML file if it's interesting for debugging
        with file(XMLTEMPLATE % pagenum, 'w') as of:
            of.write('\n'.join(xml))
            
        dom = ET.fromstring('\n'.join(xml))

        # Transform to hOCR
        newdom = transform(dom)

        # post-process HTML

        # strip headwords

        # fix leading symbols t -> dagger & II -> ||

        # apply semantic markup to entries

        print 'Writing page %d - %d XML lines processed' % (pagenum,linenum)
        with file(HTMLTEMPLATE % pagenum, 'w') as of:
            of.write(ET.tostring(newdom, pretty_print=True))
        
