"""
Myntra Selenium Connector
Handles Myntra price extraction using dedicated Selenium module.
"""

from typing import List, Optional
from .base_connector import BaseConnector


class MyntraSeleniumConnector(BaseConnector):
    """Myntra e-commerce connector using Selenium module"""
    
    @property
    def site_name(self) -> str:
        return 'myntra'
    
    @property
    def domain_patterns(self) -> List[str]:
        return ['myntra.com', 'myntr.it']
    

    
    @property
    def is_blocked_site(self) -> bool:
        return True  # Myntra blocks Playwright
    
    @property
    def use_selenium_module(self) -> bool:
        return True  # Use external module
    
    def extract_price_selenium(self, driver, url: str) -> Optional[str]:
        """Extract Myntra price using Selenium"""
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        
        try:
            # Myntra loads dynamically, wait for price element
            wait = WebDriverWait(driver, 10)
            
            # Priority 1: Check inside main containers
            if hasattr(self, 'container_selectors') and self.container_selectors:
                for container_sel in self.container_selectors:
                    try:
                        container = driver.find_element(By.CSS_SELECTOR, container_sel)
                        
                        # Try specific selector inside container
                        try:
                            elem = container.find_element(By.CSS_SELECTOR, '.pdp-price strong')
                            text = elem.text.strip()
                            cleaned = self.clean_price(text)
                            if cleaned != "N/A" and self.is_valid_price(cleaned):
                                return cleaned
                        except:
                            pass

                        # Try other selectors inside container
                        for selector in self.price_selectors:
                            try:
                                elements = container.find_elements(By.CSS_SELECTOR, selector)
                                for element in elements:
                                    text = element.text.strip()
                                    if text and '₹' in text:
                                        cleaned = self.clean_price(text)
                                        if cleaned != "N/A" and self.is_valid_price(cleaned):
                                            return cleaned
                            except:
                                continue
                    except:
                        continue
            
            # Fallback based on original logic but careful
            
            # Try specific selling price selector first
            try:
                elem = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '.pdp-price strong')))
                text = elem.text.strip()
                cleaned = self.clean_price(text)
                if cleaned != "N/A" and self.is_valid_price(cleaned):
                    return cleaned
            except:
                pass
            
            # Try other selectors
            for selector in self.price_selectors:
                try:
                    elem = driver.find_element(By.CSS_SELECTOR, selector)
                    text = elem.text.strip()
                    if text and '₹' in text:
                        cleaned = self.clean_price(text)
                        if cleaned != "N/A" and self.is_valid_price(cleaned):
                            return cleaned
                except:
                    continue
            
            return None
        except Exception as e:
            return None
    
    @property
    def selenium_module_name(self) -> str:
        return 'myntra_selenium'
    
    async def extract_price_playwright(self, page, url: str) -> Optional[str]:
        """Myntra blocks Playwright"""
        return None
    

