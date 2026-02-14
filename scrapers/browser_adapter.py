"""
BrowserAdapter — Unified async interface for Playwright and Selenium.

Wraps both backends behind a single API so scrapers only need
one set of extraction methods instead of duplicate _playwright/_selenium versions.

Usage:
    # Playwright
    browser = BrowserAdapter(page, 'playwright')
    
    # Selenium
    browser = BrowserAdapter(driver, 'selenium')
    
    # Then in scraper:
    el = await browser.query_selector('.price')
    text = await browser.get_text(el)
"""
from typing import Optional, List, Any


class BrowserElement:
    """Wrapper around a Playwright ElementHandle or Selenium WebElement"""
    
    def __init__(self, element, backend_type: str):
        self._element = element
        self._backend = backend_type
    
    @property
    def raw(self):
        """Access the underlying Playwright/Selenium element"""
        return self._element


class BrowserAdapter:
    """
    Unified async interface for both Playwright Page and Selenium WebDriver.
    
    All methods are async. For Selenium (which is synchronous), the calls
    simply return values directly — Python's async/await handles this fine.
    """
    
    def __init__(self, backend, backend_type: str):
        """
        Args:
            backend: Playwright Page or Selenium WebDriver instance
            backend_type: 'playwright' or 'selenium'
        """
        self._backend = backend
        self._type = backend_type
    
    @property
    def backend_type(self) -> str:
        return self._type
    
    @property
    def raw(self):
        """Access the underlying Page or WebDriver"""
        return self._backend
    
    # ── Element Queries ──
    
    async def query_selector(self, selector: str) -> Optional[BrowserElement]:
        """Find first element matching CSS selector, or None"""
        try:
            if self._type == 'playwright':
                el = await self._backend.query_selector(selector)
                return BrowserElement(el, self._type) if el else None
            else:
                from selenium.webdriver.common.by import By
                el = self._backend.find_element(By.CSS_SELECTOR, selector)
                return BrowserElement(el, self._type) if el else None
        except Exception:
            return None
    
    async def query_selector_all(self, selector: str) -> List[BrowserElement]:
        """Find all elements matching CSS selector"""
        try:
            if self._type == 'playwright':
                elements = await self._backend.query_selector_all(selector)
                return [BrowserElement(el, self._type) for el in elements]
            else:
                from selenium.webdriver.common.by import By
                elements = self._backend.find_elements(By.CSS_SELECTOR, selector)
                return [BrowserElement(el, self._type) for el in elements]
        except Exception:
            return []
    
    async def query_selector_xpath(self, xpath: str) -> Optional[BrowserElement]:
        """Find first element matching XPath"""
        try:
            if self._type == 'playwright':
                el = await self._backend.query_selector(f'xpath={xpath}')
                return BrowserElement(el, self._type) if el else None
            else:
                from selenium.webdriver.common.by import By
                el = self._backend.find_element(By.XPATH, xpath)
                return BrowserElement(el, self._type) if el else None
        except Exception:
            return None

    async def query_selector_all_xpath(self, xpath: str) -> List[BrowserElement]:
        """Find all elements matching XPath"""
        try:
            if self._type == 'playwright':
                elements = await self._backend.query_selector_all(f'xpath={xpath}')
                return [BrowserElement(el, self._type) for el in elements]
            else:
                from selenium.webdriver.common.by import By
                elements = self._backend.find_elements(By.XPATH, xpath)
                return [BrowserElement(el, self._type) for el in elements]
        except Exception:
            return []
    
    # ── Element Data Extraction ──
    
    async def get_text(self, element: BrowserElement) -> str:
        """Get visible text content of an element"""
        try:
            if self._type == 'playwright':
                text = await element.raw.text_content()
                return (text or '').strip()
            else:
                return (element.raw.text or '').strip()
        except Exception:
            return ''
    
    async def get_inner_text(self, element: BrowserElement) -> str:
        """Get inner text (rendered) of an element"""
        try:
            if self._type == 'playwright':
                text = await element.raw.inner_text()
                return (text or '').strip()
            else:
                return (element.raw.text or '').strip()
        except Exception:
            return ''
    
    async def get_attribute(self, element: BrowserElement, attr: str) -> Optional[str]:
        """Get an attribute value from an element"""
        try:
            if self._type == 'playwright':
                return await element.raw.get_attribute(attr)
            else:
                return element.raw.get_attribute(attr)
        except Exception:
            return None
    
    # ── Page-level Operations ──
    
    async def get_page_content(self) -> str:
        """Get full page HTML content"""
        try:
            if self._type == 'playwright':
                return await self._backend.content()
            else:
                return self._backend.page_source
        except Exception:
            return ''
    
    async def get_title(self) -> str:
        """Get page title"""
        try:
            if self._type == 'playwright':
                return await self._backend.title()
            else:
                return self._backend.title
        except Exception:
            return ''
    
    async def get_url(self) -> str:
        """Get current page URL"""
        try:
            if self._type == 'playwright':
                return self._backend.url
            else:
                return self._backend.current_url
        except Exception:
            return ''
    
    # ── Advanced Operations ──
    
    async def evaluate(self, element: BrowserElement, js_expression: str) -> Any:
        """Execute JavaScript on an element. Playwright-only feature; returns None for Selenium."""
        try:
            if self._type == 'playwright':
                return await element.raw.evaluate(js_expression)
            else:
                # Selenium doesn't support per-element JS evaluation easily
                return None
        except Exception:
            return None
    
    async def evaluate_handle(self, element: BrowserElement, js_expression: str) -> Optional[BrowserElement]:
        """Execute JS and return element handle. Playwright-only; returns None for Selenium."""
        try:
            if self._type == 'playwright':
                handle = await element.raw.evaluate_handle(js_expression)
                el = handle.as_element()
                return BrowserElement(el, self._type) if el else None
            else:
                return None
        except Exception:
            return None
    
    async def is_visible(self, element: BrowserElement) -> bool:
        """Check if element is visible"""
        try:
            if self._type == 'playwright':
                return await element.raw.is_visible()
            else:
                return element.raw.is_displayed()
        except Exception:
            return False
    
    async def click(self, element: BrowserElement):
        """Click an element"""
        try:
            if self._type == 'playwright':
                await element.raw.click()
            else:
                element.raw.click()
        except Exception:
            pass
