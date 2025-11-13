#!/usr/bin/env python3
"""
Test Nykaa scraper with the provided URL using the main scraper
"""
import asyncio
from product_price import EcommerceScraper
from playwright.async_api import async_playwright

async def test_nykaa():
    url = "https://www.nykaa.com/bagsy-malone-stylish-vegan-leather-multipurpose-pouch/p/1491371"
    
    print("=" * 80)
    print("Testing Nykaa Scraper with Main EcommerceScraper")
    print("=" * 80)
    print(f"\nURL: {url}\n")
    
    scraper = EcommerceScraper()
    
    async with async_playwright() as playwright:
        try:
            result = await scraper.scrape_product_price(
                playwright,
                url,
                use_virtual_display=True,
                force_selenium=False  # Try Playwright first, fallback to Selenium
            )
            
            print("\n" + "=" * 80)
            print("RESULTS")
            print("=" * 80)
            print(f"Site: {result.get('site', 'unknown')}")
            print(f"Price: {result.get('price', 'N/A')}")
            print(f"Status: {result.get('status', 'unknown')}")
            print(f"Method: {result.get('method', 'unknown')}")
            print(f"Success: {result.get('success', False)}")
            
            if result.get('stock_status'):
                stock = result['stock_status']
                print(f"Stock: {stock.get('stock_status', 'unknown')} (in_stock: {stock.get('in_stock', 'unknown')})")
            
            if result.get('error'):
                print(f"Error: {result['error']}")
            
            if result.get('success') and result.get('price') != 'N/A':
                print(f"\n✅ SUCCESS! Price extracted: ₹{result.get('price')}")
            else:
                print(f"\n❌ FAILED to extract price")
                
        except Exception as e:
            print(f"❌ Exception: {e}")
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(test_nykaa())


