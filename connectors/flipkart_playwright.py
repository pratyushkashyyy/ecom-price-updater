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
        import json
        
        # Priority 1: Try JSON-LD structured data (most reliable)
        try:
            json_ld_scripts = await page.query_selector_all('script[type="application/ld+json"]')
            for script in json_ld_scripts:
                try:
                    content = await script.text_content()
                    if content:
                        data = json.loads(content)
                        
                        # Handle both single object and array of objects
                        items = [data] if isinstance(data, dict) else data if isinstance(data, list) else []
                        
                        for item in items:
                            # Check for Product schema
                            if item.get('@type') == 'Product' or item.get('type') == 'Product':
                                # Try offers.price
                                if 'offers' in item:
                                    offers = item['offers']
                                    if isinstance(offers, dict):
                                        price = offers.get('price')
                                        if price:
                                            cleaned = self.clean_price(str(price))
                                            if cleaned != "N/A" and self.is_valid_price(cleaned):
                                                print(f"  ✓ Found JSON-LD price: ₹{cleaned}")
                                                return cleaned
                                    elif isinstance(offers, list):
                                        for offer in offers:
                                            price = offer.get('price')
                                            if price:
                                                cleaned = self.clean_price(str(price))
                                                if cleaned != "N/A" and self.is_valid_price(cleaned):
                                                    print(f"  ✓ Found JSON-LD price: ₹{cleaned}")
                                                    return cleaned
                except (json.JSONDecodeError, KeyError, AttributeError):
                    continue
        except Exception as e:
            print(f"  ⚠️  JSON-LD extraction failed: {e}")
        
        # Priority 2: Try CSS selectors (fallback)
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
