#!/usr/bin/env python3
"""
E-commerce Price Scraper
Scrapes product prices from multiple e-commerce sites with automatic Playwright/Selenium fallback
"""

import asyncio
import sys
from product_price import EcommerceScraper
from playwright.async_api import async_playwright


async def scrape_price(url: str, use_virtual_display: bool = False) -> dict:
    """
    Scrape price from a single product URL
    
    Args:
        url: Product URL to scrape
        use_virtual_display: Use Xvfb virtual display for browser automation
        
    Returns:
        Dictionary with url, site, price, status, and method used
    """
    scraper = EcommerceScraper()
    
    async with async_playwright() as playwright:
        result = await scraper.scrape_product_price(
            playwright,
            url,
            use_virtual_display=use_virtual_display
        )
    
    return result


async def scrape_prices(urls: list, max_concurrent: int = 5, use_virtual_display: bool = False) -> list:
    """
    Scrape prices from multiple product URLs
    
    Args:
        urls: List of product URLs to scrape
        max_concurrent: Maximum number of concurrent scrapes
        use_virtual_display: Use Xvfb virtual display for browser automation
        
    Returns:
        List of dictionaries with scraping results
    """
    scraper = EcommerceScraper()
    
    async with async_playwright() as playwright:
        results = await scraper.scrape_multiple_products(
            playwright,
            urls,
            max_concurrent=max_concurrent,
            use_virtual_display=use_virtual_display
        )
    
    return results


def print_result(result: dict, index: int = None):
    """Print a single scraping result in a formatted way"""
    prefix = f"{index}. " if index is not None else ""
    site = result.get('site', 'UNKNOWN').upper()
    price = result.get('price', 'N/A')
    method = result.get('method', 'unknown')
    status = result.get('status', '')
    
    # Format URL (truncate if too long)
    url = result.get('url', '')
    url_display = url[:70] + "..." if len(url) > 70 else url
    
    print(f"\n{prefix}{site}")
    print(f"   URL: {url_display}")
    print(f"   Price: ₹{price}" if price != 'N/A' else "   Price: N/A")
    print(f"   Method: {method}")
    if status:
        print(f"   Status: {status}")


def print_summary(results: list):
    """Print a summary of scraping results"""
    playwright_success = []
    selenium_used = []
    failed = []
    
    for result in results:
        method = result.get('method', 'unknown')
        site = result.get('site', 'UNKNOWN').upper()
        price = result.get('price', 'N/A')
        
        if method == 'playwright' and price != 'N/A':
            playwright_success.append(site)
        elif method == 'selenium' and price != 'N/A':
            selenium_used.append(site)
        else:
            failed.append(site)
    
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"\n✅ Playwright Success: {len(playwright_success)} sites")
    if playwright_success:
        print(f"   {', '.join(set(playwright_success))}")
    
    print(f"\n⚠️  Selenium Required (Blocked): {len(selenium_used)} sites")
    if selenium_used:
        print(f"   {', '.join(set(selenium_used))}")
    
    print(f"\n❌ Failed: {len(failed)} sites")
    if failed:
        print(f"   {', '.join(set(failed))}")
    
    # Success rate
    success = len(playwright_success) + len(selenium_used)
    total = len(results)
    success_rate = (success / total * 100) if total > 0 else 0
    print(f"\n📊 Success Rate: {success}/{total} ({success_rate:.1f}%)")


async def main():
    """Main function to run price scraping"""
    
    # Default test URLs (can be customized)
    default_urls = [
        "https://www.amazon.in/Apple-MacBook-16-inch-16%E2%80%91core-40%E2%80%91core/dp/B0CM5QYZ3R/",
        "https://www.flipkart.com/24-energy-large-battery-mosquito-bat-big-head-racquet-light-charging-wire-electric-insect-killer-indoor-outdoor/p/itm997a7e072213f",
        "https://www.myntra.com/sports-shoes/hrx+by+hrithik+roshan/hrx-by-hrithik-roshan-unisex-mesh-running--shoes/32093860/buy",
        "https://www.nykaa.com/braun-silk-epil-9-890-epilator-for-long-lasting-hair-removal-includes-a-bikini-styler/p/1178844",
        "https://www.ajio.com/yousta-men-washed-relaxed-fit-crew-neck-t-shirt/p/443079993_blackcharcoal",
        "https://www.meesho.com/frekman-stylish-cotton-blend-check-mens-shirt/p/1kv4b",
    ]
    
    # Check for virtual display flag first
    use_virtual_display = '--virtual-display' in sys.argv or '-v' in sys.argv
    
    # Filter out virtual display flags and get URLs
    url_args = [arg for arg in sys.argv[1:] if arg not in ['--virtual-display', '-v']]
    
    # Check if URLs are provided as command line arguments
    if len(url_args) > 0:
        urls = url_args
        print(f"Scraping prices from {len(urls)} URL(s)...")
    else:
        urls = default_urls
        print(f"Using default test URLs ({len(urls)} sites)...")
        print("Usage: python scrape_prices.py [--virtual-display|-v] <url1> <url2> ...")
        print("       --virtual-display or -v: Use virtual display for browser automation")
    
    print("=" * 70)
    print("E-commerce Price Scraper")
    print("=" * 70)
    
    if use_virtual_display:
        print("\nUsing virtual display (Xvfb) - browsers run without physical display")
        print("Starting scraping (trying Playwright first, falling back to Selenium if blocked)...")
    else:
        print("\nStarting scraping (trying Playwright first, falling back to Selenium if blocked)...")
    
    # Scrape prices
    results = await scrape_prices(urls, max_concurrent=5, use_virtual_display=use_virtual_display)
    
    # Print results
    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)
    
    for i, result in enumerate(results, 1):
        print_result(result, index=i)
    
    # Print summary
    print_summary(results)
    
    # Return results as JSON if needed (for programmatic use)
    return results


if __name__ == "__main__":
    try:
        results = asyncio.run(main())
        
        # Optionally save results to a file
        import json
        with open('price_results.json', 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\n💾 Results saved to price_results.json")
        
    except KeyboardInterrupt:
        print("\n\n❌ Scraping interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


