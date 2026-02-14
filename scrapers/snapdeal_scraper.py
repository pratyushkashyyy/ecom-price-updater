"""
Snapdeal scraper
"""
from typing import Dict, Optional
from .base_scraper import BaseScraper
from .browser_adapter import BrowserAdapter


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
    
    async def extract_price(self, browser: BrowserAdapter) -> Optional[str]:
        """Extract price from Snapdeal"""
        selectors = ['.payBlkBig', '.pdp-final-price', '.pdp-selling-price']
        
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
        
        return None
