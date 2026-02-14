"""
Flipkart scraper (including Shopsy)
"""
import re
from typing import Dict, Optional
from .base_scraper import BaseScraper
from .browser_adapter import BrowserAdapter
import asyncio

class FlipkartScraper(BaseScraper):
    """Scraper for Flipkart.com and Shopsy.in"""
    
    def get_site_name(self) -> str:
        return 'flipkart'
    
    def get_stock_indicators(self) -> Dict:
        return {
            'out_of_stock': [
                'out of stock',
                'sold out',
                'currently unavailable',
                'unavailable',
                'out of stock!',
                'notify me',
                'notify when available',
                'coming soon',
                'temporarily unavailable'
            ],
            'selectors': [
                '._16FRp0',
                '._9-sL7L',
                '.sold-out',
                '[class*="out-of-stock"]',
                '[class*="sold-out"]',
                '[class*="notify"]',
                'button:has-text("Notify")',
                'button:has-text("Notify Me")',
                '[class*="unavailable"]',
                '._2UzuFa',
                '._2KpZ6l._2UzuFa'
            ]
        }
    
    async def extract_price(self, browser: BrowserAdapter) -> Optional[str]:
        """Extract price from Flipkart/Shopsy using JSON-LD first, then CSS selectors"""
        # Check for error page first
        try:
            page_content = await browser.get_page_content()
            if "Something went wrong" in page_content and "Please try again later" in page_content:
                 print("  ⚠️ FLIPKART ERROR PAGE DETECTED (E002/Generic Block)")
                 return None
        except:
            pass

        # PRIORITY 1: Try JSON-LD extraction (most reliable)
        try:
            import json
            # Get all script tags with type="application/ld+json"
            scripts = await browser.query_selector_all('script[type="application/ld+json"]')
            
            for script in scripts:
                try:
                    script_content = await browser.get_inner_text(script)
                    if not script_content:
                        continue
                    
                    data = json.loads(script_content)
                    
                    # Handle both single object and array of objects
                    if isinstance(data, list):
                        for item in data:
                            price = self._extract_price_from_jsonld(item)
                            if price:
                                print(f"  ✅ Found price via JSON-LD: {price}")
                                return price
                    else:
                        price = self._extract_price_from_jsonld(data)
                        if price:
                            print(f"  ✅ Found price via JSON-LD: {price}")
                            return price
                except json.JSONDecodeError:
                    continue
                except Exception as e:
                    print(f"  JSON-LD parsing error: {e}")
                    continue
        except Exception as e:
            print(f"  JSON-LD extraction failed: {e}")

        # PRIORITY 2: CSS selectors fallback
        print("  Falling back to CSS selectors...")
        selectors = self.price_selectors
        
        found_prices = []
        for selector in selectors:
            try:
                if 'css-' in selector:
                    sel = f'.{selector}' if not selector.startswith('.') and not selector.startswith('[') else selector
                else:
                    sel = selector
                
                elements = await browser.query_selector_all(sel)
                
                for el in elements[:5]:
                    price_text = await browser.get_text(el)
                    cleaned_price = self.clean_price(price_text)
                    if cleaned_price != "N/A" and self.is_valid_price(cleaned_price):
                        try:
                            price_float = float(cleaned_price.replace(',', ''))
                            if 10 <= price_float <= 10000000:
                                found_prices.append((price_float, cleaned_price))
                        except:
                            continue
            except:
                continue
        
        # Return highest price (main product price)
        if found_prices:
            found_prices.sort(key=lambda x: x[0], reverse=True)
            print(f"  ✅ Found price via CSS selector: {found_prices[0][1]}")
            return found_prices[0][1]
        
        return None
    
    def _extract_price_from_jsonld(self, data: dict) -> Optional[str]:
        """Extract price from JSON-LD structured data"""
        try:
            # Check if it's a Product schema
            schema_type = data.get('@type', '')
            if schema_type not in ['Product', 'ItemPage']:
                return None
            
            # Try offers.price first
            offers = data.get('offers', {})
            if isinstance(offers, dict):
                price = offers.get('price')
                if price:
                    # Clean and validate
                    price_str = str(price).replace(',', '')
                    if self.is_valid_price(price_str):
                        return price_str
                
                # Try lowPrice for aggregate offers
                low_price = offers.get('lowPrice')
                if low_price:
                    price_str = str(low_price).replace(',', '')
                    if self.is_valid_price(price_str):
                        return price_str
            
            # Try direct price field
            price = data.get('price')
            if price:
                price_str = str(price).replace(',', '')
                if self.is_valid_price(price_str):
                    return price_str
                    
        except Exception as e:
            print(f"  Error extracting from JSON-LD: {e}")
        
        return None
    
    async def extract_product_details(self, browser: BrowserAdapter) -> Dict:
        """Extract product details from Flipkart using multiple strategies.
        
        Flipkart uses dynamically-generated class names, so we use:
        1. JSON-LD structured data (most reliable)
        2. Meta tags (og:title, og:image)
        3. Robust attribute-based selectors
        4. Generic element selectors with validation
        """
        details = {
            'name': None,
            'image_url': None,
            'rating': None,
            'review_count': None
        }
        
        # STRATEGY 1: Extract from JSON-LD structured data
        try:
            import json
            scripts = await browser.query_selector_all('script[type="application/ld+json"]')
            
            for script in scripts:
                try:
                    script_content = await browser.get_inner_text(script)
                    if not script_content:
                        continue
                    
                    data = json.loads(script_content)
                    
                    # Handle both single object and array
                    items = data if isinstance(data, list) else [data]
                    
                    for item in items:
                        schema_type = item.get('@type', '')
                        if schema_type in ['Product', 'ItemPage']:
                            # Extract name
                            if not details['name']:
                                name = item.get('name')
                                if name and len(name) > 5:
                                    details['name'] = name
                                    print(f"  ✅ Found name via JSON-LD: {name}")
                            
                            # Extract image
                            if not details['image_url']:
                                image = item.get('image')
                                if image:
                                    # Image can be string or array
                                    if isinstance(image, list):
                                        image = image[0] if image else None
                                    if isinstance(image, dict):
                                        image = image.get('url')
                                    if image and image.startswith('http'):
                                        details['image_url'] = self.clean_image_url(image)
                                        print(f"  ✅ Found image via JSON-LD")
                except (json.JSONDecodeError, Exception) as e:
                    continue
        except Exception as e:
            print(f"  JSON-LD extraction error: {e}")
        
        # STRATEGY 2: Extract from meta tags
        if not details['name']:
            try:
                meta_selectors = [
                    'meta[property="og:title"]',
                    'meta[name="twitter:title"]',
                    'meta[property="title"]'
                ]
                for sel in meta_selectors:
                    try:
                        meta = await browser.query_selector(sel)
                        if meta:
                            content = await browser.get_attribute(meta, 'content')
                            if content and len(content) > 5 and 'Flipkart' not in content:
                                # Clean up common suffixes
                                name = content.split(' : ')[0]  # Remove " : Flipkart.com"
                                name = name.split(' - ')[0]  # Remove " - Buy Online"
                                if len(name) > 5:
                                    details['name'] = name
                                    print(f"  ✅ Found name via meta tag: {name}")
                                    break
                    except:
                        continue
            except Exception as e:
                print(f"  Meta tag name extraction error: {e}")
        
        if not details['image_url']:
            try:
                meta_selectors = [
                    'meta[property="og:image"]',
                    'meta[name="twitter:image"]',
                    'meta[property="image"]'
                ]
                for sel in meta_selectors:
                    try:
                        meta = await browser.query_selector(sel)
                        if meta:
                            content = await browser.get_attribute(meta, 'content')
                            if content and content.startswith('http'):
                                details['image_url'] = self.clean_image_url(content)
                                print(f"  ✅ Found image via meta tag")
                                break
                    except:
                        continue
            except Exception as e:
                print(f"  Meta tag image extraction error: {e}")
        
        # STRATEGY 3: Use robust selectors from selectors.json
        if not details['name']:
            name_sels = self.site_selectors.get('name_selectors', [])
            for sel in name_sels:
                try:
                    el = await browser.query_selector(sel)
                    if el:
                        text = await browser.get_inner_text(el)
                        if text and len(text) > 5 and 'Flipkart' not in text:
                            details['name'] = text
                            print(f"  ✅ Found name via selector {sel}: {text}")
                            break
                except:
                    continue
        
        if not details['image_url']:
            img_sels = self.site_selectors.get('image_selectors', [])
            for sel in img_sels:
                try:
                    el = await browser.query_selector(sel)
                    if el:
                        src = await browser.get_attribute(el, 'src')
                        if src and src.startswith('http'):
                            details['image_url'] = self.clean_image_url(src)
                            print(f"  ✅ Found image via selector {sel}")
                            break
                except:
                    continue
        
        # STRATEGY 4: Generic fallback - find h1/h2 elements
        if not details['name']:
            try:
                for tag in ['h1', 'h2']:
                    try:
                        el = await browser.query_selector(tag)
                        if el:
                            text = await browser.get_inner_text(el)
                            if text and len(text) > 5 and 'Flipkart' not in text and 'Online Shopping' not in text:
                                details['name'] = text
                                print(f"  ✅ Found name via {tag} tag: {text}")
                                break
                    except:
                        continue
            except:
                pass
        
        # Final cleanup for Flipkart-specific generic titles
        name = details.get('name')
        if name:
            if any(generic in name for generic in ['Item Store Online', 'Flipkart.com', 'Online Shopping Site', 'Buy Online']):
                details['name'] = None
        
        return details

    async def check_stock_status(self, browser: BrowserAdapter) -> Dict:
        """Check stock status with Flipkart-specific logic"""
        stock_status = {
            'in_stock': True,
            'stock_status': 'in_stock',
            'message': None
        }
        
        # Check for error page
        try:
            page_content = await browser.get_page_content()
            if "Something went wrong" in page_content and "Please try again later" in page_content:
                 stock_status['in_stock'] = False
                 stock_status['stock_status'] = 'error'
                 stock_status['message'] = "Flipkart Error Page (E002/Block)"
                 return stock_status
        except:
            pass
            
        # 1. Check using selectors first
        for selector in self.stock_indicators['selectors']:
            try:
                element = await browser.query_selector(selector)
                if element:
                    text = await browser.get_text(element)
                    if any(oos_text in text.lower() for oos_text in self.stock_indicators['out_of_stock']):
                        stock_status['in_stock'] = False
                        stock_status['stock_status'] = 'out_of_stock'
                        stock_status['message'] = f'Product is out of stock (selector: {selector})'
                        return stock_status
            except Exception:
                continue
        
        # 2. Check for "Notify Me" button (indicates out of stock)
        try:
            notify_selectors = [
                'button:has-text("Notify")',
                'button:has-text("Notify Me")',
                '[class*="notify"]',
                '._2UzuFa',
                '._2KpZ6l._2UzuFa',
                'button._2KpZ6l',
            ]
            for selector in notify_selectors:
                try:
                    notify_elem = await browser.query_selector(selector)
                    if notify_elem:
                        visible = await browser.is_visible(notify_elem)
                        if visible:
                            button_text = (await browser.get_text(notify_elem)).lower()
                            if any(keyword in button_text for keyword in ['notify', 'notify me', 'notify when']):
                                stock_status['in_stock'] = False
                                stock_status['stock_status'] = 'out_of_stock'
                                stock_status['message'] = f'Product is out of stock (Notify Me button found: {selector}, text: {button_text})'
                                return stock_status
                except:
                    continue
        except:
            pass

        # 3. Check page content in product area
        try:
            product_area = await browser.query_selector('[class*="product"], [class*="pdp"], [id*="product"]')
            if product_area:
                product_text = (await browser.get_text(product_area)).lower()
                for oos_text in self.stock_indicators['out_of_stock']:
                    if oos_text in product_text:
                        stock_status['in_stock'] = False
                        stock_status['stock_status'] = 'out_of_stock'
                        stock_status['message'] = f'Product appears to be out of stock (detected in product area: "{oos_text}")'
                        return stock_status
        except:
            pass
            
        return stock_status
