"""Unit tests for eBook Ingestion, Typography, and Compilation Engine."""

import io
import zipfile
from pathlib import Path
import pymupdf
import pytest

from nousetsu.ebook.models import (
    EbookChapter,
    EbookMetadata,
    EbookExportOptions,
    EbookImportParams,
)
from nousetsu.ebook.typography import (
    has_thai_text,
    wrap_thai_paragraph,
    wrap_thai_text,
    get_book_stylesheet,
)
from nousetsu.ebook.reader import (
    EpubReader,
    PdfReader,
    inspect_ebook,
    extract_ebook_to_directory,
)
from nousetsu.ebook.writer import (
    Epub3Writer,
    HtmlPrintWriter,
    compile_project_to_ebook,
)
from nousetsu.storage.repository import NovelRepository
from nousetsu.models.bible import NovelBible, CharacterProfile, GlossaryItem
from starlette.testclient import TestClient
from nousetsu.cli.web_server import create_app


def test_thai_typography_detection():
    """Verify Thai Unicode character detection."""
    assert has_thai_text("สวัสดีชาวโลก") is True
    assert has_thai_text("Hello World!") is False
    assert has_thai_text("こんにちは世界") is False
    assert has_thai_text("Chap 1: การตื่นรู้ของราชา") is True


def test_thai_word_wrap_and_markdown_protection():
    """Verify pythainlp ZWSP insertion protects markdown elements."""
    raw_thai = "ฉันกำลังอ่านนิยายแปล"
    wrapped = wrap_thai_paragraph(raw_thai)
    assert "\u200b" in wrapped

    # Markdown link and header protection
    md_text = "# บทที่ 1: การผจญภัย\n\nนี่คือเนื้อหา [อ่านต่อ](https://example.com) สำหรับวันนี้"
    wrapped_md = wrap_thai_text(md_text)
    assert wrapped_md.startswith("# ")
    assert "[อ่านต่อ](https://example.com)" in wrapped_md


def test_book_stylesheet_generation():
    """Verify stylesheet generates font imports and publication layout CSS."""
    css_th = get_book_stylesheet("th")
    assert "Sarabun" in css_th
    assert "text-justify" in css_th
    assert "@media print" in css_th

    css_ja = get_book_stylesheet("ja")
    assert "Noto Serif JP" in css_ja


def test_epub3_generation_and_reading(tmp_path: Path):
    """Verify full roundtrip: generate compliant EPUB3 and read back chapters."""
    meta = EbookMetadata(
        title="Test Light Novel",
        author="Author San",
        language="en",
        description="A great fantasy journey.",
        chapters=[
            EbookChapter(
                index=1,
                title="Chapter 1: The Beginning",
                content_text="Once upon a time in a fantasy world...\n\n**The End of Start.**",
            ),
            EbookChapter(
                index=2,
                title="Chapter 2: Magic Forest",
                content_text="They entered the deep enchanted woods.\n\n> A strange beast roared.",
            ),
        ],
    )

    writer = Epub3Writer(meta, apply_thai_word_wrap=False)
    epub_bytes = writer.build_epub_bytes()
    assert len(epub_bytes) > 500

    # 1. Verify mimetype is first file and uncompressed
    with zipfile.ZipFile(io.BytesIO(epub_bytes), "r") as zf:
        first_info = zf.infolist()[0]
        assert first_info.filename == "mimetype"
        assert first_info.compress_type == zipfile.ZIP_STORED
        assert zf.read("mimetype") == b"application/epub+zip"
        assert "META-INF/container.xml" in zf.namelist()
        assert "OEBPS/content.opf" in zf.namelist()
        assert "OEBPS/toc.xhtml" in zf.namelist()

    # 2. Verify EpubReader extracts chapters correctly
    reader = EpubReader(epub_bytes)
    extracted_meta = reader.read_metadata()
    assert extracted_meta.title == "Test Light Novel"
    assert len(extracted_meta.chapters) == 2
    assert "Beginning" in extracted_meta.chapters[0].title
    assert "Forest" in extracted_meta.chapters[1].title
    assert "fantasy world" in extracted_meta.chapters[0].content_text


def test_pdf_reader_with_pymupdf(tmp_path: Path):
    """Verify PyMuPDF extracts chapters, bookmarks, and normalized Thai diacritics."""
    pdf_file = tmp_path / "test_novel.pdf"

    # Create synthetic PDF using PyMuPDF
    doc = pymupdf.open()
    # Page 1: Chapter 1
    p1 = doc.new_page()
    p1.insert_text((50, 100), "Chapter 1: Awakening", fontsize=16)
    p1.insert_text((50, 140), "In the beginning there was light.", fontsize=12)

    # Page 2: Chapter 2 with Thai diacritics
    p2 = doc.new_page()
    p2.insert_text((50, 100), "Chapter 2: The Magic Beast", fontsize=16)
    tahoma_path = Path("C:/Windows/Fonts/tahoma.ttf")
    if tahoma_path.exists():
        font = pymupdf.Font(fontfile=str(tahoma_path))
        p2.insert_font(fontname="tahoma", fontbuffer=font.buffer)
        p2.insert_text((50, 140), "ผู้กล้าที่แท้จริงได้ตื่นขึ้นมาแล้ว", fontname="tahoma", fontsize=12)
    else:
        p2.insert_text((50, 140), "The true hero has awakened", fontsize=12)

    # Set bookmarks/TOC
    doc.set_toc([
        [1, "Chapter 1: Awakening", 1],
        [1, "Chapter 2: The Magic Beast", 2],
    ])
    doc.save(str(pdf_file))
    doc.close()

    # Read using PdfReader
    reader = PdfReader(pdf_file)
    meta = reader.read_metadata()
    assert len(meta.chapters) == 2
    assert meta.chapters[0].title == "Chapter 1: Awakening"
    assert "In the beginning" in meta.chapters[0].content_text
    assert meta.chapters[1].title == "Chapter 2: The Magic Beast"
    if tahoma_path.exists():
        assert "ผู้กล้าที่แท้จริง" in meta.chapters[1].content_text
    else:
        assert "true hero" in meta.chapters[1].content_text

    # Test inspect_ebook
    inspect_res = inspect_ebook(pdf_file)
    assert inspect_res.format == "pdf"
    assert inspect_res.total_chapters == 2
    assert inspect_res.chapters[0].title == "Chapter 1: Awakening"

    # Test extraction to directory
    dest = tmp_path / "extracted_chapters"
    res = extract_ebook_to_directory(pdf_file, dest)
    assert res["success"] is True
    assert res["total_extracted"] == 2
    assert (dest / "0001 - Chapter 1_ Awakening.txt").exists()


def test_compile_project_to_ebook(tmp_path: Path):
    """Verify compile_project_to_ebook generates both EPUB and Printable HTML with Bible appendix."""
    # Setup mock novel project
    proj_dir = tmp_path / "novel_proj"
    proj_dir.mkdir(parents=True)
    repo = NovelRepository(proj_dir)
    cfg = repo.load_config()
    cfg.title = "Isekai Reincarnation"
    repo.save_config(cfg)

    # Populate translated chapters
    trans_dir = proj_dir / "translated_chapters"
    trans_dir.mkdir(parents=True, exist_ok=True)
    (trans_dir / "0001.md").write_text("# Chapter 1: The Summoning\n\nHe was summoned to another world.", encoding="utf-8")
    (trans_dir / "0002.md").write_text("# Chapter 2: The First Quest\n\nA quest was waiting in the tavern.", encoding="utf-8")

    # Add Novel Bible entries
    bible = NovelBible()
    bible.characters.append(CharacterProfile(name="Erika", role="Heroine"))
    bible.glossary.append(GlossaryItem(source="Dragon King", target="Ryuou", category="Title"))
    repo.save_bible(bible)

    # 1. Compile EPUB
    epub_opts = EbookExportOptions(
        format="epub",
        include_bible_appendix=True,
    )
    epub_bytes, filename, mime = compile_project_to_ebook(repo, epub_opts)
    assert mime == "application/epub+zip"
    assert filename.endswith(".epub")
    assert len(epub_bytes) > 1000

    # Verify appendix inside EPUB
    with zipfile.ZipFile(io.BytesIO(epub_bytes), "r") as zf:
        assert "OEBPS/appendix.xhtml" in zf.namelist()
        appendix_text = zf.read("OEBPS/appendix.xhtml").decode("utf-8")
        assert "Erika" in appendix_text
        assert "Dragon King" in appendix_text

    # 2. Compile HTML Print
    html_opts = EbookExportOptions(
        format="html_print",
        include_bible_appendix=True,
    )
    html_bytes, h_filename, h_mime = compile_project_to_ebook(repo, html_opts)
    assert h_mime == "text/html"
    assert h_filename.endswith(".html")
    html_str = html_bytes.decode("utf-8")
    assert "Print / Save to PDF" in html_str
    assert "The Summoning" in html_str
    assert "Erika" in html_str


def test_ebook_web_api(tmp_path: Path):
    """Test FastAPI eBook inspect, import, and export endpoints."""
    proj_dir = tmp_path / "web_novel"
    repo = NovelRepository(proj_dir)
    cfg = repo.load_config()
    cfg.title = "Web Novel Adventure"
    repo.save_config(cfg)

    # Build dummy EPUB for inspect and import
    builder = Epub3Writer(
        EbookMetadata(
            title="Web Novel Adventure",
            author="Master Mayoi",
            chapters=[
                EbookChapter(index=1, title="Chapter 1: Genesis", content_text="In the beginning of the great fantasy universe, the hero awakened to great power."),
                EbookChapter(index=2, title="Chapter 2: Journey", content_text="They set off across the endless mountains toward the distant royal capital."),
            ],
        )
    )
    epub_bytes = builder.build()

    client = TestClient(create_app())

    # 1. Inspect endpoint
    resp_inspect = client.post(
        "/api/ebook/inspect",
        files={"file": ("novel.epub", io.BytesIO(epub_bytes), "application/epub+zip")},
    )
    assert resp_inspect.status_code == 200
    inspect_data = resp_inspect.json()
    assert inspect_data["title"] == "Web Novel Adventure"
    assert inspect_data["total_chapters"] == 2

    # 2. Import endpoint
    resp_import = client.post(
        "/api/ebook/import",
        data={"project_path": str(proj_dir), "folder": "Volume_01"},
        files={"file": ("novel.epub", io.BytesIO(epub_bytes), "application/epub+zip")},
    )
    assert resp_import.status_code == 200
    import_data = resp_import.json()
    assert import_data["success"] is True
    assert import_data["imported_count"] == 2
    assert (proj_dir / "Volume_01").is_dir()
    assert len(list((proj_dir / "Volume_01").glob("*.txt"))) == 2

    # 3. Export endpoint (EPUB)
    # Populate a translated chapter first
    trans_dir = proj_dir / "Volume_01_th"
    trans_dir.mkdir(parents=True, exist_ok=True)
    (trans_dir / "0001.md").write_text("# บทที่ 1\n\nเนื้อเรื่องภาษาไทย", encoding="utf-8")

    resp_export = client.post(
        "/api/ebook/export",
        json={"project_path": str(proj_dir), "format": "epub", "folder": "Volume_01"},
    )
    assert resp_export.status_code == 200
    assert resp_export.headers["content-type"] == "application/epub+zip"
    assert len(resp_export.content) > 500

    # 4. Preview endpoint (ToC + Chapter Prose + Typography)
    resp_prev = client.post(
        "/api/ebook/preview",
        json={
            "project_path": str(proj_dir),
            "folder": "Volume_01",
            "preview_chapter_index": 1,
            "font_family": "Prompt",
            "font_size": 18,
            "line_height": 2.0,
        },
    )
    assert resp_prev.status_code == 200
    prev_data = resp_prev.json()
    assert prev_data["title"] == "Web Novel Adventure"
    assert prev_data["total_chapters"] == 1
    assert len(prev_data["toc"]) == 1
    assert prev_data["toc"][0]["title"] == "บทที่ 1"
    assert "เนื้อเรื่อง" in prev_data["sample_chapter_html"]

    # 5. Export endpoint (Native PDF)
    resp_export_pdf = client.post(
        "/api/ebook/export",
        json={
            "project_path": str(proj_dir),
            "format": "pdf",
            "folder": "Volume_01",
            "font_family": "Kanit",
            "font_size": 16,
        },
    )
    assert resp_export_pdf.status_code == 200
    assert resp_export_pdf.headers["content-type"] == "application/pdf"
    assert resp_export_pdf.content.startswith(b"%PDF-")
    assert len(resp_export_pdf.content) > 1000

    # 6. Export endpoint (Printable HTML)
    resp_export_html = client.post(
        "/api/ebook/export",
        json={"project_path": str(proj_dir), "format": "html", "folder": "Volume_01"},
    )
    assert resp_export_html.status_code == 200
    assert "text/html" in resp_export_html.headers["content-type"]
    assert "เนื้อเรื่อง" in resp_export_html.text
    assert "ภาษาไทย" in resp_export_html.text

    # 7. Check /api/folders returns translated_folders and default_translated_folder
    resp_folders = client.get(f"/api/folders?project_path={proj_dir}")
    assert resp_folders.status_code == 200
    f_data = resp_folders.json()
    assert "translated_folders" in f_data
    assert any(tf["folder"] == "Volume_01_th" for tf in f_data["translated_folders"])
    assert f_data["default_translated_folder"] == "Volume_01_th"


def test_pdf_writer_and_preview(tmp_path: Path):
    """Test PdfWriter and preview_project_ebook directly."""
    from nousetsu.ebook.writer import PdfWriter, preview_project_ebook, compile_project_to_ebook

    proj_dir = tmp_path / "pdf_novel"
    repo = NovelRepository(proj_dir)
    cfg = repo.load_config()
    cfg.title = "The Azure Alchemist"
    repo.save_config(cfg)

    trans_dir = proj_dir / "raw_chapters_th"
    trans_dir.mkdir(parents=True, exist_ok=True)
    (trans_dir / "0001.md").write_text("# Chapter 1: The Azure Cauldron\n\nInside the ancient chamber, smoke curled from the cauldron.", encoding="utf-8")
    (trans_dir / "0002.md").write_text("# Chapter 2: The Pill Tribulation\n\nThunder rumbled in the clear sky as the celestial pill formed.", encoding="utf-8")

    # Test preview with automatic folder resolution (folder=None)
    options_auto = EbookExportOptions(
        title="The Azure Alchemist",
        author="Master Mayoi",
        font_family="Noto Serif Thai",
        font_size=18,
        line_height=1.8,
    )
    preview = preview_project_ebook(repo, options_auto, preview_chapter_index=2)
    assert preview.total_chapters == 2
    assert len(preview.toc) == 2
    assert preview.sample_chapter_index == 2
    assert preview.sample_chapter_title == "Chapter 2: The Pill Tribulation"
    assert "Thunder rumbled" in preview.sample_chapter_html

    # Test compilation with automatic folder resolution (folder=None)
    pdf_bytes, filename, mime = compile_project_to_ebook(repo, options_auto)
    assert mime == "application/epub+zip"
    assert len(pdf_bytes) > 1000

    # Test PDF Writer directly
    metadata = EbookMetadata(
        title="The Azure Alchemist",
        author="Master Mayoi",
        chapters=[
            EbookChapter(index=1, title="Chapter 1", content_text="Sample text 1"),
            EbookChapter(index=2, title="Chapter 2", content_text="Sample text 2"),
        ]
    )
    pdf_writer = PdfWriter(metadata, font_family="Prompt", font_size=16)
    pdf_bytes = pdf_writer.build_pdf_bytes()
    assert pdf_bytes.startswith(b"%PDF-")
    assert len(pdf_bytes) > 2000



