"""
Snapdeal scraper
"""
import asyncio
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
                '.sold-out',
                '.sold-out-err'
            ]
        }
    
    # DELETED get_price_selectors to force reading from selectors.json
    
    async def extract_price(self, browser: BrowserAdapter) -> Optional[str]:
        """Extract price from Snapdeal"""
        
        # SMART WAIT: Wait dynamically for Snapdeal's price class
        try:
            if browser.engine == 'playwright':
                # Wait up to 4 seconds for the price, but don't crash if it's missing
                await browser.page.wait_for_selector('.payBlkBig, [itemprop="price"]', timeout=4000)
        except:
            pass
            
        await asyncio.sleep(2) 

        # DEAD LINK PROTECTION: Stop immediately if Snapdeal shows a 404/Not Found page
        try:
            page_content = await browser.get_page_content()
            content_lower = page_content.lower()
            if (
                "page not found" in content_lower or
                "we couldn't find the page" in content_lower or
                "<title>404" in content_lower or
                "snapdeal.com/404" in content_lower
            ):
                 print("  ⚠️ SNAPDEAL 404 DETECTED - Dead Link!")
                 return None
        except:
            pass

        # Strategy 1: Dynamic selectors from selectors.json
        selectors = self.price_selectors
        for selector in selectors:
            try:
                elements = await browser.query_selector_all(selector)
                candidates = []
                for element in elements[:5]:
                    price_text = await browser.get_text(element)
                    candidates.extend(self.extract_price_candidates_from_text(price_text))

                    for attr in ('value', 'aria-label', 'title', 'data-price', 'content'):
                        attr_value = await browser.get_attribute(element, attr)
                        candidates.extend(self.extract_price_candidates_from_text(attr_value))

                price = self._pick_current_price(candidates)
                if price:
                    return price
            except:
                continue
                
        # Strategy 2: Hard Fallback (Scan specific itemprop elements)
        try:
            candidates = await browser.query_selector_all('[itemprop="price"]')
            for candidate in candidates:
                text = await browser.get_attribute(candidate, 'value') or await browser.get_text(candidate)
                if text:
                    cleaned = self.clean_price(text)
                    if cleaned != "N/A" and self.is_valid_price(cleaned):
                        return cleaned
        except:
            pass
        
        return None

    def _pick_current_price(self, candidates: list) -> Optional[str]:
        """Choose the likely selling price from selector-level Snapdeal candidates."""
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
        """Extract Snapdeal MRP from explicit cut-price/MRP selectors only."""
        for selector in self.get_original_price_selectors():
            candidates = []
            try:
                elements = await browser.query_selector_all(selector)
                for element in elements[:10]:
                    text = await browser.get_text(element)
                    candidates.extend(self.extract_price_candidates_from_text(text))

                    for attr in ('value', 'aria-label', 'title', 'data-price', 'content'):
                        attr_value = await browser.get_attribute(element, attr)
                        candidates.extend(self.extract_price_candidates_from_text(attr_value))
            except Exception:
                continue

            original_price = self.pick_original_price(candidates, current_price)
            if original_price:
                return original_price

        return None
