"""Unit tests for SEARCH/REPLACE diff patching utility."""
import pytest
from nousetsu.utils.diff_patcher import apply_search_replace_patches, is_patch_format


def test_is_patch_format():
    assert not is_patch_format("")
    assert not is_patch_format("Just normal novel text without patches.")
    
    valid_patch = (
        "<<<<<<< SEARCH\n"
        "old sentence\n"
        "=======\n"
        "new sentence\n"
        ">>>>>>>"
    )
    assert is_patch_format(valid_patch)


def test_apply_single_patch():
    original = (
        "# Chapter 1\n\n"
        "The brave hero stepped forward into the dark dungeon.\n"
        "He drew his ancient sword and listened closely.\n"
    )
    patch = (
        "<<<<<<< SEARCH\n"
        "The brave hero stepped forward into the dark dungeon.\n"
        "=======\n"
        "The courageous warrior strode forward into the shadowed abyss.\n"
        ">>>>>>>"
    )
    result, applied, failed = apply_search_replace_patches(original, patch)
    assert applied == 1
    assert failed == 0
    assert "The courageous warrior strode forward into the shadowed abyss." in result
    assert "He drew his ancient sword" in result
    assert "# Chapter 1" in result


def test_apply_multiple_patches():
    original = (
        "Line one.\n"
        "Line two.\n"
        "Line three.\n"
        "Line four.\n"
    )
    patches = (
        "<<<<<<< SEARCH\n"
        "Line one.\n"
        "=======\n"
        "Alpha line.\n"
        ">>>>>>>\n\n"
        "<<<<<<< SEARCH\n"
        "Line four.\n"
        "=======\n"
        "Omega line.\n"
        ">>>>>>>"
    )
    result, applied, failed = apply_search_replace_patches(original, patches)
    assert applied == 2
    assert failed == 0
    assert "Alpha line.\nLine two.\nLine three.\nOmega line.\n" == result


def test_whitespace_tolerance():
    original = (
        "First line.\n"
        "   Second line with indentation.  \n"
        "Third line.\n"
    )
    patch = (
        "<<<<<<< SEARCH\n"
        "Second line with indentation.\n"
        "=======\n"
        "Modified second line.\n"
        ">>>>>>>"
    )
    result, applied, failed = apply_search_replace_patches(original, patch)
    assert applied == 1
    assert failed == 0
    assert "Modified second line." in result


def test_failed_patch_does_not_corrupt_text():
    original = "This text cannot be found."
    patch = (
        "<<<<<<< SEARCH\n"
        "Completely non-existent sentence.\n"
        "=======\n"
        "Should not appear.\n"
        ">>>>>>>"
    )
    result, applied, failed = apply_search_replace_patches(original, patch)
    assert applied == 0
    assert failed == 1
    assert result == original


def test_no_changes_needed():
    original = "Flawless text."
    patch = "NO_CHANGES_NEEDED"
    result, applied, failed = apply_search_replace_patches(original, patch)
    assert applied == 0
    assert failed == 0
    assert result == original


def test_multi_paragraph_with_blank_lines_and_trailing_whitespace():
    original = (
        "Paragraph one with trailing space. \n\n"
        "Paragraph two with another trailing space. \n\n"
        "Paragraph three unchanged.\n"
    )
    patch = (
        "<<<<<<< SEARCH\n"
        "Paragraph one with trailing space.\n\n"
        "Paragraph two with another trailing space.\n"
        "=======\n"
        "Polished paragraph one.\n\n"
        "Polished paragraph two.\n"
        ">>>>>>>"
    )
    result, applied, failed = apply_search_replace_patches(original, patch)
    assert applied == 1
    assert failed == 0
    assert "Polished paragraph one." in result
    assert "Polished paragraph two." in result
    assert "Paragraph three unchanged." in result


def test_canonicalize_quote_matching():
    """SEARCH block uses 「」brackets but draft text uses ASCII double quotes."""
    original = (
        '"นั่นสินะคะ"\n'
        '\n'
        'เธอพยักหน้ารับ\n'
    )
    patch = (
        '<<<<<<< SEARCH\n'
        '\u300cนั่นสินะคะ\u300d\n'
        '=======\n'
        '"นั่นล่ะสิคะ"\n'
        '>>>>>>>'
    )
    result, applied, failed = apply_search_replace_patches(original, patch)
    assert applied == 1
    assert failed == 0
    assert 'นั่นล่ะสิคะ' in result


def test_canonicalize_fullwidth_punctuation():
    """SEARCH block uses fullwidth ？ and ！ but draft has ASCII ? and !."""
    original = 'เธอถามว่า "จริงหรือ?" เขาตอบ "ใช่!"\n'
    patch = (
        '<<<<<<< SEARCH\n'
        'เธอถามว่า "จริงหรือ\uff1f" เขาตอบ "ใช่\uff01"\n'
        '=======\n'
        'เธอถามขึ้นว่า "จริงหรือ?" เขาตอบ "ใช่!"\n'
        '>>>>>>>'
    )
    result, applied, failed = apply_search_replace_patches(original, patch)
    assert applied == 1
    assert failed == 0
    assert 'เธอถามขึ้นว่า' in result


def test_canonicalize_ellipsis_normalization():
    """SEARCH block uses … (U+2026) but draft text uses ... (three dots)."""
    original = 'เธอลังเลอยู่สักครู่... แล้วก็พูดออกมา\n'
    patch = (
        '<<<<<<< SEARCH\n'
        'เธอลังเลอยู่สักครู่\u2026 แล้วก็พูดออกมา\n'
        '=======\n'
        'เธอลังเลอยู่ชั่วขณะ... แล้วเอ่ยขึ้น\n'
        '>>>>>>>'
    )
    result, applied, failed = apply_search_replace_patches(original, patch)
    assert applied == 1
    assert failed == 0
    assert 'เธอลังเลอยู่ชั่วขณะ' in result


def test_source_language_search_block_skipped():
    """SEARCH block containing Japanese source text should be skipped."""
    original = 'The hero drew his sword and charged forward.\n'
    patch = (
        '<<<<<<< SEARCH\n'
        '意を決してしゃべるサフィナに、思わず横やりを入れてしまう私。'
        'だって、名前なんて覚えたくもなかったから、'
        'それほどに私の彼に対する印象は最悪なのだ。\n'
        '=======\n'
        "Safina spoke with determination, but I couldn't help interrupting.\n"
        '>>>>>>>'
    )
    result, applied, failed = apply_search_replace_patches(original, patch)
    assert applied == 0
    assert failed == 1
    assert result == original  # Original text unchanged


def test_mixed_quote_styles_multiline():
    """Multi-line SEARCH with CJK brackets and fullwidth ? while draft uses ASCII."""
    original = (
        '"คุณเป็นใคร?" เธอถาม\n'
        '\n'
        '"ฉันเป็นอัศวิน" เขาตอบ\n'
    )
    patch = (
        '<<<<<<< SEARCH\n'
        '\u300cคุณเป็นใคร\uff1f\u300d เธอถาม\n'
        '\n'
        '\u300cฉันเป็นอัศวิน\u300d เขาตอบ\n'
        '=======\n'
        '"คุณเป็นใครกันแน่?" เธอถามขึ้น\n'
        '\n'
        '"ข้าคืออัศวิน" เขาตอบอย่างหนักแน่น\n'
        '>>>>>>>'
    )
    result, applied, failed = apply_search_replace_patches(original, patch)
    assert applied == 1
    assert failed == 0
    assert 'คุณเป็นใครกันแน่?' in result
    assert 'ข้าคืออัศวิน' in result


def test_canonicalize_typographic_quotes_english():
    """SEARCH block uses typographic \u201ccurly\u201d quotes but draft has straight quotes."""
    original = 'He said "I will protect you" with conviction.\n'
    patch = (
        '<<<<<<< SEARCH\n'
        'He said \u201cI will protect you\u201d with conviction.\n'
        '=======\n'
        'He declared "I shall protect you" with unwavering resolve.\n'
        '>>>>>>>'
    )
    result, applied, failed = apply_search_replace_patches(original, patch)
    assert applied == 1
    assert failed == 0
    assert 'He declared' in result

