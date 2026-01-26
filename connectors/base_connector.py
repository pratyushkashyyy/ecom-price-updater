"""
Base Connector Class
Defines the interface that all e-commerce connectors must implement.
"""

import re
from abc import ABC, abstractmethod
from typing import List, Optional


class BaseConnector(ABC):
    """Abstract base class for e-commerce site connectors"""
    
    @property
    @abstractmethod
    def site_name(self) -> str:
        """Return the name of the e-commerce site (lowercase)"""
        pass
    
    @property
    @abstractmethod
    def domain_patterns(self) -> List[str]:
        """Return list of domain patterns to identify this site"""
        pass
    
    @property
    def price_selectors(self) -> List[str]:
        """Return list of CSS selectors for price elements from config"""
        import json
        import os
        
        try:
            # Look for selectors.json in the project root (parent of connectors dir)
            # Current file is in connectors/base_connector.py
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            config_path = os.path.join(base_dir, 'selectors.json')
            
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    site_config = data.get(self.site_name, {})
                    # Handle both list (legacy) and dict (new) structure
                    if isinstance(site_config, list):
                        return site_config
                    elif isinstance(site_config, dict):
                        return site_config.get('price_selectors', [])
        except Exception as e:
            print(f"Error loading selectors for {self.site_name}: {e}")
            
        return []

    @property
    def container_selectors(self) -> List[str]:
        """Return list of main product container selectors from config"""
        import json
        import os
        
        try:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            config_path = os.path.join(base_dir, 'selectors.json')
            
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    site_config = data.get(self.site_name, {})
                    if isinstance(site_config, dict):
                        return site_config.get('container_selectors', [])
        except Exception:
            pass
            
        return []

    @property
    def out_of_stock_keywords(self) -> List[str]:
        """Return list of out-of-stock keywords from config"""
        import json
        import os
        
        try:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            config_path = os.path.join(base_dir, 'selectors.json')
            
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    site_config = data.get(self.site_name, {})
                    if isinstance(site_config, dict):
                        return site_config.get('out_of_stock', [])
        except Exception:
            pass
            
        return []
    
    @property
    def is_blocked_site(self) -> bool:
        """Return True if this site blocks Playwright and requires Selenium"""
        return False
    
    @property
    def use_selenium_module(self) -> bool:
        """Return True if this site has a dedicated Selenium module to use"""
        return False
    
    @property
    def selenium_module_name(self) -> Optional[str]:
        """Return the name of the Selenium module if use_selenium_module is True"""
        return None
    
    def clean_price(self, price_text: str) -> str:
        """
        Clean and extract price from text.
        Can be overridden by subclasses for site-specific cleaning.
        """
        if not price_text:
            return "N/A"
        
        # First, try to find any currency symbol followed by digits
        price_patterns = [
            r'[₹$€£¥]\s*([\d,]+(?:\.\d{2})?)',  # Currency symbol with digits (₹ 1,23,456.78)
            r'([\d,]+(?:\.\d{2})?)\s*[₹$€£¥]',  # Digits with currency symbol (1,23,456.78₹)
            r'([\d,]+(?:\.\d{2})?)',  # Just digits with commas and optional decimals
        ]
        
        for pattern in price_patterns:
            match = re.search(pattern, price_text)
            if match:
                price = match.group(1) if match.groups() else match.group(0)
                # Remove all commas to check if it's a valid number
                price_without_comma = price.replace(',', '')
                # Validate that it's a reasonable price
                try:
                    price_value = float(price_without_comma)
                    if price_value >= 1:  # Minimum price is 1
                        # Additional validation to ensure it's a reasonable price
                        if self.is_valid_price(price):
                            return price
                except ValueError:
                    continue
        
        # Fallback: remove non-digit characters except commas and dots
        price_clean = re.sub(r'[^\d.,₹$€£¥]', '', price_text)
        
        # If no digits found, return original text
        if not re.search(r'\d', price_clean):
            return "N/A"
        
        return price_clean.strip()
    
    def is_valid_price(self, price: str) -> bool:
        """
        Check if the extracted price is valid and reasonable.
        Can be overridden by subclasses for site-specific validation.
        """
        if not price or price == "N/A":
            return False
        
        # Remove commas and check numeric value
        price_without_comma = price.replace(',', '').strip()
        
        try:
            price_value = float(price_without_comma)
            # Price should be between 1 and 1 billion (to exclude product IDs)
            # Product IDs are usually very long numbers
            if 1 <= price_value <= 1000000000:
                # If the number is too long without commas, it's likely not a price
                if len(price_without_comma) > 12 and ',' not in price:
                    return False
                return True
        except ValueError:
            return False
        
        return False
    
    @abstractmethod
    async def extract_price_playwright(self, page, url: str) -> Optional[str]:
        """
        Extract price using Playwright.
        
        Args:
            page: Playwright page object
            url: Product URL
            
        Returns:
            Price as string or None if not found
        """
        pass
    
    @abstractmethod
    def extract_price_selenium(self, driver, url: str) -> Optional[str]:
        """
        Extract price using Selenium.
        
        Args:
            driver: Selenium WebDriver instance
            url: Product URL
            
        Returns:
            Price as string or None if not found
        """
        pass
    
    def matches_domain(self, url: str) -> bool:
        """Check if URL matches this connector's domain patterns"""
        url_lower = url.lower()
        return any(pattern in url_lower for pattern in self.domain_patterns)
    
    def check_availability(self, page_content: str) -> dict:
        """Check if product is available or out of stock"""
        page_lower = page_content.lower()
        
        # Common out-of-stock patterns (Hardcoded defaults)
        out_of_stock_patterns = [
            r'out\s*of\s*stock',
            r'currently\s*unavailable',
            r'sold\s*out',
            r'temporarily\s*out\s*of\s*stock',
            r'item\s*not\s*found',
            r'product\s*not\s*found',
            r'this\s*product\s*is\s*currently\s*unavailable',
        ]

        # Add patterns from config
        config_patterns = self.out_of_stock_keywords
        for pattern in config_patterns:
             # Escape pattern to treat as literal, but then replace spaces with \s* for flexibility
             escaped = re.escape(pattern)
             flexible = escaped.replace(r'\ ', r'\s*')
             out_of_stock_patterns.append(flexible)
        
        for pattern in out_of_stock_patterns:
            if re.search(pattern, page_lower, re.IGNORECASE):
                return {'available': False, 'status': 'out_of_stock'}
        
        return {'available': True, 'status': 'available'}

