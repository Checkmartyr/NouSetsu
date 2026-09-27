"""Typography utilities for Thai script handling, word wrapping, and book CSS generation."""

import re
from typing import List

try:
    import pythainlp
    _HAS_PYTHAINLP = True
except ImportError:
    _HAS_PYTHAINLP = False

# Regex detecting any Thai Unicode characters
THAI_CHAR_PATTERN = re.compile(r"[\u0E00-\u0E7F]")

# Regex to protect markdown elements (images, links, code blocks) from ZWSP insertion
MD_LINK_OR_IMG_PATTERN = re.compile(r"(!?\[.*?\]\(.*?\)|`[^`]+`)")


def has_thai_text(text: str) -> bool:
    """Check if the text contains any Thai Unicode characters."""
    return bool(THAI_CHAR_PATTERN.search(text))


def wrap_thai_paragraph(paragraph: str) -> str:
    """Insert invisible zero-width spaces (\u200b) between Thai words in a paragraph.

    Protects markdown links, images, and inline code from being broken.
    """
    if not _HAS_PYTHAINLP or not has_thai_text(paragraph):
        return paragraph

    # Split paragraph by markdown links/code snippets so we only tokenize prose
    parts = MD_LINK_OR_IMG_PATTERN.split(paragraph)
    result_parts: List[str] = []

    for part in parts:
        if not part:
            continue
        # If it's a markdown link/image/code, preserve as-is
        if MD_LINK_OR_IMG_PATTERN.match(part):
            result_parts.append(part)
        elif has_thai_text(part):
            try:
                words = pythainlp.tokenize.word_tokenize(part, engine="newmm")
                result_parts.append("\u200b".join(words))
            except Exception:
                result_parts.append(part)
        else:
            result_parts.append(part)

    return "".join(result_parts)


def wrap_thai_text(content: str) -> str:
    """Process multi-line markdown or prose text, applying Thai word wrapping to prose lines."""
    if not _HAS_PYTHAINLP or not has_thai_text(content):
        return content

    lines = content.split("\n")
    processed_lines: List[str] = []
    in_code_block = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            processed_lines.append(line)
            continue

        if in_code_block or not stripped:
            processed_lines.append(line)
            continue

        # Keep markdown headers intact while wrapping heading text
        if stripped.startswith("#"):
            header_prefix = re.match(r"^(#+\s*)(.*)$", line)
            if header_prefix:
                prefix, text = header_prefix.groups()
                processed_lines.append(f"{prefix}{wrap_thai_paragraph(text)}")
                continue

        processed_lines.append(wrap_thai_paragraph(line))

    return "\n".join(processed_lines)


def get_book_stylesheet(language: str = "th") -> str:
    """Return publication-grade CSS for EPUB3 and HTML print media with Sarabun font."""
    font_import = ""
    font_family = "'Sarabun', 'Noto Sans Thai', 'Segoe UI', Tahoma, sans-serif"

    if language.lower().startswith("th"):
        font_import = "@import url('https://fonts.googleapis.com/css2?family=Sarabun:ital,wght@0,300;0,400;0,600;1,400;1,600&display=swap');"
    elif language.lower().startswith("ja"):
        font_import = "@import url('https://fonts.googleapis.com/css2?family=Noto+Serif+JP:wght@400;600&display=swap');"
        font_family = "'Noto Serif JP', 'Hiragino Mincho ProN', 'Yu Mincho', serif"
    elif language.lower().startswith("zh"):
        font_import = "@import url('https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@400;600&display=swap');"
        font_family = "'Noto Serif SC', 'Songti SC', 'SimSun', serif"
    else:
        font_import = "@import url('https://fonts.googleapis.com/css2?family=Literata:ital,opsz,wght@0,7..72,400;0,7..72,600;1,7..72,400&display=swap');"
        font_family = "'Literata', 'Georgia', serif"

    return f"""/* NouSetsu Book Publication Stylesheet */
{font_import}

@charset "UTF-8";

html, body {{
    margin: 0;
    padding: 0;
    font-family: {font_family};
    font-size: 16px;
    line-height: 1.8;
    color: #1a1a1a;
    background-color: #ffffff;
    text-align: justify;
    text-justify: inter-word;
    word-break: normal;
    overflow-wrap: break-word;
    line-break: normal;
}}

body {{
    padding: 2rem 2.5rem;
    max-width: 800px;
    margin: 0 auto;
}}

/* Typography Hierarchy */
h1.book-title {{
    font-size: 2.2rem;
    font-weight: 600;
    text-align: center;
    margin-top: 4rem;
    margin-bottom: 0.5rem;
    line-height: 1.3;
}}

h2.book-author {{
    font-size: 1.2rem;
    font-weight: 400;
    text-align: center;
    color: #555555;
    margin-bottom: 4rem;
}}

h2.chapter-title {{
    font-size: 1.6rem;
    font-weight: 600;
    margin-top: 3rem;
    margin-bottom: 1.5rem;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid #e0deda;
    page-break-before: always;
    break-before: page;
}}

p {{
    text-indent: 1.6em;
    margin-top: 0;
    margin-bottom: 0.6em;
}}

p.no-indent, blockquote p, .dialogue p {{
    text-indent: 0;
}}

blockquote {{
    margin: 1.5rem 2rem;
    padding: 0.5rem 1rem;
    border-left: 3px solid #d9a05b;
    background-color: #faf8f5;
    font-style: italic;
    color: #444444;
}}

/* Illustrations & Figures */
figure {{
    margin: 2rem 0;
    text-align: center;
    page-break-inside: avoid;
    break-inside: avoid;
}}

figure img {{
    max-width: 100%;
    height: auto;
    border-radius: 4px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}}

figcaption {{
    font-size: 0.9rem;
    color: #777777;
    margin-top: 0.5rem;
}}

/* Status Screen / LitRPG System Box */
.status-box {{
    margin: 1.5rem 1rem;
    padding: 1.2rem;
    border: 1px solid #c9c3ba;
    background-color: #f7f5f0;
    border-radius: 4px;
    font-family: inherit;
    font-size: 0.95rem;
    page-break-inside: avoid;
    break-inside: avoid;
}}

/* Novel Bible Appendix */
.appendix-section {{
    margin-top: 4rem;
    page-break-before: always;
    break-before: page;
}}

.character-card {{
    border: 1px solid #e5e2dc;
    border-radius: 4px;
    padding: 1rem;
    margin-bottom: 1rem;
    background-color: #fcfbf9;
    page-break-inside: avoid;
}}

.character-name {{
    font-weight: 600;
    font-size: 1.1rem;
    color: #2b2622;
}}

.character-meta {{
    font-size: 0.85rem;
    color: #857d75;
    margin-bottom: 0.4rem;
}}

table.glossary-table {{
    width: 100%;
    border-collapse: collapse;
    margin: 1.5rem 0;
}}

table.glossary-table th, table.glossary-table td {{
    border: 1px solid #ddd;
    padding: 8px 12px;
    text-align: left;
    font-size: 0.95rem;
}}

table.glossary-table th {{
    background-color: #f4f2ee;
    font-weight: 600;
}}

/* Paged Print Rules (@media print) */
@page {{
    size: A5;
    margin: 20mm 15mm 20mm 15mm;
    @bottom-center {{
        content: counter(page);
        font-family: {font_family};
        font-size: 9pt;
        color: #777777;
    }}
}}

@media print {{
    body {{
        padding: 0;
        max-width: 100%;
    }}

    .no-print {{
        display: none !important;
    }}

    a {{
        text-decoration: none;
        color: inherit;
    }}
}}
"""
