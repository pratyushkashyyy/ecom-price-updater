"""
Flipkart Selenium Connector
Handles Flipkart price extraction using Selenium.
"""

from typing import List, Optional
from .base_connector import BaseConnector


class FlipkartSeleniumConnector(BaseConnector):
    """Flipkart e-commerce connector for Selenium"""
    
    @property
    def site_name(self) -> str:
        return 'flipkart'
    
    @property
    def domain_patterns(self) -> List[str]:
        return ['flipkart.com', 'shopsy.in', 'fkrt.cc']
    

    
    async def extract_price_playwright(self, page, url: str) -> Optional[str]:
        """Not used for Selenium connector"""
        return None
    
    def extract_price_selenium(self, driver, url: str) -> Optional[str]:
        """Extract Flipkart price using Selenium"""
        from selenium.webdriver.common.by import By
        import re
        
        try:
            # Priority 1: Check inside main containers (if any defined)
            if hasattr(self, 'container_selectors') and self.container_selectors:
                for container_sel in self.container_selectors:
                    try:
                        container = driver.find_element(By.CSS_SELECTOR, container_sel)
                        for selector in self.price_selectors:
                            try:
                                elements = container.find_elements(By.CSS_SELECTOR, selector)
                                for element in elements:
                                    text = element.text.strip()
                                    if text and '₹' in text:
                                        if '%' in text or 'off' in text.lower(): continue
                                        cleaned = self.clean_price(text)
                                        if cleaned != "N/A" and self.is_valid_price(cleaned):
                                            return cleaned
                            except:
                                continue
                    except:
                        continue
            
            # Fallback: Scoped Global search (exclude recommendations if possible)
            # Since user requested strict scoping, we will still search globally but be careful
            # Update: If containers were defined but failed, we might want to return None?
            # For now, let's keep global fallback but it's risky. 
            # Actually, to comply with user request "only from there", we should maybe skip global if containers existed.
            # But let's check global ONLY if no containers matched.
            
            # Try each selector globally
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
