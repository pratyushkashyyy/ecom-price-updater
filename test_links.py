import asyncio
import os
import json
from product_price import EcommerceScraper

async def test_links():
    scraper = EcommerceScraper()
    
    # Read links from file
    with open("links.txt", "r") as f:
        links = [line.strip() for line in f if line.strip() and not line.startswith("#")]
        
    print(f"Testing {len(links)} links from links.txt...")
    
    results = []
    
    # Process sequentially to avoid overwhelming the system and ensure valid results
    for i, link in enumerate(links, 1):
        print(f"\n[{i}/{len(links)}] Testing: {link}")
        
        # Split comment if exists (the user file had comments on some lines)
        url = link.split()[0] 
        
        try:
            # Use headless by default, but scraping logic uses undetected_chromedriver which is generally headed/visible
            # The user's system seems to support it.
            # We will use scrape_product_price which now defaults to Selenium first.
            result = await asyncio.wait_for(
                scraper.scrape_product_price(None, url, use_virtual_display=False), 
                timeout=180 # 3 minutes total timeout per link
            )
            
            status = "✅ Success" if result.get("success") else "❌ Failed"
            price = result.get("price", "N/A")
            site = result.get("site", "Unknown")
            method = result.get("method", "Unknown")
            
            print(f"  Status: {status}")
            print(f"  Price: {price}")
            print(f"  Site: {site}")
            print(f"  Method: {method}")
            if not result.get("success"):
                print(f"  Error: {result.get('status')} - {result.get('error')}")
                
            results.append({
                "url": url,
                "status": status,
                "price": price,
                "site": site,
                "method": method,
                "details": result
            })
            
        except Exception as e:
            print(f"  ❌ Exception: {e}")
            results.append({
                "url": url,
                "status": "❌ Exception",
                "price": "N/A",
                "site": "Unknown",
                "method": "Unknown",
                "error": str(e)
            })
            
    # Save results
    with open("link_test_results.json", "w") as f:
        json.dump(results, f, indent=2)
        
    print("\n\nTest Completed. Results saved to link_test_results.json")

if __name__ == "__main__":
    asyncio.run(test_links())
