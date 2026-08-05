# The Laws of Robotics - Barnes & Noble Press Interior

This project generates a 7 x 10 inch print interior for:

**The Laws of Robotics of Daniel Joseph Mueller**  
**First Edition**

The body uses Liberation Serif and includes mirrored binding margins, page numbers, the requested dedication, numbered laws, and a divider every 100 laws.

## Fastest run

### Windows PowerShell

```powershell
.\run_build.ps1
```

### Linux or macOS

```bash
./run_build.sh
```

## Manual workflow

```bash
python -m pip install -r requirements.txt
python fetch_source.py
python build_laws_interior.py --source Laws-of-Robotics.txt
python review_pdf.py The_Laws_of_Robotics_of_Daniel_Joseph_Mueller_First_Edition_Interior.pdf
```

## Files

- `build_laws_interior.py` - typesets the complete book.
- `fetch_source.py` - downloads the current repository text.
- `review_pdf.py` - runs preflight tools when available and renders every page to PNG.
- `build_and_review.py` - completes the full fetch/build/review sequence.
- `build_hardcover_cover.py` - creates the B&N printed-case hardcover wrap cover.
- `build_complete_book.py` - creates a 7 x 10 reading PDF with front cover, interior, and back cover pages.
- `run_build.ps1` and `run_build.sh` - one-command launchers.

## Hardcover cover

The supplied B&N printed-case template is 16.389 x 11.5 inches with a 0.5-inch spine.
Generate the matching matte-white wrap cover with:

```bash
python build_hardcover_cover.py
```

## Complete reading PDF

The B&N wrap cover remains a separate upload file. Create a reader-facing PDF with a 7 x 10 front cover page, the complete interior, and a 7 x 10 back cover page with:

```bash
python build_complete_book.py
```

## Review checklist

Review the rendered images in `review_render/`, especially:

1. Half-title, title, copyright, and dedication pages.
2. The first body page and page-number placement on odd/even pages.
3. Every 100-law divider.
4. Several dense pages for clipping, widows, or unusual glyphs.
5. The final two pages.

The source text is preserved exactly apart from whitespace normalization and automatic law numbering.
