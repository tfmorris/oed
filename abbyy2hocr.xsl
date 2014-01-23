<?xml version='1.0' encoding='utf-8'?>
<xsl:stylesheet version='1.0' xmlns:xsl='http://www.w3.org/1999/XSL/Transform'>
<!-- 
Adapted by Tom Morris for the first edition of the Oxford English Dictionary
based on a version by Rod Page
Source: http://iphylo.blogspot.com/2011/07/correcting-ocr-using-hocr-firefox.html#comment-400434491
-->
<xsl:output method='html' version='1.0' encoding='utf-8' indent='yes'/>

<xsl:variable name="scale" select="800 div //page/@width" />

<!-- Compute column boundaries - way may need something fancier -->
<xsl:variable name="left" select="//page/@width div 4" />
<xsl:variable name="right" select="//page/@width * 55 div 100" />

<xsl:template match="/">
<html>
<head>
<meta name="ocr-system" content="ABBYY-FineReader 6"/>
<meta name="ocr-capabilities" content="ocr_line ocr_page"/>
<meta name="ocr-langs" content="en"/>
<meta name="ocr-scripts" content="Latn"/>
<meta name="ocr-microformats" content=""/>
<link rel="stylesheet" type="text/css" href="3column.css" />
<title>OCR Output</title>
</head>
<body>

<xsl:apply-templates select="//page" />
</body>
</html>
</xsl:template>

<xsl:template match="//page">
  <div id="header"><a id="prev">Prev </a> header placeholder <a id="next"> Next</a> </div>
  <div class="ocr_page" id="container">
		<xsl:attribute name="scan_res">
			<xsl:value-of select="@resolution" />
			<xsl:text> </xsl:text>
			<xsl:value-of select="@resolution" />
		</xsl:attribute>
		<xsl:attribute name="title">
			<xsl:text>bbox 0 0 </xsl:text>
			<xsl:value-of select="@width" />
			<xsl:text> </xsl:text>
			<xsl:value-of select="@height" />
			<xsl:text>; </xsl:text>
		</xsl:attribute>

	<xsl:apply-templates select="block" />

  </div>
  <div id="footer">footer placeholder</div>
</xsl:template>

<xsl:template match="block">
  <div class="ocr_carea column">
		<xsl:attribute name="title">
			<xsl:text>blockType: </xsl:text>
			<xsl:value-of select="@blockType" />
			<xsl:text> bbox </xsl:text>
			<xsl:value-of select="@l" />
			<xsl:text> </xsl:text>
			<xsl:value-of select="@t" />
			<xsl:text> </xsl:text>
			<xsl:value-of select="@r" />
			<xsl:text> </xsl:text>
			<xsl:value-of select="@b" />
		</xsl:attribute>
		<xsl:attribute name="id">
		  <xsl:choose>
		    <xsl:when test="@l &lt; $left">
		      <xsl:text>left</xsl:text>
		    </xsl:when>
		    <xsl:when test="@l &gt; $right">
		      <xsl:text>right</xsl:text>
		    </xsl:when>
		    <xsl:otherwise>
		      <xsl:text>center</xsl:text>
		    </xsl:otherwise>
		  </xsl:choose>
		</xsl:attribute>

    <xsl:apply-templates select="text/par" />
  </div>
</xsl:template>

<xsl:template match="par">
	<p class="ocr_par">
		<xsl:apply-templates select="line" />
	</p>
</xsl:template>


<xsl:template match="line">
<span class="ocr_line">
		<xsl:attribute name="title">
			<xsl:text>bbox </xsl:text>
			<xsl:value-of select="@l" />
			<xsl:text> </xsl:text>
			<xsl:value-of select="@t" />
			<xsl:text> </xsl:text>
			<xsl:value-of select="@r" />
			<xsl:text> </xsl:text>
			<xsl:value-of select="@b" />
		</xsl:attribute>
	<xsl:apply-templates select="formatting" />
</span>
<xsl:text> </xsl:text>
</xsl:template>

<xsl:template match="formatting">
   <span>
     <xsl:attribute name="style">
	<xsl:text>font-size:</xsl:text>
	<xsl:value-of select="@fs" />
	<xsl:text>0pt</xsl:text>
     </xsl:attribute>

	<xsl:choose>
		<xsl:when test="@bold='true' and @italic='true'">
			<b><em>
			<xsl:apply-templates select="charParams" />
			</em></b>
		</xsl:when>
		<xsl:when test="@bold='true'">
			<b>
			<xsl:apply-templates select="charParams" />
			</b>
		</xsl:when>
		<xsl:when test="@italic='true'">
			<em>
			<xsl:apply-templates select="charParams" />
			</em>
		</xsl:when>
		<xsl:when test="@smallcaps='true'">
			<span style="font-variant:small-caps;">
			<xsl:apply-templates select="charParams" />
			</span>
		</xsl:when>
		<xsl:when test="@superscript='true'">
			<sup>
			<xsl:apply-templates select="charParams" />
			</sup>
		</xsl:when>
		<xsl:when test="@subscript='true'">
			<sub>
			<xsl:apply-templates select="charParams" />
			</sub>
		</xsl:when>
		<xsl:otherwise>
			<xsl:apply-templates select="charParams" />
		</xsl:otherwise>
	</xsl:choose>

   </span>
</xsl:template>

<xsl:template match="charParams[@charConfidence &lt; 45 and @wordFromDictionary='false']" priority="5">
  <span>
     <xsl:attribute name="class">
	<xsl:text>very_low_confidence</xsl:text>
     </xsl:attribute>
	<xsl:value-of select="." /> 
  </span>
</xsl:template>
<xsl:template match="charParams[@charConfidence &lt; 50 and @wordFromDictionary='false']" priority="4">
  <span>
     <xsl:attribute name="class">
	<xsl:text>low_confidence</xsl:text>
     </xsl:attribute>
	<xsl:value-of select="." /> 
  </span>
</xsl:template>

<xsl:template match="charParams" priority="3">
	<xsl:value-of select="." /> 
</xsl:template>

</xsl:stylesheet>
