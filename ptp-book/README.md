# ptp-book

Builds an EPUB and a PDF from Meinberg's IEEE 1588 / PTP blog articles,
one article per chapter, in reading-path order.

```
pip install requests beautifulsoup4 pillow
python build_ptp_book.py
```

You also need [pandoc](https://pandoc.org/installing.html) and one PDF
engine: xelatex, weasyprint, wkhtmltopdf or Calibre's `ebook-convert`. The
output goes to `ptp_book/`, which is git-ignored. The articles are
Meinberg's, so the generated book is for personal use only.
