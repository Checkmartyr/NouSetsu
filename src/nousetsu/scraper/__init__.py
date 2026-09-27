"""
NouSetsu Scraper Integration Module.
Provides URL inspection, TOC discovery, and headless batch extraction powered by Novel-Scraper.
"""

from nousetsu.scraper.models import (
    ScraperChapterItem,
    ScraperInspectRequest,
    ScraperInspectResponse,
    ScraperExtractRequest,
    ScraperStatusResponse,
)
from nousetsu.scraper.detector import (
    find_scraper_directory,
    find_scraper_python,
    get_scraper_info,
)
from nousetsu.scraper.bridge import NovelScraperBridge

__all__ = [
    "ScraperChapterItem",
    "ScraperInspectRequest",
    "ScraperInspectResponse",
    "ScraperExtractRequest",
    "ScraperStatusResponse",
    "find_scraper_directory",
    "find_scraper_python",
    "get_scraper_info",
    "NovelScraperBridge",
]
