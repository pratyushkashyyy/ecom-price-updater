"""
Ajio scraper
"""
from typing import Dict, Optional
from playwright.async_api import Page
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from .base_scraper import BaseScraper


class AjioScraper(BaseScraper):
    """Scraper for Ajio.com"""
    
    def get_site_name(self) -> str:
        return 'ajio'
    
    def get_stock_indicators(self) -> Dict:
        return {
            'out_of_stock': [
                'out of stock',
                'sold out',
                'currently unavailable',
                'unavailable'
            ],
            'selectors': [
                '[class*="out-of-stock"]',
                '[class*="sold-out"]',
                '.sold-out'
            ]
        }
    
    def get_price_selectors(self) -> list:
        return [
            '.prod-sp',
            'span[class*="prod-sp"]',
            '.prod-base-price',
            'span[class*="price"]',
            '[class*="prod-base-price"]',
            '[data-id="price"]',
            '.price',
        ]
    
    async def extract_price_playwright(self, page: Page) -> Optional[str]:
        """Extract price from Ajio using Playwright"""
        selectors = ['.prod-sp', '.prod-base-price', '[data-id="price"]', '.price']
        
        for selector in selectors:
            try:
                element = await page.query_selector(selector, timeout=2000)
                if element:
                    price_text = (await element.text_content()).strip()
                    cleaned_price = self.clean_price(price_text)
                    if cleaned_price != "N/A" and self.is_valid_price(cleaned_price):
                        try:
                            price_float = float(cleaned_price.replace(',', ''))
                            if price_float >= 50:
                                return cleaned_price
                        except:
                            pass
            except:
                continue
        
        return None
    
    def extract_price_selenium(self, driver: WebDriver) -> Optional[str]:
        """Extract price from Ajio using Selenium"""
        import json
        wait = WebDriverWait(driver, 10)
        
        # Priority 1: Try JSON-LD structured data
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
                                                return cleaned
                                    elif isinstance(offers, list):
                                        for offer in offers:
                                            price = offer.get('price')
                                            if price:
                                                cleaned = self.clean_price(str(price))
                                                if cleaned != "N/A" and self.is_valid_price(cleaned):
                                                    return cleaned
                except (json.JSONDecodeError, KeyError, AttributeError):
                    continue
        except Exception:
            pass
        
        # Priority 2: CSS selectors
        selectors = ['.prod-sp', '.prod-base-price', '[data-id="price"]', '.price']
        
        for selector in selectors:
            try:
                element = wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                text = element.text.strip()
                cleaned_price = self.clean_price(text)
                if cleaned_price != "N/A" and self.is_valid_price(cleaned_price):
                    try:
                        price_float = float(cleaned_price.replace(',', ''))
                        if price_float >= 50:
                            return cleaned_price
                    except:
                        pass
            except:
                continue
        
        return None

