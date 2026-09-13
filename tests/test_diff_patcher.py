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
