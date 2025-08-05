import os
import pandas as pd
import base64
import requests
from datetime import datetime
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
import json

neos = NeosClient()

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

    print("🔑 DEBUG: Requesting access token")
    response = requests.post(url, headers=headers, data=data)
    print(f"🔑 DEBUG: Token response status: {response.status_code}, body: {response.text}")
    response.raise_for_status()
    token = response.json().get("access_token")
    print("🔑 DEBUG: Received token ending with:", token[-10:] if token else "None")
    return token


def send_email(to, subject, body, cc=None, attachments=None, content_type="HTML"):
    token = get_access_token()
    from_email = os.environ.get("DEFAULT_SENDER_EMAIL")
    if not from_email:
        raise ValueError("DEFAULT_SENDER_EMAIL environment variable is not set.")

    print(f"📧 DEBUG: Sending email from {from_email} to {to}")

    # Format attachments for Microsoft Graph
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
            "body": {
                "contentType": content_type,
                "content": body
            },
            "toRecipients": [{"emailAddress": {"address": to}}],
            "ccRecipients": [{"emailAddress": {"address": addr}} for addr in (cc or [])],
            "attachments": formatted_attachments
        },
        "saveToSentItems": "true"
    }

    url = f"https://graph.microsoft.com/v1.0/users/{from_email}/sendMail"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    print(f"🔍 DEBUG: Sending email with payload:\n{json.dumps(message, indent=2)}")
    response = requests.post(url, headers=headers, json=message)

    print(f"📬 Response Status Code: {response.status_code}")
    print(f"📬 Response Text: {response.text}")

    if response.status_code != 202:
        raise Exception(f"Email send failed: {response.status_code} {response.text}")
    print("✅ Email accepted for delivery (202)")



async def build_email(client_data: dict, template_name: str, attachments: list = None) -> tuple:
    try:
        sanitized = {
            "name": sanitize_text(str(client_data.get("Case Details First Party Name (First, Last)", ""))),
            "RA": sanitize_text(str(client_data.get("Referred By Name (Full - Last, First)", ""))),
            "ID": sanitize_text(str(client_data.get("Case Number", "")))
        }

        recipient_email = sanitize_email(client_data.get("Case Details First Party Details Default Email Account Address", ""))
        if not recipient_email or recipient_email == "invalid@example.com":
            raise AppError(
                code="EMAIL_BUILD_001",
                message=f"Invalid email for client: {sanitized.get('name', '[Unknown]')}",
                details=f"Row data: {client_data}",
            )

        template_path = os.path.normpath(template_name)
        if not os.path.exists(template_path):
            template_path = download_template_file("email", template_name, "email_templates_cache")

        subject, body, cc = merge_template(template_path, sanitized)
        if not subject or not body:
            raise AppError(
                code="EMAIL_BUILD_003",
                message=f"Template merge failed for template: {template_path}",
                details=f"Sanitized data: {sanitized}",
            )

        log_audit_event("Email Built", {
            "tenant_id": get_tenant_id(),
            "user_id": get_user_id(),
            "client_name": sanitized.get("name"),
            "template_path": template_path,
        })

        return subject, body, cc or [], sanitized, attachments or [], recipient_email

    except AppError:
        raise
    except Exception as e:
        handle_error(
            e,
            code="EMAIL_BUILD_004",
            user_message="Failed to build email.",
            raise_it=True
        )


async def send_email_and_update(client: dict, subject: str, body: str, cc: list,
                                template_name: str, attachments: list = None) -> str:
    print("⚙️ ENTERED send_email_and_update")
    try:
        recipient_email = sanitize_email(client.get("Case Details First Party Details Default Email Account Address", ""))
        print(f"🔍 DEBUG: Recipient email: {recipient_email}")
        if not recipient_email or recipient_email == "invalid@example.com":
            raise AppError(
                code="EMAIL_SEND_001",
                message=f"Cannot send email: invalid email address for client {client.get('name', '[Unknown]')}",
            )

        await check_quota("emails_sent", get_tenant_id(), get_user_id(), 1)

        body_type = "HTML" if body.strip().startswith("<") else "Text"

        print("🧭 Reached the email send step in send_email_and_update")
        print(f"🚀 Calling send_email for: {recipient_email}")

        send_email(
            to=recipient_email,
            subject=subject,
            body=body,
            cc=cc,
            attachments=attachments,
            content_type=body_type
        )

        try:
            await neos.update_case_status(client.get("CaseID", ""), STATUS_QUESTIONNAIRE_SENT)
        except Exception as e:
            logger.warning(f"⚠️ NEOS update failed for CaseID {client.get('CaseID', '')}: {e}")

        template_path = os.path.normpath(template_name)
        if not os.path.exists(template_path):
            template_path = download_template_file("email", template_name, "email_templates_cache")

        await log_email(client, subject, body, template_path, cc)
        log_usage("emails_sent", get_tenant_id(), get_user_id(), 1, {"template_path": template_path})

        log_audit_event("Email Sent", {
            "tenant_id": get_tenant_id(),
            "user_id": get_user_id(),
            "client_name": client.get("name", client.get("ClientName")),
            "template_path": template_path,
            "case_id": client.get("CaseID", ""),
        })

        return "✅ Sent"

    except AppError as ae:
        print(f"❌ AppError in send_email_and_update: {ae}")
        logger.error(redact_log(mask_phi(str(ae))))
        return f"❌ Failed: {ae.code}"
    except Exception as e:
        print(f"❌ Exception in send_email_and_update: {e}")
        fallback_name = client.get("name", client.get("ClientName", "[Unknown Client]"))
        handle_error(
            e,
            code="EMAIL_SEND_002",
            user_message=f"Failed to send email for {fallback_name}.",
        )
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
            "template_path": entry["Template Path"],
        })

    except Exception as e:
        print("❌ Exception in log_email:", e)
        handle_error(
            e,
            code="EMAIL_LOG_001",
            user_message=f"Failed to log email for {client.get('name', client.get('ClientName', 'Unknown'))}",
        )
