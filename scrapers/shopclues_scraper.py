"""
Shopclues scraper
"""
from typing import Dict, Optional
from .base_scraper import BaseScraper
from .browser_adapter import BrowserAdapter


class ShopcluesScraper(BaseScraper):
    """Scraper for Shopclues.com"""
    
    def get_site_name(self) -> str:
        return 'shopclues'
    
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
        selectors = list(self.site_selectors.get('price_selectors', []))
        for selector in [
            '.f_price',
            '.price',
            '[class*="price"]'
        ]:
            if selector not in selectors:
                selectors.append(selector)
        return selectors
    
    async def extract_price(self, browser: BrowserAdapter) -> Optional[str]:
        """Extract price from Shopclues"""
        selectors = self.price_selectors
        
        for selector in selectors:
            try:
                elements = await browser.query_selector_all(selector)
                candidates = []
                for element in elements[:5]:
                    price_text = await browser.get_text(element)
                    candidates.extend(self.extract_price_candidates_from_text(price_text))

                    for attr in ('aria-label', 'title', 'data-price', 'content'):
                        attr_value = await browser.get_attribute(element, attr)
                        candidates.extend(self.extract_price_candidates_from_text(attr_value))

                price = self._pick_current_price(candidates)
                if price:
                    return price
            except:
                continue
        
        return None

    def _pick_current_price(self, candidates: list) -> Optional[str]:
        """Choose the likely selling price from selector-level Shopclues candidates."""
        valid = []
        seen = set()
        for candidate in candidates:
            value = self.price_to_float(candidate)
            if value is None or value < 50:
                continue
            key = round(value, 2)
            if key in seen:
                continue
            seen.add(key)
            valid.append((value, candidate))

        if not valid:
            return None

        valid.sort(key=lambda item: item[0])
        return valid[0][1]

    async def extract_original_price(
        self,
        browser: BrowserAdapter,
        current_price: Optional[str] = None
    ) -> Optional[str]:
        """Extract Shopclues MRP from explicit old/MRP selectors only."""
        for selector in self.get_original_price_selectors():
            candidates = []
            try:
                elements = await browser.query_selector_all(selector)
                for element in elements[:10]:
                    text = await browser.get_text(element)
                    candidates.extend(self.extract_price_candidates_from_text(text))

                    for attr in ('aria-label', 'title', 'data-price', 'content'):
                        attr_value = await browser.get_attribute(element, attr)
                        candidates.extend(self.extract_price_candidates_from_text(attr_value))
            except Exception:
                continue

            original_price = self.pick_original_price(candidates, current_price)
            if original_price:
                return original_price

        return None
