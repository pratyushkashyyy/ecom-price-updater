import re
import json
import urllib.parse
import random
import asyncio
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from playwright.async_api import async_playwright, Playwright, Browser, Page
from typing import List, Dict, Optional
from urllib.parse import urlparse

class EcommerceScraper:
    def __init__(self):
        # List of realistic user agents to rotate
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
        ]
        
        # Define price selectors for different e-commerce sites
        self.site_selectors = {
            'amazon': [
                'input[type="hidden"][name="items[0.base][customerVisiblePrice][amount]"]',  # Top priority: Hidden input with price value
                '.a-price.priceToPay .a-offscreen',  # Main price in buybox (most reliable)
                '.a-price.priceToPay .a-price-whole',  # Main price whole number
                '.a-price.aok-align-center.priceToPay .a-offscreen',  # Buybox centered price
                '#tp_price_block_total_price_ww .a-offscreen',  # Total price
                '.a-price.aok-align-center .a-offscreen',  # Centered price
                '.a-price.aok-align-center .a-price-whole',  # Centered whole price
                '.a-price-whole',
                '.a-price .a-offscreen', 
                '.a-price-range',
                '.a-price .a-price-symbol',
                '#priceblock_dealprice',
                '#priceblock_ourprice',
                '.a-price .a-text-price',
                '.a-price .a-price-symbol + span',
                '.a-price-range .a-price-symbol + span',
                '.a-price .a-offscreen + span'
            ],
            'flipkart': [
                '._30jeq3',
                '._16Jk6d',
                '._1vC4OE',
                '._3qQ9m1',
                '.Nx9bqj'
            ],
            'myntra': [
                '.pdp-price',
                '.pdp-discounted-price',
                '.pdp-mrp',
                '[class*="price"]'
            ],
            'nykaa': [
                '.css-1jczs19',
                '.css-1d0jf8e',
                '[class*="price"]',
                '.price'
            ],
            'snapdeal': [
                '.payBlkBig',
                '.pdp-final-price',
                '.pdp-selling-price',
                '[class*="price"]'
            ],
            'ajio': [
                '.prod-sp',  # Selling price
                'span[class*="prod-sp"]',
                '.prod-base-price',  # MRP
                'span[class*="price"]',
                '[class*="prod-base-price"]',
                '[data-id="price"]',
                '.price',
            ],
            'meesho': [
                '.pdp-price',
                '[class*="pdp-price"]',
                'span[class*="price"]',
                'div[class*="price"]',
                '[data-price]',
                '.price',
            ],
            'shopclues': [
                '.f_price',
                '.price',
                '[class*="price"]'
            ]
        }

    def identify_site(self, url: str) -> str:
        """Identify the e-commerce site from URL"""
        domain = urlparse(url).netloc.lower()
        
        if 'amazon' in domain:
            return 'amazon'
        elif 'flipkart' in domain or 'shopsy' in domain:
            return 'flipkart'
        elif 'myntra' in domain:
            return 'myntra'
        elif 'nykaa' in domain:
            return 'nykaa'
        elif 'snapdeal' in domain:
            return 'snapdeal'
        elif 'ajio' in domain:
            return 'ajio'
        elif 'meesho' in domain:
            return 'meesho'
        elif 'shopclues' in domain:
            return 'shopclues'
        else:
            return 'generic'

    def is_valid_price(self, price: str) -> bool:
        """Check if the extracted price is valid and reasonable"""
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

    def scrape_with_selenium(self, product_url: str, site: str = None, use_virtual_display: bool = False) -> str:
        """Generic Selenium scraper for sites that block Playwright"""
        if site is None:
            site = self.identify_site(product_url)
        
        # Setup virtual display if requested
        vdisplay = None
        if use_virtual_display:
            try:
                from virtual_display import VirtualDisplay
                vdisplay = VirtualDisplay()
                if not vdisplay.start():
                    vdisplay = None  # Fallback if virtual display fails
            except ImportError:
                print("⚠️  virtual_display module not available, running without virtual display")
        
        # Try site-specific Selenium modules first
        if site == 'nykaa':
            try:
                from nykaa_selenium import scrape_nykaa_with_selenium
                price = scrape_nykaa_with_selenium(product_url)
                if vdisplay:
                    vdisplay.stop()
                return price if price else 'N/A'
            except ImportError:
                pass
        elif site == 'meesho':
            try:
                from meesho_selenium import scrape_meesho_with_selenium
                price = scrape_meesho_with_selenium(product_url)
                if vdisplay:
                    vdisplay.stop()
                return price if price else 'N/A'
            except ImportError:
                try:
                    from meesho_price import scrape_meesho
                    result = scrape_meesho(product_url)
                    if vdisplay:
                        vdisplay.stop()
                    if result and result.get('price'):
                        return result['price']
                except ImportError:
                    pass
        elif site == 'ajio':
            try:
                from ajio_selenium import scrape_ajio_with_selenium
                price = scrape_ajio_with_selenium(product_url)
                if vdisplay:
                    vdisplay.stop()
                return price if price else 'N/A'
            except ImportError:
                pass
        elif site == 'myntra':
            try:
                from myntra_selenium import scrape_myntra_with_selenium
                price = scrape_myntra_with_selenium(product_url)
                if vdisplay:
                    vdisplay.stop()
                return price if price else 'N/A'
            except ImportError:
                pass
        
        # Fallback to inline Selenium implementation
        try:
            import undetected_chromedriver as uc
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            
            options = uc.ChromeOptions()
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-blink-features=AutomationControlled')
            
            if use_virtual_display and vdisplay:
                # Configure for virtual display (no headless needed)
                try:
                    from virtual_display import setup_virtual_display_for_selenium
                    setup_virtual_display_for_selenium(options)
                except ImportError:
                    pass
            else:
                # Use headless mode if virtual display not available
                options.add_argument('--headless=new')
            
            options.add_argument('--start-maximized')
            
            driver = uc.Chrome(options=options, version_main=None)
            
            try:
                driver.get(product_url)
                time.sleep(random.uniform(3, 6))
                
                wait = WebDriverWait(driver, 15)
                
                # Site-specific selectors
                if site == 'amazon':
                    # Top priority: Check hidden input field with price (most reliable)
                    try:
                        hidden_price_input = WebDriverWait(driver, 3).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, 'input[type="hidden"][name="items[0.base][customerVisiblePrice][amount]"]'))
                        )
                        price_value = hidden_price_input.get_attribute('value')
                        if price_value:
                            try:
                                price_float = float(price_value)
                                if 100 <= price_float <= 10000000:
                                    return price_value
                            except:
                                pass
                    except:
                        pass
                    
                    # Amazon-specific price selectors (prioritize buybox/main price)
                    amazon_selectors = [
                        ('.a-price.priceToPay .a-offscreen', 'main_price_offscreen'),
                        ('.a-price.priceToPay .a-price-whole', 'main_price_whole'),
                        ('.a-price.aok-align-center.priceToPay .a-offscreen', 'buybox_price_offscreen'),
                        ('.a-price.aok-align-center.priceToPay', 'buybox_price'),
                        ('#tp_price_block_total_price_ww .a-offscreen', 'total_price_offscreen'),
                        ('.a-price.aok-align-center .a-offscreen', 'centered_price_offscreen'),
                        ('.a-price.aok-align-center .a-price-whole', 'centered_price_whole'),
                        ('.a-price .a-offscreen', 'any_price_offscreen'),
                        ('.a-price-whole', 'price_whole'),
                        ('#priceblock_ourprice', 'priceblock_ourprice'),
                        ('#priceblock_dealprice', 'priceblock_dealprice'),
                    ]
                    
                    # Optimized sequential check with fast-fail for top selectors
                    # Check most likely selectors first with shorter timeouts
                    priority_selectors = amazon_selectors[:5]  # Top 5 most reliable
                    fallback_selectors = amazon_selectors[5:]   # Others as fallback
                    
                    # Fast check for priority selectors (shorter timeout)
                    for selector, selector_name in priority_selectors:
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
                                        if 100 <= price_float <= 10000000:
                                            return price_value
                                    except:
                                        pass
                        except:
                            continue  # Fast fail, move to next
                    
                    # Check fallback selectors if priority ones didn't work
                    for selector, selector_name in fallback_selectors:
                        try:
                            # Try direct find_element (faster than wait.until if element exists)
                            price_elem = driver.find_element(By.CSS_SELECTOR, selector)
                            text = price_elem.text.strip()
                            if text and '₹' in text:
                                price_match = re.search(r'₹\s*([\d,]+(?:\.\d{1,2})?)', text)
                                if price_match:
                                    price_value = price_match.group(1).replace(',', '')
                                    try:
                                        price_float = float(price_value)
                                        if 100 <= price_float <= 10000000:
                                            return price_value
                                    except:
                                        pass
                        except:
                            continue
                    
                    # Quick buybox check (already loaded, no wait needed)
                    try:
                        buybox = driver.find_element(By.ID, 'buybox')
                        if buybox:
                            # Use find_elements directly (no wait needed, element exists)
                            price_in_buybox = buybox.find_elements(By.CSS_SELECTOR, '.a-price.priceToPay .a-offscreen, .a-price.priceToPay .a-price-whole')
                            for price_elem in price_in_buybox[:3]:  # Limit to first 3
                                try:
                                    text = price_elem.text.strip()
                                    if text and '₹' in text:
                                        price_match = re.search(r'₹\s*([\d,]+(?:\.\d{1,2})?)', text)
                                        if price_match:
                                            price_value = price_match.group(1).replace(',', '')
                                            try:
                                                price_float = float(price_value)
                                                if 100 <= price_float <= 10000000:
                                                    return price_value
                                            except:
                                                pass
                                except:
                                    continue
                    except:
                        pass
                elif site == 'nykaa':
                    # Try to find selling price (css-1jczs19)
                    try:
                        selling_price_elem = wait.until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, ".css-1jczs19"))
                        )
                        text = selling_price_elem.text.strip()
                        if text and '₹' in text:
                            price_match = re.search(r'₹\s*([\d,]+(?:\.\d{1,2})?)', text)
                            if price_match:
                                price_value = price_match.group(1).replace(',', '')
                                return price_value
                    except:
                        pass
                elif site == 'meesho':
                    # Try h4 element with price (most reliable for Meesho)
                    try:
                        price_elem = wait.until(
                            EC.presence_of_element_located((By.XPATH, "//h4[contains(text(), '₹')]"))
                        )
                        text = price_elem.text.strip()
                        if text and '₹' in text:
                            price_match = re.search(r'₹\s*([\d,]+(?:\.\d{1,2})?)', text)
                            if price_match:
                                price_value = price_match.group(1).replace(',', '')
                                try:
                                    if float(price_value) > 50:
                                        return price_value
                                except:
                                    pass
                    except:
                        pass
                elif site == 'ajio':
                    # Try to find selling price (.prod-sp)
                    try:
                        selling_price_elem = wait.until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, ".prod-sp"))
                        )
                        text = selling_price_elem.text.strip()
                        if text and '₹' in text:
                            price_match = re.search(r'₹\s*([\d,]+(?:\.\d{1,2})?)', text)
                            if price_match:
                                price_value = price_match.group(1).replace(',', '')
                                try:
                                    if float(price_value) > 50:
                                        return price_value
                                except:
                                    pass
                    except:
                        pass
                elif site == 'myntra':
                    # Try to find discounted price first, then regular price
                    try:
                        # Try discounted price first
                        price_elem = wait.until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, ".pdp-discounted-price"))
                        )
                        text = price_elem.text.strip()
                        if text and '₹' in text:
                            price_match = re.search(r'₹\s*([\d,]+(?:\.\d{1,2})?)', text)
                            if price_match:
                                price_value = price_match.group(1).replace(',', '')
                                try:
                                    if float(price_value) > 50:
                                        return price_value
                                except:
                                    pass
                    except:
                        # Fallback to regular price
                        try:
                            price_elem = wait.until(
                                EC.presence_of_element_located((By.CSS_SELECTOR, ".pdp-price"))
                            )
                            text = price_elem.text.strip()
                            if text and '₹' in text:
                                price_match = re.search(r'₹\s*([\d,]+(?:\.\d{1,2})?)', text)
                                if price_match:
                                    price_value = price_match.group(1).replace(',', '')
                                    try:
                                        if float(price_value) > 50:
                                            return price_value
                                    except:
                                        pass
                        except:
                            pass
                
                # Generic fallback: try any element with ₹
                try:
                    price_elem = wait.until(
                        EC.presence_of_element_located((By.XPATH, "//*[contains(text(), '₹')]"))
                    )
                    text = price_elem.text.strip()
                    if text and '₹' in text and len(text) < 100:
                        price_match = re.search(r'₹\s*([\d,]+(?:\.\d{1,2})?)', text)
                        if price_match:
                            price_value = price_match.group(1).replace(',', '')
                            try:
                                if float(price_value) > 50:  # Reasonable threshold
                                    return price_value
                            except:
                                pass
                except:
                    pass
                
                # Last resort: regex on page source
                page_source = driver.page_source
                price_match = re.search(r'₹\s*([\d,]+(?:\.\d{1,2})?)', page_source)
                if price_match:
                    price_value = price_match.group(1).replace(',', '')
                    try:
                        if float(price_value) > 50:
                            return price_value
                    except:
                        pass
                
                return 'N/A'
            finally:
                try:
                    driver.quit()
                except:
                    pass
                if vdisplay:
                    vdisplay.stop()
        except Exception as e:
            if vdisplay:
                vdisplay.stop()
            return 'N/A'

    def scrape_nykaa_with_selenium(self, product_url: str) -> str:
        """Scrape Nykaa using Selenium (for when Playwright is blocked)"""
        return self.scrape_with_selenium(product_url, 'nykaa')

    def clean_price(self, price_text: str) -> str:
        """Clean and extract price from text"""
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

    async def scrape_product_price(self, playwright: Playwright, product_url: str, headless: bool = True, 
                                   force_selenium: bool = False, use_virtual_display: bool = False) -> Dict:
        site = self.identify_site(product_url)
        
        # If force_selenium is True or site is known to be blocked, use Selenium directly
        sites_known_blocked = ['nykaa', 'meesho', 'ajio', 'myntra']  # Sites known to block Playwright or need Selenium
        
        if force_selenium or site in sites_known_blocked:
            price = await asyncio.to_thread(self.scrape_with_selenium, product_url, site, use_virtual_display)
            return {
                'url': product_url,
                'site': site,
                'price': price if price != 'N/A' else 'N/A',
                'status': 'success (Selenium)' if price != 'N/A' else 'Price not found',
                'method': 'selenium'
            }
        
        # Try Playwright first
        user_agent = random.choice(self.user_agents)
        browser = None
        context = None
        
        try:
            # For virtual display, we don't use headless mode
            # The virtual display handles the "headless" part
            playwright_headless = headless if not use_virtual_display else False
            
            browser = await playwright.chromium.launch(headless=playwright_headless)
            context = await browser.new_context(
                user_agent=user_agent,
                viewport={'width': 1920, 'height': 1080},
                locale='en-US',
                timezone_id='America/New_York',
                permissions=['geolocation'],
                extra_http_headers={
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'none',
                    'Cache-Control': 'max-age=0',
                },
                ignore_https_errors=True,
            )
            page = await context.new_page()
            
            max_retries = 2
            blocked = False
            for attempt in range(max_retries):
                try:
                    await page.goto(product_url, timeout=30000, wait_until='domcontentloaded')
                    await asyncio.sleep(3 + random.uniform(1, 3))
                    
                    # Check if page is blocked (common patterns)
                    page_content = await page.content()
                    page_title = await page.title()
                    
                    # Check for blocking indicators
                    if any(indicator in page_content.lower() or indicator in page_title.lower() 
                           for indicator in ['access denied', 'blocked', 'forbidden', 'cloudflare', 'captcha']):
                        blocked = True
                        break
                    
                    break
                except Exception as e:
                    if attempt == max_retries - 1:
                        # If Playwright fails, mark as blocked
                        blocked = True
                    await asyncio.sleep(2 + random.uniform(0.5, 1.5))
            
            if blocked:
                # Fallback to Selenium
                if context:
                    await context.close()
                if browser:
                    await browser.close()
                
                price = await asyncio.to_thread(self.scrape_with_selenium, product_url, site, use_virtual_display)
                return {
                    'url': product_url,
                    'site': site,
                    'price': price if price != 'N/A' else 'N/A',
                    'status': 'success (Selenium fallback)' if price != 'N/A' else 'Price not found',
                    'method': 'selenium',
                    'reason': 'Playwright blocked'
                }
            
            result = {
                'url': product_url,
                'site': site,
                'price': 'N/A',
                'status': 'success',
                'method': 'playwright'
            }
            
            price_selectors = self.site_selectors.get(site, ['.price', '[class*="price"]', '#price'])
            
            async def strategy1_site_selectors():
                # Amazon-specific logic: prioritize buybox/main price
                if site == 'amazon':
                    # Top priority: Check hidden input field with price (most reliable)
                    try:
                        hidden_price_input = await page.query_selector('input[type="hidden"][name="items[0.base][customerVisiblePrice][amount]"]', timeout=2000)
                        if hidden_price_input:
                            price_value = await hidden_price_input.get_attribute('value')
                            if price_value:
                                try:
                                    price_float = float(price_value)
                                    if 100 <= price_float <= 10000000:
                                        return price_value
                                except:
                                    pass
                    except:
                        pass
                    
                    amazon_priority_selectors = [
                        '.a-price.priceToPay .a-offscreen',
                        '.a-price.priceToPay .a-price-whole',
                        '.a-price.aok-align-center.priceToPay .a-offscreen',
                        '#tp_price_block_total_price_ww .a-offscreen',
                        '.a-price.aok-align-center .a-offscreen',
                    ]
                    
                    # Check top 2 selectors first (most likely to succeed)
                    for selector in amazon_priority_selectors[:2]:
                        try:
                            element = await page.query_selector(selector, timeout=2000)
                            if element:
                                price_text = (await element.text_content()).strip()
                                cleaned_price = self.clean_price(price_text)
                                if cleaned_price != "N/A" and self.is_valid_price(cleaned_price):
                                    try:
                                        price_float = float(cleaned_price.replace(',', ''))
                                        if 100 <= price_float <= 1000000000:
                                            return cleaned_price
                                    except:
                                        pass
                        except:
                            continue
                    
                    # Check remaining selectors in parallel (smaller batch for speed)
                    async def check_selector(selector):
                        try:
                            element = await page.query_selector(selector, timeout=1000)
                            if element:
                                price_text = (await element.text_content()).strip()
                                cleaned_price = self.clean_price(price_text)
                                if cleaned_price != "N/A" and self.is_valid_price(cleaned_price):
                                    try:
                                        price_float = float(cleaned_price.replace(',', ''))
                                        if 100 <= price_float <= 100000:
                                            return cleaned_price
                                    except:
                                        pass
                        except:
                            pass
                        return None
                    
                    # Check remaining selectors concurrently
                    results = await asyncio.gather(
                        *[check_selector(sel) for sel in amazon_priority_selectors[2:]],
                        return_exceptions=True
                    )
                    
                    # Return first valid result
                    for result in results:
                        if result and isinstance(result, str):
                            return result
                    
                    # Quick buybox check
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
                                        if 100 <= price_float <= 10000000:
                                            return cleaned_price
                                    except:
                                        pass
                    except:
                        pass
                
                # Generic selector logic - check sequentially with early exit for speed
                for selector in price_selectors:
                    try:
                        price_elements = await page.query_selector_all(selector)
                        # Check only first few elements (price usually in first match)
                        for element in price_elements[:3]:
                            price_text = (await element.text_content()).strip()
                            cleaned_price = self.clean_price(price_text)
                            if cleaned_price != "N/A" and self.is_valid_price(cleaned_price):
                                # Additional validation for Amazon
                                if site == 'amazon':
                                    try:
                                        price_float = float(cleaned_price.replace(',', ''))
                                        if 100 <= price_float <= 10000000:
                                            return cleaned_price
                                    except:
                                        continue
                                else:
                                    return cleaned_price
                    except:
                        continue
                
                return None
            
            async def strategy2_pattern_matching():
                try:
                    # Only check elements with price-related classes/ids (much faster)
                    price_related = await page.query_selector_all('[class*="price"], [id*="price"], [class*="Price"], [id*="Price"]')
                    # Limit to first 100 elements for speed
                    elements_to_check = price_related[:100] if len(price_related) > 100 else price_related
                    
                    # Process elements sequentially but efficiently (early exit)
                    for element in elements_to_check:
                        try:
                            text = await element.text_content()
                            if text and re.search(r'[₹$€£¥]\s*\d{2,}|\d{3,}', text):
                                cleaned_price = self.clean_price(text)
                                if cleaned_price != "N/A" and self.is_valid_price(cleaned_price):
                                    # Additional validation for Amazon
                                    if site == 'amazon':
                                        try:
                                            price_float = float(cleaned_price.replace(',', ''))
                                            if 100 <= price_float <= 10000000:
                                                return cleaned_price
                                        except:
                                            continue
                                    return cleaned_price
                        except:
                            continue
                except:
                    pass
                return None
            
            async def strategy3_json_ld():
                try:
                    json_scripts = await page.query_selector_all('script[type="application/ld+json"]')
                    
                    # Process JSON scripts in parallel
                    async def process_json_script(script):
                        try:
                            json_data = json.loads(await script.text_content())
                            if isinstance(json_data, dict) and 'offers' in json_data:
                                offers = json_data['offers']
                                if isinstance(offers, dict) and 'price' in offers:
                                    return str(offers['price'])
                            # Also check for @graph (array format)
                            if isinstance(json_data, dict) and '@graph' in json_data:
                                for item in json_data.get('@graph', []):
                                    if isinstance(item, dict) and 'offers' in item:
                                        offers = item['offers']
                                        if isinstance(offers, dict) and 'price' in offers:
                                            return str(offers['price'])
                        except:
                            pass
                        return None
                    
                    results = await asyncio.gather(
                        *[process_json_script(script) for script in json_scripts],
                        return_exceptions=True
                    )
                    
                    # Return first valid result
                    for result in results:
                        if result and isinstance(result, str) and self.is_valid_price(result):
                            return result
                except:
                    pass
                return None
            
            strategy_results = await asyncio.gather(
                strategy1_site_selectors(),
                strategy2_pattern_matching(),
                strategy3_json_ld(),
                return_exceptions=True
            )
            
            price_found = False
            for extracted_price in strategy_results:
                if extracted_price and isinstance(extracted_price, str) and self.is_valid_price(extracted_price):
                    result['price'] = extracted_price
                    price_found = True
                    break
            
            # If price not found with Playwright, fallback to Selenium
            if not price_found:
                price = await asyncio.to_thread(self.scrape_with_selenium, product_url, site, use_virtual_display)
                if price != 'N/A':
                    result['price'] = price
                    result['method'] = 'selenium'
                    result['status'] = 'success (Selenium fallback)'
                else:
                    result['status'] = 'Price not found (tried Playwright and Selenium)'
            
            return result
            
        except Exception as e:
            # If Playwright fails, try Selenium as fallback
            if 'playwright' in str(e).lower() or 'timeout' in str(e).lower() or 'navigation' in str(e).lower():
                price = await asyncio.to_thread(self.scrape_with_selenium, product_url, site, use_virtual_display)
                return {
                    'url': product_url,
                    'site': site,
                    'price': price if price != 'N/A' else 'N/A',
                    'status': f'Playwright failed, Selenium: {"success" if price != "N/A" else "failed"}',
                    'method': 'selenium',
                    'error': str(e)
                }
            else:
                return {
                    'url': product_url,
                    'site': site,
                    'price': 'N/A',
                    'status': f'Error: {str(e)}'
                }
        finally:
            if context:
                try:
                    await context.close()
                except:
                    pass
            if browser:
                try:
                    await browser.close()
                except:
                    pass

    async def scrape_multiple_products(self, playwright: Playwright, urls: List[str], 
                                        max_concurrent: int = 20, headless: bool = True, 
                                        use_virtual_display: bool = False) -> List[Dict]:
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def scrape_with_limit(url):
            async with semaphore:
                return await self.scrape_product_price(playwright, url, headless=headless, use_virtual_display=use_virtual_display)
        
        tasks = [scrape_with_limit(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append({
                    'url': urls[i],
                    'site': self.identify_site(urls[i]),
                    'price': 'N/A',
                    'status': f'Error: {str(result)}'
                })
            else:
                processed_results.append(result)
        
        return processed_results

async def main():
    scraper = EcommerceScraper()
    
    test_urls = [
        "https://www.amazon.in/Solitude-Soap-Dispenser-Dishwashing-2/dp/B0DVCCL9SY?th=1&linkCode=sl1&tag=appdeals04-21&linkId=19022195a19556b6ca2d8acacd073049&language=en_IN&ref_=as_li_ss_tl",
        "https://www.amazon.in/Apple-MacBook-16-inch-16%E2%80%91core-40%E2%80%91core/dp/B0CM5QYZ3R/?_encoding=UTF8&pd_rd_w=XxnCZ&content-id=amzn1.sym.fa294cf3-99e4-435e-8284-16ec3b3e2443%3Aamzn1.symc.752cde0b-d2ce-4cce-9121-769ea438869e&pf_rd_p=fa294cf3-99e4-435e-8284-16ec3b3e2443&pf_rd_r=QFVCTBSSJW1EMSA5Q749&pd_rd_wg=aNbQr&pd_rd_r=a76fc29b-5e69-4fc8-bab8-696b6fdfce91&ref_=pd_hp_d_atf_ci_mcx_mr_ca_hp_atf_d&th=1",  # Amazon 
        "https://www.flipkart.com/24-energy-large-battery-mosquito-bat-big-head-racquet-light-charging-wire-electric-insect-killer-indoor-outdoor/p/itm997a7e072213f?pid=EIKGJEVQUTZMGGZJ&lid=LSTEIKGJEVQUTZMGGZJDXHO4Y&marketplace=FLIPKART&store=rja%2Fplv%2Foej&srno=b_1_1&otracker=browse&fm=organic&iid=en_catibhIh2mq6LS_giqrkMGGJF8VJvCdRj2vhTbAbNpWj3lw5BTmKghdclcrzxHQURE4M-xn2S_POOoS3xv6fow%3D%3D&ppt=None&ppn=None&ssid=h5j3kjtjyo0000001761471120825",  # Flipkart 
        "https://www.shopsy.in/slippers/p/itmf166ce1205815?pid=XSSGTMTG7NATWGWV&lid=LSTXSSGTMTG7NATWGWVCIJZTN&marketplace=FLIPKART&sattr[]=color&sattr[]=size",  # Shopsy
        "https://www.myntra.com/sports-shoes/hrx+by+hrithik+roshan/hrx-by-hrithik-roshan-unisex-mesh-running--shoes/32093860/buy",  # Myntra
        "https://www.nykaa.com/braun-silk-epil-9-890-epilator-for-long-lasting-hair-removal-includes-a-bikini-styler/p/1178844?productId=1178844&pps=1",  # Nykaa
        "https://www.snapdeal.com/product/mustmom-bright-ethnic-pure-cotton/662689652480",  # Snapdeal
        "https://www.ajio.com/yousta-men-washed-relaxed-fit-crew-neck-t-shirt/p/443079993_blackcharcoal?",  # Ajio
        "https://www.meesho.com/frekman-stylish-cotton-blend-check-mens-shirt/p/1kv4b",  # Meesho
        "https://www.shopclues.com/hit-square-polyster-gym-sports-hood-cotton-blend-tshirt-for-men-relax-153546672.html"  # ShopClues
    ]
    
    print("Testing E-commerce Price Scraper - Detecting Blocked Sites")
    print("=" * 70)
    print("\nTesting all URLs with Playwright first, falling back to Selenium if blocked...\n")
    
    async with async_playwright() as playwright:
        results = await scraper.scrape_multiple_products(
                playwright,
                test_urls,
                max_concurrent=5,  # Reduced for testing
                headless=True,
            )
        
        # Analyze results
        playwright_success = []
        selenium_used = []
        failed = []
        
        for i, result in enumerate(results, 1):
            method = result.get('method', 'unknown')
            site = result['site'].upper()
            price = result['price']
            status = result['status']
            
            print(f"\n{i}. {site}")
            print(f"   URL: {result['url'][:80]}...")
            print(f"   Price: {price}")
            print(f"   Method: {method}")
            print(f"   Status: {status}")
            
            if method == 'playwright' and price != 'N/A':
                playwright_success.append(site)
            elif method == 'selenium' and price != 'N/A':
                selenium_used.append(site)
                if 'fallback' in status.lower() or 'blocked' in status.lower():
                    print(f"   ⚠️  BLOCKED - Using Selenium")
            else:
                failed.append(site)
                print(f"   ❌ FAILED")
        
        # Summary
        print("\n" + "=" * 70)
        print("SUMMARY")
        print("=" * 70)
        print(f"\n✅ Playwright Success: {', '.join(playwright_success) if playwright_success else 'None'}")
        print(f"⚠️  Selenium Required (Blocked): {', '.join(selenium_used) if selenium_used else 'None'}")
        print(f"❌ Failed: {', '.join(failed) if failed else 'None'}")
        
        if selenium_used:
            print(f"\n📝 Sites automatically switched to Selenium:")
            for site in selenium_used:
                print(f"   - {site}")

if __name__ == "__main__":
    asyncio.run(main())
