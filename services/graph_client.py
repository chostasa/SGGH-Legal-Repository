import aiohttp
import asyncio
import time
from config import AppConfig, get_config
from utils.retry_utils import http_retry
from core.security import redact_log, mask_phi
from core.error_handling import handle_error
from core.usage_tracker import log_usage, check_quota
from core.auth import get_tenant_id, get_user_id
from core.audit import log_audit_event
from logger import logger

GRAPH_TOKEN_ENDPOINT = "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"


class GraphClient:
    def __init__(self, config: AppConfig = None):
        self.config = config or get_config()
        self.token = None

    async def _get_token(self) -> str:
        """
        Retrieve Microsoft Graph API access token with retry and error handling.
        """
        start_time = time.time()
        try:
            url = GRAPH_TOKEN_ENDPOINT.format(tenant_id=self.config.GRAPH_TENANT_ID)
            data = {
                "client_id": self.config.GRAPH_CLIENT_ID,
                "client_secret": self.config.GRAPH_CLIENT_SECRET,
                "scope": "https://graph.microsoft.com/.default",
                "grant_type": "client_credentials"
            }
            headers = {"Content-Type": "application/x-www-form-urlencoded"}

            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=data, headers=headers, timeout=10) as response:
                    if response.status != 200:
                        handle_error(
                            ValueError(f"Graph token request failed: {response.status}"),
                            code="GRAPH_AUTH_002",
                            user_message="Unable to authenticate with Microsoft Graph. Please contact support.",
                            raise_it=True
                        )

                    json_resp = await response.json()
                    token = json_resp.get("access_token")
                    if not token:
                        handle_error(
                            ValueError("No access token returned from Microsoft."),
                            code="GRAPH_AUTH_003",
                            user_message="Unable to authenticate with Microsoft Graph. Please contact support.",
                            raise_it=True
                        )

                    self.token = token
                    duration = time.time() - start_time
                    logger.info(redact_log(mask_phi(f"⏱️ Graph token retrieval took {duration:.2f}s")))
                    return token

        except Exception as e:
            handle_error(
                e,
                code="GRAPH_AUTH_001",
                user_message="Failed to authenticate with Microsoft Graph.",
                raise_it=True
            )

    async def send_email(
        self,
        sender_address: str = None,
        to: str = None,
        subject: str = None,
        body: str = None,
        cc: list = None,
        attachments: list = None,
        body_type: str = "HTML"
    ):
        """
        Send an email using Microsoft Graph API with full HTML support and attachments.
        body_type: "HTML" (default) or "Text"
        """
        start_time = time.time()
        try:
            # Allow fallback to default sender address from config if not provided
            sender = sender_address or self.config.GRAPH_SENDER_EMAIL

            if not sender or not to or not subject or not body:
                handle_error(
                    ValueError("One or more required email fields are empty."),
                    code="GRAPH_SEND_003",
                    user_message="Cannot send email because required fields are missing.",
                    raise_it=True
                )

            tenant_id = get_tenant_id()
            user_id = get_user_id()

            # Quota enforcement
            check_quota(tenant_id, "emails_sent", 1)

            if not self.token:
                await self._get_token()

            url = f"{GRAPH_API_BASE}/users/{sender}/sendMail"
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            }

            # Format recipients
            to_recipients = [{"emailAddress": {"address": to}}]
            cc_recipients = [{"emailAddress": {"address": addr}} for addr in (cc or [])]

            # Build attachments if provided (already base64 encoded)
            formatted_attachments = attachments or []

            payload = {
                "message": {
                    "subject": subject,
                    "body": {
                        "contentType": body_type,
                        "content": body
                    },
                    "toRecipients": to_recipients,
                    "ccRecipients": cc_recipients,
                },
                "saveToSentItems": "true"
            }

            if formatted_attachments:
                payload["message"]["attachments"] = formatted_attachments

            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload, timeout=10) as response:
                    if response.status != 202:
                        handle_error(
                            ValueError(f"Graph email send failed with status {response.status}"),
                            code="GRAPH_SEND_001",
                            user_message=f"Failed to send email to {to}.",
                            raise_it=True
                        )

            duration = time.time() - start_time
            log_usage("emails_sent", tenant_id, user_id, 1, {"recipient": to, "duration": duration})
            log_audit_event(
                "Graph Email Sent",
                {"recipient": to, "subject": subject, "duration": f"{duration:.2f}s"}
            )
            logger.info(mask_phi(redact_log(f"✅ Email sent via Graph to {to} in {duration:.2f}s")))
            return True

        except Exception as e:
            handle_error(
                e,
                code="GRAPH_SEND_002",
                user_message=f"Graph email send failed for {to}.",
                raise_it=True
            )
