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
            
        import asyncio
        await asyncio.sleep(2) 

        # DEAD LINK PROTECTION: Stop immediately if Snapdeal shows a 404/Not Found page
        try:
            page_content = await browser.get_page_content()
            content_lower = page_content.lower()
            if "page not found" in content_lower or "404" in content_lower or "we couldn't find the page" in content_lower:
                 print("  ⚠️ SNAPDEAL 404 DETECTED - Dead Link!")
                 return None
        except:
            pass

        # Strategy 1: Dynamic selectors from selectors.json
        selectors = self.price_selectors
        for selector in selectors:
            try:
                el = await browser.query_selector(selector)
                if el:
                    price_text = await browser.get_text(el)
                    cleaned_price = self.clean_price(price_text)
                    if cleaned_price != "N/A" and self.is_valid_price(cleaned_price):
                        try:
                            if float(cleaned_price.replace(',', '')) >= 50:
                                return cleaned_price
                        except:
                            pass
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