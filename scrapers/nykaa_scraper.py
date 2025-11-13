"""
Nykaa scraper
"""
from typing import Dict, Optional
from playwright.async_api import Page
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from .base_scraper import BaseScraper


class NykaaScraper(BaseScraper):
    """Scraper for Nykaa.com"""
    
    def get_site_name(self) -> str:
        return 'nykaa'
    
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
            '.css-1jczs19',  # Selling price
            '.css-1d0jf8e',  # Price container
            '[class*="css-1jczs19"]',  # Selling price (any element)
            '[class*="price"]',
            '.price',
            'span:has-text("₹")',  # Any span with ₹
            '[data-testid*="price"]',  # Price test id
        ]
    
    async def extract_price_playwright(self, page: Page) -> Optional[str]:
        """Extract price from Nykaa using Playwright"""
        # Try multiple strategies
        selectors = [
            '.css-1jczs19',  # Main selling price
            '[class*="css-1jczs19"]',  # Selling price variant
            '.css-1d0jf8e',  # Price container
            '[class*="price"]',
            '.price',
        ]
        
        # Strategy 1: Try specific selectors
        for selector in selectors:
            try:
                element = await page.query_selector(selector, timeout=3000)
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
        
        # Strategy 2: Find all elements with ₹ symbol and extract prices
        try:
            # Find all elements containing ₹ using XPath
            elements_with_rupee = await page.query_selector_all('xpath=//*[contains(text(), "₹")]')
            found_prices = []
            
            for element in elements_with_rupee[:20]:  # Check first 20
                try:
                    text = (await element.text_content()).strip()
                    if text and '₹' in text and len(text) < 100:
                        cleaned_price = self.clean_price(text)
                        if cleaned_price != "N/A" and self.is_valid_price(cleaned_price):
                            try:
                                price_float = float(cleaned_price.replace(',', ''))
                                if 50 <= price_float <= 1000000:  # Reasonable range
                                    # Get parent element to check class
                                    parent = await element.evaluate_handle('el => el.parentElement')
                                    parent_class = ''
                                    if parent:
                                        try:
                                            parent_class = await parent.as_element().get_attribute('class') or ''
                                        except:
                                            pass
                                    
                                    # Prefer selling price class (css-1jczs19)
                                    priority = 0 if 'css-1jczs19' in parent_class else 1
                                    found_prices.append((priority, price_float, cleaned_price))
                            except:
                                continue
                except:
                    continue
            
            # Sort by priority (selling price first) then by price
            if found_prices:
                found_prices.sort(key=lambda x: (x[0], -x[1]))
                return found_prices[0][2]
        except:
            pass
        
        # Strategy 3: Search page content for price patterns
        try:
            page_content = await page.content()
            import re
            # Look for price in common Nykaa patterns
            patterns = [
                r'₹\s*([\d,]+(?:\.\d{1,2})?)',
                r'<[^>]*class="[^"]*css-1jczs19[^"]*"[^>]*>.*?₹\s*([\d,]+(?:\.\d{1,2})?)',
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, page_content, re.IGNORECASE | re.DOTALL)
                if matches:
                    prices = [m.replace(',', '') for m in matches if m]
                    if prices:
                        try:
                            price_floats = [float(p) for p in prices]
                            valid_prices = [p for p in price_floats if 50 <= p <= 1000000]
                            if valid_prices:
                                # Return median price (most likely the main price)
                                valid_prices.sort()
                                return str(int(valid_prices[len(valid_prices)//2]))
                        except:
                            pass
        except:
            pass
        
        return None
    
    def extract_price_selenium(self, driver: WebDriver) -> Optional[str]:
        """Extract price from Nykaa using Selenium"""
        import re
        wait = WebDriverWait(driver, 15)
        selectors = [
            '.css-1jczs19',  # Main selling price
            '[class*="css-1jczs19"]',  # Selling price variant
            '.css-1d0jf8e',  # Price container
            '[class*="price"]',
            '.price',
        ]
        
        # Strategy 1: Try specific selectors
        found_prices = []
        for selector in selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for element in elements[:5]:  # Check first 5 matches
                    try:
                        text = element.text.strip()
                        if text and '₹' in text and len(text) < 100:
                            price_match = re.search(r'₹\s*([\d,]+(?:\.\d{1,2})?)', text)
                            if price_match:
                                price_value = price_match.group(1).replace(',', '')
                                try:
                                    price_float = float(price_value)
                                    if 50 <= price_float <= 1000000:
                                        class_name = element.get_attribute('class') or ''
                                        # Prefer selling price class
                                        priority = 0 if 'css-1jczs19' in class_name else 1
                                        found_prices.append((priority, price_float, price_value))
                                except:
                                    pass
                    except:
                        continue
            except:
                continue
        
        if found_prices:
            # Sort by priority (selling price first) then by price
            found_prices.sort(key=lambda x: (x[0], -x[1]))
            return found_prices[0][2]
        
        # Strategy 2: Find all elements with ₹ symbol
        try:
            rupee_elements = driver.find_elements(By.XPATH, "//*[contains(text(), '₹')]")
            for elem in rupee_elements[:20]:
                try:
                    text = elem.text.strip()
                    if text and '₹' in text and len(text) < 100:
                        price_match = re.search(r'₹\s*([\d,]+(?:\.\d{1,2})?)', text)
                        if price_match:
                            price_value = price_match.group(1).replace(',', '')
                            try:
                                price_float = float(price_value)
                                if 50 <= price_float <= 1000000:
                                    return price_value
                            except:
                                pass
                except:
                    continue
        except:
            pass
        
        # Strategy 3: Search page source
        try:
            page_source = driver.page_source
            patterns = [
                r'₹\s*([\d,]+(?:\.\d{1,2})?)',
                r'<[^>]*class="[^"]*css-1jczs19[^"]*"[^>]*>.*?₹\s*([\d,]+(?:\.\d{1,2})?)',
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, page_source, re.IGNORECASE | re.DOTALL)
                if matches:
                    prices = [m.replace(',', '') for m in matches if m]
                    if prices:
                        try:
                            price_floats = [float(p) for p in prices]
                            valid_prices = [p for p in price_floats if 50 <= p <= 1000000]
                            if valid_prices:
                                valid_prices.sort()
                                return str(int(valid_prices[len(valid_prices)//2]))
                        except:
                            pass
        except:
            pass
        
        return None

