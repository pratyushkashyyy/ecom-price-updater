"""
Generic scraper for unknown sites
"""
from typing import Dict, Optional
from .base_scraper import BaseScraper
from .browser_adapter import BrowserAdapter


class GenericScraper(BaseScraper):
    """Generic scraper for any e-commerce site"""
    
    def get_site_name(self) -> str:
        return 'generic'
    
    def get_stock_indicators(self) -> Dict:
        return {
            'out_of_stock': [
                'out of stock',
                'sold out',
                'currently unavailable',
                'unavailable',
                'temporarily out of stock'
            ],
            'selectors': [
                '[class*="out-of-stock"]',
                '[class*="sold-out"]',
                '[class*="unavailable"]',
                '.sold-out',
                '.out-of-stock'
            ]
        }
    
    def get_price_selectors(self) -> list:
        return [
            '[itemprop="price"]',
            '.price',
            '.product-price',
            '.offer-price',
            '.sale-price',
            '[data-price]',
            '.current-price'
        ]
    
    async def extract_price(self, browser: BrowserAdapter) -> Optional[str]:
        """Extract price generically"""
        # Try generic selectors
        for selector in self.price_selectors:
            try:
                elements = await browser.query_selector_all(selector)
                for el in elements:
                    text = await browser.get_text(el)
                    cleaned = self.clean_price(text)
                    if cleaned != "N/A" and self.is_valid_price(cleaned):
                        return cleaned
            except:
                continue
        
        # Try meta tags
        try:
            meta = await browser.query_selector('meta[property="product:price:amount"]')
            if meta:
                price = await browser.get_attribute(meta, 'content')
                if price:
                    return price
            
            meta = await browser.query_selector('meta[property="og:price:amount"]')
            if meta:
                price = await browser.get_attribute(meta, 'content')
                if price:
                    return price
        except:
            pass
            
        return None
