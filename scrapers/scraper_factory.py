"""
Factory class to get the appropriate scraper for a given URL
"""
import json
import os
from urllib.parse import urlparse
from .amazon_scraper import AmazonScraper
from .flipkart_scraper import FlipkartScraper
from .myntra_scraper import MyntraScraper
from .ajio_scraper import AjioScraper
from .nykaa_scraper import NykaaScraper
from .snapdeal_scraper import SnapdealScraper
from .shopclues_scraper import ShopcluesScraper
from .hygulife_scraper import HygulifeScraper
from .meesho_scraper import MeeshoScraper
from .generic_scraper import GenericScraper

class ScraperFactory:
    """Factory to create scraper instances based on URL"""
    
    _selectors = None
    
    @classmethod
    def load_selectors(cls):
        """Load selectors from JSON file once"""
        if cls._selectors is None:
            try:
                base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                json_path = os.path.join(base_path, 'selectors.json')
                with open(json_path, 'r', encoding='utf-8') as f:
                    cls._selectors = json.load(f)
            except Exception as e:
                print(f"Warning: Could not load selectors.json: {e}")
                cls._selectors = {}
        return cls._selectors
    
    @staticmethod
    def is_known_site(url: str) -> bool:
        """Check if URL maps to a known (non-generic) scraper"""
        return ScraperFactory.identify_site(url) != 'generic'
    
    @staticmethod
    def get_scraper(url: str):
        """Identify site and return appropriate scraper with injected selectors"""
        site = ScraperFactory.identify_site(url)
        selectors = ScraperFactory.load_selectors().get(site, {})
        
        if site == 'amazon':
            return AmazonScraper(selectors=selectors)
        elif site == 'flipkart':
            return FlipkartScraper(selectors=selectors)
        elif site == 'myntra':
            return MyntraScraper(selectors=selectors)
        elif site == 'ajio':
            return AjioScraper(selectors=selectors)
        elif site == 'nykaa':
            return NykaaScraper(selectors=selectors)
        elif site == 'snapdeal':
            return SnapdealScraper(selectors=selectors)
        elif site == 'shopclues':
            return ShopcluesScraper(selectors=selectors)
        elif site == 'hygulife':
            return HygulifeScraper(selectors=selectors)
        elif site == 'meesho':
            return MeeshoScraper(selectors=selectors)
        else:
            return GenericScraper(selectors=selectors)
            
    @staticmethod
    def identify_site(url: str) -> str:
        """Identify the e-commerce site from URL"""
        domain = urlparse(url).netloc.lower()
        
        # Handle short URLs and redirect domains
        if 'amzn.to' in domain or 'amzn' in domain:
            return 'amazon'
        elif 'amazon' in domain:
            return 'amazon'
        elif 'flipkart' in domain or 'shopsy' in domain or 'fkrt.cc' in domain:
            return 'flipkart'
        elif 'myntra' in domain or 'myntr.it' in domain:
            return 'myntra'
        elif 'nykaa' in domain:
            return 'nykaa'
        elif 'snapdeal' in domain:
            return 'snapdeal'
        elif 'ajio' in domain or 'ajiio.in' in domain:
            return 'ajio'
        elif 'meesho' in domain or 'msho.in' in domain:
            return 'meesho'
        elif 'shopclues' in domain:
            return 'shopclues'
        elif 'hygulife' in domain or 'hyugalife' in domain:
            return 'hygulife'
        elif 'bitli.in' in domain:
            return 'generic'  # Can't determine from domain alone, needs browser
        elif 'extp.in' in domain:
            return 'generic'  # Short-link domain, needs browser resolution
        else:
            return 'generic'
