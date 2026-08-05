Book component format
=====================

The interior builder reads this folder before falling back to Laws-of-Robotics.txt.
Edit these .txt files to change book metadata, front matter, definitions, or chapters
without changing Python code.

Front-matter files can use metadata tokens from metadata.txt, such as {{title}},
{{edition}}, {{author}}, and {{copyright_year}}.

Front matter
------------

Files in front-matter are rendered in this order:

1. half-title.txt
2. title-page.txt
3. copyright.txt
4. dedication.txt
5. definitions.txt, only when it does not begin with <skip/>

Definitions
-----------

To add a definitions preface, replace the contents of front-matter/definitions.txt
with something like:

<spacer height="0.75"/>

<section title="Definitions"/>

<definition term="MAN">
Definition text goes here.
</definition>

<definition term="Vanity">
Definition text goes here.
</definition>

The builder keeps front matter unnumbered and starts the numbered body on the next
odd page.

Chapters
--------

Every .txt file in chapters is rendered in filename order. Add a chapter by creating
a new file such as chapters/02-new-chapter.txt:

<chapter title="New Chapter Title"/>

First numbered law or paragraph.

Second numbered law or paragraph.

Blank lines separate numbered laws. Law numbering continues across chapters.
Use <skip/> as the first line of a chapter file to exclude it.

Tags
----

Supported block tags:

<spacer height="0.25"/>
<pagebreak/>
<section title="Definitions"/>
<chapter title="Chapter Title"/>
<include path="../Laws-of-Robotics.txt"/>
<half-title>Text</half-title>
<title>Text</title>
<edition>Text</edition>
<author>Text</author>
<copyright>Text</copyright>
<dedication-heading>Text</dedication-heading>
<dedication>Text</dedication>
<center>Text</center>
<paragraph>Text</paragraph>
<preface>Text</preface>
<definition term="Term">Text</definition>

Supported inline tags:

<italic>italic text</italic>
<bold>bold text</bold>
<term>bold term text</term>
<br/>
<linebreak/>

Include paths are resolved relative to this book-components folder.
