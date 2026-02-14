"""
Ajio scraper
"""
from typing import Dict, Optional
from .base_scraper import BaseScraper
from .browser_adapter import BrowserAdapter


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
    
    async def extract_price(self, browser: BrowserAdapter) -> Optional[str]:
        """Extract price from Ajio"""
        selectors = ['.prod-sp', '.prod-base-price', '[data-id="price"]', '.price']
        
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
