"""eBook Ingestion Engine for PDF and EPUB files.

Features:
- PyMuPDF integration for complex script (Thai/CJK) extraction with zero floating tone marks.
- EPUB3/EPUB2 spine parsing with HTML-to-markdown conversion.
- Illustration extraction into dedicated assets directories.
- Chapter segmentation via TOC bookmarks and script-aware heading heuristics.
"""

import base64
import html
import io
import mimetypes
import os
import re
import unicodedata
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any, Union

import pymupdf

from nousetsu.ebook.models import (
    EbookChapter,
    EbookMetadata,
    EbookInspectChapterItem,
    EbookInspectResult,
    EbookImportParams,
)

# Common regex patterns to detect chapter titles across languages
CHAPTER_HEADING_REGEX = re.compile(
    r"^\s*(?:#+\s*)?(?:"
    r"Chapter\s+\d+|"
    r"第\s*[\d0-9一二三四五六七八九十百千]+\s*[話章回節]|"
    r"ตอนที่\s*\d+|"
    r"บทที่\s*\d+|"
    r"Prologue|Epilogue|Side\s*Story|Interlude|"
    r"序章|終章|転章|幕間"
    r")",
    re.IGNORECASE | re.MULTILINE,
)

HTML_TAG_CLEANER = re.compile(r"<[^>]+>")


def _clean_html_to_markdown(html_content: str) -> Tuple[str, Optional[str], List[str]]:
    """Convert chapter HTML to clean markdown prose, extracting title and referenced images."""
    detected_title: Optional[str] = None
    images: List[str] = []

    # Unescape HTML entities
    text = html.unescape(html_content)

    # Extract first <h1> or <title> as candidate chapter title
    h1_match = re.search(r"<h[1-2][^>]*>(.*?)</h[1-2]>", text, re.IGNORECASE | re.DOTALL)
    if h1_match:
        detected_title = HTML_TAG_CLEANER.sub("", h1_match.group(1)).strip()

    # Replace <img src="..." /> with markdown image syntax ![img](assets/...)
    def _img_sub(match: re.Match) -> str:
        src_match = re.search(r'src=["\']([^"\']+)["\']', match.group(0), re.IGNORECASE)
        alt_match = re.search(r'alt=["\']([^"\']+)["\']', match.group(0), re.IGNORECASE)
        alt = alt_match.group(1) if alt_match else "illustration"
        if src_match:
            src = src_match.group(1)
            img_filename = Path(src).name
            images.append(src)
            return f"\n\n![{alt}](assets/{img_filename})\n\n"
        return ""

    text = re.sub(r"<img[^>]+>", _img_sub, text, flags=re.IGNORECASE)

    # Convert block elements to clean markdown line breaks
    text = re.sub(r"<(?:p|div|section|article)[^>]*>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</(?:p|div|section|article)>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<h1[^>]*>(.*?)</h1>", r"\n\n# \1\n\n", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<h2[^>]*>(.*?)</h2>", r"\n\n## \1\n\n", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<h3[^>]*>(.*?)</h3>", r"\n\n### \1\n\n", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<blockquote[^>]*>(.*?)</blockquote>", r"\n\n> \1\n\n", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<strong[^>]*>(.*?)</strong>", r"**\1**", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<b[^>]*>(.*?)</b>", r"**\1**", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<em[^>]*>(.*?)</em>", r"*\1*", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<i[^>]*>(.*?)</i>", r"*\1*", text, flags=re.IGNORECASE | re.DOTALL)

    # Strip remaining HTML tags
    clean_text = HTML_TAG_CLEANER.sub("", text)

    # Normalize paragraph spacing (collapse 3+ newlines to 2)
    clean_text = re.sub(r"\n{3,}", "\n\n", clean_text).strip()

    return clean_text, detected_title, images


class EpubReader:
    """Extracts metadata, chapters, and illustrations from an EPUB container."""

    def __init__(self, file_path_or_bytes: Any):
        if isinstance(file_path_or_bytes, (str, Path)):
            self.file_path = Path(file_path_or_bytes)
            self.zip_file = zipfile.ZipFile(self.file_path, "r")
        else:
            self.file_path = None
            self.zip_file = zipfile.ZipFile(io.BytesIO(file_path_or_bytes), "r")

    def read_metadata(self) -> EbookMetadata:
        """Parse EPUB package OPF and extract chapters and images."""
        namelist = self.zip_file.namelist()

        # 1. Locate OPF file path from META-INF/container.xml
        opf_path = "OEBPS/content.opf"
        if "META-INF/container.xml" in namelist:
            try:
                container_data = self.zip_file.read("META-INF/container.xml")
                root = ET.fromstring(container_data)
                for rootfile in root.iter("{urn:oasis:names:tc:opendocument:xmlns:container}rootfile"):
                    full_path = rootfile.attrib.get("full-path")
                    if full_path:
                        opf_path = full_path
                        break
            except Exception:
                pass

        if opf_path not in namelist:
            # Fallback: scan for any .opf file in the archive
            opf_cand = next((n for n in namelist if n.lower().endswith(".opf")), None)
            if opf_cand:
                opf_path = opf_cand

        opf_dir = Path(opf_path).parent

        # 2. Parse OPF package XML
        title: Optional[str] = None
        author = None
        language = "th"
        description = None
        manifest: Dict[str, Tuple[str, str]] = {}  # id -> (href, media-type)
        spine_ids: List[str] = []
        cover_id = None

        if opf_path in namelist:
            try:
                opf_xml = self.zip_file.read(opf_path)
                root = ET.fromstring(opf_xml)

                # Metadata
                for elem in root.iter():
                    tag = elem.tag.split("}")[-1].lower()
                    if tag == "title" and elem.text and not title:
                        title = elem.text.strip()
                    elif tag in ("creator", "author") and elem.text and not author:
                        author = elem.text.strip()
                    elif tag == "language" and elem.text:
                        language = elem.text.strip()
                    elif tag == "description" and elem.text:
                        description = elem.text.strip()
                    elif tag == "meta" and elem.attrib.get("name") == "cover":
                        cover_id = elem.attrib.get("content")
                # Manifest
                for item in root.iter():
                    if item.tag.split("}")[-1].lower() == "item":
                        i_id = item.attrib.get("id")
                        href = item.attrib.get("href")
                        mtype = item.attrib.get("media-type", "")
                        if i_id and href:
                            manifest[i_id] = (href, mtype)
                            if "cover-image" in item.attrib.get("properties", ""):
                                cover_id = i_id

                # Spine
                for itemref in root.iter():
                    if itemref.tag.split("}")[-1].lower() == "itemref":
                        idref = itemref.attrib.get("idref")
                        if idref and idref in manifest:
                            spine_ids.append(idref)
            except Exception:
                pass

        if not title:
            title = self.file_path.stem if self.file_path else "Novel"

        # 3. Read Cover Image
        cover_bytes: Optional[bytes] = None
        cover_ext: str = "jpg"
        if cover_id and cover_id in manifest:
            c_href, c_type = manifest[cover_id]
            c_path = (opf_dir / c_href).as_posix()
            if c_path in namelist:
                try:
                    cover_bytes = self.zip_file.read(c_path)
                    cover_ext = mimetypes.guess_extension(c_type) or ".jpg"
                    cover_ext = cover_ext.lstrip(".")
                except Exception:
                    pass

        # 4. Read Spine Chapters
        chapters: List[EbookChapter] = []
        extracted_images: Dict[str, bytes] = {}

        # Cache all images in archive for instant lookup
        for name in namelist:
            lower = name.lower()
            if lower.endswith((".jpg", ".jpeg", ".png", ".webp", ".gif")):
                try:
                    extracted_images[Path(name).name] = self.zip_file.read(name)
                except Exception:
                    pass

        ch_idx = 1
        for sid in spine_ids:
            href, _ = manifest[sid]
            lower_href = href.lower()
            if any(k in lower_href for k in ("cover", "titlepage", "title_page", "nav.xhtml", "toc.xhtml")):
                continue

            doc_path = (opf_dir / href).as_posix()
            if doc_path not in namelist:
                continue

            try:
                raw_bytes = self.zip_file.read(doc_path)
                try:
                    html_str = raw_bytes.decode("utf-8")
                except UnicodeDecodeError:
                    html_str = raw_bytes.decode("cp1252", errors="replace")

                clean_text, detected_title, img_refs = _clean_html_to_markdown(html_str)

                # Skip completely blank structural pages with no prose or title
                word_count = len(clean_text.split())
                if word_count < 5 and not img_refs and not detected_title:
                    continue

                ch_title = detected_title or f"Chapter {ch_idx}"
                # Collect matching image assets
                ch_images: List[Dict[str, Any]] = []
                for iref in img_refs:
                    iname = Path(iref).name
                    if iname in extracted_images:
                        ch_images.append({
                            "name": iname,
                            "ext": Path(iname).suffix.lstrip("."),
                            "data": extracted_images[iname],
                        })

                chapters.append(EbookChapter(
                    index=ch_idx,
                    title=ch_title,
                    content_text=clean_text,
                    images=ch_images,
                    source_file=Path(doc_path).name,
                ))
                ch_idx += 1
            except Exception:
                continue

        # If no spine items were found, fallback to scanning XHTML files directly
        if not chapters:
            html_files = [n for n in namelist if n.lower().endswith((".xhtml", ".html", ".htm"))]
            html_files.sort()
            for idx, hfile in enumerate(html_files, start=1):
                try:
                    raw_bytes = self.zip_file.read(hfile)
                    clean_text, detected_title, img_refs = _clean_html_to_markdown(raw_bytes.decode("utf-8", errors="replace"))
                    if len(clean_text.split()) >= 15:
                        chapters.append(EbookChapter(
                            index=idx,
                            title=detected_title or f"Chapter {idx}",
                            content_text=clean_text,
                            images=[],
                            source_file=Path(hfile).name,
                        ))
                except Exception:
                    pass

        return EbookMetadata(
            title=title,
            author=author,
            language=language,
            description=description,
            cover_image_bytes=cover_bytes,
            cover_image_ext=cover_ext,
            chapters=chapters,
        )


class PdfReader:
    """Extracts metadata, chapters, and illustrations from a PDF document using PyMuPDF."""

    def __init__(self, file_path_or_bytes: Any):
        if isinstance(file_path_or_bytes, (str, Path)):
            self.file_path = Path(file_path_or_bytes)
            self.doc = pymupdf.open(str(self.file_path))
        else:
            self.file_path = None
            self.doc = pymupdf.open(stream=file_path_or_bytes, filetype="pdf")

    def read_metadata(self) -> EbookMetadata:
        """Extract title, author, cover, chapters, and images using PyMuPDF."""
        meta = self.doc.metadata or {}
        title = meta.get("title") or (self.file_path.stem if self.file_path else "Novel")
        author = meta.get("author") or None

        # 1. Extract cover image from first page if present
        cover_bytes: Optional[bytes] = None
        cover_ext: str = "jpg"
        if len(self.doc) > 0:
            first_page = self.doc[0]
            images = first_page.get_images()
            if images:
                xref = images[0][0]
                try:
                    base_img = self.doc.extract_image(xref)
                    cover_bytes = base_img["image"]
                    cover_ext = base_img.get("ext", "jpg")
                except Exception:
                    pass

        # 2. Extract chapters via PDF outline bookmarks (TOC)
        toc = self.doc.get_toc()  # [[lvl, title, pno], ...]
        chapters: List[EbookChapter] = []

        if toc:
            for idx, item in enumerate(toc, start=1):
                lvl, c_title, pno = item[0], item[1].strip(), item[2] - 1  # 0-indexed
                # Determine end page for this chapter
                next_pno = toc[idx][2] - 1 if idx < len(toc) else len(self.doc)
                next_pno = max(pno + 1, min(next_pno, len(self.doc)))

                page_texts: List[str] = []
                ch_images: List[Dict[str, Any]] = []

                for p_idx in range(pno, next_pno):
                    page = self.doc[p_idx]
                    raw_t = page.get_text("text")
                    norm_t = unicodedata.normalize("NFC", raw_t)
                    if norm_t.strip():
                        page_texts.append(norm_t.strip())

                    # Extract page images
                    for img_info in page.get_images():
                        xref = img_info[0]
                        try:
                            b_img = self.doc.extract_image(xref)
                            img_name = f"ill_ch{str(idx).zfill(4)}_p{p_idx}_{xref}.{b_img.get('ext', 'jpg')}"
                            ch_images.append({
                                "name": img_name,
                                "ext": b_img.get("ext", "jpg"),
                                "data": b_img["image"],
                            })
                        except Exception:
                            pass

                full_chapter_text = "\n\n".join(page_texts)
                # Link images at top or appropriate positions
                if ch_images:
                    img_markdown = "\n\n".join(f"![Illustration](assets/{im['name']})" for im in ch_images)
                    full_chapter_text = f"{img_markdown}\n\n{full_chapter_text}"

                chapters.append(EbookChapter(
                    index=idx,
                    title=c_title or f"Chapter {idx}",
                    content_text=full_chapter_text,
                    images=ch_images,
                    source_file=f"page_{pno + 1}-{next_pno}.pdf",
                ))

        # 3. If no TOC bookmarks exist, use regex heuristics across page streams
        if not chapters:
            current_ch_idx = 1
            current_title = "Chapter 1"
            current_pages: List[str] = []
            current_images: List[Dict[str, Any]] = []

            for p_idx, page in enumerate(self.doc):
                raw_t = page.get_text("text")
                norm_t = unicodedata.normalize("NFC", raw_t)

                # Check if page begins with a chapter heading
                heading_match = CHAPTER_HEADING_REGEX.search(norm_t[:200])
                if heading_match and current_pages:
                    # Flush previous chapter
                    ch_text = "\n\n".join(current_pages)
                    if current_images:
                        img_md = "\n\n".join(f"![Illustration](assets/{im['name']})" for im in current_images)
                        ch_text = f"{img_md}\n\n{ch_text}"
                    chapters.append(EbookChapter(
                        index=current_ch_idx,
                        title=current_title,
                        content_text=ch_text,
                        images=current_images,
                        source_file=f"section_{current_ch_idx}.pdf",
                    ))
                    current_ch_idx += 1
                    current_title = heading_match.group(0).strip("# \t\r\n")
                    current_pages = []
                    current_images = []

                if norm_t.strip():
                    current_pages.append(norm_t.strip())

                for img_info in page.get_images():
                    xref = img_info[0]
                    try:
                        b_img = self.doc.extract_image(xref)
                        img_name = f"ill_p{p_idx}_{xref}.{b_img.get('ext', 'jpg')}"
                        current_images.append({
                            "name": img_name,
                            "ext": b_img.get("ext", "jpg"),
                            "data": b_img["image"],
                        })
                    except Exception:
                        pass

            # Flush remaining pages
            if current_pages:
                ch_text = "\n\n".join(current_pages)
                if current_images:
                    img_md = "\n\n".join(f"![Illustration](assets/{im['name']})" for im in current_images)
                    ch_text = f"{img_md}\n\n{ch_text}"
                chapters.append(EbookChapter(
                    index=current_ch_idx,
                    title=current_title,
                    content_text=ch_text,
                    images=current_images,
                    source_file=f"section_{current_ch_idx}.pdf",
                ))

        return EbookMetadata(
            title=title,
            author=author,
            language="th",
            cover_image_bytes=cover_bytes,
            cover_image_ext=cover_ext,
            chapters=chapters,
        )


class EbookReader:
    """Unified reader interface for EPUB and PDF files."""

    def __init__(self, reader: Union[EpubReader, PdfReader], fmt: str):
        self._reader = reader
        self._format = fmt
        self._meta: Optional[EbookMetadata] = None

    @classmethod
    def from_file(cls, file_path: Union[Path, str]) -> "EbookReader":
        p = Path(file_path)
        ext = p.suffix.lower()
        if ext == ".epub":
            return cls(EpubReader(p), "epub")
        elif ext == ".pdf":
            return cls(PdfReader(p), "pdf")
        raise ValueError(f"Unsupported eBook format '{ext}'. Must be .epub or .pdf.")

    @classmethod
    def from_bytes(cls, data: bytes, filename: str = "novel.epub") -> "EbookReader":
        ext = Path(filename).suffix.lower()
        if ext == ".epub":
            return cls(EpubReader(data), "epub")
        elif ext == ".pdf":
            return cls(PdfReader(data), "pdf")
        raise ValueError(f"Unsupported eBook format '{ext}'. Must be .epub or .pdf.")

    def read_metadata(self) -> EbookMetadata:
        if self._meta is None:
            self._meta = self._reader.read_metadata()
        return self._meta

    def inspect(self) -> EbookInspectResult:
        meta = self.read_metadata()
        cover_base64: Optional[str] = None
        if meta.cover_image_bytes:
            mime = f"image/{meta.cover_image_ext}"
            enc = base64.b64encode(meta.cover_image_bytes).decode("ascii")
            cover_base64 = f"data:{mime};base64,{enc}"

        chapter_items = [
            EbookInspectChapterItem(
                index=ch.index,
                title=ch.title,
                word_count=len(ch.content_text.split()),
                has_images=len(ch.images) > 0,
            )
            for ch in meta.chapters
        ]

        return EbookInspectResult(
            title=meta.title,
            author=meta.author,
            format=self._format,
            total_chapters=len(chapter_items),
            chapters=chapter_items,
            has_cover=meta.cover_image_bytes is not None,
            cover_base64=cover_base64,
        )

    def extract_chapters(
        self,
        start_chapter: Optional[int] = None,
        end_chapter: Optional[int] = None,
        selected_indices: Optional[List[int]] = None,
    ) -> List[EbookChapter]:
        meta = self.read_metadata()
        indices_set = set(selected_indices) if selected_indices else None
        res: List[EbookChapter] = []
        for ch in meta.chapters:
            if indices_set and ch.index not in indices_set:
                continue
            if start_chapter and ch.index < start_chapter:
                continue
            if end_chapter and ch.index > end_chapter:
                continue
            res.append(ch)
        return res

    def extract_images(self) -> List[Any]:
        meta = self.read_metadata()
        res = []

        class _ExtractedImg:
            def __init__(self, filename: str, data: bytes):
                self.filename = filename
                self.image_bytes = data

        if meta.cover_image_bytes:
            res.append(_ExtractedImg(f"cover.{meta.cover_image_ext}", meta.cover_image_bytes))

        for ch in meta.chapters:
            for img in ch.images:
                name = img.get("name")
                data = img.get("data")
                if name and isinstance(data, bytes):
                    res.append(_ExtractedImg(name, data))
        return res


def inspect_ebook(
    file_input: Union[Path, str, bytes],
    filename: Optional[str] = None,
) -> EbookInspectResult:
    """Inspect an EPUB or PDF file and return preview metadata without modifying disk."""
    if isinstance(file_input, bytes):
        reader = EbookReader.from_bytes(file_input, filename=filename or "novel.epub")
    else:
        reader = EbookReader.from_file(file_input)
    return reader.inspect()


def extract_ebook_to_directory(
    file_input: Union[Path, str, bytes],
    dest_dir: Path,
    params: Optional[EbookImportParams] = None,
    filename: Optional[str] = None,
) -> Dict[str, Any]:
    """Extract chapters from an EPUB or PDF file and write text files and assets to disk."""
    params = params or EbookImportParams()
    if isinstance(file_input, bytes):
        reader = EbookReader.from_bytes(file_input, filename=filename or "novel.epub")
    else:
        reader = EbookReader.from_file(file_input)

    metadata = reader.read_metadata()
    dest_dir.mkdir(parents=True, exist_ok=True)
    assets_dir = dest_dir / "assets"
    if params.extract_images:
        assets_dir.mkdir(parents=True, exist_ok=True)

    # Save cover art if present
    if metadata.cover_image_bytes and params.extract_images:
        cover_path = assets_dir / f"cover.{metadata.cover_image_ext}"
        cover_path.write_bytes(metadata.cover_image_bytes)

    extracted_files: List[str] = []
    skipped_files: List[str] = []

    # Determine which chapters to import
    selected_indices = set(params.chapter_indices) if params.chapter_indices else None

    for ch in metadata.chapters:
        if selected_indices and ch.index not in selected_indices:
            continue
        if params.start_chapter and ch.index < params.start_chapter:
            continue
        if params.end_chapter and ch.index > params.end_chapter:
            continue

        safe_title = re.sub(r'[<>:\"/\\|?*]', '_', ch.title)[:60]
        filename_out = f"{str(ch.index).zfill(4)} - {safe_title}.txt"
        target_file = dest_dir / filename_out

        if target_file.exists() and not params.overwrite:
            skipped_files.append(filename_out)
            continue

        # Save chapter illustrations
        if params.extract_images and ch.images:
            for img in ch.images:
                img_name = img.get("name")
                img_data = img.get("data")
                if img_name and isinstance(img_data, bytes):
                    (assets_dir / img_name).write_bytes(img_data)

        target_file.write_text(ch.content_text, encoding="utf-8")
        extracted_files.append(filename_out)

    return {
        "success": True,
        "title": metadata.title,
        "author": metadata.author,
        "total_extracted": len(extracted_files),
        "total_skipped": len(skipped_files),
        "extracted_files": extracted_files,
        "skipped_files": skipped_files,
    }
