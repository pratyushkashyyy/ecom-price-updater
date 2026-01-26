"""
Flipkart Playwright Connector
Handles Flipkart price extraction using Playwright only.
"""

from typing import List, Optional
from .base_connector import BaseConnector


class FlipkartPlaywrightConnector(BaseConnector):
    """Flipkart e-commerce connector for Playwright"""
    
    @property
    def site_name(self) -> str:
        return 'flipkart'
    
    @property
    def domain_patterns(self) -> List[str]:
        return ['flipkart.com', 'shopsy.in', 'fkrt.cc']
    

    
    @property
    def is_blocked_site(self) -> bool:
        return False  # Flipkart works with Playwright
    
    async def extract_price_playwright(self, page, url: str) -> Optional[str]:
        """Extract Flipkart price using Playwright"""
        import re
        
        # Try each selector
        for selector in self.price_selectors:
            try:
                elements = await page.query_selector_all(selector)
                for element in elements:
                    text = await element.text_content()
                    if text and '₹' in text:
                        # Filter out discount percentages
                        if '%' in text or 'off' in text.lower():
                            continue
                        
                        # Check if this is a strikethrough price (MRP) - skip it
                        try:
                            parent = await element.evaluate_handle('el => el.parentElement')
                            parent_classes = await parent.evaluate('el => el.className')
                            # Skip if parent has strikethrough/MRP classes
                            if any(cls in parent_classes.lower() for cls in ['strike', 'mrp', 'yhyocc', 'krYCnD']):
                                continue
                        except:
                            pass
                        
                        cleaned = self.clean_price(text)
                        if cleaned != "N/A" and self.is_valid_price(cleaned):
                            return cleaned
            except:
                continue
        
        return None
    
    def extract_price_selenium(self, driver, url: str) -> Optional[str]:
        """Flipkart Selenium extraction (fallback)"""
        from selenium.webdriver.common.by import By
        import re
        
        try:
            # Try each selector
            for selector in self.price_selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        text = element.text.strip()
                        if text and '₹' in text:
                            # Filter out discount percentages
                            if '%' in text or 'off' in text.lower():
                                continue
                            
                            cleaned = self.clean_price(text)
                            if cleaned != "N/A" and self.is_valid_price(cleaned):
                                return cleaned
                except:
                    continue
            
            return None
        except:
            return None
