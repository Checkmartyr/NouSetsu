"""eBook Compilation Engine for EPUB3 and Printable PDF HTML.

Features:
- Pure Python EPUB3 generator with compliant container layout, OPF manifest, and dual TOC.
- PyThaiNLP zero-width space (ZWSP) line wrapping for pristine typography on e-readers.
- Standalone HTML print viewer with @media print CSS for 1-click browser PDF export.
- Automatic Novel Bible Character & Terminology appendix generation.
"""

import base64
import html
import io
import mimetypes
import os
import re
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any

try:
    import pymupdf
    _HAS_PYMUPDF = True
except ImportError:
    _HAS_PYMUPDF = False

from nousetsu.ebook.models import (
    EbookChapter,
    EbookMetadata,
    EbookExportOptions,
    EbookPreviewChapterItem,
    EbookPreviewResult,
)
from nousetsu.ebook.typography import wrap_thai_text, get_book_stylesheet
from nousetsu.storage.repository import NovelRepository


def _markdown_to_xhtml(md_text: str) -> str:
    """Convert clean markdown prose to valid XHTML tags for EPUB3 / HTML."""
    lines = md_text.split("\n")
    xhtml_parts: List[str] = []
    in_list = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if in_list:
                xhtml_parts.append("</ul>")
                in_list = False
            continue

        # Header 1-3
        if stripped.startswith("### "):
            if in_list:
                xhtml_parts.append("</ul>")
                in_list = False
            xhtml_parts.append(f"<h3>{html.escape(stripped[4:])}</h3>")
        elif stripped.startswith("## "):
            if in_list:
                xhtml_parts.append("</ul>")
                in_list = False
            xhtml_parts.append(f"<h2>{html.escape(stripped[3:])}</h2>")
        elif stripped.startswith("# "):
            if in_list:
                xhtml_parts.append("</ul>")
                in_list = False
            xhtml_parts.append(f"<h1>{html.escape(stripped[2:])}</h1>")
        # Blockquote
        elif stripped.startswith("> "):
            if in_list:
                xhtml_parts.append("</ul>")
                in_list = False
            xhtml_parts.append(f"<blockquote><p>{html.escape(stripped[2:])}</p></blockquote>")
        # Unordered list item
        elif stripped.startswith("- ") or stripped.startswith("* "):
            if not in_list:
                xhtml_parts.append("<ul>")
                in_list = True
            xhtml_parts.append(f"<li>{html.escape(stripped[2:])}</li>")
        # Image tag ![alt](src)
        elif stripped.startswith("!["):
            img_m = re.match(r"!\[(.*?)\]\((.*?)\)", stripped)
            if img_m:
                alt, src = img_m.groups()
                src_filename = Path(src).name
                xhtml_parts.append(
                    f'<figure><img src="images/{src_filename}" alt="{html.escape(alt)}" />'
                    f'<figcaption>{html.escape(alt)}</figcaption></figure>'
                )
            else:
                xhtml_parts.append(f"<p>{html.escape(stripped)}</p>")
        else:
            if in_list:
                xhtml_parts.append("</ul>")
                in_list = False
            # Format basic bold and italic
            p_text = html.escape(stripped)
            p_text = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", p_text)
            p_text = re.sub(r"\*(.*?)\*", r"<em>\1</em>", p_text)
            xhtml_parts.append(f"<p>{p_text}</p>")

    if in_list:
        xhtml_parts.append("</ul>")

    return "\n".join(xhtml_parts)


class Epub3Writer:
    """Compiles an EbookMetadata container into an EPUB3 binary archive."""

    def __init__(
        self,
        metadata: EbookMetadata,
        apply_thai_word_wrap: bool = True,
        font_family: Optional[str] = "Sarabun",
        font_size: Optional[int] = 16,
        line_height: Optional[float] = 1.8,
    ):
        self.meta = metadata
        self.apply_thai_wrap = apply_thai_word_wrap
        self.font_family = font_family
        self.font_size = font_size
        self.line_height = line_height
        self.book_id = f"urn:uuid:{uuid.uuid4()}"
        self.now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def build_epub_bytes(self, bible_appendix_html: Optional[str] = None) -> bytes:
        """Create the in-memory uncompressed mimetype and compressed EPUB3 package."""
        buf = io.BytesIO()

        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            # 1. Uncompressed 'mimetype' must be the very first file
            zf.writestr(
                "mimetype",
                "application/epub+zip",
                compress_type=zipfile.ZIP_STORED,
            )

            # 2. META-INF/container.xml
            zf.writestr(
                "META-INF/container.xml",
                """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>""",
            )

            # 3. OEBPS/stylesheet.css
            css_content = get_book_stylesheet(
                self.meta.language,
                font_family=self.font_family,
                font_size=self.font_size,
                line_height=self.line_height,
            )
            zf.writestr("OEBPS/stylesheet.css", css_content)

            # 4. Cover Image
            cover_filename = None
            if self.meta.cover_image_bytes:
                cover_filename = f"cover.{self.meta.cover_image_ext or 'jpg'}"
                zf.writestr(f"OEBPS/images/{cover_filename}", self.meta.cover_image_bytes)

                # Cover XHTML page
                cover_xhtml = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="{self.meta.language}">
<head>
  <title>Cover</title>
  <link rel="stylesheet" type="text/css" href="stylesheet.css"/>
  <style>
    body.cover-page {{ padding: 0; margin: 0; text-align: center; }}
    img.cover-img {{ max-width: 100%; max-height: 100vh; object-fit: contain; }}
  </style>
</head>
<body class="cover-page">
  <img class="cover-img" src="images/{cover_filename}" alt="Cover Image"/>
</body>
</html>"""
                zf.writestr("OEBPS/cover.xhtml", cover_xhtml)

            # 5. Title Page
            title_xhtml = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="{self.meta.language}">
<head>
  <title>{html.escape(self.meta.title)}</title>
  <link rel="stylesheet" type="text/css" href="stylesheet.css"/>
</head>
<body>
  <h1 class="book-title">{html.escape(self.meta.title)}</h1>
  {f'<h2 class="book-author">{html.escape(self.meta.author)}</h2>' if self.meta.author else ''}
  {f'<div class="status-box"><p>{html.escape(self.meta.description)}</p></div>' if self.meta.description else ''}
</body>
</html>"""
            zf.writestr("OEBPS/titlepage.xhtml", title_xhtml)

            # 6. Chapters & Images
            manifest_items: List[Tuple[str, str, str, str]] = [  # id, href, media-type, properties
                ("css", "stylesheet.css", "text/css", ""),
                ("titlepage", "titlepage.xhtml", "application/xhtml+xml", ""),
            ]
            spine_itemrefs: List[str] = ["titlepage"]

            if cover_filename:
                mtype = mimetypes.guess_type(cover_filename)[0] or "image/jpeg"
                manifest_items.append(("cover-image", f"images/{cover_filename}", mtype, "cover-image"))
                manifest_items.append(("cover-page", "cover.xhtml", "application/xhtml+xml", ""))
                spine_itemrefs.insert(0, "cover-page")

            # Store chapter illustrations
            stored_images: Dict[str, str] = {}
            for ch in self.meta.chapters:
                for img in ch.images:
                    iname = img["name"]
                    idata = img["data"]
                    if iname not in stored_images and isinstance(idata, bytes):
                        zf.writestr(f"OEBPS/images/{iname}", idata)
                        im_type = mimetypes.guess_type(iname)[0] or "image/jpeg"
                        im_id = f"img_{len(stored_images) + 1}"
                        manifest_items.append((im_id, f"images/{iname}", im_type, ""))
                        stored_images[iname] = im_id

            # Write Chapter XHTMLs
            for ch in self.meta.chapters:
                ch_id = f"chapter_{ch.index}"
                ch_filename = f"chapter_{str(ch.index).zfill(4)}.xhtml"

                content = ch.content_text
                if self.apply_thai_wrap and self.meta.language.lower().startswith("th"):
                    content = wrap_thai_text(content)

                body_html = _markdown_to_xhtml(content)

                ch_xhtml = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="{self.meta.language}">
<head>
  <title>{html.escape(ch.title)}</title>
  <link rel="stylesheet" type="text/css" href="stylesheet.css"/>
</head>
<body>
  <h2 class="chapter-title">{html.escape(ch.title)}</h2>
{body_html}
</body>
</html>"""
                zf.writestr(f"OEBPS/{ch_filename}", ch_xhtml)
                manifest_items.append((ch_id, ch_filename, "application/xhtml+xml", ""))
                spine_itemrefs.append(ch_id)

            # 7. Novel Bible Appendix
            if bible_appendix_html:
                appendix_xhtml = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="{self.meta.language}">
<head>
  <title>Appendix: Novel Bible &amp; Glossary</title>
  <link rel="stylesheet" type="text/css" href="stylesheet.css"/>
</head>
<body>
  <h2 class="chapter-title">Appendix: Novel Bible &amp; Characters</h2>
{bible_appendix_html}
</body>
</html>"""
                zf.writestr("OEBPS/appendix.xhtml", appendix_xhtml)
                manifest_items.append(("appendix", "appendix.xhtml", "application/xhtml+xml", ""))
                spine_itemrefs.append("appendix")

            # 8. Navigation Table of Contents (EPUB3 toc.xhtml + NCX fallback)
            toc_links = "\n".join(
                f'      <li><a href="chapter_{str(ch.index).zfill(4)}.xhtml">{html.escape(ch.title)}</a></li>'
                for ch in self.meta.chapters
            )
            if bible_appendix_html:
                toc_links += '\n      <li><a href="appendix.xhtml">Appendix: Novel Bible &amp; Characters</a></li>'

            toc_xhtml = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="{self.meta.language}">
<head>
  <title>Table of Contents</title>
  <link rel="stylesheet" type="text/css" href="stylesheet.css"/>
</head>
<body>
  <nav epub:type="toc" id="toc">
    <h2>Table of Contents</h2>
    <ol>
{toc_links}
    </ol>
  </nav>
</body>
</html>"""
            zf.writestr("OEBPS/toc.xhtml", toc_xhtml)
            manifest_items.append(("toc", "toc.xhtml", "application/xhtml+xml", "nav"))

            # Legacy NCX for older e-readers
            ncx_navpoints = []
            for idx, ch in enumerate(self.meta.chapters, start=1):
                ncx_navpoints.append(f"""    <navPoint id="navPoint-{idx}" playOrder="{idx}">
      <navLabel><text>{html.escape(ch.title)}</text></navLabel>
      <content src="chapter_{str(ch.index).zfill(4)}.xhtml"/>
    </navPoint>""")

            ncx_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
  <head>
    <meta name="dtb:uid" content="{self.book_id}"/>
    <meta name="dtb:depth" content="1"/>
  </head>
  <docTitle><text>{html.escape(self.meta.title)}</text></docTitle>
  <navMap>
{chr(10).join(ncx_navpoints)}
  </navMap>
</ncx>"""
            zf.writestr("OEBPS/toc.ncx", ncx_xml)
            manifest_items.append(("ncx", "toc.ncx", "application/x-dtbncx+xml", ""))

            # 9. OEBPS/content.opf Package Manifest
            manifest_xml_lines = [
                f'    <item id="{m_id}" href="{m_href}" media-type="{m_type}"'
                + (f' properties="{m_prop}"' if m_prop else '')
                + '/>'
                for m_id, m_href, m_type, m_prop in manifest_items
            ]
            spine_xml_lines = [f'    <itemref idref="{s_id}"/>' for s_id in spine_itemrefs]

            opf_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="BookID">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="BookID">{self.book_id}</dc:identifier>
    <dc:title>{html.escape(self.meta.title)}</dc:title>
    {f'<dc:creator>{html.escape(self.meta.author)}</dc:creator>' if self.meta.author else ''}
    <dc:language>{self.meta.language}</dc:language>
    <dc:publisher>{html.escape(self.meta.publisher or 'NouSetsu')}</dc:publisher>
    <meta property="dcterms:modified">{self.now_iso}</meta>
  </metadata>
  <manifest>
{chr(10).join(manifest_xml_lines)}
  </manifest>
  <spine toc="ncx">
{chr(10).join(spine_xml_lines)}
  </spine>
</package>"""
            zf.writestr("OEBPS/content.opf", opf_content)

        return buf.getvalue()

    build = build_epub_bytes


class HtmlPrintWriter:
    """Compiles chapters into a standalone, printable HTML document styled for browser PDF printing."""

    @staticmethod
    def build_printable_html(
        metadata: EbookMetadata,
        bible_appendix_html: Optional[str] = None,
        apply_thai_word_wrap: bool = True,
        font_family: Optional[str] = "Sarabun",
        font_size: Optional[int] = 16,
        line_height: Optional[float] = 1.8,
    ) -> str:
        """Create high-fidelity single-page HTML with @media print rules and chosen font."""
        css = get_book_stylesheet(
            metadata.language,
            font_family=font_family,
            font_size=font_size,
            line_height=line_height,
        )

        # Chapter TOC
        toc_items = []
        for ch in metadata.chapters:
            toc_items.append(f'<li><a href="#ch-{ch.index}">{html.escape(ch.title)}</a></li>')

        # Chapters HTML
        chapter_blocks = []
        for ch in metadata.chapters:
            content = ch.content_text
            if apply_thai_word_wrap and metadata.language.lower().startswith("th"):
                content = wrap_thai_text(content)

            body_html = _markdown_to_xhtml(content)
            chapter_blocks.append(f"""<section id="ch-{ch.index}" class="chapter-section">
  <h2 class="chapter-title">{html.escape(ch.title)}</h2>
{body_html}
</section>""")

        return f"""<!DOCTYPE html>
<html lang="{metadata.language}">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{html.escape(metadata.title)} - Print Edition</title>
  <style>
{css}

/* Interactive Print Header Bar */
.print-toolbar {{
    position: sticky;
    top: 0;
    background-color: #2b2622;
    color: #f7f5f0;
    padding: 0.8rem 1.5rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
    z-index: 1000;
    border-radius: 4px;
    margin-bottom: 2rem;
}}

.print-btn {{
    background-color: #d9a05b;
    color: #1a1a1a;
    border: none;
    padding: 0.5rem 1.2rem;
    font-weight: 600;
    border-radius: 3px;
    cursor: pointer;
    font-family: inherit;
    transition: background 0.15s;
}}

.print-btn:hover {{
    background-color: #e5b375;
}}
  </style>
</head>
<body>
  <!-- Print Controls -->
  <div class="print-toolbar no-print">
    <div>
      <strong>{html.escape(metadata.title)}</strong>
      {f'<span> · {html.escape(metadata.author)}</span>' if metadata.author else ''}
      <span style="opacity: 0.7; font-size: 0.85rem; margin-left: 0.8rem;">({len(metadata.chapters)} Chapters)</span>
    </div>
    <button class="print-btn" onclick="window.print()">🖨️ Print / Save to PDF</button>
  </div>

  <!-- Book Header -->
  <header style="text-align: center; margin-bottom: 4rem;">
    <h1 class="book-title">{html.escape(metadata.title)}</h1>
    {f'<h2 class="book-author">{html.escape(metadata.author)}</h2>' if metadata.author else ''}
    {f'<p style="max-width: 600px; margin: 0 auto; color: #666;">{html.escape(metadata.description)}</p>' if metadata.description else ''}
  </header>

  <!-- Table of Contents -->
  <nav class="toc-container" style="margin-bottom: 4rem; page-break-after: always; break-after: page;">
    <h3 style="border-bottom: 1px solid #ccc; padding-bottom: 0.4rem;">Table of Contents</h3>
    <ol style="line-height: 2;">
{chr(10).join(toc_items)}
    </ol>
  </nav>

  <!-- Chapters Content -->
{chr(10).join(chapter_blocks)}

  <!-- Novel Bible Appendix -->
  {f'<section class="appendix-section"><h2 class="chapter-title">Appendix: Novel Bible &amp; Characters</h2>{bible_appendix_html}</section>' if bible_appendix_html else ''}
</body>
</html>"""


def _generate_bible_appendix_html(repo: NovelRepository) -> str:
    """Format character dossiers and active glossary from Novel Bible into clean HTML."""
    try:
        bible = repo.load_bible()
    except Exception:
        return ""

    parts: List[str] = []

    # Characters section
    if bible.characters:
        parts.append("<h3>Dramatis Personae (Character Dossiers)</h3>")
        for char in bible.characters:
            c_name = getattr(char, "name", None) or getattr(char, "canonical_name", "Unknown")
            orig = getattr(char, "original_name", "")
            orig_str = f" ({orig})" if orig and orig != c_name else ""
            aliases = getattr(char, "aliases", [])
            alias_str = f" [Aliases: {', '.join(aliases)}]" if aliases else ""
            desc_val = getattr(char, "description", "") or getattr(char, "voice", "")
            desc = f"<p>{html.escape(desc_val)}</p>" if desc_val else ""
            role_val = getattr(char, "role", "Supporting")
            parts.append(f"""<div class="character-card">
  <div class="character-name">{html.escape(c_name)}{html.escape(orig_str)}{html.escape(alias_str)}</div>
  <div class="character-meta">Role: <strong>{html.escape(role_val)}</strong></div>
  {desc}
</div>""")

    # Glossary section
    if bible.glossary:
        parts.append("<h3>Active Terminology Glossary</h3>")
        parts.append("<table class=\"glossary-table\"><thead><tr><th>Source Term</th><th>Translation</th><th>Category</th></tr></thead><tbody>")
        for term in bible.glossary:
            src = getattr(term, "term", getattr(term, "source", ""))
            tgt = getattr(term, "translation", getattr(term, "target", ""))
            cat = getattr(term, "category", "Term")
            parts.append(f"<tr><td><strong>{html.escape(src)}</strong></td><td>{html.escape(tgt)}</td><td>{html.escape(cat)}</td></tr>")
        parts.append("</tbody></table>")

    return "\n".join(parts)


class PdfWriter:
    """Publication-grade native PDF writer using PyMuPDF Story and DocumentWriter."""

    def __init__(
        self,
        metadata: EbookMetadata,
        apply_thai_word_wrap: bool = True,
        font_family: Optional[str] = "Sarabun",
        font_size: Optional[int] = 16,
        line_height: Optional[float] = 1.8,
        paper_size: str = "a5",
        margin_pt: float = 36.0,
    ):
        self.metadata = metadata
        self.apply_thai_word_wrap = apply_thai_word_wrap
        self.font_family = font_family or "Sarabun"
        self.font_size = font_size or 16
        self.line_height = line_height or 1.8
        self.paper_size = paper_size
        self.margin_pt = margin_pt

    def build_pdf_bytes(self, bible_appendix_html: Optional[str] = None) -> bytes:
        """Render publication-grade PDF bytes with header, TOC, chapters, and page numbers."""
        if not _HAS_PYMUPDF:
            raise ImportError("PyMuPDF (pymupdf) is required for PDF compilation.")

        stylesheet = get_book_stylesheet(
            language=self.metadata.language,
            font_family=self.font_family,
            font_size=self.font_size,
            line_height=self.line_height,
        )

        parts: List[str] = []
        # Title page
        parts.append(f"<h1 class=\"book-title\">{html.escape(self.metadata.title)}</h1>")
        if self.metadata.author:
            parts.append(f"<h2 class=\"book-author\">{html.escape(self.metadata.author)}</h2>")
        if self.metadata.description:
            parts.append(f"<p style=\"text-align: center; color: #666;\">{html.escape(self.metadata.description)}</p>")
        parts.append("<div style=\"break-after: page; page-break-after: always;\"></div>")

        # Table of Contents in PDF
        parts.append("<nav class=\"toc-container\"><h2 class=\"chapter-title\">Table of Contents</h2><ol>")
        for ch in self.metadata.chapters:
            parts.append(f"<li>{html.escape(ch.title)}</li>")
        parts.append("</ol></nav>")
        parts.append("<div style=\"break-after: page; page-break-after: always;\"></div>")

        # Chapters
        for ch in self.metadata.chapters:
            parts.append(f"<h2 class=\"chapter-title\">{html.escape(ch.title)}</h2>")
            raw_text = ch.content_text
            if self.apply_thai_word_wrap and self.metadata.language.lower().startswith("th"):
                raw_text = wrap_thai_text(raw_text)
            xhtml_body = _markdown_to_xhtml(raw_text)
            parts.append(f"<div class=\"chapter-body\">{xhtml_body}</div>")
            parts.append("<div style=\"break-after: page; page-break-after: always;\"></div>")

        # Novel Bible Appendix
        if bible_appendix_html:
            parts.append(f"<div class=\"appendix-section\"><h2 class=\"chapter-title\">Appendix: Novel Bible &amp; Characters</h2>{bible_appendix_html}</div>")

        full_html = f"<!DOCTYPE html><html><head><meta charset=\"utf-8\"><style>{stylesheet}</style></head><body>{''.join(parts)}</body></html>"

        buf = io.BytesIO()
        writer = pymupdf.DocumentWriter(buf)
        story = pymupdf.Story(html=full_html, user_css=stylesheet)

        rect = pymupdf.paper_rect(self.paper_size)
        content_rect = pymupdf.Rect(
            self.margin_pt,
            self.margin_pt,
            rect.width - self.margin_pt,
            rect.height - (self.margin_pt + 15),
        )

        more = 1
        while more:
            dev = writer.begin_page(rect)
            more, _ = story.place(content_rect)
            story.draw(dev)
            writer.end_page()
        writer.close()

        # Inject bottom page numbers
        raw_pdf = buf.getvalue()
        doc = pymupdf.open(stream=raw_pdf, filetype="pdf")
        for idx in range(len(doc)):
            page = doc[idx]
            page_text = f"- {idx + 1} -"
            text_pt = pymupdf.Point(rect.width / 2 - 12, rect.height - 20)
            page.insert_text(text_pt, page_text, fontsize=8.5, color=(0.45, 0.45, 0.45))

        pdf_bytes = doc.tobytes()
        doc.close()
        return pdf_bytes


def _resolve_export_output_dir(repo: NovelRepository, folder: Optional[str] = None) -> Tuple[Path, str]:
    """Resolve the target directory containing translated markdown chapters.

    Returns:
        (resolved_output_path, folder_name)
    """
    cfg = repo.load_config()
    raw_folder = (folder or "").strip()

    # 1. Explicit folder provided
    if raw_folder and raw_folder not in ("all", "default"):
        clean = raw_folder.strip("/\\")
        direct_cand = repo.root_dir / clean
        output_cand = cfg.get_volume_output_path(repo.root_dir, clean)

        if direct_cand.is_dir() and any(f.suffix.lower() == ".md" for f in direct_cand.iterdir() if f.is_file()):
            return direct_cand, direct_cand.name
        if output_cand.is_dir() and any(f.suffix.lower() == ".md" for f in output_cand.iterdir() if f.is_file()):
            return output_cand, output_cand.name

        if direct_cand.is_dir():
            return direct_cand, direct_cand.name
        if output_cand.is_dir():
            return output_cand, output_cand.name

        return direct_cand, direct_cand.name

    # 2. No explicit folder provided or 'all' / 'default'
    default_out = cfg.get_output_path(repo.root_dir)
    if default_out.is_dir() and any(f.suffix.lower() == ".md" for f in default_out.iterdir() if f.is_file()):
        return default_out, default_out.name

    # Otherwise, discover non-empty translated folders in project
    candidates: List[Tuple[Path, int]] = []
    try:
        for _, out_name, _ in repo.discover_folders():
            p = repo.root_dir / out_name
            if p.is_dir():
                md_cnt = len([f for f in p.iterdir() if f.is_file() and f.suffix.lower() == ".md"])
                if md_cnt > 0:
                    candidates.append((p, md_cnt))
    except Exception:
        pass

    if repo.root_dir.exists():
        for child in repo.root_dir.iterdir():
            if child.is_dir() and cfg.is_volume_output_folder_name(child.name):
                if not any(c[0] == child for c in candidates):
                    md_cnt = len([f for f in child.iterdir() if f.is_file() and f.suffix.lower() == ".md"])
                    if md_cnt > 0:
                        candidates.append((child, md_cnt))

    if candidates:
        candidates.sort(key=lambda c: c[1], reverse=True)
        best_path = candidates[0][0]
        return best_path, best_path.name

    return default_out, default_out.name


def preview_project_ebook(
    repo: NovelRepository,
    options: EbookExportOptions,
    preview_chapter_index: int = 1,
) -> EbookPreviewResult:
    """Generate lightweight live preview with Table of Contents and sample chapter HTML."""
    cfg = repo.load_config()
    title = options.title or cfg.title or repo.root_dir.name
    author = options.author or getattr(cfg, "author", None) or "Author"
    language = options.language or cfg.target_language or "th"

    # 1. Resolve output directory for translated chapters
    out_dir, resolved_folder_name = _resolve_export_output_dir(repo, options.folder)

    if not out_dir.exists():
        raise FileNotFoundError(f"Translated chapters directory does not exist: {out_dir}")

    md_files = [f for f in out_dir.iterdir() if f.is_file() and f.suffix.lower() == ".md"]
    md_files.sort(key=lambda p: p.name)

    if not md_files:
        raise ValueError(f"No translated markdown chapters found in {out_dir}")

    # Inspect cover image
    cover_base64: Optional[str] = None
    has_cover = False
    base_raw_name = re.sub(r'_(th|trans)$', '', resolved_folder_name)
    assets_dir = out_dir.parent / base_raw_name / "assets" if (out_dir.parent / base_raw_name / "assets").exists() else out_dir.parent / "raw_chapters" / "assets"
    for cand_name in ["cover.jpg", "cover.png", "cover.jpeg"]:
        p_cand = out_dir.parent / cand_name
        if p_cand.exists():
            mime = "image/png" if p_cand.suffix.lower() == ".png" else "image/jpeg"
            cover_base64 = f"data:{mime};base64,{base64.b64encode(p_cand.read_bytes()).decode('ascii')}"
            has_cover = True
            break
        if assets_dir.exists() and (assets_dir / cand_name).exists():
            p_cand = assets_dir / cand_name
            mime = "image/png" if p_cand.suffix.lower() == ".png" else "image/jpeg"
            cover_base64 = f"data:{mime};base64,{base64.b64encode(p_cand.read_bytes()).decode('ascii')}"
            has_cover = True
            break

    toc: List[EbookPreviewChapterItem] = []
    chapter_mds: Dict[int, Tuple[str, str]] = {}
    selected_indices = set(options.chapter_indices) if options.chapter_indices else None

    for idx, f in enumerate(md_files, start=1):
        m = re.match(r"^(\d+)", f.stem)
        ch_num = int(m.group(1)) if m else idx

        if selected_indices and ch_num not in selected_indices:
            continue
        if options.start_chapter and ch_num < options.start_chapter:
            continue
        if options.end_chapter and ch_num > options.end_chapter:
            continue

        raw_md = f.read_text(encoding="utf-8", errors="replace")
        first_line = raw_md.strip().split("\n")[0] if raw_md.strip() else ""
        ch_title = first_line.lstrip("# \t") if first_line.startswith("#") else f.stem

        words = len(raw_md.split())
        has_imgs = bool(re.search(r"!\[(.*?)\]\((.*?)\)", raw_md))
        ch_item_idx = len(toc) + 1

        toc.append(EbookPreviewChapterItem(
            index=ch_item_idx,
            title=ch_title,
            word_count=words,
            has_images=has_imgs,
            source_file=f.name,
        ))
        chapter_mds[ch_item_idx] = (ch_title, raw_md)

    if not toc:
        raise ValueError("No chapters matched the requested chapter range.")

    target_idx = max(1, min(preview_chapter_index, len(toc)))
    sample_title, sample_raw_md = chapter_mds[target_idx]

    proc_md = sample_raw_md
    if options.apply_thai_word_wrap and language.lower().startswith("th"):
        proc_md = wrap_thai_text(proc_md)

    sample_xhtml = _markdown_to_xhtml(proc_md)

    return EbookPreviewResult(
        title=title,
        author=author,
        language=language,
        total_chapters=len(toc),
        total_words=sum(c.word_count for c in toc),
        has_cover=has_cover,
        cover_base64=cover_base64,
        toc=toc,
        sample_chapter_index=target_idx,
        sample_chapter_title=sample_title,
        sample_chapter_html=sample_xhtml,
        sample_chapter_text=sample_raw_md,
    )


def compile_project_to_ebook(
    repo: NovelRepository,
    options: EbookExportOptions,
) -> Tuple[bytes, str, str]:
    """Compile translated chapters into EPUB3 binary data, native PDF, or printable HTML.

    Returns:
        (content_bytes, output_filename, mime_type)
    """
    cfg = repo.load_config()
    title = options.title or cfg.title or repo.root_dir.name
    author = options.author or getattr(cfg, "author", None) or "Author"
    language = options.language or cfg.target_language or "th"

    # 1. Resolve output directory for translated chapters
    out_dir, resolved_folder_name = _resolve_export_output_dir(repo, options.folder)

    if not out_dir.exists():
        raise FileNotFoundError(f"Translated chapters directory does not exist: {out_dir}")

    # 2. Collect translated markdown files
    md_files = [f for f in out_dir.iterdir() if f.is_file() and f.suffix.lower() == ".md"]
    md_files.sort(key=lambda p: p.name)

    if not md_files:
        raise ValueError(f"No translated markdown chapters found in {out_dir}")

    chapters: List[EbookChapter] = []
    selected_indices = set(options.chapter_indices) if options.chapter_indices else None

    # Load chapter illustrations if an assets directory exists
    base_raw_name = re.sub(r'_(th|trans)$', '', resolved_folder_name)
    assets_dir = out_dir.parent / base_raw_name / "assets" if (out_dir.parent / base_raw_name / "assets").exists() else out_dir.parent / "raw_chapters" / "assets"
    available_images: Dict[str, bytes] = {}
    if assets_dir.exists():
        for img_file in assets_dir.iterdir():
            if img_file.is_file() and img_file.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"):
                try:
                    available_images[img_file.name] = img_file.read_bytes()
                except Exception:
                    pass

    # Extract cover image if present in assets or project
    cover_bytes: Optional[bytes] = None
    cover_ext: str = "jpg"
    for cand_name in ["cover.jpg", "cover.png", "cover.jpeg"]:
        if (out_dir.parent / cand_name).exists():
            cover_bytes = (out_dir.parent / cand_name).read_bytes()
            cover_ext = Path(cand_name).suffix.lstrip(".")
            break
        if assets_dir.exists() and (assets_dir / cand_name).exists():
            cover_bytes = (assets_dir / cand_name).read_bytes()
            cover_ext = Path(cand_name).suffix.lstrip(".")
            break

    for idx, f in enumerate(md_files, start=1):
        # Extract numeric chapter from filename or sequence index
        m = re.match(r"^(\d+)", f.stem)
        ch_num = int(m.group(1)) if m else idx

        if selected_indices and ch_num not in selected_indices:
            continue
        if options.start_chapter and ch_num < options.start_chapter:
            continue
        if options.end_chapter and ch_num > options.end_chapter:
            continue

        raw_md = f.read_text(encoding="utf-8", errors="replace")

        # Determine clean chapter title
        first_line = raw_md.strip().split("\n")[0] if raw_md.strip() else ""
        if first_line.startswith("#"):
            ch_title = first_line.lstrip("# \t")
        else:
            ch_title = f.stem

        # Extract linked images
        ch_images: List[Dict[str, Any]] = []
        for match in re.finditer(r"!\[(.*?)\]\((.*?)\)", raw_md):
            im_src = match.group(2)
            im_filename = Path(im_src).name
            if im_filename in available_images:
                ch_images.append({
                    "name": im_filename,
                    "ext": Path(im_filename).suffix.lstrip("."),
                    "data": available_images[im_filename],
                })

        chapters.append(EbookChapter(
            index=len(chapters) + 1,
            title=ch_title,
            content_text=raw_md,
            images=ch_images,
            source_file=f.name,
        ))

    if not chapters:
        raise ValueError("No chapters matched the requested chapter range.")

    metadata = EbookMetadata(
        title=title,
        author=author,
        language=language,
        description=f"Translated by NouSetsu on {datetime.now().strftime('%B %Y')}",
        cover_image_bytes=cover_bytes,
        cover_image_ext=cover_ext,
        chapters=chapters,
    )

    # 3. Format Novel Bible Appendix if requested
    bible_appendix_html = None
    if options.include_bible_appendix:
        bible_appendix_html = _generate_bible_appendix_html(repo)

    safe_title = re.sub(r'[<>:\"/\\|?*]', '_', title).strip()

    # 4. Generate Output
    if options.format == "pdf":
        pdf_writer = PdfWriter(
            metadata,
            apply_thai_word_wrap=options.apply_thai_word_wrap,
            font_family=options.font_family,
            font_size=options.font_size,
            line_height=options.line_height,
        )
        pdf_bytes = pdf_writer.build_pdf_bytes(bible_appendix_html=bible_appendix_html)
        return pdf_bytes, f"{safe_title}.pdf", "application/pdf"
    elif options.format in ("html_print", "html"):
        html_str = HtmlPrintWriter.build_printable_html(
            metadata,
            bible_appendix_html=bible_appendix_html,
            apply_thai_word_wrap=options.apply_thai_word_wrap,
            font_family=options.font_family,
            font_size=options.font_size,
            line_height=options.line_height,
        )
        return html_str.encode("utf-8"), f"{safe_title}.html", "text/html"
    else:
        writer = Epub3Writer(
            metadata,
            apply_thai_word_wrap=options.apply_thai_word_wrap,
            font_family=options.font_family,
            font_size=options.font_size,
            line_height=options.line_height,
        )
        epub_data = writer.build_epub_bytes(bible_appendix_html=bible_appendix_html)
        return epub_data, f"{safe_title}.epub", "application/epub+zip"
