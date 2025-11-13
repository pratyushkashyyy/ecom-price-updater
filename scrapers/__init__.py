"""
E-commerce scrapers module
Each website has its own scraper file
"""
from .base_scraper import BaseScraper
from .amazon_scraper import AmazonScraper
from .flipkart_scraper import FlipkartScraper
from .myntra_scraper import MyntraScraper
from .nykaa_scraper import NykaaScraper
from .ajio_scraper import AjioScraper
from .meesho_scraper import MeeshoScraper
from .snapdeal_scraper import SnapdealScraper
from .shopclues_scraper import ShopcluesScraper
from .hygulife_scraper import HygulifeScraper
from .generic_scraper import GenericScraper

# Map site names to scraper classes
SCRAPER_MAP = {
    'amazon': AmazonScraper,
    'flipkart': FlipkartScraper,
    'myntra': MyntraScraper,
    'nykaa': NykaaScraper,
    'ajio': AjioScraper,
    'meesho': MeeshoScraper,
    'snapdeal': SnapdealScraper,
    'shopclues': ShopcluesScraper,
    'hygulife': HygulifeScraper,
    'generic': GenericScraper,
}

__all__ = [
    'BaseScraper',
    'AmazonScraper',
    'FlipkartScraper',
    'MyntraScraper',
    'NykaaScraper',
    'AjioScraper',
    'MeeshoScraper',
    'SnapdealScraper',
    'ShopcluesScraper',
    'HygulifeScraper',
    'GenericScraper',
    'SCRAPER_MAP',
]

