"""
Hygulife scraper (including bitli.in)
"""
import re
from typing import Dict, Optional
from playwright.async_api import Page
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from .base_scraper import BaseScraper


class HygulifeScraper(BaseScraper):
    """Scraper for Hygulife.com and bitli.in"""
    
    def get_site_name(self) -> str:
        return 'hygulife'
    
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
            '.price',
            '.product-price',
            '.sale-price',
            '.current-price',
            '[class*="price"]',
            '[class*="Price"]',
            '[data-price]',
            '.woocommerce-Price-amount',
            'span.price',
            'div.price',
            '#price',
            '.price-current',
        ]
    
    async def extract_price_playwright(self, page: Page) -> Optional[str]:
        """Extract price from Hygulife using Playwright"""
        # First, try to get base price from JSON
        try:
            page_content_for_json = await page.content()
            json_price_match = re.search(
                r'\"price\"\s*:\s*[\"\'₹]?([\d,]+(?:\.\d+)?)',
                page_content_for_json,
                re.IGNORECASE
            )
            json_base_price = None
            if json_price_match:
                try:
                    json_base_price = float(json_price_match.group(1).replace(',', ''))
                except:
                    pass
        except:
            json_base_price = None
        
        # Try to find current price (displayed price, not MRP)
        hygulife_selectors = [
            '.price',
            '.product-price',
            '.sale-price',
            '.current-price',
            '[class*="price"]',
            'span.price',
            'div.price',
        ]
        
        found_prices = []
        for selector in hygulife_selectors:
            try:
                price_elements = await page.query_selector_all(selector)
                for element in price_elements[:15]:
                    try:
                        price_text = (await element.text_content()).strip()
                        if price_text and '₹' in price_text:
                            # Skip discount/offer text
                            if any(word in price_text.lower() for word in ['save', 'off', 'discount', 'get it at', 'extra', 'upto']):
                                continue
                            
                            # Extract price value
                            price_match = re.search(r'₹\s*([\d,]+(?:\.\d{1,2})?)', price_text)
                            if price_match:
                                price_str = price_match.group(1).replace(',', '')
                                try:
                                    price_val = float(price_str)
                                    if 50 <= price_val <= 100000:
                                        # Check if element has strikethrough (MRP/original price)
                                        try:
                                            computed_style = await element.evaluate(
                                                'el => window.getComputedStyle(el).textDecoration'
                                            )
                                            parent = await element.evaluate_handle('el => el.parentElement')
                                            parent_style = ''
                                            if parent:
                                                parent_style = await parent.as_element().evaluate(
                                                    'el => window.getComputedStyle(el).textDecoration'
                                                ) if parent else ''
                                            
                                            # Skip if strikethrough (it's MRP/original price)
                                            if 'line-through' not in str(computed_style) and 'line-through' not in str(parent_style):
                                                if json_base_price:
                                                    if price_val <= json_base_price and (json_base_price - price_val) <= 100:
                                                        found_prices.append((
                                                            price_val,
                                                            price_str,
                                                            price_text,
                                                            abs(json_base_price - price_val)
                                                        ))
                                                else:
                                                    found_prices.append((price_val, price_str, price_text, 0))
                                        except:
                                            if json_base_price and price_val <= json_base_price and (json_base_price - price_val) <= 100:
                                                found_prices.append((
                                                    price_val,
                                                    price_str,
                                                    price_text,
                                                    abs(json_base_price - price_val)
                                                ))
                                            elif not json_base_price:
                                                found_prices.append((price_val, price_str, price_text, 0))
                                except:
                                    continue
                    except:
                        continue
            except:
                continue
        
        # If we found prices, prefer the one closest to JSON base price
        if found_prices:
            if json_base_price:
                found_prices.sort(key=lambda x: (x[3], x[0]))
            else:
                found_prices.sort(key=lambda x: x[0])
            return found_prices[0][1]
        
        return None
    
    def extract_price_selenium(self, driver: WebDriver) -> Optional[str]:
        """Extract price from Hygulife using Selenium"""
        wait = WebDriverWait(driver, 10)
        selectors = ['.price', '.product-price', '.sale-price', '.current-price']
        
        found_prices = []
        for selector in selectors:
            try:
                elements = wait.until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, selector))
                )
                for element in elements[:10]:
                    try:
                        text = element.text.strip()
                        if text and '₹' in text:
                            # Skip discount/offer text
                            if any(word in text.lower() for word in ['save', 'off', 'discount', 'get it at', 'extra', 'upto']):
                                continue
                            
                            price_match = re.search(r'₹\s*([\d,]+(?:\.\d{1,2})?)', text)
                            if price_match:
                                price_str = price_match.group(1).replace(',', '')
                                try:
                                    price_val = float(price_str)
                                    if 50 <= price_val <= 100000:
                                        found_prices.append((price_val, price_str))
                                except:
                                    continue
                    except:
                        continue
            except:
                continue
        
        # Return lowest price (current price, not MRP)
        if found_prices:
            found_prices.sort(key=lambda x: x[0])
            return found_prices[0][1]
        
        return None

