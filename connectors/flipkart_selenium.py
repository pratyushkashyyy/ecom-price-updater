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
        """Extract Flipkart price using Selenium with dual validation"""
        from selenium.webdriver.common.by import By
        import re
        import json
        
        try:
            jsonld_price = None
            css_price = None
            
            # Method 1: Try JSON-LD structured data
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
                                                    jsonld_price = cleaned
                                                    break
                                        elif isinstance(offers, list):
                                            for offer in offers:
                                                price = offer.get('price')
                                                if price:
                                                    cleaned = self.clean_price(str(price))
                                                    if cleaned != "N/A" and self.is_valid_price(cleaned):
                                                        jsonld_price = cleaned
                                                        break
                            if jsonld_price:
                                break
                    except (json.JSONDecodeError, KeyError, AttributeError):
                        continue
            except Exception as e:
                pass
            
            # Method 2: Try CSS selectors
            # Check inside main containers (if any defined)
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
                                        if '%' in text or 'off' in text.lower(): 
                                            continue
                                        cleaned = self.clean_price(text)
                                        if cleaned != "N/A" and self.is_valid_price(cleaned):
                                            css_price = cleaned
                                            break
                                if css_price:
                                    break
                            except:
                                continue
                        if css_price:
                            break
                    except:
                        continue
            
            # Fallback: Global CSS search if no container match
            if not css_price:
                for selector in self.price_selectors:
                    try:
                        elements = driver.find_elements(By.CSS_SELECTOR, selector)
                        for element in elements:
                            text = element.text.strip()
                            if text and '₹' in text:
                                if '%' in text or 'off' in text.lower():
                                    continue
                                cleaned = self.clean_price(text)
                                if cleaned != "N/A" and self.is_valid_price(cleaned):
                                    css_price = cleaned
                                    break
                        if css_price:
                            break
                    except:
                        continue
            
            # Validation: Compare both methods
            if jsonld_price and css_price:
                if jsonld_price == css_price:
                    print(f"  ✅ VALIDATED: Both methods agree on price: ₹{jsonld_price}")
                    return jsonld_price
                else:
                    print(f"  ⚠️  MISMATCH: JSON-LD=₹{jsonld_price}, CSS=₹{css_price} - Using JSON-LD")
                    return jsonld_price  # Prefer JSON-LD when there's a mismatch
            elif jsonld_price:
                print(f"  ✓ Found JSON-LD price: ₹{jsonld_price}")
                return jsonld_price
            elif css_price:
                print(f"  ✓ Found CSS price: ₹{css_price}")
                return css_price
            
            return None
        except:
            return None
