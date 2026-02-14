import asyncio
import sys
import threading
import time
import random
import requests
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor

# Browser automation
from playwright.async_api import async_playwright, Page
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

# Internal modules
from scrapers.scraper_factory import ScraperFactory
from scrapers.browser_adapter import BrowserAdapter
from playwright_stealth import stealth_async
from browser_config import PLAYWRIGHT_ARGS, PLAYWRIGHT_CONTEXT_OPTIONS, STEALTH_JS, SELENIUM_ARGS


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
        
    def get_random_user_agent(self):
        return random.choice(self.user_agents)

    def identify_site(self, url: str) -> str:
        """Identify site from URL (wrapper for ScraperFactory)"""
        return ScraperFactory.identify_site(url)
        
    def resolve_url(self, url: str) -> str:
        """Resolve shortened URLs to their final destination"""
        domain = urlparse(url).netloc.lower()
        shorteners = ['bitli.in', 'extp.in', 'amzn.to', 'fkrt.cc', 't.co', 'goo.gl', 'bit.ly', 'msho.in']
        
        if any(s in domain for s in shorteners):
            try:
                print(f"  Resolving short URL: {url}")
                # Try HEAD first
                try:
                    response = requests.head(url, allow_redirects=True, timeout=10)
                    if response.status_code < 400:
                         print(f"  Resolved (HEAD) to: {response.url}")
                         return response.url
                except:
                    pass
                
                # Fallback to GET
                response = requests.get(url, allow_redirects=True, timeout=10, stream=True)
                print(f"  Resolved (GET) to: {response.url}")
                return response.url
            except Exception as e:
                print(f"  Failed to resolve URL {url}: {e}")
                return url
        return url


    async def scrape_product_price(self, playwright, url: str, use_virtual_display: bool = False) -> dict:
        """
        Main entry point for scraping a product price.
        
        Two-phase site identification workflow:
          Phase 1: Domain dict lookup on the raw input URL
          Phase 2: If Phase 1 returned 'generic', open URL in browser,
                   let redirects settle, then re-identify from the final URL.
        
        Tries Playwright first, falls back to Selenium.
        """
        original_url = url
        
        result = {
            'url': url,
            'site': 'unknown',
            'price': 'N/A',
            'name': None,
            'image_url': None,
            'currency': 'INR',
            'status': 'failed',
            'method': 'unknown',
            'error': None,
            'details': {
                'name': None,
                'image_url': None,
                'rating': None,
                'review_count': None
            },
            'stock': {
                'in_stock': True,
                'stock_status': 'unknown',
                'message': None
            }
        }
        
        # ── PHASE 1: Domain Dict Lookup ──
        site = self.identify_site(url)
        print(f"  Phase 1 identification: {site}")
        
        # ── PLAYWRIGHT ATTEMPT ──
        try:
            print(f"  Launching Playwright browser (Chrome channel)...")
            browser = await playwright.chromium.launch(
                headless=False,
                channel="chrome",
                args=PLAYWRIGHT_ARGS
            )
            
            # Create context with realistic fingerprint
            context_options = PLAYWRIGHT_CONTEXT_OPTIONS.copy()
            context_options['user_agent'] = self.get_random_user_agent()
            context = await browser.new_context(**context_options)
            
            page = await context.new_page()
            
            # Apply Stealth plugin
            try:
                await stealth_async(page)
            except Exception as e:
                print(f"  Could not apply stealth plugin: {e}")
            
            # Inject additional stealth JavaScript
            try:
                await page.add_init_script(STEALTH_JS)
            except Exception as e:
                print(f"  Could not inject stealth JS: {e}")

            # Navigate and wait for redirects to settle
            try:
                await page.goto(url, timeout=60000, wait_until='networkidle')
                await asyncio.sleep(8)  # Wait for JS to render content (Flipkart, etc.)
                
                # Check if a new tab/page was opened (some short links do this)
                if len(context.pages) > 1:
                    print(f"  Multiple pages detected ({len(context.pages)}). Switching to the latest one.")
                    final_page = context.pages[-1]
                    await final_page.wait_for_load_state('domcontentloaded')
                    page = final_page
                
                # Capture the browser's final URL after all redirects
                final_url = page.url
                print(f"  Browser resolved URL to: {final_url}")
                result['url'] = final_url
                
                # ── PHASE 2: Browser-based re-identification (only if Phase 1 was generic) ──
                if site == 'generic':
                    site = self.identify_site(final_url)
                    print(f"  Phase 2 identification (from browser URL): {site}")
                
                result['site'] = site
                print(f"  Final identified site: {result['site']}")
                
                # Get the correct scraper for the identified site
                scraper = ScraperFactory.get_scraper(final_url)
                
                # Flipkart-specific: Wait for price elements to load (they render via JS)
                if site == 'flipkart':
                    try:
                        print("  Waiting for Flipkart price elements to render...")
                        await page.wait_for_selector('.Nx9bqj, .Cx5lGj, ._30jeq3, ._16Jk6d', timeout=15000)
                        print("  Price elements detected!")
                    except Exception as e:
                        print(f"  Price elements didn't load in 15s, proceeding anyway: {e}")

                # DEBUG: Save HTML to file
                try:
                    content = await page.content()
                    with open("last_scraped_page.html", "w", encoding="utf-8") as f:
                        f.write(content)
                    print("  Saved page HTML to last_scraped_page.html")
                except Exception as e:
                    print(f"  Could not save HTML: {e}")

                # Extract data using the scraper via unified adapter
                browser_adapter = BrowserAdapter(page, 'playwright')
                price = await scraper.extract_price(browser_adapter)
                details = await scraper.extract_product_details(browser_adapter)
                stock = await scraper.check_stock_status(browser_adapter)
                
                if price or details.get('name'):
                    result['price'] = price if price else None
                    result['status'] = 'success' if price else 'partial_success_no_price'
                    result['method'] = 'playwright'
                    result['details'] = details
                    result['name'] = details.get('name')
                    result['image_url'] = details.get('image_url')
                    result['stock'] = stock
                    await browser.close()
                    return result
            except Exception as e:
                print(f"  Playwright navigation/extraction error: {e}")
            
            await browser.close()
            
        except Exception as e:
            print(f"  Playwright failed: {e}")
            result['error'] = str(e)
            
        # ── SELENIUM FALLBACK ──
        print(f"  Falling back to Selenium...")
        
        options = Options()
        for arg in SELENIUM_ARGS:
            options.add_argument(arg)
        options.add_argument(f"user-agent={self.get_random_user_agent()}")
        
        # Hide automation flags
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        driver = None
        try:
            driver = webdriver.Chrome(
                service=ChromeService(ChromeDriverManager().install()),
                options=options
            )
            
            driver.get(original_url)
            time.sleep(10)  # Wait for redirects in Selenium
            
            final_url = driver.current_url
            print(f"  Selenium resolved URL to: {final_url}")
            result['url'] = final_url
            
            # Phase 2 for Selenium: re-identify from resolved URL if Phase 1 was generic
            if site == 'generic':
                site = self.identify_site(final_url)
                print(f"  Selenium Phase 2 identification: {site}")
            
            result['site'] = site
            scraper = ScraperFactory.get_scraper(final_url)
            print(f"  Selenium identified site: {result['site']}")
            
            # Extract data via unified adapter
            browser_adapter = BrowserAdapter(driver, 'selenium')
            price = await scraper.extract_price(browser_adapter)
            details = await scraper.extract_product_details(browser_adapter)
            stock = await scraper.check_stock_status(browser_adapter)
            
            if price or details.get('name'):
                result['price'] = price if price else None
                result['status'] = 'success' if price else 'partial_success_no_price'
                result['method'] = 'selenium'
                result['details'] = details
                result['name'] = details.get('name')
                result['image_url'] = details.get('image_url')
                result['stock'] = stock
            else:
                 result['status'] = 'failed_no_price'
        
        except Exception as e:
            print(f"  Selenium failed: {e}")
            result['error'] = f"Playwright and Selenium failed: {e}"
        finally:
            if driver:
                driver.quit()
                
        return result

    async def scrape_multiple_products(self, playwright, urls: list, max_concurrent: int = 5, use_virtual_display: bool = False) -> list:
        """Scrape multiple products concurrently"""
        results = []
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def scrape_bounded(url):
            async with semaphore:
                try:
                    return await self.scrape_product_price(playwright, url, use_virtual_display)
                except Exception as e:
                    return {
                        'url': url,
                        'error': str(e),
                        'status': 'error'
                    }

        tasks = [scrape_bounded(url) for url in urls]
        return await asyncio.gather(*tasks)
