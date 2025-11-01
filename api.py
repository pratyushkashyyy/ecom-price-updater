#!/usr/bin/env python3
"""
Price Scraper API
Flask API endpoint to scrape product prices from e-commerce sites
Production-ready with retry logic, logging, and error handling
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import asyncio
import logging
import time
import random
import os
from datetime import datetime
from dotenv import load_dotenv
from scrape_prices import scrape_price
from playwright.async_api import async_playwright
from product_price import EcommerceScraper

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Configure logging for production
log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Initialize scraper
scraper = EcommerceScraper()

# Configuration from environment variables (with defaults)
MAX_RETRIES = int(os.getenv('MAX_RETRIES', 5))  # Maximum number of retry attempts
MIN_RETRIES = int(os.getenv('MIN_RETRIES', 2))  # Minimum retries before giving up
RETRY_DELAY_BASE = float(os.getenv('RETRY_DELAY_BASE', 2))  # Base delay in seconds for exponential backoff
MAX_DELAY = int(os.getenv('MAX_DELAY', 30))  # Maximum delay between retries (seconds)
TIMEOUT_SECONDS = int(os.getenv('TIMEOUT_SECONDS', 60))  # Timeout per request (seconds)
DEFAULT_MAX_CONCURRENT = int(os.getenv('DEFAULT_MAX_CONCURRENT', 10))  # Default concurrent requests
MAX_MAX_CONCURRENT = int(os.getenv('MAX_MAX_CONCURRENT', 20))  # Maximum allowed concurrent requests


def run_async(coro):
    """Helper function to run async code in Flask"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


def calculate_backoff_delay(attempt: int) -> float:
    """Calculate exponential backoff delay with jitter"""
    delay = min(RETRY_DELAY_BASE * (2 ** attempt), MAX_DELAY)
    # Add jitter to prevent thundering herd
    jitter = random.uniform(0.1, 0.5) * delay
    return delay + jitter


async def scrape_with_retries(product_url: str, max_retries: int = MAX_RETRIES, 
                               use_virtual_display: bool = False) -> dict:
    """
    Scrape price with retry logic until successful or max retries reached
    
    Args:
        product_url: Product URL to scrape
        max_retries: Maximum number of retry attempts
        use_virtual_display: Use virtual display instead of headless
        
    Returns:
        Dictionary with scraping result
    """
    last_error = None
    
    for attempt in range(max_retries):
        try:
            logger.info(f"Attempt {attempt + 1}/{max_retries} for URL: {product_url[:80]}...")
            
            async def scrape():
                async with async_playwright() as playwright:
                    return await scraper.scrape_product_price(
                        playwright,
                        product_url,
                        headless=True,
                        use_virtual_display=use_virtual_display
                    )
            
            result = await scrape()
            
            # Check if price was successfully extracted
            if result.get('price') and result['price'] != 'N/A' and result['price'] is not None:
                logger.info(f"✅ Success on attempt {attempt + 1}: Price ₹{result['price']}")
                result['attempts'] = attempt + 1
                result['retried'] = attempt > 0
                return result
            
            # If price not found, log and retry
            logger.warning(f"⚠️  Attempt {attempt + 1} failed: Price not found. Status: {result.get('status')}")
            last_error = result.get('status', 'Price not found')
            
            # If we have more retries, wait before next attempt
            if attempt < max_retries - 1:
                delay = calculate_backoff_delay(attempt)
                logger.info(f"Retrying in {delay:.2f} seconds...")
                await asyncio.sleep(delay)
        
        except Exception as e:
            logger.error(f"❌ Attempt {attempt + 1} error: {str(e)}")
            last_error = str(e)
            
            # If we have more retries, wait before next attempt
            if attempt < max_retries - 1:
                delay = calculate_backoff_delay(attempt)
                logger.info(f"Retrying in {delay:.2f} seconds...")
                await asyncio.sleep(delay)
            else:
                # Last attempt failed
                return {
                    'url': product_url,
                    'site': scraper.identify_site(product_url),
                    'price': None,
                    'status': f'Failed after {max_retries} attempts: {str(e)}',
                    'method': 'unknown',
                    'attempts': max_retries,
                    'retried': True,
                    'error': str(e)
                }
    
    # All retries exhausted
    logger.error(f"❌ All {max_retries} attempts failed for URL: {product_url[:80]}...")
    return {
        'url': product_url,
        'site': scraper.identify_site(product_url),
        'price': None,
        'status': f'Failed after {max_retries} attempts. Last error: {last_error}',
        'method': 'unknown',
        'attempts': max_retries,
        'retried': True,
        'error': last_error or 'Unknown error'
    }


@app.route('/')
def index():
    """API info endpoint"""
    return jsonify({
        'name': 'E-commerce Price Scraper API',
        'version': '1.0.0',
        'endpoints': {
            '/api/price': {
                'method': 'POST',
                'description': 'Get price for a product URL',
                'parameters': {
                    'url': 'Product URL (required)',
                    'use_virtual_display': 'Use virtual display (optional, boolean)'
                }
            },
            '/api/price': {
                'method': 'GET',
                'description': 'Get price for a product URL (query parameter)',
                'parameters': {
                    'url': 'Product URL (required)',
                    'use_virtual_display': 'Use virtual display (optional, boolean)'
                }
            }
        }
    })


@app.route('/api/price', methods=['GET', 'POST'])
def get_price():
    """
    Get product price from URL with automatic retries
    
    GET: ?url=<product_url>&use_virtual_display=false&max_retries=5
    POST: {"url": "<product_url>", "use_virtual_display": false, "max_retries": 5}
    
    Returns:
        {
            "success": true/false,
            "url": "product_url",
            "price": "price_value",
            "site": "site_name",
            "method": "selenium/playwright",
            "status": "success message",
            "attempts": 3,
            "retried": true/false
        }
    """
    start_time = time.time()
    
    try:
        # Get parameters from request
        if request.method == 'POST':
            data = request.get_json() or {}
            product_url = data.get('url', '').strip()
            use_virtual_display = data.get('use_virtual_display', False)
            max_retries = int(data.get('max_retries', MAX_RETRIES))
        else:  # GET
            product_url = request.args.get('url', '').strip()
            use_virtual_display = request.args.get('use_virtual_display', 'false').lower() == 'true'
            max_retries = int(request.args.get('max_retries', MAX_RETRIES))
        
        # Validate URL
        if not product_url:
            return jsonify({
                'success': False,
                'error': 'URL parameter is required',
                'url': None,
                'price': None
            }), 400
        
        # Check if URL is valid
        if not product_url.startswith(('http://', 'https://')):
            return jsonify({
                'success': False,
                'error': 'Invalid URL format. URL must start with http:// or https://',
                'url': product_url,
                'price': None
            }), 400
        
        # Validate max_retries
        max_retries = max(1, min(max_retries, 10))  # Clamp between 1 and 10
        
        logger.info(f"📥 Request received: URL={product_url[:80]}..., max_retries={max_retries}")
        
        # Scrape price with retries
        try:
            result = run_async(scrape_with_retries(product_url, max_retries, use_virtual_display))
            
            elapsed_time = time.time() - start_time
            
            # Format response
            if result.get('price') and result['price'] != 'N/A' and result['price'] is not None:
                logger.info(f"✅ Success: Price ₹{result['price']} fetched in {elapsed_time:.2f}s")
                return jsonify({
                    'success': True,
                    'url': result['url'],
                    'price': result['price'],
                    'site': result['site'],
                    'method': result.get('method', 'unknown'),
                    'status': result.get('status', 'success'),
                    'attempts': result.get('attempts', 1),
                    'retried': result.get('retried', False),
                    'elapsed_time': round(elapsed_time, 2)
                })
            else:
                logger.error(f"❌ Failed after {result.get('attempts', max_retries)} attempts")
                return jsonify({
                    'success': False,
                    'url': result['url'],
                    'price': None,
                    'site': result['site'],
                    'method': result.get('method', 'unknown'),
                    'status': result.get('status', 'Price not found'),
                    'attempts': result.get('attempts', max_retries),
                    'retried': result.get('retried', False),
                    'error': result.get('error', 'Could not extract price from the product page'),
                    'elapsed_time': round(elapsed_time, 2)
                }), 404
        
        except Exception as e:
            elapsed_time = time.time() - start_time
            logger.error(f"❌ Exception during scraping: {str(e)}")
            return jsonify({
                'success': False,
                'url': product_url,
                'price': None,
                'error': f'Error scraping price: {str(e)}',
                'elapsed_time': round(elapsed_time, 2)
            }), 500
    
    except Exception as e:
        elapsed_time = time.time() - start_time
        logger.error(f"❌ Internal server error: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Internal server error: {str(e)}',
            'url': None,
            'price': None,
            'elapsed_time': round(elapsed_time, 2)
        }), 500


@app.route('/api/price/batch', methods=['POST'])
def get_prices_batch():
    """
    Get prices for multiple product URLs with retry logic
    
    POST: {
        "urls": ["url1", "url2", ...], 
        "use_virtual_display": false,
        "max_retries": 5,
        "max_concurrent": 10
    }
    
    Returns:
        {
            "success": true,
            "count": 2,
            "success_count": 2,
            "failed_count": 0,
            "results": [
                {
                    "success": true/false,
                    "url": "product_url",
                    "price": "price_value",
                    "site": "site_name",
                    "method": "selenium/playwright",
                    "status": "success message",
                    "attempts": 1,
                    "retried": false
                },
                ...
            ]
        }
    """
    start_time = time.time()
    
    try:
        data = request.get_json() or {}
        urls = data.get('urls', [])
        use_virtual_display = data.get('use_virtual_display', False)
        max_retries = int(data.get('max_retries', MAX_RETRIES))
        max_concurrent = int(data.get('max_concurrent', DEFAULT_MAX_CONCURRENT))
        
        if not urls:
            return jsonify({
                'success': False,
                'error': 'urls parameter is required (list of URLs)',
                'results': []
            }), 400
        
        if not isinstance(urls, list):
            return jsonify({
                'success': False,
                'error': 'urls must be a list',
                'results': []
            }), 400
        
        # Validate URLs
        valid_urls = []
        for url in urls:
            url_str = str(url).strip()
            if url_str.startswith(('http://', 'https://')):
                valid_urls.append(url_str)
        
        if not valid_urls:
            return jsonify({
                'success': False,
                'error': 'No valid URLs provided',
                'results': []
            }), 400
        
        # Validate max_retries and max_concurrent
        max_retries = max(1, min(max_retries, 10))
        max_concurrent = max(1, min(max_concurrent, MAX_MAX_CONCURRENT))
        
        logger.info(f"📥 Batch request: {len(valid_urls)} URLs, max_retries={max_retries}, max_concurrent={max_concurrent}")
        
        # Scrape prices with retries (process each URL individually with retries)
        async def scrape_batch_with_retries():
            semaphore = asyncio.Semaphore(max_concurrent)
            
            async def scrape_one(url):
                async with semaphore:
                    return await scrape_with_retries(url, max_retries, use_virtual_display)
            
            tasks = [scrape_one(url) for url in valid_urls]
            return await asyncio.gather(*tasks, return_exceptions=True)
        
        results = run_async(scrape_batch_with_retries())
        
        # Format response
        formatted_results = []
        success_count = 0
        failed_count = 0
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                formatted_results.append({
                    'success': False,
                    'url': valid_urls[i] if i < len(valid_urls) else 'unknown',
                    'price': None,
                    'site': 'unknown',
                    'method': 'unknown',
                    'status': f'Exception: {str(result)}',
                    'attempts': max_retries,
                    'retried': True,
                    'error': str(result)
                })
                failed_count += 1
            else:
                success = result.get('price') and result['price'] != 'N/A' and result['price'] is not None
                if success:
                    success_count += 1
                else:
                    failed_count += 1
                
                formatted_results.append({
                    'success': success,
                    'url': result.get('url', valid_urls[i] if i < len(valid_urls) else 'unknown'),
                    'price': result.get('price') if result.get('price') != 'N/A' else None,
                    'site': result.get('site', 'unknown'),
                    'method': result.get('method', 'unknown'),
                    'status': result.get('status', 'unknown'),
                    'attempts': result.get('attempts', 1),
                    'retried': result.get('retried', False)
                })
        
        elapsed_time = time.time() - start_time
        logger.info(f"✅ Batch complete: {success_count} success, {failed_count} failed in {elapsed_time:.2f}s")
        
        return jsonify({
            'success': True,
            'count': len(formatted_results),
            'success_count': success_count,
            'failed_count': failed_count,
            'elapsed_time': round(elapsed_time, 2),
            'results': formatted_results
        })
    
    except Exception as e:
        elapsed_time = time.time() - start_time
        logger.error(f"❌ Batch request error: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Internal server error: {str(e)}',
            'results': [],
            'elapsed_time': round(elapsed_time, 2)
        }), 500


@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'success': False,
        'error': 'Endpoint not found'
    }), 404


@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        'success': False,
        'error': 'Internal server error'
    }), 500


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for monitoring"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'service': 'price-scraper-api'
    })


if __name__ == '__main__':
    import os
    
    # Production settings
    debug_mode = os.getenv('DEBUG', 'False').lower() == 'true'
    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', 9000))
    
    print("=" * 70)
    print("E-commerce Price Scraper API - Production Ready")
    print("=" * 70)
    print(f"\nConfiguration:")
    print(f"  Max Retries: {MAX_RETRIES}")
    print(f"  Timeout: {TIMEOUT_SECONDS}s")
    print(f"  Debug Mode: {debug_mode}")
    print("\nAPI Endpoints:")
    print("  GET/POST  /api/price       - Get price for a single product URL (with retries)")
    print("  POST      /api/price/batch - Get prices for multiple product URLs (with retries)")
    print("  GET       /health          - Health check endpoint")
    print("\nBatch Configuration:")
    print(f"  max_concurrent: 1-{MAX_MAX_CONCURRENT} (default: {DEFAULT_MAX_CONCURRENT}, max: {MAX_MAX_CONCURRENT} concurrent requests)")
    print(f"\nConfiguration loaded from .env file:")
    print(f"  MAX_RETRIES: {MAX_RETRIES}")
    print(f"  DEFAULT_MAX_CONCURRENT: {DEFAULT_MAX_CONCURRENT}")
    print(f"  MAX_MAX_CONCURRENT: {MAX_MAX_CONCURRENT}")
    print(f"  PORT: {port}")
    print(f"  HOST: {host}")
    print("\nExample:")
    print('  curl -X POST http://localhost:9000/api/price \\')
    print('    -H "Content-Type: application/json" \\')
    print('    -d \'{"url": "https://www.amazon.in/product-url", "max_retries": 5}\'')
    print(f"\nStarting server on http://{host}:{port}")
    print(f"Logging level: {logging.getLevelName(logger.level)}")
    print("=" * 70)
    
    logger.info("🚀 Starting Price Scraper API server")
    
    app.run(debug=debug_mode, host=host, port=port, threaded=True)

