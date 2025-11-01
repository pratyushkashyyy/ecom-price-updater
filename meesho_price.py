import time
import random
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def make_driver():
    """Create and return a configured undetected Chrome driver."""
    options = uc.ChromeOptions()
    prefs = {
        "profile.default_content_setting_values.images": 2,   # 2 = block
        # legacy name also sometimes needed:
        "profile.managed_default_content_settings.images": 2
    }
    options.add_experimental_option("prefs", prefs)
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--start-maximized')
    # options.add_argument("--headless=new")  # uncomment if you want headless (may alter detection)
    # add any user-agent switching or profile config here if needed

    # Create driver instance (each thread should call this)
    driver = uc.Chrome(options=options, version_main=None)
    return driver


def extract_price_from_text(text: str):
    """Try multiple regex patterns to extract an Indian-rupee price from HTML/text."""
    patterns = [
        r"₹\s*([\d,]+(?:\.\d{1,2})?)",
        r"Rs\.?\s*([\d,]+(?:\.\d{1,2})?)",
        r"INR\s*([\d,]+(?:\.\d{1,2})?)"
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            return m.group(1).replace(",", "")
    return None


def scrape_meesho(url: str, timeout: int = 20, retry: int = 2):
    """Scrape a single URL. Each call creates its own driver."""
    driver = None
    last_exc = None
    for attempt in range(1, retry+1):
        try:
            driver = make_driver()
            driver.get(url)

            # small human-like delay
            time.sleep(random.uniform(2.0, 4.0))

            wait = WebDriverWait(driver, timeout)

            # Try strategies to find the price element (priority order):
            # 1) h4 element containing ₹ - most reliable for main product price
            try:
                price_el = wait.until(
                    EC.presence_of_element_located((By.XPATH, "//h4[contains(text(), '₹')]"))
                )
                text = price_el.text.strip()
                price = extract_price_from_text(text)
                if price:
                    # Verify it's a reasonable price (not a variant price)
                    try:
                        price_float = float(price)
                        if price_float > 50:  # Reasonable threshold for product price
                            return {"url": url, "price": price, "method": "h4_selector"}
                    except:
                        pass
            except Exception:
                pass

            # 2) Try span elements containing ₹ (fallback)
            try:
                price_el = wait.until(
                    EC.presence_of_element_located((By.XPATH, "//span[contains(text(), '₹')]"))
                )
                text = price_el.text.strip()
                price = extract_price_from_text(text)
                if price:
                    try:
                        price_float = float(price)
                        if price_float > 50:
                            return {"url": url, "price": price, "method": "span_selector"}
                    except:
                        pass
            except Exception:
                pass

            # 3) Any element containing the rupee symbol (broader search)
            try:
                price_el = wait.until(
                    EC.visibility_of_element_located(
                        (By.XPATH, "//*[contains(text(),'₹')]")
                    )
                )
                text = price_el.text.strip()
                price = extract_price_from_text(text)
                if price:
                    try:
                        price_float = float(price)
                        if price_float > 50:
                            return {"url": url, "price": price, "method": "element_text"}
                    except:
                        pass
            except Exception:
                pass

            # 4) Last resort: regex over page source
            page = driver.page_source
            price = extract_price_from_text(page)
            if price:
                return {"url": url, "price": price, "method": "page_source_regex"}

            # If we reached here, couldn't find price reliably
            return {"url": url, "price": None, "method": "not_found"}

        except Exception as e:
            last_exc = e
            # exponential backoff-ish retry with jitter
            sleep_for = (2 ** attempt) + random.random()
            print(f"[{url}] attempt {attempt} failed: {e}. retrying in {sleep_for:.1f}s...")
            time.sleep(sleep_for)
        finally:
            if driver:
                try:
                    driver.quit()
                except Exception:
                    pass

    # after retries
    return {"url": url, "price": None, "error": str(last_exc)}


def scrape_many(urls, max_workers: int = 3):
    """Run scrape_meesho concurrently across multiple threads and return results."""
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {executor.submit(scrape_meesho, url): url for url in urls}
        for future in as_completed(future_to_url):
            url = future_to_url[future]
            try:
                res = future.result()
            except Exception as exc:
                res = {"url": url, "price": None, "error": str(exc)}
            print(f"[done] {url} -> {res}")
            results.append(res)
    return results


if __name__ == "__main__":
    urls = [
        "https://www.meesho.com/frekman-stylish-cotton-blend-check-mens-shirt/p/1kv4b",

        # add more product URLs here
    ]
    out = scrape_many(urls, max_workers=20)
