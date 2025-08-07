import os
import pandas as pd
import base64
import requests
from datetime import datetime
from bs4 import BeautifulSoup

from core.security import sanitize_text, sanitize_email, redact_log, mask_phi
from core.constants import STATUS_INTAKE_COMPLETED, STATUS_QUESTIONNAIRE_SENT
from core.auth import get_user_id, get_tenant_id
from core.usage_tracker import log_usage, check_quota
from core.error_handling import handle_error, AppError
from core.audit import log_audit_event
from email_automation.utils.template_engine import merge_template
from services.neos_client import NeosClient
from services.dropbox_client import download_template_file
from logger import logger
from services.neos_auth import get_neos_token
import json
import re

NEOS_BASE_URL = os.getenv("NEOS_BASE_URL", "https://staging-api.neos-cloud.com")
neos = NeosClient()


def extract_guid_from_subject(subject: str) -> str:
    match = re.search(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", subject)
    return match.group(0) if match else ""


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
    response.raise_for_status()
    return response.json().get("access_token")


def clean_html_body(body: str) -> str:
    if "<html" in body.lower():
        return body
    soup = BeautifulSoup(body, "html.parser")
    body_inner = str(soup)
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body>
{body_inner}
</body>
</html>"""


def send_email(to, subject, body, cc=None, attachments=None, content_type="html"):
    token = get_access_token()
    from_email = os.environ.get("DEFAULT_SENDER_EMAIL")
    if not from_email:
        raise ValueError("DEFAULT_SENDER_EMAIL environment variable is not set.")
    body = clean_html_body(body)

    logger.info(f"📧 Sending email to: {to}")
    logger.info(f"📧 Subject: {subject}")
    logger.info(f"📧 Body Preview:\n{body}")

    formatted_attachments = []
    if attachments:
        for a in attachments:
            if hasattr(a, "read"):
                file_bytes = a.read()
                file_name = a.name
            else:
                file_name = os.path.basename(a)
                with open(a, "rb") as f:
                    file_bytes = f.read()
            formatted_attachments.append({
                "@odata.type": "#microsoft.graph.fileAttachment",
                "name": file_name,
                "contentType": "application/octet-stream",
                "contentBytes": base64.b64encode(file_bytes).decode("utf-8")
            })

    message = {
        "message": {
            "subject": subject,
            "body": {"contentType": content_type, "content": body},
            "toRecipients": [{"emailAddress": {"address": to}}],
            "ccRecipients": [{"emailAddress": {"address": addr}} for addr in (cc or [])],
            "attachments": formatted_attachments
        },
        "saveToSentItems": "true"
    }

    url = f"https://graph.microsoft.com/v1.0/users/{from_email}/sendMail"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    response = requests.post(url, headers=headers, json=message)
    if response.status_code != 202:
        raise Exception(f"Email send failed: {response.status_code} {response.text}")


async def build_email(client_data: dict, template_name: str, attachments: list = None) -> tuple:
    try:
        sanitized = {
            "name": sanitize_text(str(client_data.get("Case Details First Party Name (First, Last)", ""))),
            "RA": sanitize_text(str(client_data.get("Referred By Name (Full - Last, First)", ""))),
            "ID": sanitize_text(str(client_data.get("Case Number", "")))
        }

        recipient_email = sanitize_email(client_data.get("Case Details First Party Details Default Email Account Address", ""))
        if not recipient_email or recipient_email == "invalid@example.com":
            raise AppError("EMAIL_BUILD_001", f"Invalid email for client: {sanitized['name']}", f"Row data: {client_data}")

        template_path = os.path.normpath(template_name)
        if not os.path.exists(template_path):
            template_path = download_template_file("email", template_name, "email_templates_cache")

        subject, body, cc = merge_template(template_path, sanitized)

        if not subject or not body:
            raise AppError("EMAIL_BUILD_003", f"Template merge failed for {template_path}", f"Sanitized data: {sanitized}")

        log_audit_event("Email Built", {
            "tenant_id": get_tenant_id(),
            "user_id": get_user_id(),
            "client_name": sanitized["name"],
            "template_path": template_path,
        })

        return subject, body, cc or [], sanitized, attachments or [], recipient_email

    except AppError:
        raise
    except Exception as e:
        handle_error(e, code="EMAIL_BUILD_004", user_message="Failed to build email.", raise_it=True)

def update_case_metadata_from_subject(subject: str):
    case_id = extract_guid_from_subject(subject)
    if not case_id:
        logger.warning("❌ No GUID found in subject. Skipping NEOS updates.")
        return

    token = get_neos_token()
    update_class_code(case_id, token)
    update_case_date_label(case_id, token)


def update_class_code(case_id: str, api_token: str):
    url = f"{NEOS_BASE_URL}/cases/{case_id}"
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json-patch+json"
    }
    payload = [{
        "op": "replace",
        "path": "/ClassId",
        "value": "cd4b826f-1781-4769-9a70-b2dc01461be2"
    }]
    response = requests.patch(url, headers=headers, json=payload)
    logger.info(f"📌 Class code update response: {response.status_code} - {response.text}")
    if response.status_code not in [200, 204]:
        logger.warning(f"⚠️ Class code update failed for {case_id}")
    return response


def update_case_date_label(case_id: str, api_token: str):
    url = f"{NEOS_BASE_URL}/cases/v2/{case_id}/caseDates"
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "CaseDates": [
            {
                "CaseDateId": "63af2451-1838-4959-9203-b2dc01311d01",
                "Date": datetime.today().strftime("%Y-%m-%dT00:00:00Z"),
                "DuplicateCompletedChecklistItems": False
            }
        ]
    }
    response = requests.put(url, headers=headers, json=payload)
    logger.info(f"📌 Case date update response: {response.status_code} - {response.text}")
    if response.status_code not in [200, 204]:
        logger.warning(f"⚠️ Case date update failed for {case_id}")
    return response


async def send_email_and_update(client: dict, subject: str, body: str, cc: list, template_name: str, attachments: list = None) -> str:
    try:
        recipient_email = sanitize_email(client.get("Case Details First Party Details Default Email Account Address", ""))
        case_id = sanitize_text(str(client.get("Case Number", "")))

        if not recipient_email or recipient_email == "invalid@example.com":
            raise AppError("EMAIL_SEND_001", f"Cannot send email: invalid email for {client.get('name', '[Unknown]')}")

        check_quota("emails_sent", 1)
        send_email(to=recipient_email, subject=subject, body=body, cc=cc, attachments=attachments)

        if not case_id or not re.match(r"^[0-9a-fA-F-]{36}$", case_id):
            logger.warning("❌ Invalid or missing Case ID (GUID). Skipping NEOS update.")
        else:
            try:
                logger.info(f"📌 Using CaseID from client data: {case_id}")
                await neos.update_case_status(case_id, STATUS_QUESTIONNAIRE_SENT)
            except Exception as e:
                logger.warning(f"⚠️ NEOS update failed for CaseID {case_id}: {e}")

            neos_token = get_neos_token()
            if not neos_token:
                raise Exception("❌ Missing NEOS_API_TOKEN")
            try:
                update_case_date_label(case_id, neos_token)
                update_class_code(case_id, neos_token)
            except Exception as e:
                logger.warning(f"⚠️ Case date or class code update failed: {e}")

        template_path = os.path.normpath(template_name)
        if not os.path.exists(template_path):
            template_path = download_template_file("email", template_name, "email_templates_cache")

        await log_email(client, subject, body, template_path, cc)
        log_usage("emails_sent", 1, {"template_path": template_path})

        log_audit_event("Email Sent", {
            "tenant_id": get_tenant_id(),
            "user_id": get_user_id(),
            "client_name": client.get("name", client.get("ClientName")),
            "template_path": template_path,
            "case_id": case_id
        })

        return "✅ Sent"

    except AppError as ae:
        logger.error(redact_log(mask_phi(str(ae))))
        return f"❌ Failed: {ae.code}"
    except Exception as e:
        handle_error(e, code="EMAIL_SEND_002", user_message="Failed to send email.")
        return f"❌ Failed: {type(e).__name__}"


async def log_email(client: dict, subject: str, body: str, template_path: str, cc: list):
    try:
        subject_clean = sanitize_text(str(subject))
        body_clean = sanitize_text(str(body))
        email_clean = sanitize_email(client.get("Case Details First Party Details Default Email Account Address", "invalid@example.com"))
        name_clean = sanitize_text(str(client.get("name", client.get("ClientName", "Unknown"))))

        tenant_id = get_tenant_id()
        log_dir = os.path.join("email_automation", "logs")
        os.makedirs(log_dir, exist_ok=True)

        csv_path = os.path.join(log_dir, f"{tenant_id}_sent_email_log.csv")
        json_path = os.path.join(log_dir, f"{tenant_id}_sent_email_log.json")

        entry = {
            "Timestamp": datetime.now().isoformat(),
            "Client Name": name_clean,
            "Email": email_clean,
            "Subject": subject_clean,
            "Body": body_clean,
            "Template Path": os.path.normpath(template_path),
            "CC List": ", ".join(cc or []),
            "Case ID": client.get("CaseID", ""),
            "Class Code Before": STATUS_INTAKE_COMPLETED,
            "Class Code After": STATUS_QUESTIONNAIRE_SENT,
            "User ID": get_user_id(),
            "Tenant ID": tenant_id,
            "OpenTrackingURL": f"https://tracking.legalhub.app/open/{tenant_id}/{get_user_id()}/{client.get('CaseID', '')}"
        }

        if os.path.exists(csv_path):
            existing = pd.read_csv(csv_path)
            pd.concat([existing, pd.DataFrame([entry])], ignore_index=True).to_csv(csv_path, index=False)
        else:
            pd.DataFrame([entry]).to_csv(csv_path, index=False)

        existing_json = []
        if os.path.exists(json_path):
            with open(json_path, "r") as jf:
                try:
                    existing_json = json.load(jf)
                except json.JSONDecodeError:
                    existing_json = []
        existing_json.append(entry)
        with open(json_path, "w") as jf:
            json.dump(existing_json, jf, indent=2)

        log_audit_event("Email Logged", {
            "tenant_id": tenant_id,
            "user_id": get_user_id(),
            "client_name": name_clean,
            "template_path": entry["Template Path"]
        })

    except Exception as e:
        handle_error(e, code="EMAIL_LOG_001", user_message=f"Failed to log email for {client.get('name', client.get('ClientName', 'Unknown'))}")