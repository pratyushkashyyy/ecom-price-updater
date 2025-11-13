"""
Selenium-based scrapers (fallback implementations)
"""
from .ajio_selenium import scrape_ajio_with_selenium
from .meesho_selenium import scrape_meesho_with_selenium
from .myntra_selenium import scrape_myntra_with_selenium
from .nykaa_selenium import scrape_nykaa_with_selenium

__all__ = [
    'scrape_ajio_with_selenium',
    'scrape_meesho_with_selenium',
    'scrape_myntra_with_selenium',
    'scrape_nykaa_with_selenium',
]

