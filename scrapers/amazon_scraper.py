"""
Amazon scraper
"""
from typing import Dict, Optional
import re
import json
from .base_scraper import BaseScraper
from .browser_adapter import BrowserAdapter


class AmazonScraper(BaseScraper):
    """Scraper for Amazon.in"""
    
    def get_site_name(self) -> str:
        return 'amazon'
    
    def get_stock_indicators(self) -> Dict:
        return {
            'out_of_stock': [
                'currently unavailable',
                'out of stock',
                'temporarily out of stock',
                "we don't know when or if this item will be back in stock",
                'sold out',
                'this item is currently unavailable',
                'out of stock.',
                'currently out of stock'
            ],
            'selectors': [
                '#availability span',
                '.a-color-state',
                '#outOfStock',
                '#availability',
                '.a-alert-inline-info',
                '[data-asin] .a-color-state'
            ]
        }

    async def extract_product_details(self, browser: BrowserAdapter) -> Dict:
        """Extract product details from Amazon"""
        details = {
            'name': None,
            'image_url': None,
            'rating': None,
            'review_count': None
        }
        
        try:
            # Check for captcha
            title = await browser.get_title()
            if 'Robot Check' in title:
                print("  -> Captcha detected on product page. Skipping.")
                return details

            # Try to dismiss delivery location toaster
            try:
                toaster_dismiss = await browser.query_selector('.glow-toaster-button-dismiss')
                if toaster_dismiss:
                    await browser.click(toaster_dismiss)
                    import asyncio
                    await asyncio.sleep(1)
            except:
                pass
            
            detail_sels = self.site_selectors.get('product_detail', {})
            
            # 1. Title
            title_sel = detail_sels.get('title', '#productTitle')
            if title_sel:
                title_el = await browser.query_selector(title_sel)
                if title_el:
                    details['name'] = await browser.get_inner_text(title_el)

            # 2. Rating
            try:
                rating_sels = detail_sels.get('rating', {})
                rating_sel = rating_sels.get('average', "i[data-hook='average-star-rating'] span")
                rating_el = await browser.query_selector(rating_sel)
                if rating_el:
                    rating_text = await browser.get_inner_text(rating_el)
                    match = re.search(r'(\d+(\.\d+)?)', rating_text)
                    if match:
                        details['rating'] = match.group(1)
            except:
                pass

            # 3. Image (High Res)
            try:
                img_sels = detail_sels.get('image', {})
                img_el = await browser.query_selector(img_sels.get('main', '#landingImage'))
                if not img_el:
                    img_el = await browser.query_selector(img_sels.get('wrapper', '#imgTagWrapperId img'))
                
                if img_el:
                    src = await browser.get_attribute(img_el, 'src')
                    if src:
                        # Check for data-a-dynamic-image attribute with high-res variants
                        dynamic_data = await browser.get_attribute(img_el, 'data-a-dynamic-image')
                        if dynamic_data:
                            try:
                                data_json = json.loads(dynamic_data)
                                best_url = max(data_json.items(), key=lambda x: x[1][0])[0]
                                details['image_url'] = self.clean_image_url(best_url)
                            except:
                                details['image_url'] = self.clean_image_url(src)
                        else:
                            details['image_url'] = self.clean_image_url(src)
            except:
                pass
                
        except Exception as e:
            print(f"  -> Error scraping details: {e}")
            
        return details

    async def extract_price(self, browser: BrowserAdapter) -> Optional[str]:
        """Extract price from Amazon"""
        detail_sels = self.site_selectors.get('product_detail', {})
        price_sels = detail_sels.get('price', {})
        
        for key, sel in price_sels.items():
            try:
                elements = await browser.query_selector_all(sel)
                for el in elements:
                    text = await browser.get_inner_text(el)
                    if text and text.strip():
                        price_match = re.search(
                            r'(INR|Rs\.?|₹|\$|€|£)\s?(\d{1,3}(,\d{2,3})*(\.\d{2})?)',
                            text, re.IGNORECASE
                        )
                        if price_match:
                            raw_price = price_match.group(2)
                            cleaned = self.clean_price(raw_price)
                            if self.is_valid_price(cleaned):
                                return cleaned
            except Exception:
                continue
        return None
