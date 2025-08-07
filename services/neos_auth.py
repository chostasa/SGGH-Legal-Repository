import os
import requests

def get_neos_token():
    url = os.getenv("NEOS_AUTH_URL")
    payload = {
        "companyId": os.getenv("NEOS_COMPANY_ID"),
        "integrationId": os.getenv("NEOS_INTEGRATION_ID"),
        "apiKey": os.getenv("NEOS_API_KEY")
    }

    headers = {"Content-Type": "application/json"}
    response = requests.post(url, json=payload, headers=headers)

    print("🔍 Raw response JSON:")
    print(response.text)  

    if response.status_code != 200:
        raise Exception(f"Auth failed: {response.status_code} - {response.text}")

    return response.json().get("AccessToken")

