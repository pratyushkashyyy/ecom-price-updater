"""
Snapdeal scraper
"""
from typing import Dict, Optional
from playwright.async_api import Page
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from .base_scraper import BaseScraper


class SnapdealScraper(BaseScraper):
    """Scraper for Snapdeal.com"""
    
    def get_site_name(self) -> str:
        return 'snapdeal'
    
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
            '.payBlkBig',
            '.pdp-final-price',
            '.pdp-selling-price',
            '[class*="price"]'
        ]
    
    async def extract_price_playwright(self, page: Page) -> Optional[str]:
        """Extract price from Snapdeal using Playwright"""
        selectors = ['.payBlkBig', '.pdp-final-price', '.pdp-selling-price']
        
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
        """Extract price from Snapdeal using Selenium"""
        wait = WebDriverWait(driver, 10)
        selectors = ['.payBlkBig', '.pdp-final-price', '.pdp-selling-price']
        
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

