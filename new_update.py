import requests

#connect to database and get product_id and productUrl from products table

urls = [
    "https://www.amazon.in/dp/B0DVLBTKPH/"
    # "https://msho.in/Y9T7yO", #meesho
    # "https://amzn.to/42BrIsV", #amazon
    # "https://myntr.it/xo9egPy", #myntra
    # "https://www.nykaa.com/bagsy-malone-stylish-vegan-leather-multipurpose-pouch/p/1491371", #Nykaa
    # "https://fkrt.cc/h7H4CNp", #flipkart
    # "https://extp.in/jOdET1", #shopsy
    # "https://bitli.in/q7fx7Bq" #hygulife
]

def main():
    def fetch_price(url):
        api_url = f"https://ecom-price.appdeals.in/api/price?url={url}"
        response = requests.get(api_url)
        return response.json()

    for url in urls:
        result = fetch_price(url)
        price = result.get('price', 'N/A')
        if price == 'N/A':
            print(f"Price not found for URL: {url}")
            continue    
        else:
            print(f"Price for URL {url}: {price}")
            print(f"Updating in database for URL: {url}")
            update_api_url = "https://appdeals.in/api/update-product-price"
            product_id = 1038
            price_clean = str(price).replace(',', '').strip()
            price_int = int(float(price_clean))
            payload = {
                "product_id": product_id,
                "price": price_int
            }
            try:
                resp = requests.post(update_api_url, json=payload)
                if resp.status_code == 200:
                    print(f"Successfully updated price for product_id {product_id}")
                else:
                    print(f"Failed to update price for product_id {product_id}: {resp.status_code} {resp.text}")
            except Exception as e:
                print(f"Exception while updating price: {e}")
            print("-" * 60)

if __name__ == '__main__':
    main()