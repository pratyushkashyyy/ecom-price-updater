# E-commerce Price Scraper API

A REST API to scrape product prices from multiple Indian e-commerce sites.

## Features

- ✅ **Multiple Sites**: Amazon, Flipkart, Myntra, Nykaa, Ajio, Meesho, ShopClues
- ✅ **Automatic Fallback**: Playwright → Selenium when blocked
- ✅ **REST API**: Simple JSON API endpoints
- ✅ **Batch Processing**: Scrape multiple URLs at once

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Start the API

```bash
python api.py
```

The API will start on `http://localhost:5000`

## API Usage

### Get Single Product Price

**POST Request (with retries):**
```bash
curl -X POST http://localhost:5000/api/price \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://www.amazon.in/product-url",
    "max_retries": 5,
    "use_virtual_display": false
  }'
```

**GET Request:**
```bash
curl "http://localhost:5000/api/price?url=https://www.amazon.in/product-url&max_retries=5"
```

**Response (Success):**
```json
{
  "success": true,
  "url": "https://www.amazon.in/product-url",
  "price": "50000",
  "site": "amazon",
  "method": "selenium",
  "status": "success",
  "attempts": 2,
  "retried": true,
  "elapsed_time": 15.32
}
```

**Response (After Retries):**
```json
{
  "success": false,
  "url": "https://www.amazon.in/product-url",
  "price": null,
  "site": "amazon",
  "method": "selenium",
  "status": "Failed after 5 attempts. Last error: Price not found",
  "attempts": 5,
  "retried": true,
  "error": "Price not found",
  "elapsed_time": 45.67
}
```

### Get Multiple Product Prices

**POST Request (with retries):**
```bash
curl -X POST http://localhost:5000/api/price/batch \
  -H "Content-Type: application/json" \
  -d '{
    "urls": [
      "https://www.amazon.in/product1",
      "https://www.flipkart.com/product2"
    ],
    "max_retries": 5,
    "max_concurrent": 3,
    "use_virtual_display": false
  }'
```

**Response:**
```json
{
  "success": true,
  "count": 2,
  "success_count": 2,
  "failed_count": 0,
  "elapsed_time": 25.43,
  "results": [
    {
      "success": true,
      "url": "https://www.amazon.in/product1",
      "price": "50000",
      "site": "amazon",
      "method": "selenium",
      "status": "success",
      "attempts": 1,
      "retried": false
    },
    {
      "success": true,
      "url": "https://www.flipkart.com/product2",
      "price": "289",
      "site": "flipkart",
      "method": "selenium",
      "status": "success",
      "attempts": 2,
      "retried": true
    }
  ]
}
```

### Health Check

**GET Request:**
```bash
curl http://localhost:5000/health
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-11-01T10:30:00",
  "service": "price-scraper-api"
}
```

## Project Structure

```
.
├── api.py                 # Main API server (Flask)
├── product_price.py       # Core scraper logic
├── scrape_prices.py       # Standalone scraping script
├── nykaa_selenium.py      # Nykaa-specific scraper
├── ajio_selenium.py       # Ajio-specific scraper
├── myntra_selenium.py     # Myntra-specific scraper
├── meesho_selenium.py     # Meesho-specific scraper
├── virtual_display.py     # Virtual display support (Linux)
├── requirements.txt       # Python dependencies
└── README.md             # This file
```

## Supported Sites

| Site | Status |
|------|--------|
| Amazon | ✅ Working |
| Flipkart | ✅ Working |
| Myntra | ✅ Working |
| Nykaa | ✅ Working |
| Ajio | ✅ Working |
| Meesho | ✅ Working |
| ShopClues | ✅ Working |

## Usage Examples

### Python

```python
import requests

response = requests.post('http://localhost:5000/api/price', json={
    'url': 'https://www.amazon.in/product-url'
})
data = response.json()
print(f"Price: ₹{data['price']}")
```

### JavaScript

```javascript
fetch('http://localhost:5000/api/price', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    url: 'https://www.amazon.in/product-url'
  })
})
.then(res => res.json())
.then(data => console.log(`Price: ₹${data.price}`));
```

## Standalone Usage

You can also use the scraper directly:

```bash
python scrape_prices.py "https://www.amazon.in/product-url"
```

## Virtual Display (Linux)

For better detection avoidance on Linux:

```bash
python scrape_prices.py --virtual-display "https://www.amazon.in/product-url"
```

## Production Features

### Retry Logic
- **Automatic Retries**: Up to 5 retries (configurable, max 10) until price is fetched
- **Exponential Backoff**: Retries with increasing delays (2s, 4s, 8s, 16s, 30s max)
- **Jitter**: Random delay variation to prevent thundering herd
- **Smart Retry**: Only retries if price not found, not on validation errors

### Logging
- Structured logging with timestamps
- Logs all attempts, retries, and failures
- Production-ready logging format

### Configuration
- Environment variables:
  - `DEBUG`: Enable debug mode (default: False)
  - `HOST`: Server host (default: 0.0.0.0)
  - `PORT`: Server port (default: 5000)

### Parameters
- `max_retries`: Number of retry attempts (1-10, default: 5)
- `max_concurrent`: Concurrent requests in batch (1-10, default: 3)
- `use_virtual_display`: Use virtual display for Linux (default: false)

## Notes

- Prices are returned as strings in Indian Rupees (₹)
- The API automatically uses Selenium for sites that block Playwright
- Batch requests process up to 5 URLs concurrently (configurable)
- CORS is enabled for cross-origin requests
- All requests include attempt count and elapsed time
- Failed requests include detailed error messages

