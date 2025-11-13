"""
Amazon scraper
"""
import re
from typing import Dict, Optional
from playwright.async_api import Page
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from .base_scraper import BaseScraper


class AmazonScraper(BaseScraper):
    """Scraper for Amazon.in"""
    
    def get_site_name(self) -> str:
        return 'amazon'
    
    def get_stock_indicators(self) -> Dict:
        return {
            'out_of_stock': [
                'currently unavailable',
                'out of stock',
                'temporarily out of stock',
                "we don't know when or if this item will be back in stock",
                'unavailable',
                'sold out',
                'this item is currently unavailable',
                'out of stock.',
                'currently out of stock'
            ],
            'selectors': [
                '#availability span',
                '.a-color-state',
                '#outOfStock',
                '#availability',
                '.a-alert-inline-info',
                '[data-asin] .a-color-state'
            ]
        }
    
    def get_price_selectors(self) -> list:
        return [
            'input[type="hidden"][name="items[0.base][customerVisiblePrice][amount]"]',
            '.a-price.priceToPay .a-offscreen',
            '.a-price.priceToPay .a-price-whole',
            '.a-price.aok-align-center.priceToPay .a-offscreen',
            '#tp_price_block_total_price_ww .a-offscreen',
            '.a-price.aok-align-center .a-offscreen',
            '.a-price.aok-align-center .a-price-whole',
            '.a-price-whole',
            '.a-price .a-offscreen',
            '#priceblock_dealprice',
            '#priceblock_ourprice',
        ]
    
    async def extract_price_playwright(self, page: Page) -> Optional[str]:
        """Extract price from Amazon using Playwright"""
        # Top priority: Check hidden input field with price
        try:
            hidden_price_input = await page.query_selector(
                'input[type="hidden"][name="items[0.base][customerVisiblePrice][amount]"]',
                timeout=2000
            )
            if hidden_price_input:
                price_value = await hidden_price_input.get_attribute('value')
                if price_value:
                    try:
                        price_float = float(price_value)
                        if 10 <= price_float <= 10000000:
                            return price_value
                    except:
                        pass
        except:
            pass
        
        # Check priority selectors
        priority_selectors = [
            '.a-price.priceToPay .a-offscreen',
            '.a-price.priceToPay .a-price-whole',
            '.a-price.aok-align-center.priceToPay .a-offscreen',
            '#tp_price_block_total_price_ww .a-offscreen',
            '.a-price.aok-align-center .a-offscreen',
        ]
        
        for selector in priority_selectors[:2]:
            try:
                element = await page.query_selector(selector, timeout=2000)
                if element:
                    price_text = (await element.text_content()).strip()
                    cleaned_price = self.clean_price(price_text)
                    if cleaned_price != "N/A" and self.is_valid_price(cleaned_price):
                        try:
                            price_float = float(cleaned_price.replace(',', ''))
                            if 10 <= price_float <= 1000000000:
                                return cleaned_price
                        except:
                            pass
            except:
                continue
        
        # Check remaining selectors
        for selector in priority_selectors[2:]:
            try:
                element = await page.query_selector(selector, timeout=1000)
                if element:
                    price_text = (await element.text_content()).strip()
                    cleaned_price = self.clean_price(price_text)
                    if cleaned_price != "N/A" and self.is_valid_price(cleaned_price):
                        try:
                            price_float = float(cleaned_price.replace(',', ''))
                            if 10 <= price_float <= 100000:
                                return cleaned_price
                        except:
                            pass
            except:
                continue
        
        # Check buybox
        try:
            buybox = await page.query_selector('#buybox', timeout=1000)
            if buybox:
                price_elem = await buybox.query_selector('.a-price.priceToPay .a-offscreen', timeout=500)
                if price_elem:
                    price_text = (await price_elem.text_content()).strip()
                    cleaned_price = self.clean_price(price_text)
                    if cleaned_price != "N/A" and self.is_valid_price(cleaned_price):
                        try:
                            price_float = float(cleaned_price.replace(',', ''))
                            if 10 <= price_float <= 10000000:
                                return cleaned_price
                        except:
                            pass
        except:
            pass
        
        return None
    
    def extract_price_selenium(self, driver: WebDriver) -> Optional[str]:
        """Extract price from Amazon using Selenium"""
        # Top priority: Check hidden input field
        try:
            hidden_price_input = WebDriverWait(driver, 3).until(
                EC.presence_of_element_located((
                    By.CSS_SELECTOR,
                    'input[type="hidden"][name="items[0.base][customerVisiblePrice][amount]"]'
                ))
            )
            price_value = hidden_price_input.get_attribute('value')
            if price_value:
                try:
                    price_float = float(price_value)
                    if 10 <= price_float <= 10000000:
                        # Special handling for price = 500
                        if price_float == 500:
                            # Try to find higher price in buybox
                            try:
                                buybox = driver.find_element(By.ID, 'buybox')
                                all_prices = buybox.find_elements(
                                    By.CSS_SELECTOR,
                                    '.a-price .a-offscreen, .a-price .a-price-whole'
                                )
                                higher_prices = []
                                for p_elem in all_prices:
                                    try:
                                        p_text = p_elem.text.strip()
                                        if '₹' in p_text:
                                            p_match = re.search(r'₹\s*([\d,]+(?:\.\d{1,2})?)', p_text)
                                            if p_match:
                                                p_val = float(p_match.group(1).replace(',', ''))
                                                if 10 <= p_val <= 10000000 and p_val != 500 and p_val > 500:
                                                    higher_prices.append((p_val, p_text))
                                    except:
                                        continue
                                if higher_prices:
                                    higher_prices.sort(key=lambda x: x[0], reverse=True)
                                    return str(int(higher_prices[0][0]))
                            except:
                                pass
                        return price_value
                except:
                    pass
        except:
            pass
        
        # Check priority selectors
        amazon_selectors = [
            ('.a-price.priceToPay .a-offscreen', 'main_price_offscreen'),
            ('.a-price.priceToPay .a-price-whole', 'main_price_whole'),
            ('.a-price.aok-align-center.priceToPay .a-offscreen', 'buybox_price_offscreen'),
            ('.a-price.aok-align-center.priceToPay', 'buybox_price'),
            ('#tp_price_block_total_price_ww .a-offscreen', 'total_price_offscreen'),
        ]
        
        for selector, _ in amazon_selectors:
            try:
                price_elem = WebDriverWait(driver, 3).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                text = price_elem.text.strip()
                if text and '₹' in text:
                    price_match = re.search(r'₹\s*([\d,]+(?:\.\d{1,2})?)', text)
                    if price_match:
                        price_value = price_match.group(1).replace(',', '')
                        try:
                            price_float = float(price_value)
                            if 10 <= price_float <= 10000000:
                                if price_float == 500:
                                    # Check for higher price
                                    continue
                                return price_value
                        except:
                            pass
            except:
                continue
        
        # Check fallback selectors
        fallback_selectors = [
            '.a-price.aok-align-center .a-offscreen',
            '.a-price-whole',
            '#priceblock_ourprice',
            '#priceblock_dealprice',
        ]
        
        for selector in fallback_selectors:
            try:
                price_elem = driver.find_element(By.CSS_SELECTOR, selector)
                text = price_elem.text.strip()
                if text and '₹' in text:
                    price_match = re.search(r'₹\s*([\d,]+(?:\.\d{1,2})?)', text)
                    if price_match:
                        price_value = price_match.group(1).replace(',', '')
                        try:
                            price_float = float(price_value)
                            if 10 <= price_float <= 10000000:
                                if price_float == 500:
                                    continue
                                return price_value
                        except:
                            pass
            except:
                continue
        
        return None

