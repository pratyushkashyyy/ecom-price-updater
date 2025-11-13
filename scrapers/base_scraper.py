"""
Base scraper class for e-commerce websites
All individual scrapers should inherit from this class
"""
import re
from typing import Dict, Optional
from abc import ABC, abstractmethod
from playwright.async_api import Page
from selenium.webdriver.remote.webdriver import WebDriver


class BaseScraper(ABC):
    """Base class for all e-commerce scrapers"""
    
    def __init__(self):
        self.site_name = self.get_site_name()
        self.stock_indicators = self.get_stock_indicators()
        self.price_selectors = self.get_price_selectors()
    
    @abstractmethod
    def get_site_name(self) -> str:
        """Return the site name identifier (e.g., 'amazon', 'flipkart')"""
        pass
    
    @abstractmethod
    def get_stock_indicators(self) -> Dict:
        """Return stock status indicators for this site"""
        pass
    
    @abstractmethod
    def get_price_selectors(self) -> list:
        """Return list of CSS selectors for finding prices"""
        pass
    
    def clean_price(self, text: str) -> str:
        """Extract price from text, removing currency symbols and formatting"""
        if not text:
            return "N/A"
        
        # Remove common currency symbols and extract number
        price_match = re.search(r'[₹$€£¥]?\s*([\d,]+(?:\.\d{1,2})?)', str(text))
        if price_match:
            return price_match.group(1).replace(',', '')
        return "N/A"
    
    def is_valid_price(self, price_str: str) -> bool:
        """Check if price string is valid"""
        if not price_str or price_str == "N/A":
            return False
        try:
            price = float(price_str.replace(',', ''))
            return price > 0
        except (ValueError, TypeError):
            return False
    
    @abstractmethod
    async def extract_price_playwright(self, page: Page) -> Optional[str]:
        """Extract price using Playwright (async)"""
        pass
    
    @abstractmethod
    def extract_price_selenium(self, driver: WebDriver) -> Optional[str]:
        """Extract price using Selenium"""
        pass
    
    async def check_stock_status_playwright(self, page: Page) -> Dict:
        """Check stock status using Playwright"""
        try:
            page_content = await page.content()
            page_title = await page.title()
            return self.check_stock_status(page_content, page_title, page=page)
        except Exception as e:
            return {
                'in_stock': True,
                'stock_status': 'unknown',
                'message': f'Error checking stock: {str(e)}'
            }
    
    def check_stock_status_selenium(self, driver: WebDriver) -> Dict:
        """Check stock status using Selenium"""
        try:
            page_content = driver.page_source
            page_title = driver.title
            return self.check_stock_status(page_content, page_title, driver=driver)
        except Exception as e:
            return {
                'in_stock': True,
                'stock_status': 'unknown',
                'message': f'Error checking stock: {str(e)}'
            }
    
    def check_stock_status(self, page_content: str, page_title: str, 
                          driver: Optional[WebDriver] = None, 
                          page: Optional[Page] = None) -> Dict:
        """Check if product is in stock or out of stock"""
        stock_status = {
            'in_stock': True,
            'stock_status': 'in_stock',
            'message': None
        }
        
        indicators = self.stock_indicators
        out_of_stock_texts = indicators.get('out_of_stock', [])
        selectors = indicators.get('selectors', [])
        
        # Check page content and title for out-of-stock indicators
        content_lower = (page_content + ' ' + page_title).lower()
        
        for oos_text in out_of_stock_texts:
            if oos_text.lower() in content_lower:
                stock_status['in_stock'] = False
                stock_status['stock_status'] = 'out_of_stock'
                stock_status['message'] = f'Found out-of-stock indicator: {oos_text}'
                return stock_status
        
        # Check selectors if driver/page is available
        if driver:
            from selenium.webdriver.common.by import By
            for selector in selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        for elem in elements:
                            text = elem.text.lower()
                            if any(oos_text.lower() in text for oos_text in out_of_stock_texts):
                                stock_status['in_stock'] = False
                                stock_status['stock_status'] = 'out_of_stock'
                                stock_status['message'] = f'Found out-of-stock element with selector: {selector}'
                                return stock_status
                except:
                    continue
        elif page:
            # For Playwright, we'd need async methods - this is a simplified version
            # The actual implementation should use async methods
            pass
        
        return stock_status

