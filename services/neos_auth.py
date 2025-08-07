import os
import requests
from dotenv import load_dotenv

load_dotenv()

def get_neos_token():
    url = os.getenv("NEOS_AUTH_URL")
    payload = {
        "username": os.getenv("NEOS_USERNAME"),
        "password": os.getenv("NEOS_PASSWORD"),
        "companyId": os.getenv("NEOS_COMPANY_ID"),
        "integrationId": os.getenv("NEOS_INTEGRATION_ID")
    }

    headers = {"Content-Type": "application/json"}
    response = requests.post(url, json=payload, headers=headers)

    if response.status_code != 200:
        raise Exception(f"Auth failed: {response.status_code} - {response.text}")

    data = response.json()
    return data.get("token")
