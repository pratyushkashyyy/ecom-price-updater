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
        
        # Load selectors from JSON file
        self.load_selectors()

    def load_selectors(self):
        """Load selectors from selectors.json file"""
        try:
            with open('selectors.json', 'r') as f:
                data = json.load(f)
            
            self.stock_indicators = {}
            self.site_selectors = {}
            self.name_selectors = {}
            self.image_selectors = {}
            self.image_selectors = {}
            
            for site, config in data.items():
                # Setup stock indicators
                self.stock_indicators[site] = {
                    'out_of_stock': config.get('out_of_stock', []),
                    'selectors': config.get('selectors', [])  # Some sites might have specific selectors for stock
                }
                
                # Setup price selectors
                self.site_selectors[site] = config.get('price_selectors', [])
                
                # Setup other selectors
                self.name_selectors[site] = config.get('name_selectors', [])
                self.image_selectors[site] = config.get('image_selectors', [])
                self.image_selectors[site] = config.get('image_selectors', [])
                
            # Add generic fallback if not present
            if 'generic' not in self.stock_indicators:
                self.stock_indicators['generic'] = {
                    'out_of_stock': [
                        'out of stock',
                        'sold out',
                        'currently unavailable',
                        'unavailable',
                        'temporarily out of stock'
                    ],
                    'selectors': [
                        '[class*="out-of-stock"]',
                        '[class*="sold-out"]',
                        '[class*="unavailable"]',
                        '.sold-out',
                        '.out-of-stock'
                    ]
                }
                
        except Exception as e:
            print(f"Error loading selectors.json: {e}")
            # Fallback to empty dicts or basic defaults if file load fails
            self.stock_indicators = {'generic': {'out_of_stock': ['out of stock'], 'selectors': []}}
            self.site_selectors = {}

    def identify_site(self, url: str) -> str:
        """Identify the e-commerce site from URL"""
        domain = urlparse(url).netloc.lower()
        
        # Handle short URLs and redirect domains
        if 'amzn.to' in domain or 'amzn' in domain:
            return 'amazon'
        elif 'amazon' in domain:
            return 'amazon'
        elif 'flipkart' in domain or 'shopsy' in domain or 'fkrt.cc' in domain:
            return 'flipkart'
        elif 'myntra' in domain or 'myntr.it' in domain:
            return 'myntra'
        elif 'nykaa' in domain:
            return 'nykaa'
        elif 'snapdeal' in domain:
            return 'snapdeal'
        elif 'ajio' in domain or 'ajiio.in' in domain:
            return 'ajio'
        elif 'meesho' in domain or 'msho.in' in domain:
            return 'meesho'
        elif 'shopclues' in domain:
            return 'shopclues'
        elif 'hygulife' in domain or 'hyugalife' in domain:
            return 'hygulife'
        elif 'bitli.in' in domain:
            return 'generic'  # bitli.in can redirect to different sites (hygulife, nykaa, etc.), identify from final URL
        else:
            return 'generic'

    def check_stock_status(self, page_content: str, page_title: str, site: str, driver=None, page=None) -> dict:
        """
        Check if product is in stock or out of stock.
        Returns dict with 'in_stock' (bool) and 'stock_status' (str) keys.
        """
        stock_status = {
            'in_stock': True,  # Default to in stock
            'stock_status': 'in_stock',
            'message': None
        }
        
        # Get stock indicators for the site
        indicators = self.stock_indicators.get(site, self.stock_indicators['generic'])
        out_of_stock_texts = indicators['out_of_stock']
        selectors = indicators.get('selectors', [])
        
        # Check page content and title for out-of-stock indicators
        content_lower = (page_content + ' ' + page_title).lower()
        
        for oos_text in out_of_stock_texts:
            if oos_text.lower() in content_lower:
                stock_status['in_stock'] = False
                stock_status['stock_status'] = 'out_of_stock'
                stock_status['message'] = f'Product appears to be out of stock (detected: "{oos_text}")'
                return stock_status
        
        # Check using selectors if driver/page is provided
        if driver:  # Selenium
            try:
                from selenium.webdriver.common.by import By
                from selenium.common.exceptions import NoSuchElementException, TimeoutException
                
                for selector in selectors:
                    try:
                        element = driver.find_element(By.CSS_SELECTOR, selector)
                        if element and element.is_displayed():
                            text = element.text.strip().lower()
                            if any(oos_text.lower() in text for oos_text in out_of_stock_texts):
                                stock_status['in_stock'] = False
                                stock_status['stock_status'] = 'out_of_stock'
                                stock_status['message'] = f'Product is out of stock (selector: {selector})'
                                return stock_status
                    except (NoSuchElementException, TimeoutException):
                        continue
            except Exception:
                pass
        
        # Note: For Playwright, use check_stock_status_async method instead
        
        # Additional check: If price is found but "Add to Cart" button is missing/disabled, might be out of stock
        # This is a heuristic and might not be 100% accurate
        if 'amazon' in site.lower():
            if driver:
                try:
                    from selenium.webdriver.common.by import By
                    # Check if "Add to Cart" button exists and is enabled
                    add_to_cart = driver.find_elements(By.ID, 'add-to-cart-button')
                    buy_now = driver.find_elements(By.ID, 'buy-now-button')
                    if not add_to_cart and not buy_now:
                        # Check for "Notify me" or similar buttons
                        notify_buttons = driver.find_elements(By.CSS_SELECTOR, '[id*="notify"], [class*="notify"]')
                        if notify_buttons:
                            stock_status['in_stock'] = False
                            stock_status['stock_status'] = 'out_of_stock'
                            stock_status['message'] = 'Product appears to be out of stock (no Add to Cart button, notify button present)'
                            return stock_status
                except Exception:
                    pass
        
        return stock_status
    
        return stock_status

    def clean_image_url(self, url: str) -> str:
        """
        Clean image URL to get the highest resolution version.
        Removes resizing parameters and specific patterns.
        """
        if not url:
            return None
            
        try:
            # Amazon specific: Remove _SL, _AC, _SX patterns for full size
            # e.g., https://.../image._SL1500_.jpg -> https://.../image.jpg
            if 'amazon' in url or 'media-amazon' in url:
                url = re.sub(r'\._[A-Z]{2}\d+_', '', url)
                url = re.sub(r'\._[A-Z]{2}\d+,\d+,\d+,\d+_', '', url)
            
            # Common resizing params
            url = re.sub(r'\?width=\d+&?', '?', url)
            url = re.sub(r'\?height=\d+&?', '?', url)
            url = re.sub(r'\?w=\d+&?', '?', url)
            url = re.sub(r'\?h=\d+&?', '?', url)
            
            # Remove trailing ? or & if empty
            if url.endswith('?') or url.endswith('&'):
                url = url[:-1]
                
            return url.strip()
        except:
            return url

    def extract_product_details(self, driver_or_page, site: str, is_async: bool = False) -> dict:
        """
        Extract product details (name, image, rating) using selectors or generic meta tags.
        Supports both Selenium (driver) and Playwright (page).
        """
        details = {
            'name': None,
            'image_url': None,
            'name': None,
            'image_url': None
        }
        
        # Helper to get text/attribute safely
        async def get_async(selector, attr=None):
            try:
                el = await driver_or_page.query_selector(selector)
                if el:
                    if attr:
                        return await el.get_attribute(attr)
                    return await el.text_content()
            except:
                pass
            return None
            
        def get_sync(selector, attr=None):
            try:
                from selenium.webdriver.common.by import By
                els = driver_or_page.find_elements(By.CSS_SELECTOR, selector)
                if els:
                    if attr:
                        return els[0].get_attribute(attr)
                    return els[0].text
            except:
                pass
            return None

        # 1. Extract Name
        selectors = self.name_selectors.get(site, [])
        for sel in selectors:
            val = None
            if is_async:
                # Need to use run_until_complete if calling from async context but logic not yet fully async-ready
                # But here we assume this method is called from proper context (async or sync)
                # Since we can't easily mix, we will split common logic or check is_async flag
                pass # Handled below
            else:
                pass
        
        # To avoid complexity, let's process each field sequentially with check
        
        # --- NAME ---
        name = None
        # Try site-specific selectors
        for sel in self.name_selectors.get(site, []):
            if is_async:
                 # Logic handled better solely inside extract_product_details_async
                 pass 
            else:
                 val = get_sync(sel)
                 if val and len(val.strip()) > 0:
                     name = val.strip()
                     break
                     
        # Fallback to meta tags (sync)
        if not name and not is_async:
             try:
                from selenium.webdriver.common.by import By
                # og:title
                metas = driver_or_page.find_elements(By.CSS_SELECTOR, 'meta[property="og:title"]')
                if metas:
                    name = metas[0].get_attribute('content')
                if not name:
                    name = driver_or_page.title
                
                # Filter generic titles (especially for Flipkart)
                if name and any(generic in name for generic in ['Item Store Online', 'Flipkart.com', 'Online Shopping Site', 'Buy Online']):
                    # Try harder to find specific element
                    try:
                        h1s = driver_or_page.find_elements(By.TAG_NAME, 'h1')
                        for h1 in h1s:
                            txt = h1.text.strip()
                            if txt and len(txt) > 5 and 'Flipkart' not in txt:
                                name = txt
                                break
                    except:
                        pass
                    
                    # If still generic, set to None so we don't return garbage
                    if name and any(generic in name for generic in ['Item Store Online', 'Flipkart.com', 'Online Shopping Site', 'Buy Online']):
                        name = None
             except:
                 pass
        
        details['name'] = name
        
        # --- IMAGE ---
        image = None
        
        # helper for image attributes
        img_attrs = ['src', 'data-src', 'srcset', 'data-srcset', 'data-high-res', 'data-old-hires']
        
        for sel in self.image_selectors.get(site, []):
            if not is_async:
                # For each selector, try all common image attributes
                for attr in img_attrs:
                    val = get_sync(sel, attr)
                    if val:
                        if 'srcset' in attr:
                            # Parse srcset: pick largest (last entry usually)
                            try:
                                parts = val.split(',')
                                last_part = parts[-1].strip()
                                # format: url size, we want url
                                val = last_part.split(' ')[0]
                            except:
                                continue
                        
                        cleaned_val = self.clean_image_url(val)
                        if cleaned_val and 'data:image' not in cleaned_val and 'placeholder' not in cleaned_val:
                            image = cleaned_val
                            break
                if image:
                    break
        
        
        # Fallback: Use product name to find image (Robust heuristic)
        if not image and name:
            try:
                # Clean name for matching (take first 2 words)
                name_parts = name.split()
                if len(name_parts) >= 2:
                    short_name = f"{name_parts[0]} {name_parts[1]}"
                    # Find all images with alt text containing short name
                    if is_async:
                        # Async Not fully implemented for this fallback yet
                        pass 
                    else:
                        from selenium.webdriver.common.by import By
                        # Case insensitive xpath match for alt text
                        xpath = f"//img[contains(translate(@alt, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{short_name.lower()}')]"
                        imgs = driver_or_page.find_elements(By.XPATH, xpath)
                        for img in imgs:
                            # Try attributes
                            for attr in img_attrs:
                                val = img.get_attribute(attr)
                                clean = self.clean_image_url(val)
                                if clean and 'data:image' not in clean:
                                    image = clean
                                    break
                            if image: break
            except:
                pass

        # Fallback meta tags (sync)
        if not image and not is_async:
            try:
                from selenium.webdriver.common.by import By
                metas = driver_or_page.find_elements(By.CSS_SELECTOR, 'meta[property="og:image"]')
                if metas:
                    image = self.clean_image_url(metas[0].get_attribute('content'))
            except:
                pass
                
        details['image_url'] = image
        
        return details

    async def extract_product_details_async(self, page, site: str) -> dict:
        """Async version of details extraction for Playwright"""
        details = {
            'name': None,
            'image_url': None,
            'name': None,
            'image_url': None
        }
        
        # --- NAME ---
        name = None
        for sel in self.name_selectors.get(site, []):
            try:
                el = await page.query_selector(sel)
                if el:
                    txt = await el.text_content()
                    if txt and txt.strip():
                        name = txt.strip()
                        break
            except:
                continue
                
        # Fallback meta tags
        if not name:
            try:
                el = await page.query_selector('meta[property="og:title"]')
                if el:
                    name = await el.get_attribute('content')
                if not name:
                    name = await page.title()
            except:
                pass
        details['name'] = name
        
        # --- IMAGE ---
        image = None
        for sel in self.image_selectors.get(site, []):
            try:
                el = await page.query_selector(sel)
                if el:
                    # Try to get high-res attributes first
                    found_val = None
                    for attr in ['data-high-res', 'data-zoom-image', 'data-old-hires', 'data-src', 'srcset', 'src']:
                        val = await el.get_attribute(attr)
                        if val:
                            if attr == 'srcset':
                                try:
                                    parts = val.split(',')
                                    last_part = parts[-1].strip()
                                    val = last_part.split(' ')[0]
                                except:
                                    continue
                            found_val = val
                            break
                    
                    if found_val:
                        image = self.clean_image_url(found_val)
                        if image:
                            break
            except:
                continue
        
        # Fallback meta tags
        if not image:
            try:
                el = await page.query_selector('meta[property="og:image"]')
                if el:
                    image = self.clean_image_url(await el.get_attribute('content'))
            except:
                pass
        details['image_url'] = image


        
        return details
    
    async def check_stock_status_async(self, page, site: str) -> dict:
        """
        Async version of check_stock_status for Playwright.
        Check if product is in stock or out of stock.
        Returns dict with 'in_stock' (bool) and 'stock_status' (str) keys.
        """
        stock_status = {
            'in_stock': True,  # Default to in stock
            'stock_status': 'in_stock',
            'message': None
        }
        
        # For hygulife, check JSON data first (more reliable than text search)
        if site == 'hygulife':
            try:
                page_content = await page.content()
                # Look for stock_status in JSON data
                import re
                stock_status_match = re.search(r'"stock_status"\s*:\s*(true|false)', page_content, re.IGNORECASE)
                inventory_stock_match = re.search(r'"inventory_is_in_stock"\s*:\s*(true|false)', page_content, re.IGNORECASE)
                
                if stock_status_match:
                    is_stock = stock_status_match.group(1).lower() == 'true'
                    if not is_stock:
                        stock_status['in_stock'] = False
                        stock_status['stock_status'] = 'out_of_stock'
                        stock_status['message'] = 'Product is out of stock (from JSON stock_status)'
                        return stock_status
                
                if inventory_stock_match:
                    is_inventory_stock = inventory_stock_match.group(1).lower() == 'true'
                    if not is_inventory_stock:
                        stock_status['in_stock'] = False
                        stock_status['stock_status'] = 'out_of_stock'
                        stock_status['message'] = 'Product is out of stock (from JSON inventory_is_in_stock)'
                        return stock_status
                
                # If JSON shows in stock, trust that over text search
                if stock_status_match or inventory_stock_match:
                    return stock_status  # Return in_stock if JSON confirms it
            except Exception:
                pass
        
        # Get stock indicators for the site
        indicators = self.stock_indicators.get(site, self.stock_indicators['generic'])
        out_of_stock_texts = indicators['out_of_stock']
        selectors = indicators.get('selectors', [])
        
        # Get page content and title
        try:
            page_content = await page.content()
            page_title = await page.title()
            content_lower = (page_content + ' ' + page_title).lower()
            
            # For hygulife, be more careful - only check specific selectors, not entire page content
            # (page content might have "sold out" from other products)
            if site == 'hygulife':
                # Only check using specific selectors, not page-wide text search
                for selector in selectors:
                    try:
                        element = await page.query_selector(selector)
                        if element:
                            text = (await element.text_content()).strip().lower()
                            if any(oos_text in text for oos_text in out_of_stock_texts):
                                stock_status['in_stock'] = False
                                stock_status['stock_status'] = 'out_of_stock'
                                stock_status['message'] = f'Product is out of stock (selector: {selector})'
                                return stock_status
                    except Exception:
                        continue
            else:
                # For Flipkart, check selectors first (more reliable than page-wide text search)
                if site == 'flipkart':
                    # Check using selectors first
                    for selector in selectors:
                        try:
                            element = await page.query_selector(selector)
                            if element:
                                text = (await element.text_content()).strip().lower()
                                if any(oos_text in text for oos_text in out_of_stock_texts):
                                    stock_status['in_stock'] = False
                                    stock_status['stock_status'] = 'out_of_stock'
                                    stock_status['message'] = f'Product is out of stock (selector: {selector})'
                                    return stock_status
                        except Exception:
                            continue
                    
                    # Also check for "Notify Me" button (indicates out of stock)
                    try:
                        notify_selectors = [
                            'button:has-text("Notify")',
                            'button:has-text("Notify Me")',
                            '[class*="notify"]',
                            '._2UzuFa',
                            '._2KpZ6l._2UzuFa',
                            'button._2KpZ6l',  # Generic Flipkart button, check text
                        ]
                        for selector in notify_selectors:
                            try:
                                notify_elem = await page.query_selector(selector)
                                if notify_elem:
                                    # Check if it's visible and not disabled
                                    is_visible = await notify_elem.is_visible()
                                    if is_visible:
                                        # Check button text to confirm it's a notify button
                                        button_text = (await notify_elem.text_content()).strip().lower()
                                        if any(keyword in button_text for keyword in ['notify', 'notify me', 'notify when']):
                                            stock_status['in_stock'] = False
                                            stock_status['stock_status'] = 'out_of_stock'
                                            stock_status['message'] = f'Product is out of stock (Notify Me button found: {selector}, text: {button_text})'
                                            return stock_status
                            except:
                                continue
                        
                        # Also check all buttons on the page for notify text
                        try:
                            all_buttons = await page.query_selector_all('button')
                            for button in all_buttons[:20]:  # Check first 20 buttons
                                try:
                                    button_text = (await button.text_content()).strip().lower()
                                    if any(keyword in button_text for keyword in ['notify me', 'notify when available', 'notify']):
                                        is_visible = await button.is_visible()
                                        if is_visible:
                                            stock_status['in_stock'] = False
                                            stock_status['stock_status'] = 'out_of_stock'
                                            stock_status['message'] = f'Product is out of stock (Notify Me button found in page buttons)'
                                            return stock_status
                                except:
                                    continue
                        except:
                            pass
                    except:
                        pass
                    
                    # Then check page content for out-of-stock text (but be more specific)
                    # Only check in main product area, not entire page
                    try:
                        # Look for out of stock text in product details area
                        product_area = await page.query_selector('[class*="product"], [class*="pdp"], [id*="product"]')
                        if product_area:
                            product_text = (await product_area.text_content()).lower()
                            for oos_text in out_of_stock_texts:
                                if oos_text in product_text:
                                    stock_status['in_stock'] = False
                                    stock_status['stock_status'] = 'out_of_stock'
                                    stock_status['message'] = f'Product appears to be out of stock (detected in product area: "{oos_text}")'
                                    return stock_status
                        
                        # Also check entire page content for "sold out" (more aggressive check)
                        # This is a fallback if product area selector doesn't work
                        page_content_lower = content_lower
                        for oos_text in ['sold out', 'out of stock', 'currently unavailable']:
                            if oos_text in page_content_lower:
                                # Make sure it's not from unrelated content (like reviews)
                                # Check if it's near price-related elements
                                try:
                                    # Look for price elements and check nearby text
                                    price_elements = await page.query_selector_all('[class*="price"], ._30jeq3, .Nx9bqj')
                                    for price_elem in price_elements[:5]:
                                        try:
                                            # Get parent container
                                            parent = await price_elem.evaluate_handle('el => el.closest("div")')
                                            if parent:
                                                parent_text = (await parent.as_element().text_content()).lower()
                                                if oos_text in parent_text:
                                                    stock_status['in_stock'] = False
                                                    stock_status['stock_status'] = 'out_of_stock'
                                                    stock_status['message'] = f'Product appears to be out of stock (detected near price: "{oos_text}")'
                                                    return stock_status
                                        except:
                                            continue
                                except:
                                    pass
                    except:
                        pass
                else:
                    # For other sites, check for out-of-stock text in content
                    for oos_text in out_of_stock_texts:
                        if oos_text in content_lower:
                            stock_status['in_stock'] = False
                            stock_status['stock_status'] = 'out_of_stock'
                            stock_status['message'] = f'Product appears to be out of stock (detected: "{oos_text}")'
                            return stock_status
                    
                    # Check using selectors
                    for selector in selectors:
                        try:
                            element = await page.query_selector(selector)
                            if element:
                                text = (await element.text_content()).strip().lower()
                                if any(oos_text in text for oos_text in out_of_stock_texts):
                                    stock_status['in_stock'] = False
                                    stock_status['stock_status'] = 'out_of_stock'
                                    stock_status['message'] = f'Product is out of stock (selector: {selector})'
                                    return stock_status
                        except Exception:
                            continue
        except Exception:
            pass
        
        return stock_status
    
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

    def navigate_and_identify(self, driver, product_url: str, initial_site: str = None) -> tuple:
        """
        Navigate to URL, wait for redirects, capture final URL, and identify site.
        Returns: (final_url, identified_site)
        """
        print(f"  🌐 Navigating to: {product_url}")
        driver.get(product_url)
        
        # For short URLs, wait longer for redirects to complete
        is_short_url = any(domain in product_url.lower() for domain in ['myntr.it', 'fkrt.cc', 'amzn.to', 'msho.in', 'ajiio.in', 'bitli.in'])
        is_myntra_short = 'myntr.it' in product_url.lower()
        is_bitli_short = 'bitli.in' in product_url.lower()
        
        # Bitli.in short URLs may redirect to different sites (hygulife, nykaa, etc.)
        if is_bitli_short:
            print(f"  🔄 Bitli short URL detected - waiting for redirects...")
            # Wait for redirects to complete by checking if URL stabilizes
            max_redirect_wait = 20  # Maximum seconds to wait for redirects
            redirect_check_interval = 0.5
            max_checks = int(max_redirect_wait / redirect_check_interval)
            
            previous_url = driver.current_url
            stable_count = 0
            required_stable_checks = 4  # URL must be stable for 2 seconds
            
            print(f"  🔄 Waiting for redirects to complete (max {max_redirect_wait}s)...")
            for check in range(max_checks):
                time.sleep(redirect_check_interval)
                current_url = driver.current_url
                
                if current_url != previous_url:
                    print(f"  🔄 Redirect {check + 1}: {previous_url[:60]}... -> {current_url[:80]}...")
                    previous_url = current_url
                    stable_count = 0
                else:
                    stable_count += 1
                    if stable_count >= required_stable_checks:
                        print(f"  ✅ URL stabilized after {check * redirect_check_interval:.1f}s")
                        break
            
            # Additional wait for page to fully load after redirects
            time.sleep(2 + random.uniform(1, 2))
        # Myntra short URLs go through multiple redirects (3-4+), need special handling
        elif is_myntra_short:
            print(f"  🔄 Myntra short URL detected - waiting for multiple redirects...")
            # Wait for redirects to complete by checking if URL stabilizes
            max_redirect_wait = 30  # Maximum seconds to wait for redirects
            redirect_check_interval = 0.5  # Check every 0.5 seconds
            max_checks = int(max_redirect_wait / redirect_check_interval)
            
            previous_url = driver.current_url
            stable_count = 0
            required_stable_checks = 4  # URL must be stable for 2 seconds (4 * 0.5s)
            
            print(f"  🔄 Waiting for redirects to complete (max {max_redirect_wait}s)...")
            for check in range(max_checks):
                time.sleep(redirect_check_interval)
                current_url = driver.current_url
                
                if current_url != previous_url:
                    print(f"  🔄 Redirect {check + 1}: {previous_url[:60]}... -> {current_url[:80]}...")
                    previous_url = current_url
                    stable_count = 0  # Reset stability counter
                else:
                    stable_count += 1
                    if stable_count >= required_stable_checks:
                        print(f"  ✅ URL stabilized after {check * redirect_check_interval:.1f}s")
                        break
            
            # Additional wait for page to fully load after redirects
            time.sleep(2 + random.uniform(1, 2))
        else:
            wait_time = random.uniform(5, 8) if is_short_url else random.uniform(3, 6)
            time.sleep(wait_time)
        
        # Capture final URL after navigation and redirects
        final_url = driver.current_url
        if final_url != product_url:
            print(f"  🔄 Final redirect: {product_url[:50]}... -> {final_url[:100]}...")
        
        print(f"  📍 Final URL after navigation: {final_url[:100]}...")
        
        # Identify site from final URL
        identified_site = self.identify_site(final_url)
        
        if initial_site:
            if identified_site != initial_site and identified_site != 'generic':
                print(f"  🔄 Site identified: {initial_site} -> {identified_site} (from final URL)")
        else:
            print(f"  🏷️  Site identified: {identified_site} (from final URL)")
        
        return final_url, identified_site
    
    def scrape_with_selenium(self, product_url: str, site: str = None, use_virtual_display: bool = False) -> str:
        """
        Generic Selenium scraper for sites that block Playwright.
        New flow: Navigate → Capture final URL → Identify site → Extract price
        """
        # Don't create a new virtual display here - it should already be set up
        # by scrape_product_price if use_virtual_display is True
        # The DISPLAY environment variable will be inherited from the parent process
        vdisplay = None  # Not managing virtual display here - it's managed at a higher level
        
        # Try site-specific Selenium modules first (only if we know the site from initial URL)
        # Use site if provided, otherwise identify from URL
        site_to_use = site if site is not None else self.identify_site(product_url)
        
        # Don't clean up Chrome processes here - it would kill active processes from concurrent requests
        # Only cleanup happens after driver.quit() in cleanup_chrome_driver()
        
        if site_to_use == 'nykaa':
            try:
                from scrapers.selenium.nykaa_selenium import scrape_nykaa_with_selenium
                price = scrape_nykaa_with_selenium(product_url)
                if price and price != 'N/A':
                    if vdisplay:
                        vdisplay.stop()
                    return price
            except ImportError:
                pass
            except Exception as e:
                print(f"⚠️  Error in nykaa_selenium: {e}")
        elif site_to_use == 'meesho':
            try:
                from scrapers.selenium.meesho_selenium import scrape_meesho_with_selenium
                price = scrape_meesho_with_selenium(product_url)
                if price and price != 'N/A':
                    # Don't stop virtual display here - it's managed at a higher level
                    return price
                # If price not found, fall through to inline Selenium
                print("⚠️  Meesho-specific scraper did not find price, falling back to inline Selenium")
            except ImportError:
                pass
            except Exception as e:
                print(f"⚠️  Error in meesho_selenium: {e}, falling back to inline Selenium")
                # Fall through to inline Selenium
        elif site_to_use == 'ajio':
            try:
                from scrapers.selenium.ajio_selenium import scrape_ajio_with_selenium
                price = scrape_ajio_with_selenium(product_url)
                if price and price != 'N/A':
                    if vdisplay:
                        vdisplay.stop()
                    return price
                # If price not found, fall through to inline Selenium (don't stop vdisplay yet)
                print("⚠️  Ajio-specific scraper did not find price, falling back to inline Selenium")
            except ImportError:
                pass
            except Exception as e:
                print(f"⚠️  Error in ajio_selenium: {e}, falling back to inline Selenium")
                # Fall through to inline Selenium
        elif site_to_use == 'myntra':
            try:
                from scrapers.selenium.myntra_selenium import scrape_myntra_with_selenium
                from urllib3.exceptions import ProtocolError
                from http.client import RemoteDisconnected
                
                # Retry logic for connection errors
                max_retries = 3
                last_error = None
                for attempt in range(max_retries):
                    try:
                        price = scrape_myntra_with_selenium(product_url, max_retries=1)  # Let function handle its own retries
                        if price and price != 'N/A':
                            if vdisplay:
                                vdisplay.stop()
                            return price
                        # If price not found, fall through to inline Selenium
                        print("⚠️  Myntra-specific scraper did not find price, falling back to inline Selenium")
                        break
                    except (ProtocolError, RemoteDisconnected, ConnectionError, OSError) as e:
                        last_error = e
                        if attempt < max_retries - 1:
                            import time
                            import random
                            wait_time = random.uniform(2, 5) * (attempt + 1)
                            time.sleep(wait_time)
                            continue
                        else:
                            # Fall through to inline Selenium
                            print(f"⚠️  Myntra scraper connection error after {max_retries} attempts, falling back to inline Selenium")
                            break
                    except Exception as e:
                        print(f"⚠️  Error in myntra_selenium (attempt {attempt + 1}): {e}")
                        if attempt < max_retries - 1:
                            continue
                        # Fall through to inline Selenium
                        break
            except ImportError:
                pass
            except Exception as e:
                print(f"⚠️  Error importing myntra_selenium: {e}, falling back to inline Selenium")
                # Fall through to inline Selenium
        
        # Fallback to inline Selenium implementation
        try:
            import undetected_chromedriver as uc
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            
            options = uc.ChromeOptions()
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            
            if use_virtual_display and vdisplay:
                # Configure for virtual display (no headless needed)
                try:
                    from virtual_display import setup_virtual_display_for_selenium
                    setup_virtual_display_for_selenium(options)
                except ImportError:
                    pass
            
            driver = uc.Chrome(options=options, version_main=None)
            
            try:
                price_value = 'N/A'
                # NEW FLOW: Navigate → Capture final URL → Identify site → Extract price
                # Use site_to_use if available, otherwise identify from URL
                initial_site_for_nav = site_to_use if 'site_to_use' in locals() else (site if site is not None else self.identify_site(product_url))
                final_url, identified_site = self.navigate_and_identify(driver, product_url, initial_site_for_nav)
                site = identified_site  # Use the identified site from final URL
                
                # Reduce wait timeout to prevent hanging - use shorter waits
                wait = WebDriverWait(driver, 10)  # Reduced from 15 to 10 seconds
                
                # Site-specific selectors based on identified site
                if site == 'amazon':
                    print(f"\n🔍 [DEBUG] Starting Amazon price extraction for: {final_url}")
                    
                    # Top priority: Check hidden input field with price (most reliable)
                    try:
                        hidden_price_input = WebDriverWait(driver, 3).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, 'input[type="hidden"][name="items[0.base][customerVisiblePrice][amount]"]'))
                        )
                        price_value = hidden_price_input.get_attribute('value')
                        if price_value:
                            try:
                                price_float = float(price_value)
                                print(f"  ✓ Found hidden input price: ₹{price_value}")
                                # Require minimum 10 to avoid picking up non-price numbers, but allow low prices
                                if 10 <= price_float <= 10000000:
                                    # Special handling: if price is exactly 500, check for higher price (might be variant)
                                    if price_float == 500:
                                        print(f"    ⚠️  WARNING: Price is 500 - checking for higher main price...")
                                        # Try to find a higher price in buybox
                                        try:
                                            buybox = driver.find_element(By.ID, 'buybox')
                                            all_prices = buybox.find_elements(By.CSS_SELECTOR, '.a-price .a-offscreen, .a-price .a-price-whole')
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
                                                main_price_val = str(int(higher_prices[0][0]))
                                                print(f"    ✅ Found higher main price: ₹{main_price_val} (ignoring 500)")
                                                return main_price_val
                                        except:
                                            pass
                                    print(f"  ✅ Using hidden input price: ₹{price_value}")
                                    return price_value
                                else:
                                    print(f"  ⚠️  Hidden input price {price_value} failed validation (not in range 10-10000000)")
                            except:
                                pass
                    except Exception as e:
                        print(f"  ℹ️  Hidden input not found: {str(e)[:50]}")
                    
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
                    
                    print(f"  🔎 Checking {len(priority_selectors)} priority selectors...")
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
                                        print(f"  📍 Found via '{selector_name}': ₹{price_value} (text: '{text[:50]}')")
                                        
                                        # Additional validation: check if element is in buybox or price block
                                        try:
                                            parent = price_elem.find_element(By.XPATH, './ancestor::*[contains(@class, "buybox") or contains(@id, "price") or contains(@id, "buy")]')
                                            if parent:
                                                parent_class = parent.get_attribute('class') or ''
                                                parent_id = parent.get_attribute('id') or ''
                                                print(f"    Parent context: class='{parent_class[:50]}', id='{parent_id[:50]}'")
                                        except:
                                            pass
                                        
                                        # Require minimum 10 to avoid picking up non-price numbers
                                        if 10 <= price_float <= 10000000:
                                            # Additional check: if price is exactly 500, it might be a variant/unit price
                                            # Check if there's a higher price nearby (main price is usually higher)
                                            if price_float == 500:
                                                print(f"    ⚠️  WARNING: Price is 500 - might be variant/unit price, checking for main price...")
                                                # Try to find a higher price in the buybox
                                                try:
                                                    buybox = driver.find_element(By.ID, 'buybox')
                                                    all_prices = buybox.find_elements(By.CSS_SELECTOR, '.a-price .a-offscreen, .a-price .a-price-whole')
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
                                                        main_price_val = str(int(higher_prices[0][0]))
                                                        print(f"    ✅ Found higher main price: ₹{main_price_val} (ignoring 500)")
                                                        return main_price_val
                                                    else:
                                                        print(f"    ⚠️  No higher price found, but 500 might be incorrect")
                                                except:
                                                    pass
                                            
                                            print(f"    ✅ Using price from '{selector_name}': ₹{price_value}")
                                            return price_value
                                        else:
                                            print(f"    ❌ Price {price_value} failed validation (not in range 10-10000000)")
                                    except Exception as e:
                                        print(f"    ❌ Error validating price: {str(e)[:50]}")
                        except Exception as e:
                            continue  # Fast fail, move to next
                    
                    print(f"  🔎 Checking {len(fallback_selectors)} fallback selectors...")
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
                                        print(f"  📍 Found via '{selector_name}': ₹{price_value} (text: '{text[:50]}')")
                                        
                                        # Require minimum 10 to avoid picking up non-price numbers
                                        if 10 <= price_float <= 10000000:
                                            # Skip 500 as it's likely a variant/unit price
                                            if price_float == 500:
                                                print(f"    ⚠️  Skipping 500 - likely variant/unit price, not main product price")
                                                continue
                                            print(f"    ✅ Using price from '{selector_name}': ₹{price_value}")
                                            return price_value
                                        else:
                                            print(f"    ❌ Price {price_value} failed validation")
                                    except:
                                        pass
                        except:
                            continue
                    
                    # Quick buybox check (already loaded, no wait needed)
                    try:
                        buybox = driver.find_element(By.ID, 'buybox')
                        if buybox:
                            print(f"  🔎 Checking buybox for prices...")
                            # Use find_elements directly (no wait needed, element exists)
                            price_in_buybox = buybox.find_elements(By.CSS_SELECTOR, '.a-price.priceToPay .a-offscreen, .a-price.priceToPay .a-price-whole')
                            found_prices = []
                            for price_elem in price_in_buybox[:5]:  # Check more elements
                                try:
                                    text = price_elem.text.strip()
                                    if text and '₹' in text:
                                        price_match = re.search(r'₹\s*([\d,]+(?:\.\d{1,2})?)', text)
                                        if price_match:
                                            price_value = price_match.group(1).replace(',', '')
                                            try:
                                                price_float = float(price_value)
                                                if 10 <= price_float <= 10000000:
                                                    found_prices.append((price_float, price_value, text))
                                            except:
                                                pass
                                except:
                                    continue
                            
                            if found_prices:
                                # Sort by price, highest first (main price is usually highest)
                                found_prices.sort(key=lambda x: x[0], reverse=True)
                                for price_float, price_value, text in found_prices:
                                    print(f"  📍 Buybox price: ₹{price_value} (text: '{text[:50]}')")
                                    # Skip 500 if there's a higher price
                                    if price_float == 500 and len(found_prices) > 1:
                                        print(f"    ⚠️  Skipping 500, using higher price instead")
                                        continue
                                    print(f"    ✅ Using buybox price: ₹{price_value}")
                                    return price_value
                    except Exception as e:
                        print(f"  ℹ️  Buybox check failed: {str(e)[:50]}")
                    
                    print(f"  ❌ No valid price found for Amazon product")
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
                    # Meesho typically shows main price in h4 element with class 'sc-dOfePm haKcEH'
                    try:
                        # First try to find h4 with the specific class that contains main price
                        # Try to find element without waiting first (faster)
                        try:
                            price_elems = driver.find_elements(By.CSS_SELECTOR, "h4.sc-dOfePm.haKcEH")
                            if not price_elems:
                                # Only wait if element not found immediately
                                try:
                                    price_elem = wait.until(
                                        EC.presence_of_element_located((By.CSS_SELECTOR, "h4.sc-dOfePm.haKcEH"))
                                    )
                                    price_elems = [price_elem]
                                except:
                                    price_elems = []
                            
                            if price_elems:
                                price_elem = price_elems[0]
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
                            # Fallback: try any h4 element with price
                            h4_elements = driver.find_elements(By.XPATH, "//h4[contains(text(), '₹')]")
                            if not h4_elements:
                                # Only wait if elements not found immediately
                                try:
                                    h4_elements = wait.until(
                                        EC.presence_of_all_elements_located((By.XPATH, "//h4[contains(text(), '₹')]"))
                                    )
                                except:
                                    h4_elements = []
                            
                            # Find the main product price (first valid one)
                            for price_elem in h4_elements:
                                try:
                                    text = price_elem.text.strip()
                                    if text and '₹' in text and len(text) < 50:  # Main price is usually short
                                        price_match = re.search(r'₹\s*([\d,]+(?:\.\d{1,2})?)', text)
                                        if price_match:
                                            price_value = price_match.group(1).replace(',', '')
                                            try:
                                                price_float = float(price_value)
                                                # Main product price is usually reasonable (50-100000)
                                                if 50 <= price_float <= 100000:
                                                    return price_value
                                            except:
                                                continue
                                except:
                                    continue
                            
                            # If no valid price found in loop, try first element
                            if h4_elements:
                                text = h4_elements[0].text.strip()
                                if text and '₹' in text:
                                    price_match = re.search(r'₹\s*([\d,]+(?:\.\d{1,2})?)', text)
                                    if price_match:
                                        price_value = price_match.group(1).replace(',', '')
                                        try:
                                            if float(price_value) > 50:
                                                return price_value
                                        except:
                                            pass
                    except Exception as e:
                        # If h4 fails, try alternative selectors
                        try:
                            # Try span elements with price
                            price_elem = wait.until(
                                EC.presence_of_element_located((By.XPATH, "//span[contains(text(), '₹')]"))
                            )
                            text = price_elem.text.strip()
                            if text and '₹' in text and len(text) < 50:
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
                        # Try to find element without waiting first (faster)
                        selling_price_elems = driver.find_elements(By.CSS_SELECTOR, ".prod-sp")
                        if not selling_price_elems:
                            # Only wait if element not found immediately
                            try:
                                selling_price_elem = wait.until(
                                    EC.presence_of_element_located((By.CSS_SELECTOR, ".prod-sp"))
                                )
                                selling_price_elems = [selling_price_elem]
                            except:
                                selling_price_elems = []
                        
                        if selling_price_elems:
                            selling_price_elem = selling_price_elems[0]
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
                        # Try discounted price first - try to find element without waiting first (faster)
                        price_elems = driver.find_elements(By.CSS_SELECTOR, ".pdp-discounted-price")
                        if not price_elems:
                            # Only wait if element not found immediately
                            try:
                                price_elem = wait.until(
                                    EC.presence_of_element_located((By.CSS_SELECTOR, ".pdp-discounted-price"))
                                )
                                price_elems = [price_elem]
                            except:
                                price_elems = []
                        
                        if price_elems:
                            price_elem = price_elems[0]
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
                            price_elems = driver.find_elements(By.CSS_SELECTOR, ".pdp-price")
                            if not price_elems:
                                # Only wait if element not found immediately
                                try:
                                    price_elem = wait.until(
                                        EC.presence_of_element_located((By.CSS_SELECTOR, ".pdp-price"))
                                    )
                                    price_elems = [price_elem]
                                except:
                                    price_elems = []
                            
                            if price_elems:
                                price_elem = price_elems[0]
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
                    # For Amazon, all specific selectors have been tried above
                    # Don't fall through to generic fallbacks to avoid picking up non-price numbers
                
                elif site == 'flipkart':
                    # Flipkart-specific price extraction with discount filtering
                    flipkart_selectors = ['._30jeq3', '.Nx9bqj', '._16Jk6d', '._1vC4OE', '._3qQ9m1']
                    found_prices = []
                    
                    # Try Flipkart-specific selectors first
                    for selector in flipkart_selectors:
                        try:
                            # Try to find elements without waiting first (faster)
                            price_elems = driver.find_elements(By.CSS_SELECTOR, selector)
                            if not price_elems:
                                # Only wait if elements not found immediately
                                try:
                                    price_elems = wait.until(
                                        EC.presence_of_all_elements_located((By.CSS_SELECTOR, selector))
                                    )
                                except:
                                    price_elems = []
                            for price_elem in price_elems[:5]:  # Check first 5 matches
                                text = price_elem.text.strip()
                                if text and '₹' in text:
                                    price_match = re.search(r'₹\s*([\d,]+(?:\.\d{1,2})?)', text)
                                    if price_match:
                                        price_value = price_match.group(1).replace(',', '')
                                        try:
                                            price_float = float(price_value)
                                            # Flipkart prices should be reasonable (>= 50)
                                            if 50 <= price_float <= 10000000:
                                                found_prices.append((price_float, price_value, text))
                                        except:
                                            continue
                        except:
                            continue
                    
                    # If found prices, return the highest (main product price)
                    if found_prices:
                        found_prices.sort(key=lambda x: x[0], reverse=True)
                        print(f"  ✅ Found Flipkart price: ₹{found_prices[0][1]} (from {len(found_prices)} matches)")
                        return found_prices[0][1]
                    
                    # Fallback: search all elements but filter out discount text
                    try:
                        all_price_elems = driver.find_elements(By.XPATH, "//*[contains(text(), '₹')]")
                        found_prices = []
                        for price_elem in all_price_elems[:50]:  # Check first 50
                            try:
                                text = price_elem.text.strip()
                                # Skip discount/offer text
                                if text and ('off' in text.lower() or 'discount' in text.lower() or 'extra' in text.lower()):
                                    continue
                                
                                if text and '₹' in text and len(text) < 100:
                                    price_match = re.search(r'₹\s*([\d,]+(?:\.\d{1,2})?)', text)
                                    if price_match:
                                        price_value = price_match.group(1).replace(',', '')
                                        try:
                                            price_float = float(price_value)
                                            if 50 <= price_float <= 10000000:
                                                found_prices.append((price_float, price_value, text))
                                        except:
                                            continue
                            except:
                                continue
                        
                        # Return highest price (main product price)
                        if found_prices:
                            found_prices.sort(key=lambda x: x[0], reverse=True)
                            print(f"  ✅ Found Flipkart price (fallback): ₹{found_prices[0][1]}")
                            return found_prices[0][1]
                    except:
                        pass
                
                # Generic fallback: try any element with ₹ (only for non-Amazon sites)
                if site != 'amazon' and site != 'flipkart':
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
                    
                    # Last resort: regex on page source (only for non-Amazon sites)
                    if site != 'amazon' and site != 'flipkart':
                        page_source = driver.page_source
                        price_match = re.search(r'₹\s*([\d,]+(?:\.\d{1,2})?)', page_source)
                        if price_match:
                            price_value = price_match.group(1).replace(',', '')
                            try:
                                if float(price_value) > 50:
                                    return price_value
                            except:
                                pass
                
                # If no price was found, set to 'N/A'
                if found_price_value is None:
                    found_price_value = 'N/A'

            finally:
                # Extract additional details
                details = self.extract_product_details(driver, site)
                
                # Check stock status
                stock_status = self.check_stock_status(driver.page_source, driver.title, site, driver=driver)
                
                # Clean up
                try:
                     from chrome_cleanup import cleanup_chrome_driver
                     cleanup_chrome_driver(driver)
                except ImportError:
                     # Fallback to standard cleanup if utility not found
                     try:
                         driver.quit()
                     except:
                         try:
                             driver.close()
                         except:
                             pass
                except Exception as e:
                    print(f"  ⚠️  Error during driver cleanup: {e}")
                finally: # This finally block is for the inner try-except for driver cleanup
                    if vdisplay:
                        vdisplay.stop()
                        
                result = {
                    'price': price_value,
                    'stock_status': stock_status
                }
                result.update(details)
                return result
        except Exception as e:
            # Ensure cleanup even on exception
            try:
                if 'driver' in locals() and driver:
                    try:
                        from chrome_cleanup import cleanup_chrome_driver
                        cleanup_chrome_driver(driver)
                    except ImportError:
                        try:
                            driver.quit()
                        except:
                            pass
            except:
                pass
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

    async def navigate_and_identify_async(self, page, product_url: str, initial_site: str = None) -> tuple:
        """
        Navigate to URL, wait for redirects, capture final URL, and identify site (async for Playwright).
        Returns: (final_url, identified_site)
        """
        print(f"  🌐 Navigating to: {product_url}")
        
        # For short URLs, wait for networkidle to ensure redirects complete
        # For regular URLs, use domcontentloaded for faster loading
        is_short_url = any(domain in product_url.lower() for domain in ['myntr.it', 'fkrt.cc', 'amzn.to', 'msho.in', 'ajiio.in', 'bitli.in'])
        is_amazon_short = 'amzn.to' in product_url.lower()
        is_myntra_short = 'myntr.it' in product_url.lower()
        is_bitli_short = 'bitli.in' in product_url.lower()
        is_flipkart_short = 'fkrt.cc' in product_url.lower()
        
        # Bitli.in short URLs may redirect to different sites (hygulife, nykaa, etc.), handle similar to Myntra
        if is_bitli_short:
            print(f"  🔄 Bitli short URL detected - waiting for redirects...")
            try:
                # Start navigation with domcontentloaded
                await page.goto(product_url, timeout=90000, wait_until='domcontentloaded')
                
                # Wait for redirects to complete by checking if URL stabilizes
                max_redirect_wait = 20  # Maximum seconds to wait for redirects
                redirect_check_interval = 0.5
                max_checks = int(max_redirect_wait / redirect_check_interval)
                
                previous_url = page.url
                stable_count = 0
                required_stable_checks = 4  # URL must be stable for 2 seconds
                
                print(f"  🔄 Waiting for redirects to complete (max {max_redirect_wait}s)...")
                for check in range(max_checks):
                    await asyncio.sleep(redirect_check_interval)
                    current_url = page.url
                    
                    if current_url != previous_url:
                        print(f"  🔄 Redirect {check + 1}: {previous_url[:60]}... -> {current_url[:80]}...")
                        previous_url = current_url
                        stable_count = 0
                    else:
                        stable_count += 1
                        if stable_count >= required_stable_checks:
                            print(f"  ✅ URL stabilized after {check * redirect_check_interval:.1f}s")
                            break
                
                # Additional wait for page to fully load after redirects
                await asyncio.sleep(2 + random.uniform(1, 2))
                
            except Exception as e:
                print(f"  ⚠️  Bitli navigation error: {str(e)[:100]}")
                try:
                    await page.goto(product_url, timeout=90000, wait_until='load')
                    await asyncio.sleep(3 + random.uniform(1, 2))
                except Exception as e2:
                    print(f"  ⚠️  Load state also failed: {str(e2)[:100]}")
                    await asyncio.sleep(5)
        # Myntra short URLs go through multiple redirects (3-4+), need special handling
        elif is_myntra_short:
            print(f"  🔄 Myntra short URL detected - waiting for multiple redirects...")
            try:
                # Start navigation with domcontentloaded (faster initial load)
                await page.goto(product_url, timeout=90000, wait_until='domcontentloaded')
                
                # Wait for redirects to complete by checking if URL stabilizes
                # Myntra can have 3-4+ redirects, so we need to wait for URL to stop changing
                max_redirect_wait = 30  # Maximum seconds to wait for redirects
                redirect_check_interval = 0.5  # Check every 0.5 seconds
                max_checks = int(max_redirect_wait / redirect_check_interval)
                
                previous_url = page.url
                stable_count = 0
                required_stable_checks = 4  # URL must be stable for 2 seconds (4 * 0.5s)
                
                print(f"  🔄 Waiting for redirects to complete (max {max_redirect_wait}s)...")
                for check in range(max_checks):
                    await asyncio.sleep(redirect_check_interval)
                    current_url = page.url
                    
                    if current_url != previous_url:
                        print(f"  🔄 Redirect {check + 1}: {previous_url[:60]}... -> {current_url[:80]}...")
                        previous_url = current_url
                        stable_count = 0  # Reset stability counter
                    else:
                        stable_count += 1
                        if stable_count >= required_stable_checks:
                            print(f"  ✅ URL stabilized after {check * redirect_check_interval:.1f}s")
                            break
                
                # Additional wait for page to fully load after redirects
                await asyncio.sleep(2 + random.uniform(1, 2))
                
            except Exception as e:
                print(f"  ⚠️  Myntra navigation error: {str(e)[:100]}")
                # Fallback: try with load state
                try:
                    await page.goto(product_url, timeout=90000, wait_until='load')
                    await asyncio.sleep(3 + random.uniform(1, 2))
                except Exception as e2:
                    print(f"  ⚠️  Load state also failed: {str(e2)[:100]}")
                    # Last resort: just wait
                    await asyncio.sleep(5)
        # Flipkart short URLs (fkrt.cc) may have redirects, handle similar to Myntra
        elif is_flipkart_short:
            print(f"  🔄 Flipkart short URL detected (fkrt.cc) - waiting for redirects...")
            try:
                # Start navigation with domcontentloaded
                await page.goto(product_url, timeout=90000, wait_until='domcontentloaded')
                
                # Wait for redirects to complete by checking if URL stabilizes
                max_redirect_wait = 20  # Maximum seconds to wait for redirects
                redirect_check_interval = 0.5
                max_checks = int(max_redirect_wait / redirect_check_interval)
                
                previous_url = page.url
                stable_count = 0
                required_stable_checks = 4  # URL must be stable for 2 seconds
                
                print(f"  🔄 Waiting for redirects to complete (max {max_redirect_wait}s)...")
                for check in range(max_checks):
                    await asyncio.sleep(redirect_check_interval)
                    current_url = page.url
                    
                    if current_url != previous_url:
                        print(f"  🔄 Redirect {check + 1}: {previous_url[:60]}... -> {current_url[:80]}...")
                        previous_url = current_url
                        stable_count = 0
                    else:
                        stable_count += 1
                        if stable_count >= required_stable_checks:
                            print(f"  ✅ URL stabilized after {check * redirect_check_interval:.1f}s")
                            break
                
                # Additional wait for page to fully load after redirects
                await asyncio.sleep(2 + random.uniform(1, 2))
                
            except Exception as e:
                print(f"  ⚠️  Flipkart navigation error: {str(e)[:100]}")
                try:
                    await page.goto(product_url, timeout=90000, wait_until='load')
                    await asyncio.sleep(3 + random.uniform(1, 2))
                except Exception as e2:
                    print(f"  ⚠️  Load state also failed: {str(e2)[:100]}")
                    await asyncio.sleep(5)
        # Amazon short URLs can be slow, use shorter timeout and fallback faster
        elif is_amazon_short:
            # Try networkidle with shorter timeout for Amazon short URLs
            try:
                await page.goto(product_url, timeout=30000, wait_until='networkidle')
            except Exception as e:
                # If networkidle times out quickly, fallback to domcontentloaded
                print(f"  ⚠️  Networkidle timeout for Amazon short URL, trying domcontentloaded: {str(e)[:100]}")
                try:
                    await page.goto(product_url, timeout=60000, wait_until='domcontentloaded')
                except Exception as e2:
                    # If that also fails, try load state
                    print(f"  ⚠️  Domcontentloaded also failed, trying load: {str(e2)[:100]}")
                    await page.goto(product_url, timeout=60000, wait_until='load')
        elif is_short_url:
            # For other short URLs, try networkidle with longer timeout
            try:
                await page.goto(product_url, timeout=60000, wait_until='networkidle')
            except Exception as e:
                # If networkidle times out, try with domcontentloaded
                print(f"  ⚠️  Networkidle timeout, trying domcontentloaded: {str(e)[:100]}")
                await page.goto(product_url, timeout=60000, wait_until='domcontentloaded')
        else:
            # Regular URLs use domcontentloaded
            await page.goto(product_url, timeout=60000, wait_until='domcontentloaded')
        
        # Wait for redirects and page load (longer wait for short URLs, but Myntra, Bitli, and Flipkart already handled above)
        if not is_myntra_short and not is_bitli_short and not is_flipkart_short:
            wait_time = 5 + random.uniform(2, 4) if is_short_url else 3 + random.uniform(1, 3)
            await asyncio.sleep(wait_time)
        
        # Check if URL changed (redirect happened)
        final_url = page.url
        if final_url != product_url:
            print(f"  🔄 Final redirect: {product_url[:50]}... -> {final_url[:100]}...")
        
        print(f"  📍 Final URL after navigation: {final_url[:100]}...")
        
        # Identify site from final URL
        # Check if Bitli redirects to Nykaa (linkredirect.in with nykaa in URL)
        if is_bitli_short and 'linkredirect.in' in final_url.lower() and 'nykaa' in final_url.lower():
            # Extract the actual destination URL from linkredirect
            try:
                from urllib.parse import parse_qs, urlparse
                parsed = urlparse(final_url)
                params = parse_qs(parsed.query)
                if 'dl' in params:
                    dest_url = params['dl'][0]
                    # Decode URL if needed
                    import urllib.parse
                    dest_url = urllib.parse.unquote(dest_url)
                    print(f"  🔄 Bitli redirects to Nykaa: {dest_url[:80]}...")
                    identified_site = self.identify_site(dest_url)
                    
                    # Navigate to the actual destination URL
                    print(f"  🌐 Navigating to actual Nykaa product page...")
                    try:
                        await page.goto(dest_url, timeout=60000, wait_until='domcontentloaded')
                        await asyncio.sleep(2 + random.uniform(1, 2))
                        final_url = page.url
                        print(f"  📍 Final destination URL: {final_url[:100]}...")
                    except Exception as nav_error:
                        print(f"  ⚠️  Could not navigate to destination: {nav_error}")
                        # Continue with linkredirect URL if navigation fails
                else:
                    identified_site = self.identify_site(final_url)
            except Exception as e:
                print(f"  ⚠️  Could not parse redirect URL: {e}")
                identified_site = self.identify_site(final_url)
        else:
            identified_site = self.identify_site(final_url)
        
        if initial_site:
            if identified_site != initial_site and identified_site != 'generic':
                print(f"  🔄 Site identified: {initial_site} -> {identified_site} (from final URL)")
        else:
            print(f"  🏷️  Site identified: {identified_site} (from final URL)")
        
        return final_url, identified_site
    
    async def scrape_product_price(self, playwright: Playwright, product_url: str, 
                                   force_selenium: bool = False, use_virtual_display: bool = False,
                                   force_playwright: bool = False) -> Dict:
        # NEW FLOW: Will identify site after navigation
        initial_site = self.identify_site(product_url)
        site = initial_site  # Will be updated after navigation
        
        # Setup virtual display early if requested (needed for both Playwright and Selenium)
        vdisplay = None
        if use_virtual_display:
            try:
                from virtual_display import VirtualDisplay
                vdisplay = VirtualDisplay()
                if vdisplay.start():
                    # Give virtual display a moment to fully initialize
                    import time
                    time.sleep(1)
                    # Verify DISPLAY is set
                    import os
                    if os.environ.get('DISPLAY'):
                        print(f"✅ Virtual display ready: DISPLAY={os.environ.get('DISPLAY')}")
                    else:
                        print("⚠️  Virtual display started but DISPLAY not set")
                else:
                    vdisplay = None  # Fallback if virtual display fails
            except ImportError:
                print("⚠️  virtual_display module not available, running without virtual display")
            except Exception as e:
                print(f"⚠️  Error setting up virtual display: {e}")
                vdisplay = None
        
        # PRIMARY STRATEGY: Selenium (undetected_chromedriver)
        # We attempt this first as it is more robust against bot protections like Cloudflare/Akamai
        if not force_playwright:
             # Add timeout for Selenium operations to prevent hanging
            selenium_timeout = 120.0 if site in ['meesho', 'myntra', 'ajio'] else 90.0
            try:
                price = await asyncio.wait_for(
                    asyncio.to_thread(self.scrape_with_selenium, product_url, site, use_virtual_display),
                    timeout=selenium_timeout
                )
            except asyncio.TimeoutError:
                print(f"⚠️  Selenium operation timed out after {selenium_timeout}s for {site}")
                price = 'N/A'
            except Exception as e:
                print(f"⚠️  Selenium error: {e}")
                price = 'N/A'

            # If successful, or if force_selenium is True, return immediately
            if (isinstance(price, dict) or (price != 'N/A' and price is not None)) or force_selenium:
                 # Stop virtual display if it was started
                if vdisplay:
                    try:
                        vdisplay.stop()
                    except:
                        pass
                
                # Handle dictionary return (Generic Selenium path)
                if isinstance(price, dict):
                    result_data = price
                    extracted_price = result_data.get('price', 'N/A')
                    stock_status = result_data.get('stock_status', {'in_stock': True, 'stock_status': 'in_stock', 'message': None})
                    details = {k: v for k, v in result_data.items() if k not in ['price', 'stock_status']}
                else:
                    # Handle string return (Site-specific scrapers)
                    extracted_price = price if price is not None else 'N/A'
                    stock_status = {'in_stock': True, 'stock_status': 'in_stock', 'message': None}
                    # For string returns, we don't have details, trying to fetch if possible or leave empty
                    details = self.extract_product_details(None, site)

                # Check if price is valid number (and not N/A)
                success = extracted_price != 'N/A' and extracted_price is not None
                
                # If valid price but stock_status says out of stock, success might be False depending on logic
                # But usually if price is found, we consider it partial success. 
                # Be careful: If price is N/A, and stock is OOS, status should satisfy user.
                
                final_status = 'success (Selenium)' if success else 'Price not found'
                if not success and stock_status.get('stock_status') == 'out_of_stock':
                     final_status = 'Product is out of stock'
                
                return {
                    'url': product_url,
                    'site': site,
                    'price': extracted_price,
                    'status': final_status,
                    'method': 'selenium',
                    'stock_status': stock_status,
                    'success': success, # Success implies price found. OOS with no price is technically success=False for price, but we found status.
                     **details
                }
                    
            print(f"  ⚠️  Selenium failed to find price, falling back to Playwright...")
        
        # SECONDARY STRATEGY: Playwright
        # Fallback if Selenium failed or if force_playwright is True
        browser = None
        context = None
        
        try:
            # Ensure DISPLAY is set for Playwright's subprocess
            import os
            env = os.environ.copy()
            # Only use headed mode if virtual display is actually active
            # If virtual display was requested but failed, fall back to headless
            use_headed = False
            if use_virtual_display and vdisplay and vdisplay.is_active:
                env['DISPLAY'] = vdisplay.display_var
                use_headed = True
            elif use_virtual_display and (not vdisplay or not vdisplay.is_active):
                # Virtual display was requested but failed, use headless mode
                print("⚠️  Virtual display failed, falling back to headless mode")
                use_headed = False
            
            # Launch with heavy stealth args
            browser = await playwright.chromium.launch(
                headless=not use_headed, 
                env=env,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-infobars',
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-extensions',
                    '--disable-dev-shm-usage',
                    '--disable-accelerated-2d-canvas',
                    '--no-first-run',
                    '--no-zygote',
                    '--disable-gpu'
                ]
            )
            context = await browser.new_context(
                ignore_https_errors=True,
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={'width': 1920, 'height': 1080}
            )
            
            # Inject stealth scripts to hide automation
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)
            
            page = await context.new_page()
            
            # Navigate & Identify
            blocked = False
            try:
                final_url, identified_site = await self.navigate_and_identify_async(page, product_url, initial_site)
                site = identified_site  # Use the identified site from final URL
                
                # Check for blocking indicators
                try:
                    page_content = await page.content()
                    page_title = await page.title()
                    
                    # Amazon Continue Shopping
                    if site == 'amazon' and ('continue shopping' in page_content.lower() or 'continue shopping' in page_title.lower()):
                         blocked = True
                    
                    # Nykaa 404
                    if site == 'nykaa' and ('ek 404' in page_title.lower() or '404' in page_title.lower()):
                        # 404 is not "blocked", it's just not found.
                        # Return early.
                        if context: await context.close()
                        if browser: await browser.close()
                        if vdisplay: 
                            try: vdisplay.stop() 
                            except: pass
                        return {
                            'url': product_url,
                            'site': site,
                            'price': 'N/A',
                            'status': 'Product page not found (404)',
                            'method': 'playwright',
                            'stock_status': {'in_stock': False, 'stock_status': 'not_found', 'message': 'Product page not found'},
                            'success': False
                        }

                    # Blocking Keywords
                    if any(indicator in page_content.lower() or indicator in page_title.lower() 
                            for indicator in ['access denied', 'blocked', 'forbidden', 'cloudflare', 'captcha']):
                         blocked = True
                         
                except Exception:
                    blocked = True
            except Exception:
                blocked = True
            
            if blocked:
                 print(f"  ⚠️  Playwright blocked as well.")
                 if context: await context.close()
                 if browser: await browser.close()
                 if vdisplay: 
                    try: vdisplay.stop() 
                    except: pass
                 return {
                    'url': product_url,
                    'site': site,
                    'price': 'N/A',
                    'status': 'Blocked (Both Selenium and Playwright failed)',
                    'method': 'playwright',
                    'reason': 'Blocked',
                    'stock_status': {'in_stock': True, 'stock_status': 'unknown', 'message': None},
                    'success': False,
                     **self.extract_product_details(None, site)
                }
            
            # If we are here, Playwright is successful (page is open).
            # Check stock & details
            stock_status = await self.check_stock_status_async(page, site)
            details = await self.extract_product_details_async(page, site)
            
            # Prepare result dictionary for fall-through
            # The 'price' field will be populated by the strategies below
            result = {
                'url': product_url,
                'site': site,
                'price': None,
                'status': 'success',
                'method': 'playwright',
                'stock_status': stock_status,
                'success': False # Will be updated if price found
            }
            result.update(details)
            
            # FALL THROUGH to extraction strategies (lines 1960+)
            # Do NOT close browser here; it is needed for strategies.
            # Browser will be closed in finally block at end of function.
            
            price_selectors = self.site_selectors.get(site, ['.price', '[class*="price"]', '#price'])
            
            async def strategy1_site_selectors():
                # Hygulife-specific logic: prioritize current/sale price selectors
                if site == 'hygulife':
                    # First, try to get base price from JSON to use as reference
                    page_content_for_json = await page.content()
                    json_price_match = re.search(r'\"price\"\s*:\s*[\"\'₹]?([\d,]+(?:\.\d+)?)', page_content_for_json, re.IGNORECASE)
                    json_base_price = None
                    if json_price_match:
                        try:
                            json_base_price = float(json_price_match.group(1).replace(',', ''))
                        except:
                            pass
                    
                    # Try to find current price (displayed price, not MRP)
                    # Look for elements that might contain the current selling price
                    hygulife_selectors = [
                        '.price',  # Generic price class
                        '.product-price',  # Product price
                        '.sale-price',  # Sale price
                        '.current-price',  # Current price
                        '[class*="price"]',  # Any price class
                        'span.price',  # Span with price
                        'div.price',  # Div with price
                    ]
                    
                    found_prices = []
                    for selector in hygulife_selectors:
                        try:
                            price_elements = await page.query_selector_all(selector)
                            for element in price_elements[:15]:  # Check first 15 matches
                                try:
                                    price_text = (await element.text_content()).strip()
                                    if price_text and '₹' in price_text:
                                        # Skip discount/offer text
                                        if any(word in price_text.lower() for word in ['save', 'off', 'discount', 'get it at', 'extra', 'upto']):
                                            continue
                                        
                                        # Extract price value
                                        price_match = re.search(r'₹\s*([\d,]+(?:\.\d{1,2})?)', price_text)
                                        if price_match:
                                            price_str = price_match.group(1).replace(',', '')
                                            try:
                                                price_val = float(price_str)
                                                # Filter: reasonable product prices (50-100000), skip very small amounts
                                                if 50 <= price_val <= 100000:
                                                    # Check if element or parent has strikethrough (MRP/original price)
                                                    try:
                                                        computed_style = await element.evaluate('el => window.getComputedStyle(el).textDecoration')
                                                        parent = await element.evaluate_handle('el => el.parentElement')
                                                        parent_style = ''
                                                        if parent:
                                                            parent_style = await parent.as_element().evaluate('el => window.getComputedStyle(el).textDecoration') if parent else ''
                                                        
                                                        # Skip if strikethrough (it's MRP/original price)
                                                        if 'line-through' not in str(computed_style) and 'line-through' not in str(parent_style):
                                                            # If we have JSON base price, prefer price close to but less than base price
                                                            if json_base_price:
                                                                # Current price should be <= base price and close to it
                                                                if price_val <= json_base_price and (json_base_price - price_val) <= 100:
                                                                    found_prices.append((price_val, price_str, price_text, abs(json_base_price - price_val)))
                                                            else:
                                                                found_prices.append((price_val, price_str, price_text, 0))
                                                    except:
                                                        # If we can't check style, still add it
                                                        if json_base_price and price_val <= json_base_price and (json_base_price - price_val) <= 100:
                                                            found_prices.append((price_val, price_str, price_text, abs(json_base_price - price_val)))
                                                        elif not json_base_price:
                                                            found_prices.append((price_val, price_str, price_text, 0))
                                            except:
                                                continue
                                except:
                                    continue
                        except:
                            continue
                    
                    # If we found prices, prefer the one closest to JSON base price (current price)
                    if found_prices:
                        # Sort by proximity to base price (if available), then by price value
                        if json_base_price:
                            found_prices.sort(key=lambda x: (x[3], x[0]))  # Sort by proximity, then price
                        else:
                            found_prices.sort(key=lambda x: x[0])  # Sort by price value
                        
                        # Return the price closest to base price (current price)
                        return found_prices[0][1]
                
                # Amazon-specific logic: prioritize buybox/main price
                elif site == 'amazon':
                    # Top priority: Check hidden input field with price (most reliable)
                    try:
                        hidden_price_input = await page.query_selector('input[type="hidden"][name="items[0.base][customerVisiblePrice][amount]"]', timeout=2000)
                        if hidden_price_input:
                            price_value = await hidden_price_input.get_attribute('value')
                            if price_value:
                                try:
                                    price_float = float(price_value)
                                    # Require minimum 10 to avoid picking up non-price numbers
                                    if 10 <= price_float <= 10000000:
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
                                        # Require minimum 10 to avoid picking up non-price numbers
                                        if 10 <= price_float <= 1000000000:
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
                                        # Require minimum 10 to avoid picking up non-price numbers
                                        if 10 <= price_float <= 100000:
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
                                        # Require minimum 10 to avoid picking up non-price numbers
                                        if 10 <= price_float <= 10000000:
                                            return cleaned_price
                                    except:
                                        pass
                    except:
                        pass
                
                # Flipkart-specific logic: prioritize main price selectors
                if site == 'flipkart':
                    flipkart_priority_selectors = ['._30jeq3', '.Nx9bqj', '._16Jk6d', '._1vC4OE']
                    for selector in flipkart_priority_selectors:
                        try:
                            price_elements = await page.query_selector_all(selector)
                            found_prices = []
                            for element in price_elements[:5]:  # Check first 5 matches
                                price_text = (await element.text_content()).strip()
                                cleaned_price = self.clean_price(price_text)
                                if cleaned_price != "N/A" and self.is_valid_price(cleaned_price):
                                    try:
                                        price_float = float(cleaned_price.replace(',', ''))
                                        # Flipkart prices should be reasonable (>= 50 typically)
                                        if 50 <= price_float <= 10000000:
                                            found_prices.append((price_float, cleaned_price))
                                    except:
                                        continue
                            
                            # If we found prices, return the highest one (main product price)
                            if found_prices:
                                found_prices.sort(key=lambda x: x[0], reverse=True)
                                return found_prices[0][1]  # Return highest price
                        except:
                            continue
                
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
                                        # Require minimum 10 to avoid picking up non-price numbers
                                        if 10 <= price_float <= 10000000:
                                            return cleaned_price
                                    except:
                                        continue
                                # For Flipkart, ensure minimum price threshold
                                elif site == 'flipkart':
                                    try:
                                        price_float = float(cleaned_price.replace(',', ''))
                                        # Flipkart products typically cost >= 50, reject very low prices (likely discounts)
                                        if 50 <= price_float <= 10000000:
                                            return cleaned_price
                                    except:
                                        continue
                                # For Hygulife, ensure minimum price threshold
                                elif site == 'hygulife':
                                    try:
                                        price_float = float(cleaned_price.replace(',', ''))
                                        # Hygulife products typically cost >= 50, reject very low prices
                                        if 50 <= price_float <= 100000:
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
                    # For Amazon, only use specific price class selectors to avoid false positives
                    if site == 'amazon':
                        # Only check Amazon-specific price classes
                        price_related = await page.query_selector_all('.a-price, .a-price-whole, .a-price-symbol, .a-offscreen, #priceblock_ourprice, #priceblock_dealprice, #tp_price_block_total_price_ww')
                    else:
                        # For other sites, check elements with price-related classes/ids
                        price_related = await page.query_selector_all('[class*="price"], [id*="price"], [class*="Price"], [id*="Price"]')
                    
                    # Limit to first 100 elements for speed
                    elements_to_check = price_related[:100] if len(price_related) > 100 else price_related
                    
                    # For Flipkart, collect all prices and prefer the highest (main product price)
                    if site == 'flipkart':
                        found_prices = []
                        for element in elements_to_check:
                            try:
                                text = await element.text_content()
                                # Skip discount/offer text that contains "off" or "discount"
                                if text and ('off' in text.lower() or 'discount' in text.lower() or 'extra' in text.lower()):
                                    continue
                                
                                if text and re.search(r'[₹$€£¥]\s*\d{2,}|\d{3,}', text):
                                    cleaned_price = self.clean_price(text)
                                    if cleaned_price != "N/A" and self.is_valid_price(cleaned_price):
                                        try:
                                            price_float = float(cleaned_price.replace(',', ''))
                                            # Flipkart: reject very low prices (likely discounts) and require >= 50
                                            if 50 <= price_float <= 10000000:
                                                found_prices.append((price_float, cleaned_price))
                                        except:
                                            continue
                            except:
                                continue
                        
                        # Return the highest price (main product price is usually highest)
                        if found_prices:
                            found_prices.sort(key=lambda x: x[0], reverse=True)
                            return found_prices[0][1]
                        return None
                    
                    # For Hygulife, collect all prices and prefer the one closest to JSON base price
                    if site == 'hygulife':
                        found_prices = []
                        for element in elements_to_check:
                            try:
                                text = await element.text_content()
                                # Skip discount/offer text
                                if text and any(word in text.lower() for word in ['save', 'off', 'discount', 'get it at', 'extra', 'upto']):
                                    continue
                                
                                if text and re.search(r'[₹$€£¥]\s*\d{2,}|\d{3,}', text):
                                    cleaned_price = self.clean_price(text)
                                    if cleaned_price != "N/A" and self.is_valid_price(cleaned_price):
                                        try:
                                            price_float = float(cleaned_price.replace(',', ''))
                                            # Hygulife: reject very low prices and require >= 50
                                            if 50 <= price_float <= 100000:
                                                found_prices.append((price_float, cleaned_price))
                                        except:
                                            continue
                            except:
                                continue
                        
                        # Return the lowest price (current price, not MRP)
                        if found_prices:
                            found_prices.sort(key=lambda x: x[0])  # Sort by price, lowest first
                            return found_prices[0][1]
                        return None
                    
                    # Process elements sequentially but efficiently (early exit for speed)
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
                                            # For Amazon, require minimum 10 to avoid picking up non-price numbers
                                            if 10 <= price_float <= 10000000:
                                                # Additional check: ensure it's in a proper price container
                                                parent = await element.query_selector('xpath=..')
                                                if parent:
                                                    parent_class = await parent.get_attribute('class') or ''
                                                    if 'a-price' in parent_class or 'priceToPay' in parent_class:
                                                        return cleaned_price
                                                # If element itself has price class, it's valid
                                                elem_class = await element.get_attribute('class') or ''
                                                if 'a-price' in elem_class or 'priceToPay' in elem_class:
                                                    return cleaned_price
                                        except:
                                            continue
                                    # For Hygulife, ensure minimum price threshold
                                    elif site == 'hygulife':
                                        try:
                                            price_float = float(cleaned_price.replace(',', ''))
                                            # Hygulife products typically cost >= 50, reject very low prices
                                            if 50 <= price_float <= 100000:
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
                    
                    # Additional: Check for price in page content JSON (for sites like hygulife.com)
                    # Look for price patterns in script tags and page source
                    try:
                        page_content = await page.content()
                        
                        # For hygulife, look for multiple price fields and prefer current/sale price
                        if site == 'hygulife':
                            # Look for sale_price, current_price, discounted_price first (preferred)
                            sale_price_patterns = [
                                r'\"sale_price\"\s*:\s*[\"\'₹]?([\d,]+(?:\.\d+)?)',
                                r'\"current_price\"\s*:\s*[\"\'₹]?([\d,]+(?:\.\d+)?)',
                                r'\"discounted_price\"\s*:\s*[\"\'₹]?([\d,]+(?:\.\d+)?)',
                                r'\"selling_price\"\s*:\s*[\"\'₹]?([\d,]+(?:\.\d+)?)',
                            ]
                            
                            for pattern in sale_price_patterns:
                                matches = re.findall(pattern, page_content, re.IGNORECASE)
                                if matches:
                                    for price_str in matches:
                                        try:
                                            price_val = float(price_str.replace(',', ''))
                                            # Hygulife: require minimum 50 to reject very low prices
                                            if 50 <= price_val <= 100000:
                                                return str(int(price_val))
                                        except:
                                            continue
                            
                            # If no sale price found, look for all prices and calculate final price
                            price_json_pattern = r'\"price\"\s*:\s*[\"\'₹]?([\d,]+(?:\.\d+)?)'
                            price_matches = re.findall(price_json_pattern, page_content, re.IGNORECASE)
                            
                            # Also look for discount fields
                            discount_amount_pattern = r'\"discount\"\s*:\s*[\"\'₹]?([\d,]+(?:\.\d+)?)'
                            discount_matches = re.findall(discount_amount_pattern, page_content, re.IGNORECASE)
                            
                            if price_matches:
                                valid_prices = []
                                base_price = None
                                
                                for price_str in price_matches:
                                    try:
                                        price_val = float(price_str.replace(',', ''))
                                        # Hygulife: require minimum 50 to reject very low prices
                                        if 50 <= price_val <= 100000:
                                            valid_prices.append(price_val)
                                            # Usually the first/main price is the base price
                                            if base_price is None:
                                                base_price = price_val
                                    except:
                                        continue
                                
                                # If we found discount amount, calculate final price
                                if base_price and discount_matches:
                                    try:
                                        discount_val = float(discount_matches[0].replace(',', ''))
                                        final_price = base_price - discount_val
                                        # Hygulife: require minimum 50 for final price
                                        if 50 <= final_price <= 100000:
                                            return str(int(final_price))
                                    except:
                                        pass
                                
                                if valid_prices:
                                    # Prefer the lower price (current selling price) over higher price (MRP)
                                    valid_prices.sort()
                                    return str(int(valid_prices[0]))  # Return lowest price (current price)
                        else:
                            # For other sites, use original logic
                            price_json_pattern = r'\"price\"\s*:\s*[\"\'₹]?([\d,]+(?:\.\d+)?)'
                            price_matches = re.findall(price_json_pattern, page_content, re.IGNORECASE)
                            if price_matches:
                                # Get the first reasonable price (usually the main product price)
                                for price_str in price_matches:
                                    try:
                                        price_val = float(price_str.replace(',', ''))
                                        # Filter out unreasonable values (too small or too large)
                                        if 10 <= price_val <= 10000000:
                                            return str(int(price_val))
                                    except:
                                        continue
                    except:
                        pass
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
                    result['success'] = True
                    price_found = True
                    
                    # For Flipkart: Even if we found a price, re-check stock status
                    # Flipkart sometimes shows price even when product is sold out
                    if site == 'flipkart':
                        # Re-check stock status after price extraction
                        stock_status_recheck = await self.check_stock_status_async(page, site)
                        if stock_status_recheck.get('stock_status') == 'out_of_stock':
                            # Product is actually out of stock, override price
                            result['price'] = None
                            result['stock_status'] = stock_status_recheck
                            result['status'] = 'Product is out of stock (price found but product is sold out)'
                            price_found = False  # Mark as not found so we return out of stock
                            break
                        else:
                            # Update stock status with re-checked value
                            stock_status = stock_status_recheck
                            result['stock_status'] = stock_status
                    
                    # For hygulife: If price is successfully extracted, product is likely in stock
                    # Trust price extraction over stock_status (price extraction is more reliable)
                    # If a product truly has no stock, price usually won't be extractable
                    if site == 'hygulife' and stock_status.get('stock_status') == 'out_of_stock':
                        # Override stock status - if we can extract a price, product is available
                        stock_status = {
                            'in_stock': True,
                            'stock_status': 'in_stock',
                            'message': 'Product appears to be in stock (price successfully extracted, overriding JSON stock_status)'
                        }
                        result['stock_status'] = stock_status
                    
                    break
            
            # If price not found with Playwright, fallback to Selenium (unless force_playwright is True)
            if not price_found and not force_playwright:
                # For Flipkart: If price extraction failed, check stock status more carefully
                # Price extraction failure might indicate out of stock
                if site == 'flipkart' and stock_status.get('stock_status') != 'out_of_stock':
                    # Re-check stock status - maybe we missed it
                    stock_status = await self.check_stock_status_async(page, site)
                    result['stock_status'] = stock_status
                    
                    # If now detected as out of stock, return early
                    if stock_status.get('stock_status') == 'out_of_stock':
                        result['price'] = None
                        result['status'] = 'Product is out of stock'
                        return result
                
                # For Flipkart: Use a wrapper that also checks stock status
                if site == 'flipkart':
                    def scrape_and_check_stock():
                        price_result = self.scrape_with_selenium(product_url, site, use_virtual_display)
                        if price_result != 'N/A':
                            # Check stock status using Selenium driver
                            # We need to get the driver from scrape_with_selenium or check page content
                            # For now, we'll check stock status separately after getting price
                            return price_result, None
                        return price_result, None
                    
                    selenium_timeout = 90.0
                    try:
                        price_result, driver_ref = await asyncio.wait_for(
                            asyncio.to_thread(scrape_and_check_stock),
                            timeout=selenium_timeout
                        )
                        price = price_result
                    except asyncio.TimeoutError:
                        print(f"⚠️  Selenium operation timed out after {selenium_timeout}s for {site}")
                        price = 'N/A'
                else:
                    # Add timeout for Selenium operations to prevent hanging
                    selenium_timeout = 120.0 if site in ['meesho', 'myntra', 'ajio'] else 90.0
                    try:
                        price = await asyncio.wait_for(
                            asyncio.to_thread(self.scrape_with_selenium, product_url, site, use_virtual_display),
                            timeout=selenium_timeout
                        )
                    except asyncio.TimeoutError:
                        print(f"⚠️  Selenium operation timed out after {selenium_timeout}s for {site}")
                        price = 'N/A'
                
                if price != 'N/A':
                    # For Flipkart: Even if Selenium found a price, re-check stock status
                    # Flipkart sometimes shows price even when product is sold out
                    if site == 'flipkart':
                        # Re-check stock status - we need to check the actual page content
                        # Since we can't access Selenium driver here, check Playwright page
                        # (they should show similar content)
                        stock_status_recheck = await self.check_stock_status_async(page, site)
                        if stock_status_recheck.get('stock_status') == 'out_of_stock':
                            # Product is actually out of stock, override price
                            result['price'] = None
                            result['stock_status'] = stock_status_recheck
                            result['status'] = 'Product is out of stock (price found via Selenium but product is sold out)'
                            result['method'] = 'selenium'
                        else:
                            result['price'] = price
                            result['method'] = 'selenium'
                            result['status'] = 'success (Selenium fallback)'
                            result['stock_status'] = stock_status_recheck
                            result['success'] = True
                    else:
                        result['price'] = price
                        result['method'] = 'selenium'
                        result['status'] = 'success (Selenium fallback)'
                        result['success'] = True
                        # Stock status was already checked above for Playwright, keep it
                        # (Selenium fallback uses the same page, so stock status should still be valid)
                else:
                    # For Flipkart: If both Playwright and Selenium failed to extract price,
                    # and stock status is unknown, it's likely out of stock
                    if site == 'flipkart' and stock_status.get('stock_status') != 'out_of_stock':
                        # Final check - if we can't find price, product might be out of stock
                        # Check for "Notify Me" button or similar out-of-stock indicators
                        try:
                            notify_button = await page.query_selector('button:has-text("Notify"), button:has-text("Notify Me"), [class*="notify"]')
                            if notify_button:
                                stock_status = {
                                    'in_stock': False,
                                    'stock_status': 'out_of_stock',
                                    'message': 'Product appears to be out of stock (Notify Me button found, no price extractable)'
                                }
                                result['stock_status'] = stock_status
                                result['price'] = None
                                result['status'] = 'Product is out of stock (no price found, notify button present)'
                                return result
                        except:
                            pass
                    
                    result['status'] = 'Price not found (tried Playwright and Selenium)'
            
            return result
            
        except Exception as e:
            # If Playwright fails, try Selenium as fallback
            if 'playwright' in str(e).lower() or 'timeout' in str(e).lower() or 'navigation' in str(e).lower():
                # Add timeout for Selenium operations to prevent hanging
                selenium_timeout = 120.0 if site in ['meesho', 'myntra', 'ajio'] else 90.0
                try:
                    price = await asyncio.wait_for(
                        asyncio.to_thread(self.scrape_with_selenium, product_url, site, use_virtual_display),
                        timeout=selenium_timeout
                    )
                except asyncio.TimeoutError:
                    print(f"⚠️  Selenium operation timed out after {selenium_timeout}s for {site}")
                    price = 'N/A'
                # Default stock status for Selenium fallback
                stock_status = {'in_stock': True, 'stock_status': 'in_stock', 'message': None}
                return {
                    'url': product_url,
                    'site': site,
                    'price': price if price != 'N/A' else 'N/A',
                    'status': f'Playwright failed, Selenium: {"success" if price != "N/A" else "failed"}',
                    'method': 'selenium',
                    'error': str(e),
                    'stock_status': stock_status,
                    'success': price != 'N/A'
                }
            else:
                return {
                    'url': product_url,
                    'site': site,
                    'price': 'N/A',
                    'status': f'Error: {str(e)}',
                    'stock_status': {'in_stock': True, 'stock_status': 'unknown', 'message': None},
                    'success': False
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
            # Stop virtual display if it was started
            if vdisplay:
                try:
                    vdisplay.stop()
                except:
                    pass

    async def scrape_multiple_products(self, playwright: Playwright, urls: List[str], 
                                        max_concurrent: int = 20, 
                                        use_virtual_display: bool = False) -> List[Dict]:
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def scrape_with_limit(url):
            async with semaphore:
                return await self.scrape_product_price(playwright, url, use_virtual_display=use_virtual_display)
        
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
        "https://myntr.it/uZ7356d"
          ]
    
    print("Testing E-commerce Price Scraper - Detecting Blocked Sites")
    print("=" * 70)
    print("\nTesting all URLs with Playwright first, falling back to Selenium if blocked...\n")
    
    async with async_playwright() as playwright:
        results = await scraper.scrape_multiple_products(
                playwright,
                test_urls,
                max_concurrent=5,  # Reduced for testing
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
