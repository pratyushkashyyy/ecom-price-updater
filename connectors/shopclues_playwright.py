"""
Shopclues Playwright Connector
Handles Shopclues price extraction using Playwright.
"""

from typing import List, Optional
from .base_connector import BaseConnector


class ShopcluesPlaywrightConnector(BaseConnector):
    """Shopclues e-commerce connector for Playwright"""
    
    @property
    def site_name(self) -> str:
        return 'shopclues'
    
    @property
    def domain_patterns(self) -> List[str]:
        return ['shopclues.com']
    

    
    async def extract_price_playwright(self, page, url: str) -> Optional[str]:
        """Extract Shopclues price using Playwright"""
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
