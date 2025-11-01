import time
import random
import re
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def scrape_meesho_with_selenium(url: str):
    """Scrape Meesho using undetected Chrome driver to bypass bot detection"""
    
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
        
        print("Opening Meesho...")

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
                # Common price selectors for Meesho
                ("css", "[class*='Price']"),
                ("css", "[class*='price']"),
                ("css", "[data-testid*='price']"),
                ("css", "[data-testid*='Price']"),
                ("xpath", "//*[contains(@class, 'Price')]"),
                ("xpath", "//*[contains(@class, 'price')]"),
                ("xpath", "//h2[contains(text(), '₹')]"),
                ("xpath", "//h3[contains(text(), '₹')]"),
                ("xpath", "//h4[contains(text(), '₹')]"),
                ("xpath", "//span[contains(text(), '₹')]"),
                ("xpath", "//div[contains(text(), '₹')]"),
                ("xpath", "//p[contains(text(), '₹')]"),
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
            
            # Try specific selectors one by one
            print("\n=== Trying specific selectors ===")
            
            # Priority 1: Try to find h4 element containing main price (most reliable)
            # Based on inspection, the main price is in an h4 element
            try:
                # Wait for price element to be visible
                wait.until(EC.presence_of_element_located((By.XPATH, "//h4[contains(text(), '₹')]")))
                h4_elements = driver.find_elements(By.XPATH, "//h4[contains(text(), '₹')]")
                if h4_elements:
                    # The main product price is usually the first h4 element
                    main_price_elem = h4_elements[0]
                    text = main_price_elem.text.strip()
                    if text and '₹' in text:
                        price_match = re.search(r'₹\s*([\d,]+(?:\.\d{1,2})?)', text)
                        if price_match:
                            price_value = price_match.group(1).replace(',', '')
                            print(f"✓ Found main price using h4 selector")
                            print(f"  Tag: {main_price_elem.tag_name}")
                            print(f"  Class: {main_price_elem.get_attribute('class')}")
                            print(f"  Text: {text}")
                            print(f"  Extracted: ₹{price_value}")
                            return price_value
            except Exception as e:
                print(f"Trying h4 selector failed: {e}")
            
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
                                            found_prices.append((price_float, price_value, text))
                                    except:
                                        pass
                        except:
                            continue
                    
                    if found_prices:
                        # Sort by price value and take the first/main one
                        found_prices.sort(reverse=True)  # Highest first
                        price_value = found_prices[0][1]
                        print(f"✓ Found price using {selector_type}: '{selector}'")
                        print(f"  Text: {found_prices[0][2]}")
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
                r'<[^>]*>₹\s*([\d,]+(?:\.\d{1,2})?)</[^>]*>',
                r'"price"[^>]*>.*?₹\s*([\d,]+(?:\.\d{1,2})?)',
                r'class="[^"]*Price[^"]*"[^>]*>.*?₹\s*([\d,]+(?:\.\d{1,2})?)',
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
                                main_price = str(int(max(valid_prices)))
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
        
    finally:
        try:
            driver.quit()
        except:
            pass


if __name__ == "__main__":
    url = "https://www.meesho.com/frekman-stylish-cotton-blend-check-mens-shirt/p/1kv4b"
    scrape_meesho_with_selenium(url)

