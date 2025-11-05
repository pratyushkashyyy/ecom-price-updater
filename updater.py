#!/usr/bin/env python3
import psycopg2
import os
import httpx
import urllib.parse
import csv
import asyncio
from pathlib import Path


# Database connection
DB_CONFIG = {
    'host': os.getenv('PGHOST', 'localhost'),
    'database': os.getenv('PGDATABASE', 'affiliate2'),
    'user': os.getenv('PGUSER', 'pk'),
    'password': os.getenv('PGPASSWORD', 'Uncharted'),
    'port': int(os.getenv('PGPORT', '5432'))
}


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
            response = await client.get(url, follow_redirects=True, timeout=10.0)
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
    """Scrape product price from URL (async)"""
    async with semaphore:  # Limit concurrent requests
        print(f"Scraping product price for {id} with URL {url}")
        try:
            # Expand short URLs (like amzn.to) before scraping
            expanded_url = await expand_short_url(url, client)
            
            encoded_url = urllib.parse.quote(expanded_url, safe='')
            api_url = f"https://ecom-price.appdeals.in/api/price?url={encoded_url}"
            response = await client.get(api_url, timeout=30.0)
            if response.status_code == 200:
                data = response.json()
                
                # Check if scraping was successful
                success = data.get('success', False)
                price_str = data.get('price')
                
                # Validate price exists and scraping was successful
                if not success or not price_str:
                    print(f"⚠️  Scraping failed for ID {id}: {data.get('error', 'Unknown error')}")
                    return None
                
                # Remove commas and convert to float first (handles decimals), then to int
                price_clean = str(price_str).replace(',', '').strip()
                try:
                    price = int(float(price_clean))
                    
                    # Validation: Reject suspicious default prices
                    # Amazon products rarely cost exactly 500, so this is likely a fallback
                    if price == 500 and ('amzn.to' in url.lower() or 'amazon' in url.lower()):
                        print(f"⚠️  Suspicious price 500 for Amazon URL {id} - likely scraping failure")
                        return None
                    
                    # Additional validation: Amazon prices should typically be >= 10 (minimum validation from scraper)
                    if price < 10 and ('amzn.to' in url.lower() or 'amazon' in url.lower()):
                        print(f"⚠️  Price {price} seems too low for Amazon product {id}")
                        # Return None for very low prices, but allow it if it's a real small item
                        # Minimum price threshold is 10
                    
                    return price
                except (ValueError, TypeError) as e:
                    print(f"Error parsing price for ID {id}: {e}")
                    return None
            else:
                print(f"API returned status code: {response.status_code} for ID {id}")
                return None
        except Exception as e:
            print(f"Error scraping {id}: {e}")
            return None


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
    price = await scraping_product_price(id, url, client, semaphore)
    
    # Use lock for thread-safe CSV writing
    async with csv_lock:
        with open(output_file, 'a', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
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
    urls_to_process = []
    resume_found = False if last_processed_id else True
    
    for id, url in urls:
        # Skip until we pass the last processed ID
        if not resume_found:
            if id == last_processed_id:
                resume_found = True
                print(f"Resuming from next ID after {id}")
                continue  # Skip the last processed ID itself
            else:
                continue  # Skip IDs before the resume point
        urls_to_process.append((id, url))
    
    print(f"Processing {len(urls_to_process)} URLs with 10 concurrent workers...")
    
    # Write CSV header if file doesn't exist
    if not file_exists:
        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['id', 'url', 'price'])
    
    # Create semaphore to limit concurrent requests to 10
    semaphore = asyncio.Semaphore(2)
    # Create lock for CSV writing
    csv_lock = asyncio.Lock()
    
    # Create HTTP client with connection pooling
    async with httpx.AsyncClient(timeout=30.0) as client:
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