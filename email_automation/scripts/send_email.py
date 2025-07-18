# send_email.py

import os
import requests
from datetime import datetime

GRAPH_URL = "https://graph.microsoft.com/v1.0"

def get_access_token():
    tenant_id = os.environ.get("GRAPH_TENANT_ID")
    client_id = os.environ.get("GRAPH_CLIENT_ID")
    client_secret = os.environ.get("GRAPH_CLIENT_SECRET")

    url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "client_id": client_id,
        "scope": "https://graph.microsoft.com/.default",
        "client_secret": client_secret,
        "grant_type": "client_credentials"
    }

    response = requests.post(url, headers=headers, data=data)
    if response.status_code != 200:
        print("❌ Token request failed:", response.text)
    response.raise_for_status()
    return response.json()["access_token"]

def send_email(to, subject, body, cc=[]):
    try:
        token = get_access_token()
        from_email = os.environ.get("GRAPH_SENDER_EMAIL")

        message = {
            "message": {
                "subject": subject,
                "body": {
                    "contentType": "HTML",
                    "content": body
                },
                "toRecipients": [{"emailAddress": {"address": to}}],
                "ccRecipients": [{"emailAddress": {"address": addr}} for addr in cc],
            },
            "saveToSentItems": "true"
        }

        url = f"{GRAPH_URL}/users/{from_email}/sendMail"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        response = requests.post(url, headers=headers, json=message)

        if response.status_code != 202:
            print("❌ Email send failed:", response.text)

        response.raise_for_status()
        print(f"✅ Email successfully sent to {to}")
        return True

    except Exception as e:
        print(f"❌ Exception during email send to {to}: {e}")
        raise
