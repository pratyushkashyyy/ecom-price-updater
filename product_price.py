import re
import json
import urllib.parse
import random
import asyncio
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

    async def scrape_product_price(self, playwright: Playwright, product_url: str, headless: bool = True) -> Dict:
        user_agent = random.choice(self.user_agents)
        
        browser = await playwright.chromium.launch(headless=headless)
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
        
        try:
            max_retries = 2
            for attempt in range(max_retries):
                try:
                    await page.goto(product_url, timeout=30000, wait_until='domcontentloaded')
                    await asyncio.sleep(3 + random.uniform(1, 3))
                    break
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise e
                    await asyncio.sleep(2 + random.uniform(0.5, 1.5))
            
            site = self.identify_site(product_url)
            result = {
                'url': product_url,
                'site': site,
                'price': 'N/A',
                'status': 'success'
            }
            
            price_selectors = self.site_selectors.get(site, ['.price', '[class*="price"]', '#price'])
            
            async def strategy1_site_selectors():
                for selector in price_selectors:
                    try:
                        price_elements = await page.query_selector_all(selector)
                        for element in price_elements:
                            price_text = (await element.text_content()).strip()
                            cleaned_price = self.clean_price(price_text)
                            if cleaned_price != "N/A" and self.is_valid_price(cleaned_price):
                                return cleaned_price
                    except:
                        continue
                return None
            
            async def strategy2_pattern_matching():
                try:
                    all_elements = await page.query_selector_all('*')
                    for element in all_elements:
                        text = await element.text_content()
                        if text and re.search(r'[₹$€£¥]\s*\d{2,}|\d{3,}', text):
                            cleaned_price = self.clean_price(text)
                            if cleaned_price != "N/A" and self.is_valid_price(cleaned_price):
                                return cleaned_price
                except:
                    pass
                return None
            
            async def strategy3_json_ld():
                try:
                    json_scripts = await page.query_selector_all('script[type="application/ld+json"]')
                    for script in json_scripts:
                        try:
                            json_data = json.loads(await script.text_content())
                            if isinstance(json_data, dict) and 'offers' in json_data:
                                offers = json_data['offers']
                                if isinstance(offers, dict) and 'price' in offers:
                                    return str(offers['price'])
                        except:
                            continue
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
            
            return result
            
        except Exception as e:
            return {
                'url': product_url,
                'site': self.identify_site(product_url),
                'price': 'N/A',
                'status': f'Error: {str(e)}'
            }
        finally:
            await context.close()
            await browser.close()

    async def scrape_multiple_products(self, playwright: Playwright, urls: List[str], 
                                        max_concurrent: int = 20, headless: bool = True) -> List[Dict]:
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def scrape_with_limit(url):
            async with semaphore:
                return await self.scrape_product_price(playwright, url, headless=headless)
        
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
    
    # Test URLs for different sites - Real working product URLs
    test_urls = [
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
    
    print("Testing E-commerce Price Scraper (Async, Concurrency Only)")
    print("=" * 70)
    
    async with async_playwright() as playwright:
        results = await scraper.scrape_multiple_products(
            playwright,
            test_urls,
            max_concurrent=20,
            headless=True,
        )
        
        for i, result in enumerate(results, 1):
            print(f"\n{i}. {result['site'].upper()}")
            print(f"   URL: {result['url']}")
            print(f"   Price: {result['price']}")
            print(f"   Status: {result['status']}")

# Example usage
if __name__ == "__main__":
    asyncio.run(main())