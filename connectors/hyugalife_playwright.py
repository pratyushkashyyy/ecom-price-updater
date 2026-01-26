from .base_connector import BaseConnector
import re


class HyugalifePlaywrightConnector(BaseConnector):
    @property
    def site_name(self) -> str:
        """Return the name of the e-commerce site"""
        return 'hyugalife'
    
    @property
    def domain_patterns(self) -> list:
        """Return list of domain patterns to identify this site"""
        return ['hyugalife.com']

    async def extract_price_playwright(self, page, url):
        """Extract price from Hyugalife using Playwright with container scoping."""
        try:
            # Wait for page to load
            await page.wait_for_load_state('networkidle', timeout=10000)
            
            # Try to find price within container selectors first
            for container_selector in self.container_selectors:
                try:
                    # Convert escaped CSS selector
                    container_sel = container_selector.replace('\\:', ':')
                    containers = await page.query_selector_all(container_sel)
                    
                    if containers:
                        for container in containers:
                            for price_selector in self.price_selectors:
                                try:
                                    price_sel = price_selector.replace('\\:', ':')
                                    price_elements = await container.query_selector_all(price_sel)
                                    
                                    for element in price_elements:
                                        text = await element.text_content()
                                        if text:
                                            text = text.strip()
                                            price = self.extract_price_from_text(text)
                                            if price:
                                                return price
                                except Exception:
                                    continue
                except Exception:
                    continue
            
            # Fallback: search globally if container search fails
            for price_selector in self.price_selectors:
                try:
                    price_sel = price_selector.replace('\\:', ':')
                    elements = await page.query_selector_all(price_sel)
                    
                    for element in elements:
                        text = await element.text_content()
                        if text:
                            text = text.strip()
                            price = self.extract_price_from_text(text)
                            if price:
                                return price
                except Exception:
                    continue
            
            return None
            
        except Exception as e:
            print(f"Error extracting price from Hyugalife: {e}")
            return None

    def extract_price_selenium(self, driver, url: str):
        """Extract price from Hyugalife using Selenium with container scoping."""
        try:
            # Try to find price within container selectors first
            for container_selector in self.container_selectors:
                try:
                    from selenium.webdriver.common.by import By
                    containers = driver.find_elements(By.CSS_SELECTOR, container_selector)
                    
                    if containers:
                        for container in containers:
                            for price_selector in self.price_selectors:
                                try:
                                    price_elements = container.find_elements(By.CSS_SELECTOR, price_selector)
                                    
                                    for element in price_elements:
                                        text = element.text
                                        if text:
                                            text = text.strip()
                                            price = self.extract_price_from_text(text)
                                            if price:
                                                return price
                                except Exception:
                                    continue
                except Exception:
                    continue
            
            # Fallback: search globally if container search fails
            for price_selector in self.price_selectors:
                try:
                    from selenium.webdriver.common.by import By
                    elements = driver.find_elements(By.CSS_SELECTOR, price_selector)
                    
                    for element in elements:
                        text = element.text
                        if text:
                            text = text.strip()
                            price = self.extract_price_from_text(text)
                            if price:
                                return price
                except Exception:
                    continue
            
            return None
            
        except Exception as e:
            print(f"Error extracting price from Hyugalife with Selenium: {e}")
            return None
    
    def extract_price_from_text(self, text: str):
        """Extract price from text using the clean_price method"""
        cleaned = self.clean_price(text)
        if cleaned and cleaned != "N/A" and self.is_valid_price(cleaned):
            return cleaned
        return None
