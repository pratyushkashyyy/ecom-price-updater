"""
Meesho scraper
"""
from typing import Dict, Optional
from .base_scraper import BaseScraper
from .browser_adapter import BrowserAdapter


class MeeshoScraper(BaseScraper):
    """Scraper for Meesho.com"""
    
    def get_site_name(self) -> str:
        return 'meesho'
    
    def get_stock_indicators(self) -> Dict:
        return {
            'out_of_stock': [
                'out of stock',
                'sold out',
                'currently unavailable'
            ],
            'selectors': [
                '[class*="out-of-stock"]',
                '[class*="sold-out"]',
                '.sold-out'
            ]
        }
    
    def get_price_selectors(self) -> list:
        return [
            '[class*="Price__CurrentPrice"]',
            '.pdp-price',
            '[class*="pdp-price"]',
            'span[class*="price"]',
            'div[class*="price"]',
            '[data-price]',
            'h4',
        ]
    
    async def extract_price(self, browser: BrowserAdapter) -> Optional[str]:
        """Extract price from Meesho with robust fallback"""
        
        # 1. Try specific selectors
        selectors = [
            '[class*="Price__CurrentPrice"]', 
            '.pdp-price', 
            '[data-price]', 
            'h4'
        ]
        
        for selector in selectors:
            try:
                elements = await browser.query_selector_all(selector)
                for el in elements:
                    text = await browser.get_text(el)
                    if '₹' in text:
                        cleaned = self.clean_price(text)
                        if cleaned != "N/A" and self.is_valid_price(cleaned):
                            return cleaned
            except:
                continue
                
        # 2. Text-based fallback (scan common elements for ₹)
        try:
            candidates = await browser.query_selector_all('h4, h5, h3, span, div')
            for candidate in candidates[:50]:
                text = await browser.get_text(candidate)
                if '₹' in text and len(text) < 20:
                    cleaned = self.clean_price(text)
                    if cleaned != "N/A" and self.is_valid_price(cleaned):
                        return cleaned
        except:
            pass
        
        return None
