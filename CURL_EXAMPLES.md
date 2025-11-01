# cURL Examples for Price Scraper API

## GET Request Examples

### Basic GET Request
```bash
curl "http://localhost:9000/api/price?url=https://www.amazon.in/product-url"
```

### GET Request with Max Retries
```bash
curl "http://localhost:9000/api/price?url=https://www.amazon.in/product-url&max_retries=5"
```

### GET Request with Virtual Display (Linux)
```bash
curl "http://localhost:9000/api/price?url=https://www.amazon.in/product-url&max_retries=5&use_virtual_display=true"
```

### GET Request with URL Encoding
```bash
curl "http://localhost:9000/api/price?url=https%3A%2F%2Fwww.amazon.in%2Fproduct-url&max_retries=5"
```

### GET Request with Pretty JSON Output
```bash
curl -s "http://localhost:9000/api/price?url=https://www.amazon.in/product-url" | python -m json.tool
```

### GET Request with Headers
```bash
curl -H "Accept: application/json" \
     "http://localhost:9000/api/price?url=https://www.amazon.in/product-url&max_retries=5"
```

## POST Request Examples

### Basic POST Request
```bash
curl -X POST http://localhost:9000/api/price \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.amazon.in/product-url"}'
```

### POST Request with Max Retries
```bash
curl -X POST http://localhost:9000/api/price \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://www.amazon.in/product-url",
    "max_retries": 5,
    "use_virtual_display": false
  }'
```

### POST Request - Batch (Multiple URLs)
```bash
curl -X POST http://localhost:9000/api/price/batch \
  -H "Content-Type: application/json" \
  -d '{
    "urls": [
      "https://www.amazon.in/product1",
      "https://www.flipkart.com/product2",
      "https://www.nykaa.com/product3"
    ],
    "max_retries": 5,
    "max_concurrent": 3
  }'
```

## Health Check

```bash
curl http://localhost:9000/health
```

## Real Examples

### Amazon Product
```bash
curl "http://localhost:9000/api/price?url=https://www.amazon.in/Apple-MacBook-16-inch-16%E2%80%91core-40%E2%80%91core/dp/B0CM5QYZ3R/&max_retries=5"
```

### Nykaa Product
```bash
curl "http://localhost:9000/api/price?url=https://www.nykaa.com/braun-silk-epil-9-890-epilator-for-long-lasting-hair-removal-includes-a-bikini-styler/p/1178844&max_retries=5"
```

### Meesho Product
```bash
curl "http://localhost:9000/api/price?url=https://www.meesho.com/frekman-stylish-cotton-blend-check-mens-shirt/p/1kv4b&max_retries=5"
```

### Ajio Product
```bash
curl "http://localhost:9000/api/price?url=https://www.ajio.com/yousta-men-washed-relaxed-fit-crew-neck-t-shirt/p/443079993_blackcharcoal&max_retries=5"
```

## Response Examples

### Success Response
```json
{
  "success": true,
  "url": "https://www.amazon.in/product-url",
  "price": "50000",
  "site": "amazon",
  "method": "selenium",
  "status": "success",
  "attempts": 1,
  "retried": false,
  "elapsed_time": 8.45
}
```

### Failed Response (After Retries)
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

## Notes

- Default port is **9000**
- URLs should be properly encoded if they contain special characters
- Use quotes around URLs in curl commands to prevent shell interpretation
- `max_retries` can be set from 1 to 10 (default: 5)

