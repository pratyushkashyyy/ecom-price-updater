"""
Amazon Playwright Connector
Handles Amazon price extraction using Playwright only.
"""

from typing import List, Optional
from .base_connector import BaseConnector


class AmazonPlaywrightConnector(BaseConnector):
    """Amazon e-commerce connector for Playwright"""
    
    @property
    def site_name(self) -> str:
        return 'amazon'
    
    @property
    def domain_patterns(self) -> List[str]:
        return ['amazon.in', 'amazon.com', 'amzn.to', 'amzn.in']
    

    
    @property
    def is_blocked_site(self) -> bool:
        return False  # Amazon works with Playwright
    
    def is_valid_price(self, price: str) -> bool:
        """Amazon-specific price validation"""
        if not super().is_valid_price(price):
            return False
        
        try:
            price_value = float(price.replace(',', ''))
            # Amazon prices typically range from 10 to 10 million
            return 10 <= price_value <= 10000000
        except:
            return False
    
    async def extract_price_playwright(self, page, url: str) -> Optional[str]:
        """Extract Amazon price using Playwright"""
        import re
        
        # Priority 1: Hidden input field (most reliable)
        try:
            hidden_input = await page.query_selector('input[type="hidden"][name="items[0.base][customerVisiblePrice][amount]"]')
            if hidden_input:
                price_value = await hidden_input.get_attribute('value')
                if price_value and self.is_valid_price(price_value):
                    # Check for variant price (500 edge case)
                    price_float = float(price_value)
                    if price_float == 500:
                        # Look for higher price in buybox
                        try:
                            buybox = await page.query_selector('#buybox')
                            if buybox:
                                price_elements = await buybox.query_selector_all('.a-price .a-offscreen, .a-price .a-price-whole')
                                for elem in price_elements:
                                    text = await elem.text_content()
                                    if text and '₹' in text:
                                        match = re.search(r'₹\s*([\d,]+(?:\.\d{1,2})?)', text)
                                        if match:
                                            alt_price = match.group(1).replace(',', '')
                                            alt_float = float(alt_price)
                                            if alt_float > 500 and self.is_valid_price(alt_price):
                                                return alt_price
                        except:
                            pass
                    return price_value
        except:
            pass
        
        # Priority 2: Try selectors in order
        for selector in self.price_selectors:
            try:
                element = await page.query_selector(selector)
                if element:
                    text = await element.text_content()
                    if text:
                        cleaned = self.clean_price(text)
                        if cleaned != "N/A" and self.is_valid_price(cleaned):
                            return cleaned
            except:
                continue
        
        return None
    
    def extract_price_selenium(self, driver, url: str) -> Optional[str]:
        """Amazon Selenium extraction (fallback)"""
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        import re
        
        try:
            wait = WebDriverWait(driver, 10)
            
            # Try hidden input
            try:
                hidden_input = driver.find_element(By.CSS_SELECTOR, 'input[type="hidden"][name="items[0.base][customerVisiblePrice][amount]"]')
                price_value = hidden_input.get_attribute('value')
                if price_value and self.is_valid_price(price_value):
                    return price_value
            except:
                pass
            
            # Try selectors
            for selector in self.price_selectors:
                try:
                    element = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                    text = element.text.strip()
                    if text:
                        cleaned = self.clean_price(text)
                        if cleaned != "N/A" and self.is_valid_price(cleaned):
                            return cleaned
                except:
                    continue
            
            return None
        except:
            return None
