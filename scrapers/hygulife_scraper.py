"""
Hygulife scraper (including bitli.in)
"""
import re
from typing import Dict, Optional
from .base_scraper import BaseScraper
from .browser_adapter import BrowserAdapter


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
    
    async def extract_price(self, browser: BrowserAdapter) -> Optional[str]:
        """Extract price from Hygulife with JSON cross-reference"""
        # First, try to get base price from page JSON data
        json_base_price = None
        try:
            page_content = await browser.get_page_content()
            json_price_match = re.search(
                r'\"price\"\s*:\s*[\"\'₹]?([\d,]+(?:\.\d+)?)',
                page_content, re.IGNORECASE
            )
            if json_price_match:
                try:
                    json_base_price = float(json_price_match.group(1).replace(',', ''))
                except:
                    pass
        except:
            pass
        
        # Try to find current price (displayed price, not MRP)
        hygulife_selectors = [
            '.price', '.product-price', '.sale-price',
            '.current-price', '[class*="price"]', 'span.price', 'div.price',
        ]
        
        found_prices = []
        for selector in hygulife_selectors:
            try:
                price_elements = await browser.query_selector_all(selector)
                for element in price_elements[:15]:
                    try:
                        price_text = await browser.get_text(element)
                        if price_text and '₹' in price_text:
                            # Skip discount/offer text
                            if any(word in price_text.lower() for word in ['save', 'off', 'discount', 'get it at', 'extra', 'upto']):
                                continue
                            
                            price_match = re.search(r'₹\s*([\d,]+(?:\.\d{1,2})?)', price_text)
                            if price_match:
                                price_str = price_match.group(1).replace(',', '')
                                try:
                                    price_val = float(price_str)
                                    if 50 <= price_val <= 100000:
                                        # Check for strikethrough (MRP/original price) — Playwright only
                                        is_strikethrough = False
                                        try:
                                            computed_style = await browser.evaluate(element, 'el => window.getComputedStyle(el).textDecoration')
                                            parent = await browser.evaluate_handle(element, 'el => el.parentElement')
                                            parent_style = ''
                                            if parent:
                                                parent_style = await browser.evaluate(parent, 'el => window.getComputedStyle(el).textDecoration') or ''
                                            
                                            if 'line-through' in str(computed_style) or 'line-through' in str(parent_style):
                                                is_strikethrough = True
                                        except:
                                            pass
                                        
                                        if not is_strikethrough:
                                            if json_base_price:
                                                if price_val <= json_base_price and (json_base_price - price_val) <= 100:
                                                    found_prices.append((
                                                        price_val, price_str, price_text,
                                                        abs(json_base_price - price_val)
                                                    ))
                                            else:
                                                found_prices.append((price_val, price_str, price_text, 0))
                                except:
                                    continue
                    except:
                        continue
            except:
                continue
        
        # Prefer the price closest to JSON base price
        if found_prices:
            if json_base_price:
                found_prices.sort(key=lambda x: (x[3], x[0]))
            else:
                found_prices.sort(key=lambda x: x[0])
            return found_prices[0][1]
        
        return None

    async def check_stock_status(self, browser: BrowserAdapter) -> Dict:
        """Check stock status with Hygulife JSON logic"""
        stock_status = {
            'in_stock': True,
            'stock_status': 'in_stock',
            'message': None
        }
        
        # 1. Check JSON data first (most reliable for Hygulife)
        try:
            page_content = await browser.get_page_content()
            stock_status_match = re.search(r'"stock_status"\s*:\s*(true|false)', page_content, re.IGNORECASE)
            inventory_stock_match = re.search(r'"inventory_is_in_stock"\s*:\s*(true|false)', page_content, re.IGNORECASE)
            
            if stock_status_match:
                is_stock = stock_status_match.group(1).lower() == 'true'
                if not is_stock:
                    stock_status['in_stock'] = False
                    stock_status['stock_status'] = 'out_of_stock'
                    stock_status['message'] = 'Product is out of stock (from JSON stock_status)'
                    return stock_status
            
            if inventory_stock_match:
                is_inventory_stock = inventory_stock_match.group(1).lower() == 'true'
                if not is_inventory_stock:
                    stock_status['in_stock'] = False
                    stock_status['stock_status'] = 'out_of_stock'
                    stock_status['message'] = 'Product is out of stock (from JSON inventory_is_in_stock)'
                    return stock_status
            
            if stock_status_match or inventory_stock_match:
                return stock_status
        except Exception:
            pass
        
        # 2. Check specific selectors (not page-wide text)
        for selector in self.stock_indicators['selectors']:
            try:
                element = await browser.query_selector(selector)
                if element:
                    text = await browser.get_text(element)
                    if any(oos_text in text.lower() for oos_text in self.stock_indicators['out_of_stock']):
                        stock_status['in_stock'] = False
                        stock_status['stock_status'] = 'out_of_stock'
                        stock_status['message'] = f'Product is out of stock (selector: {selector})'
                        return stock_status
            except Exception:
                continue
                
        return stock_status
