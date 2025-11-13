"""
Flipkart scraper (including Shopsy)
"""
import re
from typing import Dict, Optional
from playwright.async_api import Page
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from .base_scraper import BaseScraper


class FlipkartScraper(BaseScraper):
    """Scraper for Flipkart.com and Shopsy.in"""
    
    def get_site_name(self) -> str:
        return 'flipkart'
    
    def get_stock_indicators(self) -> Dict:
        return {
            'out_of_stock': [
                'out of stock',
                'sold out',
                'currently unavailable',
                'unavailable',
                'out of stock!',
                'notify me',
                'notify when available',
                'coming soon',
                'temporarily unavailable'
            ],
            'selectors': [
                '._16FRp0',
                '._9-sL7L',
                '.sold-out',
                '[class*="out-of-stock"]',
                '[class*="sold-out"]',
                '[class*="notify"]',
                'button:has-text("Notify")',
                'button:has-text("Notify Me")',
                '[class*="unavailable"]',
                '._2UzuFa',
                '._2KpZ6l._2UzuFa'
            ]
        }
    
    def get_price_selectors(self) -> list:
        return [
            '._30jeq3',
            '._16Jk6d',
            '._1vC4OE',
            '._3qQ9m1',
            '.Nx9bqj'
        ]
    
    async def extract_price_playwright(self, page: Page) -> Optional[str]:
        """Extract price from Flipkart using Playwright"""
        priority_selectors = ['._30jeq3', '.Nx9bqj', '._16Jk6d', '._1vC4OE']
        
        found_prices = []
        for selector in priority_selectors:
            try:
                price_elements = await page.query_selector_all(selector)
                for element in price_elements[:5]:
                    price_text = (await element.text_content()).strip()
                    cleaned_price = self.clean_price(price_text)
                    if cleaned_price != "N/A" and self.is_valid_price(cleaned_price):
                        try:
                            price_float = float(cleaned_price.replace(',', ''))
                            if 50 <= price_float <= 10000000:
                                found_prices.append((price_float, cleaned_price))
                        except:
                            continue
            except:
                continue
        
        # Return highest price (main product price)
        if found_prices:
            found_prices.sort(key=lambda x: x[0], reverse=True)
            return found_prices[0][1]
        
        return None
    
    def extract_price_selenium(self, driver: WebDriver) -> Optional[str]:
        """Extract price from Flipkart using Selenium"""
        wait = WebDriverWait(driver, 10)
        priority_selectors = ['._30jeq3', '.Nx9bqj', '._16Jk6d', '._1vC4OE']
        
        found_prices = []
        for selector in priority_selectors:
            try:
                price_elements = wait.until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, selector))
                )
                for element in price_elements[:5]:
                    text = element.text.strip()
                    if text and '₹' in text:
                        price_match = re.search(r'₹\s*([\d,]+(?:\.\d{1,2})?)', text)
                        if price_match:
                            price_value = price_match.group(1).replace(',', '')
                            try:
                                price_float = float(price_value)
                                if 50 <= price_float <= 10000000:
                                    found_prices.append((price_float, price_value))
                            except:
                                continue
            except:
                continue
        
        # Return highest price
        if found_prices:
            found_prices.sort(key=lambda x: x[0], reverse=True)
            return found_prices[0][1]
        
        return None

