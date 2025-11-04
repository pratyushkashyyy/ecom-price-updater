#!/usr/bin/env python3
import psycopg2
import os
import requests
import urllib.parse

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

def update_product_price(id, price):
    """Update product price in products table by calling the API"""
    print(f"Updating product price for {id} with Price {price}")
    try:
        response = requests.post('http://127.0.0.1:8000/api/update-product-price', json={'product_id': id, 'price': price})
        if response.status_code == 200:
            print(f"Successfully updated product price for {id}")
            print(response.json())
        else:
            print(f"Failed to update product price for {id}")
            print(response.json())
    except Exception as e:
        print(f"Error: {e}")
        print(f"Failed to update product price for {id}")

def scraping_product_price(id, url):
    """Scrape product price from URL"""
    print(f"Scraping product price for {id} with URL {url}")
    try:
        encoded_url = urllib.parse.quote(url, safe='')
        api_url = f"https://ecom-price.appdeals.in/api/price?url={encoded_url}"
        response = requests.get(api_url)
        if response.status_code == 200:
            data = response.json()
            return data.get('price')
        else:
            print(f"API returned status code: {response.status_code}")
            return None
    except Exception as e:
        print(f"Error: {e}")
        return None



if __name__ == '__main__':
    urls = get_product_urls()
    print(len(urls))
    for id, url in urls:
        if id == 1955:
            print(scraping_product_price(id, url))
            update_product_price(id,10000)
            print(f"id: {id}, url: {url}")
            break