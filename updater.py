#!/usr/bin/env python3
import psycopg2
import os
import requests

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
        response = requests.post('http://appdeals.in/api/update-product-price', json={'product_id': id, 'price': price})
        if response.status_code == 200:
            print(f"Successfully updated product price for {id}")
        else:
            print(f"Failed to update product price for {id}")
            print(response.json())
    except Exception as e:
        print(f"Error: {e}")
        print(f"Failed to update product price for {id}")
        print(response.json())

if __name__ == '__main__':
    urls = get_product_urls()
    for id, url in urls:
        print(f"id: {id}, url: {url}")
        print(len(urls))
        
        break