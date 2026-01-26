"""
Meesho Playwright Connector
Handles Meesho price extraction using Playwright (usually blocked).
"""

from typing import List, Optional
from .base_connector import BaseConnector


class MeeshoPlaywrightConnector(BaseConnector):
    """Meesho e-commerce connector for Playwright"""
    
    @property
    def site_name(self) -> str:
        return 'meesho'
    
    @property
    def domain_patterns(self) -> List[str]:
        return ['meesho.com', 'msho.in']
    

    
    @property
    def is_blocked_site(self) -> bool:
        return True  # Meesho usually blocks Playwright
    
    async def extract_price_playwright(self, page, url: str) -> Optional[str]:
        """Meesho usually blocks Playwright"""
        for selector in self.price_selectors:
            try:
                element = await page.query_selector(selector)
                if element:
                    text = await element.text_content()
                    cleaned = self.clean_price(text)
                    if cleaned != "N/A" and self.is_valid_price(cleaned):
                        return cleaned
            except:
                continue
        return None
    
    def extract_price_selenium(self, driver, url: str) -> Optional[str]:
        """Not used for Playwright connector"""
        return None
