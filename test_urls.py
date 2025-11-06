#!/usr/bin/env python3
"""
Test script to verify specific URLs are being scraped correctly
"""

import asyncio
from playwright.async_api import async_playwright
from product_price import EcommerceScraper

async def test_urls():
    """Test the three problematic URLs"""
    urls = [
        'https://myntr.it/xo9egPy',
        'https://fkrt.cc/h7H4CNp',
        'https://www.amazon.in/dp/B0DVLBTKPH/'
    ]
    
    scraper = EcommerceScraper()
    
    print("=" * 70)
    print("Testing URL Scraping")
    print("=" * 70)
    
    async with async_playwright() as playwright:
        for i, url in enumerate(urls, 1):
            print(f"\n[{i}/{len(urls)}] Testing: {url}")
            print("-" * 70)
            
            # Test site identification
            site = scraper.identify_site(url)
            print(f"✓ Site identified: {site}")
            
            try:
                result = await scraper.scrape_product_price(
                    playwright,
                    url,
                    headless=True,
                    use_virtual_display=False
                )
                
                print(f"✓ Price: {result.get('price', 'N/A')}")
                print(f"✓ Status: {result.get('status', 'N/A')}")
                print(f"✓ Method: {result.get('method', 'N/A')}")
                
                if result.get('price') and result['price'] != 'N/A':
                    print(f"✅ SUCCESS: Price found!")
                else:
                    print(f"❌ FAILED: Price not found")
                    
            except Exception as e:
                print(f"❌ ERROR: {e}")
                import traceback
                traceback.print_exc()
    
    print("\n" + "=" * 70)
    print("Testing Complete")
    print("=" * 70)

if __name__ == '__main__':
    asyncio.run(test_urls())

