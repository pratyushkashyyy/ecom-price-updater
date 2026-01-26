from .base_connector import BaseConnector
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import re


class HyugalifeSeleniumConnector(BaseConnector):
    @property
    def site_name(self) -> str:
        """Return the name of the e-commerce site"""
        return 'hyugalife'
    
    @property
    def domain_patterns(self) -> list:
        """Return list of domain patterns to identify this site"""
        return ['hyugalife.com']

    def extract_price_selenium(self, driver, url):
        """Extract price from Hyugalife using Selenium with container scoping."""
        try:
            # Wait for page to load
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Try to find price within container selectors first
            for container_selector in self.container_selectors:
                try:
                    # Convert CSS selector for Selenium
                    container_sel = container_selector.replace('\\:', ':')
                    containers = driver.find_elements(By.CSS_SELECTOR, container_sel)
                    
                    if containers:
                        for container in containers:
                            for price_selector in self.price_selectors:
                                try:
                                    price_sel = price_selector.replace('\\:', ':')
                                    price_elements = container.find_elements(By.CSS_SELECTOR, price_sel)
                                    
                                    for element in price_elements:
                                        text = element.text.strip()
                                        if text:
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
                    elements = driver.find_elements(By.CSS_SELECTOR, price_sel)
                    
                    for element in elements:
                        text = element.text.strip()
                        if text:
                            price = self.extract_price_from_text(text)
                            if price:
                                return price
                except Exception:
                    continue
            
            return None
            
        except Exception as e:
            print(f"Error extracting price from Hyugalife: {e}")
            return None
    
    async def extract_price_playwright(self, page, url: str):
        """Extract price from Hyugalife using Playwright (not used for Selenium connector)."""
        # This is a Selenium-only connector, so Playwright method is not implemented
        # However, we need to provide it to satisfy the abstract method requirement
        return None
    
    def extract_price_from_text(self, text: str):
        """Extract price from text using the clean_price method"""
        cleaned = self.clean_price(text)
        if cleaned and cleaned != "N/A" and self.is_valid_price(cleaned):
            return cleaned
        return None
