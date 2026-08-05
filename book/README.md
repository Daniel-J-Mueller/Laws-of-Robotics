# The Laws of Robotics - Barnes & Noble Press Interior

This project generates a 7 x 10 inch print interior for:

**The Laws of Robotics of Daniel Joseph Mueller**  
**First Edition**

The body uses Liberation Serif and includes mirrored binding margins, page numbers, the requested dedication, numbered laws, and a divider every 100 laws.

## Editable book components

The interior build now prefers editable `.txt` files in `book-components/`.
Use these files for ordinary book edits instead of changing Python:

- `book-components/metadata.txt` - title, edition, author, copyright year.
- `book-components/front-matter/*.txt` - half-title, title page, copyright, dedication, and optional definitions preface.
- `book-components/chapters/*.txt` - sorted chapter files. Each chapter gets its own heading.

The existing laws source is included by reference from `book-components/chapters/01-the-laws.txt`.
To add a new chapter, add a file like `book-components/chapters/02-new-chapter.txt`:

```text
<chapter title="New Chapter Title"/>

First numbered law or paragraph.

Second numbered law or paragraph.
```

Blank lines separate numbered laws. See `book-components/README.txt` for the supported tags, including `<center>`, `<italic>`, `<bold>`, `<spacer height="0.25"/>`, `<pagebreak/>`, and the optional definitions section format.

## Fastest run

From the `book/` directory:

```bash
python book-assembler.py
```

The assembler writes:

- `OUTPUT/The_Laws_of_Robotics_of_Daniel_Joseph_Mueller_First_Edition_Interior.pdf`
- `OUTPUT/The_Laws_of_Robotics_of_Daniel_Joseph_Mueller_Hardcover_Cover.pdf`

### Windows PowerShell

```powershell
.\scripts\run_build.ps1
```

### Linux or macOS

```bash
./scripts/run_build.sh
```

## Manual workflow

```bash
python -m pip install -r requirements.txt
python book-assembler.py
python scripts/review_pdf.py OUTPUT/The_Laws_of_Robotics_of_Daniel_Joseph_Mueller_First_Edition_Interior.pdf
```

## Files

- `book-assembler.py` - no-argument assembler for the interior and exterior cover PDFs.
- `book-components/` - editable text components for metadata, front matter, definitions, and chapters.
- `OUTPUT/` - finished assembler output PDFs.
- `scripts/build_laws_interior.py` - typesets the interior.
- `scripts/fetch_source.py` - downloads the current repository text.
- `scripts/review_pdf.py` - runs preflight tools when available and renders every page to PNG.
- `scripts/build_and_review.py` - completes the full fetch/build/review sequence.
- `scripts/build_hardcover_cover.py` - creates the B&N printed-case hardcover wrap cover.
- `scripts/build_complete_book.py` - creates a 7 x 10 reading PDF with front cover, interior, and back cover pages.
- `scripts/run_build.ps1` and `scripts/run_build.sh` - one-command launchers.

## Hardcover cover

The supplied B&N printed-case template is 16.389 x 11.5 inches with a 0.5-inch spine.
Generate the matching matte-white wrap cover with:

```bash
python scripts/build_hardcover_cover.py
```

## Complete reading PDF

The B&N wrap cover remains a separate upload file. Create a reader-facing PDF with a 7 x 10 front cover page, the complete interior, and a 7 x 10 back cover page with:

```bash
python scripts/build_complete_book.py
```

## Review checklist

Review the rendered images in `review/review_render/`, especially:

1. Half-title, title, copyright, and dedication pages.
2. The first body page and page-number placement on odd/even pages.
3. Every 100-law divider.
4. Several dense pages for clipping, widows, or unusual glyphs.
5. The final two pages.

The source text is preserved exactly apart from whitespace normalization and automatic law numbering.
