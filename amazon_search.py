import re
import json
import urllib.parse
from playwright.sync_api import Playwright, sync_playwright, expect
import time
from typing import List, Dict


def scrape_amazon_products(playwright: Playwright, search_term: str = "iphone 17", max_pages: int = 1) -> List[Dict]:
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    )
    page = context.new_page()
    
    products = []
    
    try:
        page.goto("https://www.amazon.in/")
        time.sleep(2)
            
        search_box = page.get_by_role("searchbox", name="Search Amazon.in")
        search_box.click()
        search_box.fill(search_term)
        page.get_by_role("button", name="Go", exact=True).click()

        page.wait_for_selector('[data-component-type="s-search-result"]', timeout=10000)
        time.sleep(3)
            
        for page_num in range(max_pages):
                print(f"Scraping page {page_num + 1}...")
                
                page.wait_for_selector('[data-component-type="s-search-result"]', timeout=10000)
                
                product_containers = page.query_selector_all('[data-component-type="s-search-result"]')
                
                for container in product_containers:
                    try:
                        product_data = {}
                        
                        name_element = container.query_selector('h2 a span, h2 span, [data-cy="title-recipe-title"] span')
                        if name_element:
                            product_data['name'] = name_element.text_content().strip()
                        else:
                            name_alt = container.query_selector('h2 a, h2, .s-size-mini .s-color-base')
                            if name_alt:
                                product_data['name'] = name_alt.text_content().strip()
                            else:
                                product_data['name'] = "N/A"
                        
                        price_element = container.query_selector('.a-price-whole, .a-price .a-offscreen, .a-price-range')
                        if price_element:
                            price_text = price_element.text_content().strip()
                            price_clean = re.sub(r'[^\d.,₹$]', '', price_text)
                            product_data['price'] = price_clean if price_clean else price_text
                        else:
                            price_alt = container.query_selector('.a-price, .s-price, [data-cy="price-recipe"]')
                            if price_alt:
                                product_data['price'] = price_alt.text_content().strip()
                            else:
                                product_data['price'] = "N/A"
                        
                        # Extract high-resolution image (3x size)
                        img_element = container.query_selector('img')
                        if img_element:
                            # Try to get the highest resolution image
                            img_src = img_element.get_attribute('src')
                            img_data_src = img_element.get_attribute('data-src')
                            img_data_srcset = img_element.get_attribute('data-srcset')
                            
                            # Priority: data-srcset (highest res) > data-src > src
                            if img_data_srcset:
                                # Parse srcset to get the highest resolution image
                                srcset_parts = img_data_srcset.split(',')
                                highest_res_url = None
                                highest_res = 0
                                
                                for part in srcset_parts:
                                    part = part.strip()
                                    if ' ' in part:
                                        url, descriptor = part.rsplit(' ', 1)
                                        # Extract resolution (e.g., "3x", "2x", "400w")
                                        if 'x' in descriptor:
                                            try:
                                                res = float(descriptor.replace('x', ''))
                                                if res > highest_res:
                                                    highest_res = res
                                                    highest_res_url = url
                                            except:
                                                pass
                                        elif 'w' in descriptor:
                                            try:
                                                width = int(descriptor.replace('w', ''))
                                                if width > highest_res:
                                                    highest_res = width
                                                    highest_res_url = url
                                            except:
                                                pass
                                
                                if highest_res_url:
                                    product_data['image_url'] = highest_res_url
                                else:
                                    # Fallback to first URL in srcset
                                    product_data['image_url'] = srcset_parts[0].strip().split(' ')[0]
                            elif img_data_src:
                                product_data['image_url'] = img_data_src
                            elif img_src:
                                # Try to get higher resolution version of the image
                                if '_AC_' in img_src:
                                    # Amazon image URL pattern - try to get 3x version
                                    if '_AC_SX300_' in img_src:
                                        product_data['image_url'] = img_src.replace('_AC_SX300_', '_AC_SX900_')
                                    elif '_AC_SX200_' in img_src:
                                        product_data['image_url'] = img_src.replace('_AC_SX200_', '_AC_SX600_')
                                    elif '_AC_SX150_' in img_src:
                                        product_data['image_url'] = img_src.replace('_AC_SX150_', '_AC_SX450_')
                                    elif '_AC_SX100_' in img_src:
                                        product_data['image_url'] = img_src.replace('_AC_SX100_', '_AC_SX300_')
                                    else:
                                        # Try to modify dimensions in URL
                                        if '._AC_' in img_src:
                                            # Replace with higher resolution
                                            product_data['image_url'] = img_src.replace('._AC_', '._AC_SX900_')
                                        else:
                                            product_data['image_url'] = img_src
                                else:
                                    product_data['image_url'] = img_src
                            else:
                                product_data['image_url'] = "N/A"
                        else:
                            product_data['image_url'] = "N/A"
                        
                        # Extract product URL with multiple selectors
                        link_element = container.query_selector('h2 a, .s-size-mini a, [data-cy="title-recipe-title"] a, a[href*="/dp/"], a[href*="/sspa/click"]')
                        if link_element:
                            href = link_element.get_attribute('href')
                            if href:
                                # Handle complex Amazon URLs (sponsored/affiliate links)
                                if '/sspa/click' in href:
                                    # Extract the actual product URL from the tracking URL
                                    try:
                                        # Parse the URL to extract the actual product URL
                                        parsed_url = urllib.parse.urlparse(href)
                                        query_params = urllib.parse.parse_qs(parsed_url.query)
                                        if 'url' in query_params:
                                            # Decode the URL parameter
                                            encoded_url = query_params['url'][0]
                                            decoded_url = urllib.parse.unquote(encoded_url)
                                            if decoded_url.startswith('/'):
                                                product_data['product_url'] = f"https://www.amazon.in{decoded_url}"
                                            else:
                                                product_data['product_url'] = decoded_url
                                        else:
                                            product_data['product_url'] = f"https://www.amazon.in{href}"
                                    except:
                                        product_data['product_url'] = f"https://www.amazon.in{href}"
                                else:
                                    # Handle regular product links
                                    if href.startswith('/'):
                                        product_data['product_url'] = f"https://www.amazon.in{href}"
                                    elif href.startswith('http'):
                                        product_data['product_url'] = href
                                    else:
                                        product_data['product_url'] = f"https://www.amazon.in/{href}"
                            else:
                                product_data['product_url'] = "N/A"
                        else:
                            # Try alternative selectors for product links
                            alt_link = container.query_selector('a[href*="/dp/"], a[href*="/gp/product/"], a[href*="/sspa/click"]')
                            if alt_link:
                                href = alt_link.get_attribute('href')
                                if href:
                                    if '/sspa/click' in href:
                                        # Handle sponsored links
                                        try:
                                            parsed_url = urllib.parse.urlparse(href)
                                            query_params = urllib.parse.parse_qs(parsed_url.query)
                                            if 'url' in query_params:
                                                encoded_url = query_params['url'][0]
                                                decoded_url = urllib.parse.unquote(encoded_url)
                                                if decoded_url.startswith('/'):
                                                    product_data['product_url'] = f"https://www.amazon.in{decoded_url}"
                                                else:
                                                    product_data['product_url'] = decoded_url
                                            else:
                                                product_data['product_url'] = f"https://www.amazon.in{href}"
                                        except:
                                            product_data['product_url'] = f"https://www.amazon.in{href}"
                                    else:
                                        if href.startswith('/'):
                                            product_data['product_url'] = f"https://www.amazon.in{href}"
                                        else:
                                            product_data['product_url'] = href
                                else:
                                    product_data['product_url'] = "N/A"
                            else:
                                product_data['product_url'] = "N/A"
                        
                        rating_element = container.query_selector('.a-icon-alt, .a-icon-star-small')
                        if rating_element:
                            rating_text = rating_element.text_content().strip()
                            product_data['rating'] = rating_text
                        else:
                            product_data['rating'] = "N/A"
                        
                        if product_data['name'] != "N/A" and product_data['name']:
                            products.append(product_data)
                            print(f"Found product: {product_data['name'][:50]}...")
                            print(f"  URL: {product_data['product_url']}")
                    
                    except Exception as e:
                        print(f"Error extracting product data: {e}")
                        continue
                
                if page_num < max_pages - 1:
                    try:
                        next_button = page.query_selector('a[aria-label="Go to next page"]')
                        if next_button:
                            next_button.click()
                            time.sleep(3)
                        else:
                            print("No more pages available")
                            break
                    except Exception as e:
                        print(f"Error navigating to next page: {e}")
                        break
    
    except Exception as e:
        print(f"Error during scraping: {e}")
    
    finally:
        context.close()
        browser.close()
    
    return products


def save_to_json(products: List[Dict], filename: str = "amazon_products.json"):
    """Save products to JSON file"""
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(products, f, indent=2, ensure_ascii=False)
    print(f"Products saved to {filename}")


def run(playwright: Playwright) -> None:
    """
    Main function to run the Amazon product scraper
    """
    search_term = input("Enter search term (default: iphone 17): ").strip() or "iphone 17"
    max_pages = int(input("Enter number of pages to scrape (default: 1): ") or "1")
    
    print(f"Starting to scrape Amazon for: '{search_term}'")
    print(f"Scraping {max_pages} page(s)...")
    
    products = scrape_amazon_products(playwright, search_term, max_pages)
    
    if products:
        print(f"\nScraped {len(products)} products successfully!")
        
        # Display first few products
        print("\nFirst few products:")
        for i, product in enumerate(products[:3]):
            print(f"\n{i+1}. {product['name']}")
            print(f"   Price: {product['price']}")
            print(f"   Rating: {product['rating']}")
            print(f"   Image: {product['image_url'][:50]}...")
        
        # Save to JSON file
        save_to_json(products)
        
        # Ask user if they want to see all products
        show_all = input("\nDo you want to see all products? (y/n): ").lower().strip()
        if show_all == 'y':
            for i, product in enumerate(products, 1):
                print(f"\n{i}. {product['name']}")
                print(f"   Price: {product['price']}")
                print(f"   Rating: {product['rating']}")
                print(f"   URL: {product['product_url']}")
    else:
        print("No products found!")


if __name__ == "__main__":
    with sync_playwright() as playwright:
        run(playwright)