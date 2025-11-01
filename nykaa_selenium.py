import time
import random
import re
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def scrape_nykaa_with_selenium(url: str):
    """Scrape Nykaa using undetected Chrome driver to bypass bot detection"""
    
    print("Launching undetected Chrome browser...")
    
    # Use undetected chromedriver with realistic options
    options = uc.ChromeOptions()
    
    # Add some arguments to make it more realistic
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--start-maximized')
    
    try:
        # Create undetected driver
        driver = uc.Chrome(options=options, version_main=None)
        
        print("Opening Nykaa...")

        driver.get(url)
        
        # Wait a bit for page to load
        print("Waiting for page to load...")
        time.sleep(random.uniform(3, 6))
        
        try:
            title = driver.title
            wait = WebDriverWait(driver, 15)
            
            print(f"Page title: {title}")
            
            # Wait for page to fully load
            time.sleep(2)
            
            # Try multiple strategies to find price element
            price_selectors = [
                # Based on browser inspection: selling price is in span with class css-1jczs19
                ("css", ".css-1jczs19"),  # Selling price (main price)
                ("css", ".css-u05rr"),   # MRP (original price)
                ("xpath", "//span[contains(@class, 'css-1jczs19')]"),  # Selling price
                ("xpath", "//span[contains(@class, 'css-u05rr')]"),    # MRP
                ("xpath", "//span[contains(@class, 'css-1d0jf8e')]"),  # Price container
                ("xpath", "//*[contains(@class, 'css-1jczs19')]"),     # Selling price (any element)
                ("xpath", "//span[contains(text(), '₹')]"),            # Any span with ₹
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
                        data_testid = elem.get_attribute('data-testid') or ''
                        
                        # Only show elements with reasonable text length
                        if text and len(text) < 100:
                            print(f"\nElement {i+1}:")
                            print(f"  Tag: {tag}")
                            print(f"  Class: {class_name}")
                            print(f"  ID: {element_id}")
                            print(f"  Data-testid: {data_testid}")
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
            
            # Priority 1: Try to find selling price (css-1jczs19) - main product price
            print("\n=== Trying specific selectors ===")
            try:
                # Wait for price element to be visible
                selling_price_elem = wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".css-1jczs19"))
                )
                text = selling_price_elem.text.strip()
                if text and '₹' in text:
                    price_match = re.search(r'₹\s*([\d,]+(?:\.\d{1,2})?)', text)
                    if price_match:
                        price_value = price_match.group(1).replace(',', '')
                        print(f"✓ Found selling price using css-1jczs19 selector")
                        print(f"  Tag: {selling_price_elem.tag_name}")
                        print(f"  Class: {selling_price_elem.get_attribute('class')}")
                        print(f"  Text: {text}")
                        print(f"  Extracted: ₹{price_value}")
                        return price_value
            except Exception as e:
                print(f"Trying css-1jczs19 selector failed: {e}")
            
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
                        # Prefer selling price (css-1jczs19) over MRP (css-u05rr)
                        # Sort by class preference first, then by price
                        found_prices.sort(key=lambda x: (
                            0 if 'css-1jczs19' in (x[3] or '') else 1,  # Selling price first
                            -x[0]  # Then highest price
                        ))
                        price_value = found_prices[0][1]
                        print(f"✓ Found price using {selector_type}: '{selector}'")
                        print(f"  Text: {found_prices[0][2]}")
                        print(f"  Class: {found_prices[0][3]}")
                        print(f"  Extracted: ₹{price_value}")
                        return price_value
                except Exception as e:
                    continue
            
            # Fallback: regex on page source
            print("\n=== Fallback: Searching page source ===")
            page_source = driver.page_source
            
            # Try multiple regex patterns
            patterns = [
                r'₹\s*([\d,]+(?:\.\d{1,2})?)',
                r'<[^>]*class="[^"]*css-1jczs19[^"]*"[^>]*>.*?₹\s*([\d,]+(?:\.\d{1,2})?)',
                r'<span[^>]*class="[^"]*css-1jczs19[^"]*"[^>]*>.*?₹\s*([\d,]+(?:\.\d{1,2})?)',
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
                                return main_price
                        except:
                            pass
            
            print("\n❌ Could not find price")
            return None
            
        except Exception as e:
            print(f"Error reading page: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    except Exception as e:
        print(f"❌ Error occurred: {e}")
        import traceback
        traceback.print_exc()
        return None
        
    finally:
        try:
            driver.quit()
        except:
            pass


if __name__ == "__main__":
    url = "https://www.nykaa.com/braun-silk-epil-9-890-epilator-for-long-lasting-hair-removal-includes-a-bikini-styler/p/1178844?productId=1178844&pps=1"
    scrape_nykaa_with_selenium(url)

