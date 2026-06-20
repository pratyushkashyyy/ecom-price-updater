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

    def get_original_price_selectors(self) -> List[str]:
        """Return list of original/list price selectors for this site"""
        configured = self.site_selectors.get('original_price_selectors', [])
        generic = [
            'del',
            's',
            'strike',
            '[style*="line-through"]',
            '[class*="mrp"]',
            '[class*="MRP"]',
            '[class*="original"]',
            '[class*="Original"]',
            '[class*="regular"]',
            '[class*="Regular"]',
            '[class*="list-price"]',
            '[class*="ListPrice"]',
            '[class*="base-price"]',
            '[class*="BasePrice"]',
        ]
        return configured + [selector for selector in generic if selector not in configured]
        
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
        return cleaned.strip().strip(',.')

    def is_valid_price(self, price_str: str) -> bool:
        """Check if cleaned price string is valid"""
        if not price_str or price_str == "N/A":
            return False
        try:
            float(price_str.replace(',', ''))
            return True
        except ValueError:
            return False

    def price_to_float(self, price_str: str) -> Optional[float]:
        """Convert a cleaned price string to float if possible."""
        if not self.is_valid_price(price_str):
            return None
        try:
            return float(price_str.replace(',', ''))
        except (TypeError, ValueError):
            return None

    def extract_price_candidates_from_text(self, text: str) -> List[str]:
        """Extract individual price-like values from text."""
        if not text:
            return []

        candidates = []
        patterns = [
            r'(?:₹|Rs\.?|INR)\s*([\d,]+(?:\.\d{1,2})?)',
            r'([\d,]+(?:\.\d{1,2})?)\s*(?:₹|Rs\.?|INR)',
        ]

        for pattern in patterns:
            for match in re.findall(pattern, text, flags=re.IGNORECASE):
                cleaned = self.clean_price(match)
                if self.is_valid_price(cleaned):
                    candidates.append(cleaned)

        if not candidates:
            cleaned = self.clean_price(text)
            if self.is_valid_price(cleaned):
                candidates.append(cleaned)

        return candidates

    def pick_original_price(self, candidates: List[str], current_price: Optional[str] = None) -> Optional[str]:
        """Choose the most likely original/list price from candidate values."""
        current_value = self.price_to_float(current_price) if current_price else None
        unique = []
        seen = set()

        for candidate in candidates:
            value = self.price_to_float(candidate)
            if value is None:
                continue
            key = round(value, 2)
            if key in seen:
                continue
            seen.add(key)
            unique.append((value, candidate))

        if not unique:
            return None

        if current_value is not None:
            higher = [(value, candidate) for value, candidate in unique if value > current_value]
            if higher:
                higher.sort(key=lambda item: item[0])
                return higher[0][1]
            return None

        unique.sort(key=lambda item: item[0], reverse=True)
        return unique[0][1]

    def extract_original_price_candidates_from_content(self, content: str) -> List[str]:
        """Extract original/list price candidates from full page HTML/JSON text."""
        if not content:
            return []

        candidates = []
        label = (
            r'MRP|M\.R\.P\.?|List Price|Original Price|Regular Price|'
            r'Maximum Retail Price|Retail Price|Was|Compare(?: At)? Price'
        )
        patterns = [
            rf'(?:{label})[^₹\d]{{0,120}}(?:₹|Rs\.?|INR)?\s*([\d,]+(?:\.\d{{1,2}})?)',
            rf'(?:₹|Rs\.?|INR)\s*([\d,]+(?:\.\d{{1,2}})?)[^<]{{0,120}}(?:{label})',
            (
                r'"(?:mrp|MRP|maximumRetailPrice|retailPrice|originalPrice|'
                r'strikeOffPrice|listPrice|regularPrice|compareAtPrice)"\s*:\s*"?'
                r'(?:₹|Rs\.?|INR)?\s*([\d,]+(?:\.\d{1,2})?)'
            ),
            (
                r"'(?:mrp|MRP|maximumRetailPrice|retailPrice|originalPrice|"
                r"strikeOffPrice|listPrice|regularPrice|compareAtPrice)'\s*:\s*'?"
                r"(?:₹|Rs\.?|INR)?\s*([\d,]+(?:\.\d{1,2})?)"
            ),
        ]

        for pattern in patterns:
            for match in re.findall(pattern, content, flags=re.IGNORECASE):
                cleaned = self.clean_price(match)
                if self.is_valid_price(cleaned):
                    candidates.append(cleaned)

        return candidates

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

    async def extract_original_price(
        self,
        browser: BrowserAdapter,
        current_price: Optional[str] = None
    ) -> Optional[str]:
        """Extract original/list price using selector hints and generic fallbacks."""
        candidates = []
        for selector in self.get_original_price_selectors():
            try:
                elements = await browser.query_selector_all(selector)
                for element in elements[:10]:
                    text = await browser.get_text(element)
                    candidates.extend(self.extract_price_candidates_from_text(text))
                    for attr in ('aria-label', 'title', 'data-price', 'content'):
                        attr_value = await browser.get_attribute(element, attr)
                        candidates.extend(self.extract_price_candidates_from_text(attr_value))
            except:
                continue

        try:
            content = await browser.get_page_content()
            candidates.extend(self.extract_original_price_candidates_from_content(content))
        except:
            pass

        return self.pick_original_price(candidates, current_price)

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
