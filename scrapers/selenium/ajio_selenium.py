import time
import random
import re
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Import cleanup utilities
try:
    import sys
    from pathlib import Path
    # Add parent directory to path to import chrome_cleanup
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from chrome_cleanup import cleanup_chrome_driver
except ImportError:
    # Fallback if chrome_cleanup is not available
    def cleanup_chrome_driver(driver, timeout=5):
        try:
            if driver:
                driver.quit()
        except:
            try:
                if driver:
                    driver.close()
            except:
                pass


def scrape_ajio_with_selenium(url: str):
    """Scrape Ajio using undetected Chrome driver to bypass bot detection"""
    
    driver = None
    max_retries = 2
    
    for attempt in range(max_retries):
        try:
            # Don't clean up before starting - let Chrome start naturally
            # Cleanup only happens after errors to avoid interfering with startup
            print(f"Launching undetected Chrome browser... (Attempt {attempt + 1}/{max_retries})")
            
            # Use undetected chromedriver with basic options for virtual display
            options = uc.ChromeOptions()
            
            # Basic options needed for virtual display
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            
            # Try to find Chrome binary (for snap installations)
            import shutil
            chrome_binary = None
            for binary_name in ['chromium-browser', 'chromium', 'google-chrome', 'google-chrome-stable']:
                binary_path = shutil.which(binary_name)
                if binary_path:
                    chrome_binary = binary_path
                    print(f"Using Chrome binary: {chrome_binary}")
                    break
            
            if chrome_binary:
                options.binary_location = chrome_binary
            
            # Create undetected driver with error handling
            try:
                driver = uc.Chrome(options=options, version_main=None, use_subprocess=True)
            except Exception as chrome_init_error:
                print(f"Failed to initialize Chrome: {chrome_init_error}")
                # Clean up any partial processes
                try:
                    import sys
                    from pathlib import Path
                    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
                    from chrome_cleanup import kill_chrome_processes
                    kill_chrome_processes(force=True, only_orphaned=True)
                except:
                    pass
                raise  # Re-raise to be caught by outer exception handler
            
            print("Opening Ajio...")

            driver.get(url)
            
            # Wait a bit for page to load
            print("Waiting for page to load...")
            time.sleep(random.uniform(3, 6))
            
            try:
                title = driver.title
                # Reduce wait timeout to prevent hanging - use shorter waits
                wait = WebDriverWait(driver, 10)  # Reduced from 15 to 10 seconds
                
                print(f"Page title: {title}")
                
                # Wait for page to fully load
                time.sleep(2)
                
                # Try multiple strategies to find price element
                price_selectors = [
                # Ajio price selectors
                ("css", ".prod-sp"),  # Selling price
                ("css", ".prod-base-price"),  # MRP
                ("xpath", "//span[contains(@class, 'prod-sp')]"),  # Selling price span
                ("xpath", "//span[contains(@class, 'prod-base-price')]"),  # MRP span
                ("xpath", "//span[contains(@class, 'price')]"),  # Any price span
                ("xpath", "//div[contains(@class, 'price')]"),  # Any price div
                ("xpath", "//*[contains(@data-id, 'price')]"),  # Data attribute
                ("xpath", "//span[contains(text(), '₹')]"),  # Any span with ₹
                ("xpath", "//div[contains(text(), '₹')]"),  # Any div with ₹
                ]
                
                # First, let's find all elements containing ₹ symbol
                print("\n=== Searching for price elements ===")
                try:
                    # Find all elements containing ₹
                    rupee_elements = driver.find_elements(By.XPATH, "//*[contains(text(), '₹')]")
                    print(f"Found {len(rupee_elements)} elements containing ₹ symbol")
                    
                    for i, elem in enumerate(rupee_elements[:10]):  # Check first 10
                        try:
                            text = elem.text.strip()
                            tag = elem.tag_name
                            class_name = elem.get_attribute('class') or ''
                            element_id = elem.get_attribute('id') or ''
                            data_testid = elem.get_attribute('data-id') or ''
                            
                            # Only show elements with reasonable text length
                            if text and len(text) < 100:
                                print(f"\nElement {i+1}:")
                                print(f"  Tag: {tag}")
                                print(f"  Class: {class_name}")
                                print(f"  ID: {element_id}")
                                print(f"  Data-id: {data_testid}")
                                print(f"  Text: {text}")
                                
                                # Extract price number
                                price_match = re.search(r'₹\s*([\d,]+(?:\.\d{1,2})?)', text)
                                if price_match:
                                    price_value = price_match.group(1).replace(',', '')
                                    print(f"  → Extracted Price: {price_value}")
                        except Exception as e:
                            continue
                            
                except Exception as e:
                    print(f"Error finding rupee elements: {e}")
                
                # Priority 1: Try to find selling price (.prod-sp) - main product price
                print("\n=== Trying specific selectors ===")
                # Try to find element without waiting first (faster)
                try:
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
                                print(f"✓ Found selling price using .prod-sp selector")
                                print(f"  Tag: {selling_price_elem.tag_name}")
                                print(f"  Class: {selling_price_elem.get_attribute('class')}")
                                print(f"  Text: {text}")
                                print(f"  Extracted: ₹{price_value}")
                                cleanup_chrome_driver(driver)
                                return price_value
                except Exception as e:
                    print(f"Trying .prod-sp selector failed: {e}")
                
                # Priority 2: Try other specific selectors
                for selector_type, selector in price_selectors:
                    try:
                        if selector_type == "css":
                            elements = driver.find_elements(By.CSS_SELECTOR, selector)
                        else:  # xpath
                            elements = driver.find_elements(By.XPATH, selector)
                        
                        # Collect all prices found
                        found_prices = []
                        for elem in elements:
                            try:
                                text = elem.text.strip()
                                if text and '₹' in text and len(text) < 100:
                                    price_match = re.search(r'₹\s*([\d,]+(?:\.\d{1,2})?)', text)
                                    if price_match:
                                        price_value = price_match.group(1).replace(',', '')
                                        # Skip variant prices (usually smaller)
                                        try:
                                            price_float = float(price_value)
                                            if price_float > 50:  # Reasonable price threshold
                                                found_prices.append((price_float, price_value, text, elem.get_attribute('class')))
                                        except:
                                            pass
                            except:
                                continue
                        
                        if found_prices:
                            # Prefer selling price (prod-sp) over MRP (prod-base-price)
                            # Sort by class preference first, then by price
                            found_prices.sort(key=lambda x: (
                                0 if 'prod-sp' in (x[3] or '') else 1,  # Selling price first
                                -x[0]  # Then highest price
                            ))
                            price_value = found_prices[0][1]
                            print(f"✓ Found price using {selector_type}: '{selector}'")
                            print(f"  Text: {found_prices[0][2]}")
                            print(f"  Class: {found_prices[0][3]}")
                            print(f"  Extracted: ₹{price_value}")
                            cleanup_chrome_driver(driver)
                            return price_value
                    except Exception as e:
                        continue
                
                # Fallback: regex on page source
                print("\n=== Fallback: Searching page source ===")
                page_source = driver.page_source
                
                # Try multiple regex patterns
                patterns = [
                    r'₹\s*([\d,]+(?:\.\d{1,2})?)',
                    r'<[^>]*class="[^"]*prod-sp[^"]*"[^>]*>.*?₹\s*([\d,]+(?:\.\d{1,2})?)',
                    r'<span[^>]*class="[^"]*prod-sp[^"]*"[^>]*>.*?₹\s*([\d,]+(?:\.\d{1,2})?)',
                ]
                
                for pattern in patterns:
                    matches = re.findall(pattern, page_source, re.IGNORECASE | re.DOTALL)
                    if matches:
                        # Get unique prices, prefer larger numbers (likely the actual price)
                        prices = [m.replace(',', '') for m in matches if m]
                        if prices:
                            # Convert to float to find the most reasonable price
                            try:
                                price_floats = [float(p) for p in prices]
                                # Filter out very small numbers (likely not prices)
                                valid_prices = [p for p in price_floats if p > 10]
                                if valid_prices:
                                    # Prefer selling price range (usually in the middle)
                                    valid_prices.sort()
                                    main_price = str(int(valid_prices[len(valid_prices)//2]))  # Take median
                                    print(f"✓ Found price using regex: ₹{main_price}")
                                    cleanup_chrome_driver(driver)
                                    return main_price
                            except:
                                pass
                
                print("\n❌ Could not find price")
                cleanup_chrome_driver(driver)
                return None
                    
            except Exception as e:
                print(f"Error reading page: {e}")
                import traceback
                traceback.print_exc()
                cleanup_chrome_driver(driver)
                return None
            
        except Exception as e:
            # Handle Chrome connection errors and other exceptions
            from selenium.common.exceptions import SessionNotCreatedException
            error_str = str(e).lower()
            is_chrome_error = (
                isinstance(e, SessionNotCreatedException) or
                any(keyword in error_str for keyword in [
                    'session not created', 'cannot connect to chrome', 'chrome not reachable',
                    'connection refused', 'timeout', 'connection error'
                ])
            )
            
            print(f"❌ Error occurred (attempt {attempt + 1}/{max_retries}): {e}")
            
            # Clean up driver on error
            if driver:
                try:
                    cleanup_chrome_driver(driver)
                except:
                    pass
            
            # If it's a Chrome connection error and we have retries left, do cleanup and retry
            if is_chrome_error and attempt < max_retries - 1:
                print(f"Chrome connection error detected, will retry...")
                try:
                    import sys
                    from pathlib import Path
                    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
                    from chrome_cleanup import kill_chrome_processes
                    print(f"Cleaning up Chrome processes after connection error...")
                    # Clean up any stuck Chrome/ChromeDriver processes
                    # Only kill orphaned processes to avoid killing active concurrent scrapes
                    killed = kill_chrome_processes(force=True, only_orphaned=True)
                    if killed > 0:
                        print(f"Cleaned up {killed} Chrome processes")
                    # Also try to clean up the driver if it exists
                    if driver:
                        try:
                            cleanup_chrome_driver(driver)
                        except:
                            pass
                    time.sleep(2)  # Wait for ports to be released
                except:
                    pass
                continue
            else:
                # If not a Chrome error or no retries left, return None
                if not is_chrome_error:
                    import traceback
                    traceback.print_exc()
                return None
    
    # If we get here, all retries failed
    return None


if __name__ == "__main__":
    url = "https://www.ajio.com/yousta-men-washed-relaxed-fit-crew-neck-t-shirt/p/443079993_blackcharcoal"
    scrape_ajio_with_selenium(url)

