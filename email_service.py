# test_case_updates.py

import os
import requests
from datetime import datetime
from services.neos_auth import get_neos_token

BASE_URL = os.getenv("NEOS_BASE_URL", "https://staging-api.neos-cloud.com")
CASE_ID = "f413d88e-9346-4b0c-a0f1-b33200f19440"

# Constants from your curl test
CASE_DATE_ID = "63af2451-1838-4959-9203-b2dc01311d01"
CLASS_CODE_ID = "cd4b826f-1781-4769-9a70-b2dc01461be2"  # Internal ID for "Questionnaire Sent" or similar

def update_case_dates():
    token = get_neos_token()
    url = f"{BASE_URL}/cases/v2/{CASE_ID}/caseDates"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "CaseDates": [
            {
                "CaseDateId": CASE_DATE_ID,
                "Date": datetime.today().strftime("%Y-%m-%dT00:00:00Z"),
                "DuplicateCompletedChecklistItems": False
            }
        ]
    }

    print(f"🔁 PUT {url}")
    response = requests.put(url, headers=headers, json=payload)
    print(f"📡 Status: {response.status_code}")
    print(f"📄 Response: {response.text}")

    if response.status_code == 200:
        print("✅ Case dates updated successfully.")
    else:
        print("❌ Case date update failed.")

def update_class_code():
    token = get_neos_token()
    url = f"{BASE_URL}/cases/{CASE_ID}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json-patch+json"
    }
    payload = [
        {
            "op": "replace",
            "path": "/ClassId",
            "value": CLASS_CODE_ID
        }
    ]

    print(f"🔁 PATCH {url}")
    response = requests.patch(url, headers=headers, json=payload)
    print(f"📡 Status: {response.status_code}")
    print(f"📄 Response: {response.text}")

    if response.status_code in [200, 204]:
        print("✅ Class code updated successfully.")
    else:
        print("❌ Class code update failed.")


if __name__ == "__main__":
    print("\n=== Testing PUT /caseDates ===")
    update_case_dates()

    print("\n=== Testing PATCH /cases (class code) ===")
    update_class_code()
