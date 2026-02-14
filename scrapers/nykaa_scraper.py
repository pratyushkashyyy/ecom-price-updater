"""
Nykaa scraper
"""
import re
from typing import Dict, Optional
from .base_scraper import BaseScraper
from .browser_adapter import BrowserAdapter


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
            '.css-1jczs19',
            '.css-1d0jf8e',
            '[class*="css-1jczs19"]',
            '[class*="price"]',
            '.price',
            'span:has-text("₹")',
            '[data-testid*="price"]',
        ]
    
    async def extract_price(self, browser: BrowserAdapter) -> Optional[str]:
        """Extract price from Nykaa with multi-strategy approach"""
        
        # Strategy 1: Try specific selectors
        selectors = [
            '.css-1jczs19',
            '[class*="css-1jczs19"]',
            '.css-1d0jf8e',
            '[class*="price"]',
            '.price',
        ]
        
        for selector in selectors:
            try:
                el = await browser.query_selector(selector)
                if el:
                    price_text = await browser.get_text(el)
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
        
        # Strategy 2: Find all elements with ₹ symbol
        try:
            elements_with_rupee = await browser.query_selector_all_xpath('//*[contains(text(), "₹")]')
            found_prices = []
            
            for element in elements_with_rupee[:20]:
                try:
                    text = await browser.get_text(element)
                    if text and '₹' in text and len(text) < 100:
                        cleaned_price = self.clean_price(text)
                        if cleaned_price != "N/A" and self.is_valid_price(cleaned_price):
                            try:
                                price_float = float(cleaned_price.replace(',', ''))
                                if 50 <= price_float <= 1000000:
                                    # Check parent class to prefer selling price
                                    parent = await browser.evaluate_handle(element, 'el => el.parentElement')
                                    parent_class = ''
                                    if parent:
                                        parent_class = await browser.get_attribute(parent, 'class') or ''
                                    
                                    priority = 0 if 'css-1jczs19' in parent_class else 1
                                    found_prices.append((priority, price_float, cleaned_price))
                            except:
                                continue
                except:
                    continue
            
            if found_prices:
                found_prices.sort(key=lambda x: (x[0], -x[1]))
                return found_prices[0][2]
        except:
            pass
        
        # Strategy 3: Search page content for price patterns
        try:
            page_content = await browser.get_page_content()
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
                                valid_prices.sort()
                                return str(int(valid_prices[len(valid_prices)//2]))
                        except:
                            pass
        except:
            pass
        
        return None
