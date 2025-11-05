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
        
        # Handle short URLs
        if 'amzn.to' in domain or 'amzn' in domain:
            return 'amazon'
        elif 'amazon' in domain:
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

    def navigate_and_identify(self, driver, product_url: str, initial_site: str = None) -> tuple:
        """
        Navigate to URL, wait for redirects, capture final URL, and identify site.
        Returns: (final_url, identified_site)
        """
        print(f"  🌐 Navigating to: {product_url}")
        driver.get(product_url)
        time.sleep(random.uniform(3, 6))  # Wait for redirects and page load
        
        # Capture final URL after navigation and redirects
        final_url = driver.current_url
        print(f"  📍 Final URL after navigation: {final_url[:100]}...")
        
        # Identify site from final URL
        identified_site = self.identify_site(final_url)
        
        if initial_site:
            if identified_site != initial_site and identified_site != 'generic':
                print(f"  🔄 Site identified: {initial_site} -> {identified_site} (from final URL)")
        else:
            print(f"  🏷️  Site identified: {identified_site} (from final URL)")
        
        return final_url, identified_site
    
    def scrape_with_selenium(self, product_url: str, site: str = None, use_virtual_display: bool = True) -> str:
        """
        Generic Selenium scraper for sites that block Playwright.
        New flow: Navigate → Capture final URL → Identify site → Extract price
        Always uses virtual display (no headless mode)
        """
        # Always setup virtual display (no headless mode)
        vdisplay = None
        if use_virtual_display:
            try:
                from virtual_display import VirtualDisplay
                vdisplay = VirtualDisplay()
                if not vdisplay.start():
                    vdisplay = None  # Fallback if virtual display fails
                    print("⚠️  Virtual display failed to start, browser will be visible")
            except ImportError:
                print("⚠️  virtual_display module not available, browser will be visible")
        
        # Try site-specific Selenium modules first (only if we know the site from initial URL)
        initial_site = self.identify_site(product_url) if site is None else site
        if initial_site == 'nykaa':
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
            
            # Always configure for virtual display (no headless mode)
            if vdisplay:
                try:
                    from virtual_display import setup_virtual_display_for_selenium
                    setup_virtual_display_for_selenium(options)
                except ImportError:
                    pass
            # If virtual display not available, browser will run visibly (no headless)
            
            options.add_argument('--start-maximized')
            
            driver = uc.Chrome(options=options, version_main=None)
            
            try:
                # NEW FLOW: Navigate → Capture final URL → Identify site → Extract price
                final_url, identified_site = self.navigate_and_identify(driver, product_url, initial_site)
                site = identified_site  # Use the identified site from final URL
                
                wait = WebDriverWait(driver, 15)
                
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
                    # For Amazon, all specific selectors have been tried above
                    # Don't fall through to generic fallbacks to avoid picking up non-price numbers
                
                # Generic fallback: try any element with ₹ (only for non-Amazon sites)
                if site != 'amazon':
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
                    if site != 'amazon':
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

    async def navigate_and_identify_async(self, page, product_url: str, initial_site: str = None) -> tuple:
        """
        Navigate to URL, wait for redirects, capture final URL, and identify site (async for Playwright).
        Returns: (final_url, identified_site)
        """
        print(f"  🌐 Navigating to: {product_url}")
        await page.goto(product_url, timeout=30000, wait_until='domcontentloaded')
        await asyncio.sleep(3 + random.uniform(1, 3))  # Wait for redirects and page load
        
        # Capture final URL after navigation and redirects
        final_url = page.url
        print(f"  📍 Final URL after navigation: {final_url[:100]}...")
        
        # Identify site from final URL
        identified_site = self.identify_site(final_url)
        
        if initial_site:
            if identified_site != initial_site and identified_site != 'generic':
                print(f"  🔄 Site identified: {initial_site} -> {identified_site} (from final URL)")
        else:
            print(f"  🏷️  Site identified: {identified_site} (from final URL)")
        
        return final_url, identified_site
    
    async def scrape_product_price(self, playwright: Playwright, product_url: str, 
                                   force_selenium: bool = False, use_virtual_display: bool = True) -> Dict:
        # NEW FLOW: Will identify site after navigation
        initial_site = self.identify_site(product_url)
        site = initial_site  # Will be updated after navigation
        
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
            # Always use virtual display (no headless mode)
            # Virtual display handles running the browser in the background
            browser = await playwright.chromium.launch(headless=False)
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
            
            # NEW FLOW: Navigate → Capture final URL → Identify site → Extract price
            try:
                final_url, identified_site = await self.navigate_and_identify_async(page, product_url, initial_site)
                site = identified_site  # Use the identified site from final URL
                
                # Check if page is blocked (common patterns)
                page_content = await page.content()
                page_title = await page.title()
                
                # Check for blocking indicators
                blocked = any(indicator in page_content.lower() or indicator in page_title.lower() 
                             for indicator in ['access denied', 'blocked', 'forbidden', 'cloudflare', 'captcha'])
            except Exception as e:
                # If navigation fails, mark as blocked
                blocked = True
                print(f"  ⚠️  Navigation failed: {str(e)[:100]}")
            
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
                                        max_concurrent: int = 20, use_virtual_display: bool = True) -> List[Dict]:
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
        "https://amzn.to/4ndbEWK",
        "https://amzn.to/46arnjh,",
        "https://amzn.to/42BrIsV",
        "https://amzn.to/41W66Hw",
        "https://amzn.to/4nzvWcC",
          ]
    
    print("Testing E-commerce Price Scraper - Detecting Blocked Sites")
    print("=" * 70)
    print("\nTesting all URLs with Playwright first, falling back to Selenium if blocked...\n")
    
    async with async_playwright() as playwright:
        results = await scraper.scrape_multiple_products(
                playwright,
                test_urls,
                max_concurrent=5,  # Reduced for testing
                use_virtual_display=True,  # Always use virtual display (no headless)
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
