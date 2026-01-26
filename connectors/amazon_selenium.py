"""
Amazon Selenium Connector
Handles Amazon price extraction using Selenium.
"""

from typing import List, Optional
from .base_connector import BaseConnector


class AmazonSeleniumConnector(BaseConnector):
    """Amazon e-commerce connector for Selenium"""
    
    @property
    def site_name(self) -> str:
        return 'amazon'
    
    @property
    def domain_patterns(self) -> List[str]:
        return ['amazon.in', 'amazon.com', 'amzn.to', 'amzn.in']
    

    
    async def extract_price_playwright(self, page, url: str) -> Optional[str]:
        """Not used for Selenium connector"""
        return None
    
    def extract_price_selenium(self, driver, url: str) -> Optional[str]:
        """Extract Amazon price using Selenium"""
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
            
            # Define main product container selectors to scope search
            amazon_containers = ['#ppd', '#centerCol', '#apex_desktop', '#rightCol', '#buybox']
            
            # Priority 1: Check inside main containers
            for container_sel in amazon_containers:
                try:
                    # Find container first
                    container = driver.find_element(By.CSS_SELECTOR, container_sel)
                    
                    # Search for price selectors INSIDE this container
                    for selector in self.price_selectors:
                        try:
                            # Use find_elements to check if it exists inside container
                            elements = container.find_elements(By.CSS_SELECTOR, selector)
                            for element in elements:
                                text = element.text.strip()
                                if text:
                                    cleaned = self.clean_price(text)
                                    if cleaned != "N/A" and self.is_valid_price(cleaned):
                                        return cleaned
                        except:
                            continue
                except:
                    continue
            
            # Fallback: Global search (only if main container search fails)
            # CAUTION: This might pick up related items, but we need a fallback.
            # However, user explicitly asked to "locate main box... and ONLY from there".
            # So maybe we should skipping global fallback or be very strict.
            # Let's keep a very restricted global fallback for specific unique IDs
            
            strict_selectors = ['#priceblock_ourprice', '#priceblock_dealprice', '#tp_price_block_total_price_ww']
            for selector in strict_selectors:
                 try:
                    element = driver.find_element(By.CSS_SELECTOR, selector)
                    text = element.text.strip()
                    if text:
                        cleaned = self.clean_price(text)
                        if cleaned != "N/A" and self.is_valid_price(cleaned):
                            return cleaned
                 except:
                    pass

            return None
        except:
            return None
