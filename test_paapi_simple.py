"""
Simple test to verify PAAPI credentials and SDK setup
"""
import os
from dotenv import load_dotenv
from paapi5_python_sdk.api.default_api import DefaultApi
from paapi5_python_sdk.models.get_items_request import GetItemsRequest
from paapi5_python_sdk.models.get_items_resource import GetItemsResource
from paapi5_python_sdk.models.partner_type import PartnerType
from paapi5_python_sdk.models.condition import Condition
from paapi5_python_sdk.rest import ApiException

load_dotenv()

# Get credentials
access_key = os.getenv("AMAZON_PAAPI_ACCESS_KEY")
secret_key = os.getenv("AMAZON_PAAPI_SECRET_KEY")
partner_tag = os.getenv("AMAZON_PARTNER_TAG")

print("=" * 70)
print("PAAPI Credentials Check")
print("=" * 70)
print(f"Access Key: {access_key[:20] + '...' if access_key else 'NOT SET'}")
print(f"Secret Key: {'SET' if secret_key else 'NOT SET'}")
print(f"Partner Tag: {partner_tag or 'NOT SET'}")
print(f"Host: webservices.amazon.in")
print(f"Region: us-east-1")
print("=" * 70)

if not all([access_key, secret_key, partner_tag]):
    print("❌ Missing credentials in .env file!")
    exit(1)

# Initialize SDK (this handles signing automatically)
try:
    default_api = DefaultApi(
        access_key=access_key,
        secret_key=secret_key,
        host="webservices.amazon.in",
        region="us-east-1"
    )
    print("✅ SDK initialized successfully")
    print("\nThe SDK automatically handles AWS Signature Version 4 signing.")
    print("If you get a signing error, the issue is with your credentials, not the SDK.")
except Exception as e:
    print(f"❌ SDK initialization failed: {e}")
    exit(1)

# Test with a simple request
try:
    print("\n📦 Testing with a sample ASIN...")
    get_items_request = GetItemsRequest(
        partner_tag=partner_tag,
        partner_type=PartnerType.ASSOCIATES,
        marketplace="www.amazon.in",
        condition=Condition.NEW,
        item_ids=["B0812B76GH"],  # Sample ASIN
        resources=[
            GetItemsResource.ITEMINFO_TITLE,
            GetItemsResource.OFFERS_LISTINGS_PRICE,
        ],
    )
    
    response = default_api.get_items(get_items_request)
    
    if response.items_result and response.items_result.items:
        item = response.items_result.items[0]
        print("✅ SUCCESS! API call worked.")
        print(f"   ASIN: {item.asin}")
        if hasattr(item, 'item_info') and item.item_info and hasattr(item.item_info, 'title'):
            print(f"   Title: {item.item_info.title.display_value if hasattr(item.item_info.title, 'display_value') else 'N/A'}")
    elif response.errors:
        error = response.errors[0]
        print(f"❌ API Error: {error.code} - {error.message}")
        if "InvalidSignature" in error.code:
            print("\n💡 This means your credentials are wrong or expired.")
            print("   - Check that credentials match in Associates Central")
            print("   - Verify Partner Tag matches Amazon.in marketplace")
            print("   - Wait 10-15 minutes if credentials were just created")
    else:
        print("⚠️  No items returned")
        
except ApiException as e:
    print(f"❌ API Exception: {e.status}")
    print(f"   Body: {e.body}")
    if "InvalidSignature" in str(e.body):
        print("\n💡 InvalidSignature error means:")
        print("   1. Your credentials are incorrect/expired")
        print("   2. Credentials don't match the marketplace (Amazon.in)")
        print("   3. The SDK IS handling signing automatically - the issue is credentials")
except Exception as e:
    print(f"❌ Error: {e}")

print("\n" + "=" * 70)
