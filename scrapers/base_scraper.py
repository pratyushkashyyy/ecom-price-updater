from typing import Dict, Optional, List, Tuple
import re
import json
import os
from abc import ABC, abstractmethod
from .browser_adapter import BrowserAdapter, BrowserElement


class BaseScraper(ABC):
    """Base class for all e-commerce scrapers"""
    
    def __init__(self, selectors: Dict = None):
        if selectors:
            self.selectors_data = {}
            self.site_selectors = selectors
        else:
            self.selectors_data = self.load_selectors()
            self.site_selectors = self.selectors_data.get(self.get_site_name(), {})
            
        self.price_selectors = self.get_price_selectors()
        self.stock_indicators = self.get_stock_indicators()
        
    @property
    def site_name(self) -> str:
        """Property to access site name"""
        return self.get_site_name()

    def load_selectors(self) -> Dict:
        """Load selectors from JSON file"""
        try:
            file_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'selectors.json')
            if not os.path.exists(file_path):
                file_path = 'selectors.json'
                
            if os.path.exists(file_path):
                with open(file_path, 'r') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            print(f"Error loading selectors: {e}")
            return {}

    @abstractmethod
    def get_site_name(self) -> str:
        """Return the site name key used in selectors.json"""
        pass
        
    def get_price_selectors(self) -> List[str]:
        """Return list of price selectors for this site"""
        return self.site_selectors.get('price_selectors', [])
        
    def get_stock_indicators(self) -> Dict:
        """Return stock status indicators"""
        return self.site_selectors.get('out_of_stock', [])

    # ── Utility Methods ──

    def clean_price(self, price_str: str) -> str:
        """Clean price string to extract numeric value"""
        if not price_str:
            return "N/A"
        cleaned = re.sub(r'[^\d.,]', '', price_str)
        if cleaned.count('.') > 1:
            parts = cleaned.split('.')
            cleaned = "".join(parts[:-1]) + "." + parts[-1]
        return cleaned.strip()

    def is_valid_price(self, price_str: str) -> bool:
        """Check if cleaned price string is valid"""
        if not price_str or price_str == "N/A":
            return False
        try:
            float(price_str.replace(',', ''))
            return True
        except ValueError:
            return False

    def clean_image_url(self, url: str) -> str:
        """Clean image URL to get the highest resolution version."""
        if not url:
            return None
        try:
            if 'amazon' in url or 'media-amazon' in url:
                url = re.sub(r'\._[A-Z0-9]{2,}\d*[a-zA-Z0-9,_]*_', '', url)
                url = re.sub(r'\._AC_.*_', '', url)
            url = re.sub(r'\?width=\d+&?', '?', url)
            url = re.sub(r'\?height=\d+&?', '?', url)
            url = re.sub(r'\?w=\d+&?', '?', url)
            url = re.sub(r'\?h=\d+&?', '?', url)
            if url.endswith('?') or url.endswith('&'):
                url = url[:-1]
            return url.strip()
        except:
            return url

    # ── Unified Extraction Methods (use BrowserAdapter) ──

    async def extract_price(self, browser: BrowserAdapter) -> Optional[str]:
        """Extract price using unified browser adapter"""
        selectors = self.price_selectors
        for selector in selectors:
            try:
                el = await browser.query_selector(selector)
                if el:
                    text = await browser.get_text(el)
                    cleaned = self.clean_price(text)
                    if self.is_valid_price(cleaned):
                        return cleaned
            except:
                continue
        return None

    async def extract_product_details(self, browser: BrowserAdapter) -> Dict:
        """Extract product details (name, image, rating) using unified browser adapter"""
        details = {
            'name': None,
            'image_url': None,
            'rating': None,
            'review_count': None
        }
        
        # Name
        name_sels = self.site_selectors.get('name_selectors', [])
        for sel in name_sels:
            try:
                el = await browser.query_selector(sel)
                if el:
                    text = await browser.get_inner_text(el)
                    if text:
                        details['name'] = text
                        break
            except:
                continue

        # Image
        img_sels = self.site_selectors.get('image_selectors', [])
        for sel in img_sels:
            try:
                el = await browser.query_selector(sel)
                if el:
                    src = await browser.get_attribute(el, 'src')
                    if src:
                        details['image_url'] = self.clean_image_url(src)
                        break
            except:
                continue
                 
        return details

    async def check_stock_status(self, browser: BrowserAdapter) -> Dict:
        """Check if product is in stock using unified browser adapter"""
        status = {
            'in_stock': True,
            'stock_status': 'in_stock',
            'message': None
        }
        
        indicators = self.get_stock_indicators()
        try:
            content = await browser.get_page_content()
            content_lower = content.lower()
            
            phrases = indicators if isinstance(indicators, list) else indicators.get('out_of_stock', [])
            
            for phrase in phrases:
                if phrase.lower() in content_lower:
                    status['in_stock'] = False
                    status['stock_status'] = 'out_of_stock'
                    status['message'] = f"Found out-of-stock phrase: {phrase}"
                    return status
        except:
            pass
            
        return status

    # ── Backward-Compat Wrappers (old _playwright/_selenium methods) ──
    # These create a BrowserAdapter internally so old call sites still work.

    async def extract_price_playwright(self, page) -> Optional[str]:
        """Backward-compat: wraps extract_price() with Playwright adapter"""
        browser = BrowserAdapter(page, 'playwright')
        return await self.extract_price(browser)

    def extract_price_selenium(self, driver) -> Optional[str]:
        """Backward-compat: wraps extract_price() with Selenium adapter"""
        import asyncio
        browser = BrowserAdapter(driver, 'selenium')
        return asyncio.get_event_loop().run_until_complete(self.extract_price(browser))

    async def extract_product_details_playwright(self, page) -> Dict:
        """Backward-compat: wraps extract_product_details() with Playwright adapter"""
        browser = BrowserAdapter(page, 'playwright')
        return await self.extract_product_details(browser)

    def extract_product_details_selenium(self, driver) -> Dict:
        """Backward-compat: wraps extract_product_details() with Selenium adapter"""
        import asyncio
        browser = BrowserAdapter(driver, 'selenium')
        return asyncio.get_event_loop().run_until_complete(self.extract_product_details(browser))

    async def check_stock_status_playwright(self, page) -> Dict:
        """Backward-compat: wraps check_stock_status() with Playwright adapter"""
        browser = BrowserAdapter(page, 'playwright')
        return await self.check_stock_status(browser)

    def check_stock_status_selenium(self, driver) -> Dict:
        """Backward-compat: wraps check_stock_status() with Selenium adapter"""
        import asyncio
        browser = BrowserAdapter(driver, 'selenium')
        return asyncio.get_event_loop().run_until_complete(self.check_stock_status(browser))
