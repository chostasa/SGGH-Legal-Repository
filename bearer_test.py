import os
from services.neos_auth import get_neos_token

os.environ["NEOS_AUTH_URL"] = "https://staging-proxy-api.azurewebsites.net/v1/partnerlogin"
os.environ["NEOS_COMPANY_ID"] = "partner"
os.environ["NEOS_INTEGRATION_ID"] = "4ea91240-6250-42a6-a481-e25c05a77de8"
os.environ["NEOS_API_KEY"] = "64ec0dda-cd5b-4991-9022-fac268e7da99"

def run_token_test():
    try:
        token = get_neos_token()
        if token and isinstance(token, str):
            print("✅ Token retrieved successfully:")
            print(token)
        else:
            print("❌ Token is empty or invalid.")
    except Exception as e:
        print(f"❌ Error retrieving token: {e}")

if __name__ == "__main__":
    run_token_test()
