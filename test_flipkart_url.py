import requests
import json

url = "https://www.flipkart.com/flipkart/p/item?pid=RSFHBGYRGCKJNJYR&lid=LSTRSFHBGYRGCKJNJYRB787TH&affid=rohanpouri&affExtParam1=ENKR20250901A1583066569&affExtParam2=1670540"

print("Testing Flipkart URL with dual validation...")
print(f"URL: {url[:80]}...")
print("\nCalling API...")

response = requests.post(
    "http://localhost:8000/api/price",
    json={"url": url},
    timeout=120
)

print(f"\nStatus Code: {response.status_code}")
print("\nResponse:")
print(json.dumps(response.json(), indent=2))
