"""
Nykaa Selenium Connector
Handles Nykaa price extraction using dedicated Selenium module.
"""

from typing import List, Optional
from .base_connector import BaseConnector


class NykaaSeleniumConnector(BaseConnector):
    """Nykaa e-commerce connector using Selenium module"""
    
    @property
    def site_name(self) -> str:
        return 'nykaa'
    
    @property
    def domain_patterns(self) -> List[str]:
        return ['nykaa.com']
    

    
    @property
    def is_blocked_site(self) -> bool:
        return True  # Nykaa blocks Playwright
    
    @property
    def use_selenium_module(self) -> bool:
        return True  # Use external module
    
    @property
    def selenium_module_name(self) -> str:
        return 'nykaa_selenium'
    
    async def extract_price_playwright(self, page, url: str) -> Optional[str]:
        """Nykaa blocks Playwright"""
        return None
        
    def check_availability(self, page_content: str) -> dict:
        """
        Custom availability check for Nykaa to avoid false positives.
        Instead of global regex search, we check for specific strong indicators.
        """
        import re
        page_lower = page_content.lower()
        
        # specific indicators that strongly suggest out of stock
        # "Notify Me" is common on Nykaa when OOS
        if 'class="css-1g5w2k6"' in page_content or '>notify me<' in page_lower: 
             # Note: css classes are brittle, text is better. 
             pass

        # Strong OOS indicators
        oos_indicators = [
            r'>\s*sold\s*out\s*<',
            r'>\s*currently\s*unavailable\s*<',
            r'>\s*notify\s*me\s*<'
        ]
        
        for pattern in oos_indicators:
            if re.search(pattern, page_lower):
                print(f"  [NYKAA] OOS detected via pattern: {pattern}")
                return {'available': False, 'status': 'out_of_stock'}

        # If not explicitly OOS, assume available
        # The base connector was checking "out\s*of\s*stock" globally which matched hidden text
        return {'available': True, 'status': 'available'}

    
    def extract_price_selenium(self, driver, url: str) -> Optional[str]:
        """Extract price from Nykaa using multiple stable methods"""
        import json
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        
        try:
            # Wait for page to be fully loaded
            try:
                # Wait for document ready state
                WebDriverWait(driver, 15).until(
                    lambda d: d.execute_script('return document.readyState') == 'complete'
                )
                
                # Try to wait for any price-related element to appear
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, "//*[contains(text(), '₹') or contains(@class, 'price')]"))
                )
            except:
                pass
            
            # Method 1: Try meta tags (most stable)
            try:
                meta_price = driver.find_element(By.CSS_SELECTOR, 'meta[property="product:price:amount"]')
                price = meta_price.get_attribute('content')
                if price and self.is_valid_price(price):
                    return price
            except:
                pass
            
            # Method 2: Try JSON-LD structured data
            try:
                json_ld_scripts = driver.find_elements(By.CSS_SELECTOR, 'script[type="application/ld+json"]')
                for script in json_ld_scripts:
                    try:
                        data = json.loads(script.get_attribute('textContent'))
                        if isinstance(data, dict) and 'offers' in data:
                            offers = data['offers']
                            if isinstance(offers, dict) and 'price' in offers:
                                price = str(offers['price'])
                                if self.is_valid_price(price):
                                    return price
                    except:
                        continue
            except:
                pass
            
            # Method 3: Try CSS selectors from config
            for selector in self.price_selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        text = element.text.strip()
                        if text:
                            # Clean the price text
                            cleaned = self.clean_price(text)
                            if cleaned and cleaned != "N/A" and self.is_valid_price(cleaned):
                                return cleaned
                except:
                    continue
            
            # Method 4: Search for any element containing rupee symbol
            try:
                elements = driver.find_elements(By.XPATH, "//*[contains(text(), '₹')]")
                for element in elements[:10]:  # Limit to first 10
                    text = element.text.strip()
                    if text and len(text) < 20:  # Price text should be short
                        cleaned = self.clean_price(text)
                        if cleaned and cleaned != "N/A" and self.is_valid_price(cleaned):
                            return cleaned
            except:
                pass
            
            return None
            
        except Exception as e:
            print(f"  Error extracting price from Nykaa: {e}")
            return None
