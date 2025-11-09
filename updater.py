#!/usr/bin/env python3
import psycopg2
import os
import httpx
import urllib.parse
import csv
import asyncio
from pathlib import Path
from urllib.parse import urlparse


# Database connection
DB_CONFIG = {
    'host': os.getenv('PGHOST', 'localhost'),
    'database': os.getenv('PGDATABASE', 'affiliate2'),
    'user': os.getenv('PGUSER', 'pk'),
    'password': os.getenv('PGPASSWORD', 'Uncharted'),
    'port': int(os.getenv('PGPORT', '5432'))
}

# API URL for price scraping
API_BASE_URL = os.getenv('API_BASE_URL', 'http://localhost:6000')


def get_product_urls():
    """Get all product URLs from products table"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute('SELECT "id", "productUrl" FROM products WHERE "productUrl" IS NOT NULL AND "is_collection" = false AND "productUrl" != \'\';')
        results = [(row[0], row[1]) for row in cursor.fetchall()]
        cursor.close()
        conn.close()
        return results
    except Exception as e:
        print(f"Error: {e}")
        return []

async def update_product_price(id, price, client):
    """Update product price in products table by calling the API"""
    print(f"Updating product price for {id} with Price {price}")
    try:
        response = await client.post('https://testing.appdeals.in/api/update-product-price', json={'product_id': id, 'price': price})
        if response.status_code == 200:
            print(f"Successfully updated product price for {id}")
            print(response.json())
        else:
            print(f"Failed to update product price for {id}")
            print(response.json())
    except Exception as e:
        print(f"Error: {e}")
        print(f"Failed to update product price for {id}")

async def expand_short_url(url, client):
    """Expand short URLs (like amzn.to) to full URLs by following redirects"""
    # Only expand if it's a short link (amzn.to) or doesn't contain a full domain
    if 'amzn.to' in url.lower():
        try:
            # Follow redirects to get the final URL
            response = await client.get(url, follow_redirects=True, timeout=30.0)
            final_url = str(response.url)
            # Only return if it's actually an Amazon URL
            if 'amazon.in' in final_url or 'amazon.com' in final_url:
                print(f"Expanded short URL to: {final_url[:80]}...")
                return final_url
            else:
                print(f"Warning: Short URL redirects to non-Amazon URL: {final_url[:80]}...")
                return url  # Return original if redirect doesn't go to Amazon
        except Exception as e:
            print(f"Warning: Could not expand short URL {url}: {e}")
            return url  # Return original URL if expansion fails
    return url


async def scraping_product_price(id, url, client, semaphore):
    """Scrape product price from URL (async) - returns tuple (price, stock_status)"""
    async with semaphore:  # Limit concurrent requests
        print(f"Scraping product price for {id} with URL {url}")
        
        # Retry logic for timeout errors
        max_retries = 2
        retry_delays = [5, 10]  # Wait 5s then 10s between retries
        
        for attempt in range(max_retries + 1):
        try:
            # Expand short URLs (like amzn.to) before scraping
            expanded_url = await expand_short_url(url, client)
            
            encoded_url = urllib.parse.quote(expanded_url, safe='')
                # Increase max_retries for sites that are known to be difficult to scrape
                difficult_sites = ['meesho', 'ajio', 'myntra', 'nykaa']
                # Simple site identification from URL
                domain = urlparse(expanded_url).netloc.lower()
                site = None
                if 'meesho' in domain or 'msho.in' in domain:
                    site = 'meesho'
                elif 'ajio' in domain or 'ajiio.in' in domain:
                    site = 'ajio'
                elif 'myntra' in domain or 'myntr.it' in domain:
                    site = 'myntra'
                elif 'nykaa' in domain:
                    site = 'nykaa'
                max_retries_param = 3 if site in difficult_sites else 2  # More retries for difficult sites
                api_url = f"{API_BASE_URL}/api/price?url={encoded_url}&max_retries={max_retries_param}"
                # Increased timeout to 180 seconds as scraping can take 50+ seconds, some sites need more time
                timeout_value = 180.0 if attempt == 0 else 240.0  # Longer timeout on retries
                response = await client.get(api_url, timeout=timeout_value)
            
            # API returns 200 for success and 404 for failed scrapes (but with JSON body)
            # Handle both cases
            if response.status_code in [200, 404]:
                try:
                    data = response.json()
                except Exception as e:
                    print(f"⚠️  Could not parse JSON response for ID {id}: {e}")
                        return (None, None)
                    
                    # Extract stock status information
                    stock_status = data.get('stock_status', 'unknown')
                    in_stock = data.get('in_stock', True)
                    
                    # Check if product is out of stock
                    is_out_of_stock = stock_status == 'out_of_stock' or (stock_status == 'unknown' and not in_stock)
                
                # Check if scraping was successful
                success = data.get('success', False)
                price_str = data.get('price')
                
                    # If product is out of stock, save it with OUT_OF_STOCK marker
                    if is_out_of_stock:
                        stock_message = data.get('stock_message', 'Product is out of stock')
                        print(f"📦 Product {id} is OUT OF STOCK: {stock_message}")
                        return ('OUT_OF_STOCK', 'out_of_stock')
                    
                # Validate price exists and scraping was successful
                if not success or not price_str:
                    error_msg = data.get('error', data.get('status', 'Unknown error'))
                        
                        # For Flipkart: If price extraction failed, check if it's because product is out of stock
                        if 'flipkart' in url.lower() or 'fkrt.cc' in url.lower():
                            # Re-check stock status - price extraction failure might indicate out of stock
                            if stock_status == 'unknown' or stock_status is None:
                                # If stock status is unknown and price extraction failed, it might be out of stock
                                # Check the status message for clues
                                status_msg = data.get('status', '').lower()
                                if any(keyword in status_msg for keyword in ['out of stock', 'unavailable', 'notify', 'sold out']):
                                    print(f"📦 Product {id} appears to be OUT OF STOCK (price extraction failed, status indicates out of stock)")
                                    return ('OUT_OF_STOCK', 'out_of_stock')
                        
                    print(f"⚠️  Scraping failed for ID {id} ({url[:60]}...): {error_msg}")
                    if response.status_code == 404:
                        print(f"   (API returned 404 - price not found after retries)")
                        return (None, stock_status)
                
                # Remove commas and convert to float first (handles decimals), then to int
                price_clean = str(price_str).replace(',', '').strip()
                try:
                    price = int(float(price_clean))
                    
                    # Validation: Reject suspicious default prices
                    # Amazon products rarely cost exactly 500, so this is likely a fallback
                    if price == 500 and ('amzn.to' in url.lower() or 'amazon' in url.lower()):
                        print(f"⚠️  Suspicious price 500 for Amazon URL {id} - likely scraping failure")
                            return (None, stock_status)
                    
                    # Additional validation: Amazon prices should typically be >= 10 (minimum validation from scraper)
                    if price < 10 and ('amzn.to' in url.lower() or 'amazon' in url.lower()):
                        print(f"⚠️  Price {price} seems too low for Amazon product {id}")
                        # Return None for very low prices, but allow it if it's a real small item
                        # Minimum price threshold is 10
                    
                        # Validation for Hygulife: prices should be >= 50 (minimum validation from scraper)
                        if price < 50 and ('bitli.in' in url.lower() or 'hygulife' in url.lower() or 'hyugalife' in url.lower()):
                            print(f"⚠️  Price {price} seems too low for Hygulife product {id} - likely scraping failure")
                            return (None, stock_status)
                        
                        return (price, stock_status)
                except (ValueError, TypeError) as e:
                    print(f"Error parsing price for ID {id}: {e}")
                        return (None, stock_status)
            else:
                error_body = ""
                try:
                    error_body = response.text[:200]
                except:
                    pass
                print(f"⚠️  API returned status code: {response.status_code} for ID {id}")
                print(f"   Response: {error_body}")
                    return (None, None)
                
            except httpx.ReadTimeout as e:
                if attempt < max_retries:
                    wait_time = retry_delays[attempt]
                    print(f"⏱️  ReadTimeout for ID {id} (attempt {attempt + 1}/{max_retries + 1}), retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    print(f"❌ ReadTimeout for ID {id} after {max_retries + 1} attempts - API request took too long")
                    return (None, None)
            except httpx.TimeoutException as e:
                if attempt < max_retries:
                    wait_time = retry_delays[attempt]
                    print(f"⏱️  TimeoutException for ID {id} (attempt {attempt + 1}/{max_retries + 1}), retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    print(f"❌ TimeoutException for ID {id} after {max_retries + 1} attempts - API request timed out")
                    return (None, None)
        except Exception as e:
            import traceback
            error_msg = str(e) if str(e) else type(e).__name__
                # Don't retry on non-timeout errors
            print(f"❌ Error scraping {id} ({url[:60]}...): {error_msg}")
            print(f"   Exception type: {type(e).__name__}")
                if attempt == 0:  # Only print traceback on first attempt
            traceback.print_exc()
                return (None, None)


def get_last_processed_id(csv_file):
    """Get the last processed ID from CSV file"""
    if not Path(csv_file).is_file():
        return None
    
    try:
        with open(csv_file, 'r', encoding='utf-8') as csvfile:
            reader = csv.reader(csvfile)
            # Skip header row
            next(reader, None)
            last_id = None
            for row in reader:
                if row and row[0]:
                    try:
                        last_id = int(row[0])
                    except ValueError:
                        continue
            return last_id
    except Exception as e:
        print(f"Error reading CSV file: {e}")
        return None


async def process_product(id, url, client, semaphore, csv_lock, output_file):
    """Process a single product: scrape price and write to CSV"""
    price, stock_status = await scraping_product_price(id, url, client, semaphore)
    
    # Use lock for thread-safe CSV writing
    async with csv_lock:
        with open(output_file, 'a', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            # Write price (which could be a number, 'OUT_OF_STOCK', or None)
            writer.writerow([id, url, price])


async def main():
    """Main async function to process all products with 10 concurrent workers"""
    output_file = 'product_prices.csv'
    file_exists = Path(output_file).is_file()
    
    # Get the last processed ID to resume from
    last_processed_id = get_last_processed_id(output_file)
    if last_processed_id:
        print(f"Resuming from ID: {last_processed_id}")
    else:
        print("Starting from the beginning")
    
    urls = get_product_urls()
    print(f"Total URLs to process: {len(urls)}")
    
    # Filter URLs to process (skip already processed ones)
    # Read all processed IDs from CSV to avoid reprocessing
    processed_ids = set()
    if file_exists:
        try:
            with open(output_file, 'r', encoding='utf-8') as csvfile:
                reader = csv.reader(csvfile)
                next(reader, None)  # Skip header
                for row in reader:
                    if row and row[0] and row[0].isdigit():
                        processed_ids.add(int(row[0]))
        except Exception as e:
            print(f"Warning: Could not read processed IDs from CSV: {e}")
    
    # Only process URLs that haven't been processed yet (or don't have a valid price)
    urls_to_process = []
    for id, url in urls:
        if id not in processed_ids:
            urls_to_process.append((id, url))
        else:
            # Check if it has a valid price (not empty/None)
            # We'll skip reprocessing for now, but could add logic to reprocess failed ones
            pass
    
    print(f"Processing {len(urls_to_process)} URLs with 10 concurrent workers...")
    
    # Write CSV header if file doesn't exist
    if not file_exists:
        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['id', 'url', 'price'])  # price will be number, 'OUT_OF_STOCK', or empty
    
    # Create semaphore to limit concurrent requests to 10
    semaphore = asyncio.Semaphore(3)
    # Create lock for CSV writing
    csv_lock = asyncio.Lock()
    
    # Create HTTP client with connection pooling
    # Increased timeout to 180 seconds as scraping can take 50+ seconds, some sites need more time
    async with httpx.AsyncClient(timeout=180.0) as client:
        # Create tasks for all products
        tasks = [
            process_product(id, url, client, semaphore, csv_lock, output_file)
            for id, url in urls_to_process
        ]
        
        # Process all tasks concurrently (limited by semaphore)
        await asyncio.gather(*tasks, return_exceptions=True)
    
    print("Processing complete!")


if __name__ == '__main__':
    asyncio.run(main())