"""
Ajio Selenium Connector
Handles Ajio price extraction using dedicated Selenium module.
"""

from typing import List, Optional
from .base_connector import BaseConnector


class AjioSeleniumConnector(BaseConnector):
    """Ajio e-commerce connector using Selenium module"""
    
    @property
    def site_name(self) -> str:
        return 'ajio'
    
    @property
    def domain_patterns(self) -> List[str]:
        return ['ajio.com', 'ajiio.in']
    

    
    @property
    def is_blocked_site(self) -> bool:
        return True  # Ajio blocks Playwright
    
    @property
    def use_selenium_module(self) -> bool:
        return True  # Use external module
    
    @property
    def selenium_module_name(self) -> str:
        return 'ajio_selenium'
    
    async def extract_price_playwright(self, page, url: str) -> Optional[str]:
        """Ajio blocks Playwright"""
        return None
    
    def extract_price_selenium(self, driver, url: str) -> Optional[str]:
        """Use external Selenium module"""
        return None
