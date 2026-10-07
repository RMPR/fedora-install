#!/usr/bin/env python3
"""
Build a private-use EPUB and PDF from the Meinberg PTP reading path,
one article per chapter.

Requirements:
    pip install requests beautifulsoup4
    pip install pillow            # optional: converts WebP/GIF images for the PDF
    pandoc                        # https://pandoc.org/installing.html
    A PDF engine (any one):       xelatex (TeX Live / MiKTeX), weasyprint,
                                  wkhtmltopdf, or Calibre's ebook-convert

Usage:
    python build_ptp_book.py
    python build_ptp_book.py --out-dir mybook --no-pdf
"""

import argparse
import html
import mimetypes
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

URLS = [
    "https://blog.meinbergglobal.com/2013/09/14/ieee-1588-accurate/",
    "https://blog.meinbergglobal.com/2013/10/28/one-step-two-step/",
    "https://blog.meinbergglobal.com/2013/09/19/end-end-versus-peer-peer/",
    "https://blog.meinbergglobal.com/2013/10/21/ieee-1588-clock-types/",
    "https://blog.meinbergglobal.com/2019/07/31/whats-coming-in-the-next-edition-of-ieee-1588-profile-isolation/",
    "https://blog.meinbergglobal.com/2019/12/06/tlvs-in-ptp-messages/",
    "https://blog.meinbergglobal.com/2019/04/15/ptp-timescale-and-what-the-heck-is-arb-time/",
    "https://blog.meinbergglobal.com/2013/11/14/makes-master-best/",
    "https://blog.meinbergglobal.com/2022/02/01/bmca-deep-dive-part-1/",
    "https://blog.meinbergglobal.com/2022/03/11/bmca-deep-dive-part-2/",
    "https://blog.meinbergglobal.com/2014/01/09/ieee-1588-default-profile/",
    "https://blog.meinbergglobal.com/2014/08/15/hands-on-tutorial-ptpv2/",
]

BOOK_TITLE = "IEEE 1588 / PTP: A Reading Path"
BOOK_SUBTITLE = "Articles from the Meinberg Time Synchronization Blog (private copy)"

HEADERS = {"User-Agent": "Mozilla/5.0 (personal offline reading; ptp-book-builder)"}
REQUEST_DELAY_S = 1.5
RETRIES = 3

JUNK_SELECTORS = [
    "script", "style", "noscript", "iframe", "form",
    ".sharedaddy", ".sd-sharing-enabled", ".jp-relatedposts", ".addtoany_share_save_container",
    ".social-share", ".share-buttons", ".entry-comments", ".comment-respond",
    ".wp-block-buttons", ".yarpp-related", ".navigation", ".post-navigation",
]

PAGE_BREAK_CSS = """
h1 { page-break-before: always; break-before: page; }
h1.title { page-break-before: avoid; break-before: avoid; }
img { max-width: 100%; height: auto; }
.byline { color: #555; font-style: italic; margin-bottom: 1.5em; }
.source { font-size: 0.85em; color: #555; margin-top: 2em; }
body { font-family: Georgia, serif; line-height: 1.5; }
"""


def fetch(session, url, binary=False):
    last_err = None
    for attempt in range(1, RETRIES + 1):
        try:
            r = session.get(url, headers=HEADERS, timeout=30)
            r.raise_for_status()
            return r.content if binary else r.text
        except requests.RequestException as e:
            last_err = e
            time.sleep(attempt * 2)
    raise RuntimeError(f"could not fetch {url}: {last_err}")


def pick_img_src(img):
    for attr in ("data-src", "data-lazy-src", "data-orig-file", "src"):
        val = img.get(attr)
        if val and not val.startswith("data:"):
            return val
    srcset = img.get("data-srcset") or img.get("srcset")
    if srcset:
        candidates = [c.strip().split(" ")[0] for c in srcset.split(",") if c.strip()]
        if candidates:
            return candidates[-1]
    return None


def convert_image_for_latex(path):
    if path.suffix.lower() not in (".webp", ".gif"):
        return path
    try:
        from PIL import Image
    except ImportError:
        print(f"    note: {path.name} is {path.suffix}; install Pillow to include it in the PDF")
        return path
    png = path.with_suffix(".png")
    with Image.open(path) as im:
        im.convert("RGBA" if im.mode in ("RGBA", "P", "LA") else "RGB").save(png)
    return png


def extract_article(session, url, chapter_no, img_dir):
    page = fetch(session, url)
    soup = BeautifulSoup(page, "html.parser")

    title_el = soup.select_one("h1.entry-title") or soup.find("h1")
    title = title_el.get_text(strip=True) if title_el else f"Article {chapter_no}"

    author_el = soup.select_one(".entry-author-name") or soup.select_one("[rel=author]")
    author = author_el.get_text(strip=True) if author_el else ""
    date_el = soup.select_one("time.entry-time") or soup.find("time")
    date = date_el.get_text(strip=True) if date_el else ""

    body = (soup.select_one(".entry-content")
            or soup.select_one("article .post-content")
            or soup.find("article"))
    if body is None:
        raise RuntimeError("couldn't locate the article body on the page")

    for sel in JUNK_SELECTORS:
        for el in body.select(sel):
            el.decompose()

    for k, img in enumerate(body.find_all("img"), 1):
        src = pick_img_src(img)
        if not src:
            img.decompose()
            continue
        abs_src = urljoin(url, src)
        ext = Path(urlparse(abs_src).path).suffix.lower() or ".png"
        local = img_dir / f"ch{chapter_no:02d}_{k:02d}{ext}"
        try:
            local.write_bytes(fetch(session, abs_src, binary=True))
            local = convert_image_for_latex(local)
            for attr in list(img.attrs):
                if attr not in ("alt", "title"):
                    del img[attr]
            img["src"] = f"{img_dir.name}/{local.name}"
        except RuntimeError as e:
            print(f"    warning: image skipped ({e})")
            img.decompose()

    for a in body.find_all("a"):
        if a.find("img") and len(a.get_text(strip=True)) == 0:
            a.unwrap()

    byline = " · ".join(p for p in (author, date) if p)
    chapter_html = [f"<h1>{html.escape(title)}</h1>"]
    if byline:
        chapter_html.append(f'<p class="byline">{html.escape(byline)}</p>')
    chapter_html.append(body.decode_contents())
    chapter_html.append(
        f'<p class="source">Source: <a href="{html.escape(url)}">{html.escape(url)}</a></p>'
    )
    return title, author, "\n".join(chapter_html)


def run(cmd, cwd):
    print("  $ " + " ".join(cmd))
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stderr.strip()[-2000:])
    return result.returncode == 0


def build_pdf(out_dir, html_name, pdf_name, epub_name):
    for engine in ("xelatex", "lualatex", "pdflatex"):
        if shutil.which(engine):
            ok = run(["pandoc", html_name, "-o", pdf_name, "--toc",
                      f"--pdf-engine={engine}",
                      "--top-level-division=chapter",
                      "-V", "documentclass=report",
                      "-V", "geometry:margin=1in",
                      "-V", "colorlinks=true",
                      "--metadata-file=metadata.yaml"], out_dir)
            if ok:
                return True
    for engine in ("weasyprint", "wkhtmltopdf"):
        if shutil.which(engine):
            ok = run(["pandoc", html_name, "-o", pdf_name, "--toc", "--standalone",
                      f"--pdf-engine={engine}", "--css=book.css",
                      "--metadata-file=metadata.yaml"], out_dir)
            if ok:
                return True
    if shutil.which("ebook-convert"):
        return run(["ebook-convert", epub_name, pdf_name,
                    "--pdf-page-numbers", "--paper-size", "a4"], out_dir)
    print("  No PDF engine found. Install one of: TeX Live/MiKTeX (xelatex), "
          "weasyprint, wkhtmltopdf, or Calibre — or convert the EPUB with Calibre.")
    return False


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out-dir", default="ptp_book")
    ap.add_argument("--no-pdf", action="store_true", help="only build the EPUB")
    args = ap.parse_args()

    if not shutil.which("pandoc"):
        sys.exit("pandoc not found — install it from https://pandoc.org/installing.html")

    out_dir = Path(args.out_dir)
    img_dir = out_dir / "images"
    img_dir.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    chapters, authors, failures = [], [], []

    for i, url in enumerate(URLS, 1):
        print(f"[{i:2d}/{len(URLS)}] {url}")
        try:
            title, author, chapter = extract_article(session, url, i, img_dir)
            chapters.append(chapter)
            if author and author not in authors:
                authors.append(author)
            print(f"    ✓ {title}")
        except Exception as e:
            failures.append((url, str(e)))
            print(f"    ✗ {e}")
        time.sleep(REQUEST_DELAY_S)

    if not chapters:
        sys.exit("No articles could be downloaded — check your connection and try again.")

    (out_dir / "book.css").write_text(PAGE_BREAK_CSS, encoding="utf-8")
    author_line = ", ".join(authors) if authors else "Meinberg"
    (out_dir / "metadata.yaml").write_text(
        "---\n"
        f'title: "{BOOK_TITLE}"\n'
        f'subtitle: "{BOOK_SUBTITLE}"\n'
        f'author: "{author_line}"\n'
        "lang: en\n"
        "rights: Private copy for personal use only. © Meinberg Funkuhren GmbH & Co. KG\n"
        "toc-title: Contents\n"
        "---\n",
        encoding="utf-8",
    )
    html_name = "ptp_book.html"
    (out_dir / html_name).write_text(
        "<!DOCTYPE html><html><head><meta charset='utf-8'></head><body>\n"
        + "\n".join(chapters) + "\n</body></html>",
        encoding="utf-8",
    )

    print("\nBuilding EPUB…")
    epub_name = "PTP_Reading_Path.epub"
    epub_ok = run(["pandoc", html_name, "-o", epub_name, "--toc", "--toc-depth=1",
                   "--css=book.css", "--metadata-file=metadata.yaml"], out_dir)

    pdf_ok = None
    if not args.no_pdf:
        print("\nBuilding PDF…")
        pdf_ok = build_pdf(out_dir, html_name, "PTP_Reading_Path.pdf", epub_name)

    print("\n" + "=" * 60)
    print(f"Chapters included: {len(chapters)}/{len(URLS)}")
    if epub_ok:
        print(f"EPUB: {out_dir / epub_name}")
    if pdf_ok:
        print(f"PDF:  {out_dir / 'PTP_Reading_Path.pdf'}")
    if failures:
        print("\nThese articles failed (re-run the script to retry):")
        for url, err in failures:
            print(f"  - {url}\n    {err}")
    sys.exit(0 if epub_ok and not failures else 1)


if __name__ == "__main__":
    main()
