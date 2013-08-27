<?xml version='1.0' encoding='utf-8'?>
<xsl:stylesheet version='1.0' xmlns:xsl='http://www.w3.org/1999/XSL/Transform'>
<!-- 
Author: Rod Page
Source: http://iphylo.blogspot.com/2011/07/correcting-ocr-using-hocr-firefox.html#comment-400434491
-->
<xsl:output method='html' version='1.0' encoding='utf-8' indent='yes'/>


<xsl:variable name="scale" select="800 div //page/@width" />

<xsl:template match="/">
<html>
<head>
<meta name="ocr-capabilities" content="ocr_line ocr_page"/>
<meta name="ocr-langs" content="en"/>
<meta name="ocr-scripts" content="Latn"/>
<meta name="ocr-microformats" content=""/>
<title>OCR Output</title>
</head>
<body>
<xsl:apply-templates select="//page" />
</body>
</html>
</xsl:template>

<xsl:template match="//page">
  <div class="ocr_page">
		<xsl:attribute name="title">
			<xsl:text>bbox 0 0 </xsl:text>
			<xsl:value-of select="@width" />
			<xsl:text> </xsl:text>
			<xsl:value-of select="@height" />
			<xsl:text>; image bulletinofzoolo642007inte.jpeg</xsl:text>
		</xsl:attribute>

	<xsl:apply-templates select="block" />
	</div>
</xsl:template>

<xsl:template match="block">
<xsl:apply-templates select="text/par" />
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
	<xsl:choose>
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
		<xsl:otherwise>
			<xsl:apply-templates select="charParams" />
		</xsl:otherwise>
	</xsl:choose>


</xsl:template>

<xsl:template match="charParams">
	<xsl:value-of select="." /> 
</xsl:template>

</xsl:stylesheet>