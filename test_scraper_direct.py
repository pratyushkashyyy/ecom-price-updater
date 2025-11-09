#!/usr/bin/env python3
"""
Direct test of the scraper without API
Tests multiple URLs to verify core logic is working
"""

import asyncio
import sys
from product_price import EcommerceScraper
from playwright.async_api import async_playwright

# Test URLs - testing various e-commerce sites
TEST_URLS = [
    # Keep Ajio and Meesho for Playwright-only testing (even though blocked)
    "https://ajiio.in/EBdvla1",      # Ajio - Playwright-only mode
    "https://msho.in/Y9T7yO",        # Meesho - Playwright-only mode
    
    # Test URLs provided by user
    "https://myntr.it/plvEm29",      # Myntra
    "https://fkrt.cc/hBM5Bbl",       # Flipkart (short URL)
    "https://www.amazon.in/dp/B0F4436C9W?ck&tag=earnkaro09e_1454-21",  # Amazon
    "https://bitli.in/aidesDq",      # Hygulife
    "https://bitli.in/A2r9LZr",      # Hygulife
    "https://www.shopsy.in/cotton-single-bedsheet/p/itmaf2b82db462b5?pid=XPBGZJFARHYC37FX&lid=LSTXPBGZJFARHYC37FXN7KGCA&marketplace=FLIPKART&store=jra",  # Shopsy (Flipkart)
]

async def test_scraper():
    """Test the scraper directly"""
    scraper = EcommerceScraper()
    
    print("=" * 80)
    print("Testing E-commerce Scraper Directly (No API)")
    print("=" * 80)
    print(f"\nTesting {len(TEST_URLS)} URLs...\n")
    
    results = []
    
    async with async_playwright() as playwright:
        for i, url in enumerate(TEST_URLS, 1):
            print(f"\n[{i}/{len(TEST_URLS)}] Testing: {url[:60]}...")
            print("-" * 80)
            
            # Force Playwright for Ajio and Meesho (no Selenium fallback)
            site = scraper.identify_site(url)
            force_playwright = site in ['ajio', 'meesho']
            if force_playwright:
                print(f"🔧 Force Playwright mode for {site} (no Selenium fallback)")
            
            try:
                result = await scraper.scrape_product_price(
                    playwright,
                    url,
                    use_virtual_display=True,  # Use virtual display to avoid bot detection
                    force_playwright=force_playwright  # Force Playwright for Ajio/Meesho
                )
                
                results.append(result)
                
                # Print results
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
                
            except Exception as e:
                print(f"❌ Exception: {e}")
                import traceback
                traceback.print_exc()
                results.append({
                    'url': url,
                    'error': str(e),
                    'success': False
                })
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    successful = [r for r in results if r.get('success') and r.get('price') != 'N/A']
    failed = [r for r in results if not r.get('success') or r.get('price') == 'N/A']
    
    print(f"\n✅ Successful: {len(successful)}/{len(TEST_URLS)}")
    for r in successful:
        print(f"   - {r.get('site', 'unknown')}: {r.get('price', 'N/A')} ({r.get('method', 'unknown')})")
    
    print(f"\n❌ Failed: {len(failed)}/{len(TEST_URLS)}")
    for r in failed:
        print(f"   - {r.get('url', 'unknown')[:60]}...")
        print(f"     Site: {r.get('site', 'unknown')}, Status: {r.get('status', 'unknown')}")
        if r.get('error'):
            print(f"     Error: {r['error'][:100]}")

if __name__ == '__main__':
    asyncio.run(test_scraper())

