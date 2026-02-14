"""
Myntra scraper
"""
import re
from typing import Dict, Optional
from .base_scraper import BaseScraper
from .browser_adapter import BrowserAdapter


class MyntraScraper(BaseScraper):
    """Scraper for Myntra.com"""
    
    def get_site_name(self) -> str:
        return 'myntra'
    
    def get_stock_indicators(self) -> Dict:
        return {
            'out_of_stock': [
                'sold out',
                'out of stock',
                'currently unavailable',
                'unavailable'
            ],
            'selectors': [
                '.sold-out',
                '[class*="sold-out"]',
                '[class*="out-of-stock"]',
                '.pdp-notify-me'
            ]
        }
    
    def get_price_selectors(self) -> list:
        return [
            '.pdp-price',
            '.pdp-discounted-price',
            '.pdp-mrp',
            '[class*="price"]'
        ]
    
    async def extract_product_details(self, browser: BrowserAdapter) -> Dict:
        """Extract product details from Myntra"""
        details = {
            'name': None,
            'image_url': None,
            'rating': None,
            'review_count': None
        }
        
        # Name — Myntra has brand (.pdp-title) + product name (.pdp-name)
        try:
            brand_el = await browser.query_selector('.pdp-title')
            name_el = await browser.query_selector('.pdp-name')
            
            brand = await browser.get_inner_text(brand_el) if brand_el else ""
            name = await browser.get_inner_text(name_el) if name_el else ""
            
            if brand and name:
                details['name'] = f"{brand} {name}"
            elif name:
                details['name'] = name
            elif brand:
                details['name'] = brand
        except:
            pass

        # Image — Myntra uses divs with background-image
        try:
            imgs = await browser.query_selector_all('.image-grid-image')
            for img in imgs:
                style = await browser.get_attribute(img, 'style')
                if style and 'background-image' in style:
                    match = re.search(r'url\("?\'?([^"\')]+)"?\'?\)', style)
                    if match:
                        details['image_url'] = self.clean_image_url(match.group(1))
                        break
            
            # Fallback to img tags
            if not details['image_url']:
                img_el = await browser.query_selector('.image-grid-container img')
                if img_el:
                    src = await browser.get_attribute(img_el, 'src')
                    if src:
                        details['image_url'] = self.clean_image_url(src)
        except:
            pass
             
        # Rating
        try:
            rating_el = await browser.query_selector('.index-overallRating div')
            if rating_el:
                details['rating'] = await browser.get_inner_text(rating_el)
        except:
            pass

        return details

    async def extract_price(self, browser: BrowserAdapter) -> Optional[str]:
        """Extract price from Myntra"""
        selectors = self.price_selectors
        
        for selector in selectors:
            try:
                el = await browser.query_selector(selector)
                if el:
                    price_text = await browser.get_text(el)
                    cleaned_price = self.clean_price(price_text)
                    if cleaned_price != "N/A" and self.is_valid_price(cleaned_price):
                        try:
                            price_float = float(cleaned_price.replace(',', ''))
                            if price_float >= 10:
                                return cleaned_price
                        except:
                            pass
            except:
                continue
        
        return None
