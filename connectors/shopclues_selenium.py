"""
Shopclues Selenium Connector
Handles Shopclues price extraction using Selenium.
"""

from typing import List, Optional
from .base_connector import BaseConnector


class ShopcluesSeleniumConnector(BaseConnector):
    """Shopclues e-commerce connector for Selenium"""
    
    @property
    def site_name(self) -> str:
        return 'shopclues'
    
    @property
    def domain_patterns(self) -> List[str]:
        return ['shopclues.com']
    

    
    async def extract_price_playwright(self, page, url: str) -> Optional[str]:
        """Not used for Selenium connector"""
        return None
    
    def extract_price_selenium(self, driver, url: str) -> Optional[str]:
        """Extract Shopclues price using Selenium"""
        from selenium.webdriver.common.by import By
        
        try:
            for selector in self.price_selectors:
                try:
                    element = driver.find_element(By.CSS_SELECTOR, selector)
                    text = element.text.strip()
                    if text and '₹' in text:
                        cleaned = self.clean_price(text)
                        if cleaned != "N/A" and self.is_valid_price(cleaned):
                            return cleaned
                except:
                    continue
            return None
        except:
            return None
