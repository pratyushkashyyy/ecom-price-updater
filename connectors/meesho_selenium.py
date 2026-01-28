"""
Meesho Selenium Connector
Handles Meesho price extraction using dedicated Selenium module.
"""

from typing import List, Optional
from .base_connector import BaseConnector


class MeeshoSeleniumConnector(BaseConnector):
    """Meesho e-commerce connector using Selenium module"""
    
    @property
    def site_name(self) -> str:
        return 'meesho'
    
    @property
    def selenium_module_name(self) -> str:
        return 'meesho_selenium'

    async def extract_price_playwright(self, page, url: str) -> Optional[str]:
        """Meesho blocks Playwright"""
        return None
        
    @property
    def domain_patterns(self) -> List[str]:
        return ['meesho.com', 'msho.in']
    

        
    def extract_price_selenium(self, driver, url: str) -> Optional[str]:
        """Extract Meesho price using Selenium"""
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        import re
        import json
        
        try:
            # Wait for any price element
            wait = WebDriverWait(driver, 10)
            
            # Priority 1: Try JSON-LD structured data (most reliable)
            try:
                json_ld_scripts = driver.find_elements(By.CSS_SELECTOR, 'script[type="application/ld+json"]')
                for script in json_ld_scripts:
                    try:
                        content = script.get_attribute('textContent') or script.get_attribute('innerHTML')
                        if content:
                            data = json.loads(content)
                            items = [data] if isinstance(data, dict) else data if isinstance(data, list) else []
                            
                            for item in items:
                                if item.get('@type') == 'Product' or item.get('type') == 'Product':
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
            
            # Priority 2: Try h4 first (most reliable CSS selector)
            try:
                elem = wait.until(EC.presence_of_element_located((By.TAG_NAME, 'h4')))
                text = elem.text.strip()
                cleaned = self.clean_price(text)
                if cleaned != "N/A" and self.is_valid_price(cleaned):
                    return cleaned
            except:
                pass
                
            # 2. Try ShippingInfo__Price (often contains multiple lines)
            try:
                elems = driver.find_elements(By.CSS_SELECTOR, 'div[class*="ShippingInfo__Price"]')
                for elem in elems:
                    text = elem.text.strip()
                    # It might be multiline "₹95\n₹102\n7% off"
                    # We want the first line usually, or just extract first price
                    if '₹' in text:
                        match = re.search(r'₹\s*([\d,]+)', text)
                        if match:
                            cleaned = match.group(1).replace(',', '')
                            if self.is_valid_price(cleaned):
                                return cleaned
            except:
                pass
            
            # 3. Fallback to generic selectors
            for selector in self.price_selectors:
                if selector in ['h4', 'div[class*="ShippingInfo__Price"]']: continue
                try:
                    elems = driver.find_elements(By.CSS_SELECTOR, selector)
                    for elem in elems:
                        text = elem.text.strip()
                        if '₹' in text:
                            cleaned = self.clean_price(text)
                            if cleaned != "N/A" and self.is_valid_price(cleaned):
                                return cleaned
                except:
                    continue
            
            return None
        except Exception as e:
            return None
