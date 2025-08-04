import os
import pandas as pd
import base64
from datetime import datetime
from core.security import sanitize_text, sanitize_email, redact_log, mask_phi
from core.constants import STATUS_INTAKE_COMPLETED, STATUS_QUESTIONNAIRE_SENT
from core.auth import get_user_id, get_tenant_id
from core.usage_tracker import log_usage, check_quota
from core.error_handling import handle_error, AppError
from core.audit import log_audit_event
from email_automation.utils.template_engine import merge_template
from services.graph_client import GraphClient
from services.neos_client import NeosClient
from services.dropbox_client import download_template_file  # centralizes Dropbox path logic
from logger import logger
import json

graph = GraphClient()
neos = NeosClient()


async def build_email(client_data: dict, template_name: str, attachments: list = None) -> tuple:
    """
    Returns (subject, body, cc, sanitized_dict, attachments, recipient_email) for a given client row.
    Downloads and normalizes the template_path from Dropbox if missing locally.
    attachments: list of file-like objects or paths.
    """
    try:
        # Build sanitized dictionary for placeholder substitution
        sanitized = {
            "name": sanitize_text(str(client_data.get("Case Details First Party Name (First, Last)", ""))),
            "RA": sanitize_text(str(client_data.get("Referred By Name (Full - Last, First)", ""))),
            "ID": sanitize_text(str(client_data.get("Case Number", "")))
        }

        # Validate recipient email
        recipient_email = sanitize_email(
            client_data.get("Case Details First Party Details Default Email Account Address", "")
        )
        if not recipient_email or recipient_email == "invalid@example.com":
            raise AppError(
                code="EMAIL_BUILD_001",
                message=f"Invalid email for client: {sanitized.get('name', '[Unknown]')}",
                details=f"Row data: {client_data}",
            )

        # If the template doesn't exist locally, download from Dropbox (email category)
        template_path = os.path.normpath(template_name)
        if not os.path.exists(template_path):
            template_path = download_template_file("email", template_name, "email_templates_cache")

        # Merge template with sanitized placeholders
        subject, body, cc = merge_template(template_path, sanitized)
        if not subject or not body:
            raise AppError(
                code="EMAIL_BUILD_003",
                message=f"Template merge failed for template: {template_path}",
                details=f"Sanitized data: {sanitized}",
            )

        cc = cc or []

        # Log audit event for build
        log_audit_event("Email Built", {
            "tenant_id": get_tenant_id(),
            "user_id": get_user_id(),
            "client_name": sanitized.get("name"),
            "template_path": template_path,
        })

        return subject, body, cc, sanitized, attachments or [], recipient_email

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
    """
    Sends the email (with attachments), updates NEOS, logs usage and returns a result string.
    Downloads template from Dropbox if missing locally.
    """
    try:
        recipient_email = sanitize_email(
            client.get("Case Details First Party Details Default Email Account Address", "")
        )
        if not recipient_email or recipient_email == "invalid@example.com":
            raise AppError(
                code="EMAIL_SEND_001",
                message=f"Cannot send email: invalid email address for client {client.get('name', '[Unknown]')}",
            )

        # Quota check
        await check_quota("emails_sent", get_tenant_id(), get_user_id(), 1)

        # Prepare attachments for Graph
        formatted_attachments = []
        if attachments:
            for a in attachments:
                if hasattr(a, "read"):
                    file_bytes = a.read()
                    file_name = a.name
                else:
                    # If path is passed
                    file_name = os.path.basename(a)
                    with open(a, "rb") as f:
                        file_bytes = f.read()

                formatted_attachments.append({
                    "@odata.type": "#microsoft.graph.fileAttachment",
                    "name": file_name,
                    "contentType": "application/octet-stream",
                    "contentBytes": base64.b64encode(file_bytes).decode("utf-8")
                })

        # Detect body type for Graph API
        body_type = "HTML" if body.strip().startswith("<") else "Text"

        # Send email using Graph
        with logger.contextualize(tenant_id=get_tenant_id(), user_id=get_user_id()):
            await graph.send_email(
                sender_address=None,
                to=recipient_email,
                subject=subject,
                body=body,
                cc=cc,
                attachments=formatted_attachments,
                body_type=body_type
            )

        # Update NEOS case status (best-effort)
        try:
            await neos.update_case_status(client.get("CaseID", ""), STATUS_QUESTIONNAIRE_SENT)
        except Exception as e:
            logger.warning(f"⚠️ NEOS update failed for CaseID {client.get('CaseID', '')}: {e}")

        # Ensure template is available for logging
        template_path = os.path.normpath(template_name)
        if not os.path.exists(template_path):
            template_path = download_template_file("email", template_name, "email_templates_cache")

        # Log email
        await log_email(client, subject, body, template_path, cc)
        log_usage("emails_sent", get_tenant_id(), get_user_id(), 1, {"template_path": template_path})

        # Audit
        log_audit_event("Email Sent", {
            "tenant_id": get_tenant_id(),
            "user_id": get_user_id(),
            "client_name": client.get("name", client.get("ClientName")),
            "template_path": template_path,
            "case_id": client.get("CaseID", ""),
        })

        return "✅ Sent"

    except AppError as ae:
        logger.error(redact_log(mask_phi(str(ae))))
        return f"❌ Failed: {ae.code}"
    except Exception as e:
        fallback_name = client.get("name", client.get("ClientName", "[Unknown Client]"))
        handle_error(
            e,
            code="EMAIL_SEND_002",
            user_message=f"Failed to send email for {fallback_name}.",
        )
        return f"❌ Failed: {type(e).__name__}"


async def log_email(client: dict, subject: str, body: str, template_path: str, cc: list):
    """
    Logs email activity into CSV and JSON files using normalized template_path.
    """
    try:
        subject_clean = sanitize_text(str(subject))
        body_clean = sanitize_text(str(body))
        email_clean = sanitize_email(
            client.get("Case Details First Party Details Default Email Account Address", "invalid@example.com")
        )
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

        # Append to CSV
        if os.path.exists(csv_path):
            existing = pd.read_csv(csv_path)
            pd.concat([existing, pd.DataFrame([entry])], ignore_index=True).to_csv(csv_path, index=False)
        else:
            pd.DataFrame([entry]).to_csv(csv_path, index=False)

        # Append to JSON
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

        # Audit event
        log_audit_event("Email Logged", {
            "tenant_id": tenant_id,
            "user_id": get_user_id(),
            "client_name": name_clean,
            "template_path": entry["Template Path"],
        })

    except Exception as e:
        handle_error(
            e,
            code="EMAIL_LOG_001",
            user_message=f"Failed to log email for {client.get('name', client.get('ClientName', 'Unknown'))}",
        )
