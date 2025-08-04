import streamlit as st
import pandas as pd
import os
import asyncio
from datetime import datetime

from services.email_service import build_email, send_email_and_update
from services.dropbox_client import download_dashboard_df, download_template_file
from core.security import redact_log, mask_phi
from core.usage_tracker import log_usage, check_quota, get_usage_summary
from core.auth import get_user_id, get_tenant_id, get_tenant_branding
from core.audit import log_audit_event
from core.error_handling import handle_error, AppError
from logger import logger
from utils.file_utils import clean_temp_dir
from core.db import get_templates

clean_temp_dir()

# Column name options for client details
NAME_COLUMN_OPTIONS = [
    "Case Details First Party Name (First, Last)",
    "Case Details First Party Name (Full - Last, First)"
]
EMAIL_COLUMN = "Case Details First Party Details Default Email Account Address"


def run_ui():
    tenant_id = get_tenant_id()
    branding = get_tenant_branding(tenant_id)

    st.header(f"📧 Welcome Email Sender – {branding.get('firm_name', tenant_id)}")

    # Load Excel or dashboard data
    uploaded_excel = st.file_uploader("📂 Upload Excel with Client Data (Optional)", type=["xlsx"])
    if uploaded_excel:
        try:
            df = pd.read_excel(uploaded_excel)
            st.session_state.dashboard_df = df.copy()
            st.success("✅ Excel uploaded successfully. Using uploaded data.")
        except Exception as e:
            st.error(f"❌ Failed to read Excel: {e}")
            return
    else:
        try:
            if "dashboard_df" in st.session_state:
                df = st.session_state.dashboard_df.copy()
                st.info("📊 Loaded filtered clients from Dashboard.")

                # Optional column removal
                st.markdown("### 🗂️ Choose Columns to Keep (Optional)")
                all_columns = list(df.columns)
                selected_columns = st.multiselect(
                    "Select which columns to keep for email building:",
                    options=all_columns,
                    default=all_columns
                )
                df = df[selected_columns]

            else:
                # Load full dashboard data from Dropbox
                with st.spinner("📥 Loading dashboard data..."):
                    df = download_dashboard_df().copy()
        except Exception as e:
            msg = handle_error(e, code="EMAIL_UI_001")
            st.error(msg)
            return

    # Pick the correct NAME_COLUMN
    NAME_COLUMN = next((col for col in NAME_COLUMN_OPTIONS if col in df.columns), None)

    # Ensure required columns exist
    if not NAME_COLUMN or EMAIL_COLUMN not in df.columns:
        st.error(
            f"❌ Expected one of {NAME_COLUMN_OPTIONS} and '{EMAIL_COLUMN}' not found in data."
        )
        return

    # Load email templates
    email_templates = get_templates(tenant_id=tenant_id, category="email")
    if not email_templates:
        st.warning("⚠️ No email templates found. Please upload one in Template Manager.")
        return

    # Template selection
    template_options = [t["name"] for t in email_templates]
    selected_template_name = st.selectbox("Select Email Template", template_options)

    if not selected_template_name:
        st.error("❌ Selected template not found.")
        return

    # Download the template locally
    try:
        template_path = download_template_file("email", selected_template_name)
        if not os.path.exists(template_path):
            st.error(f"❌ Template file not found locally: {template_path}")
            return
    except Exception as e:
        msg = handle_error(e, code="EMAIL_UI_005")
        st.error(f"❌ Failed to download template: {msg}")
        return

    # Global attachments and CC (applies to all emails)
    st.markdown("### 📎 Global Attachments and CC (applied to all emails)")
    attachments = st.file_uploader(
        "Attach PDF or Word files", type=["pdf", "docx"], accept_multiple_files=True
    )
    global_cc = st.text_input("CC (comma-separated emails)", value="").split(",")

    # Sidebar filters
    with st.sidebar:
        st.markdown("### 🔎 Filter Clients")
        class_codes = sorted(df["Class Code Title"].dropna().unique()) if "Class Code Title" in df.columns else []
        statuses = sorted(df["Status"].dropna().unique()) if "Status" in df.columns else []

        selected_codes = st.multiselect("Class Code", class_codes, default=class_codes)
        selected_statuses = st.multiselect("Status", statuses, default=statuses) if statuses else []

        st.markdown("### 📊 Usage Summary")
        try:
            usage_summary = get_usage_summary(tenant_id, get_user_id())
            st.write(f"📨 Emails Sent: {usage_summary.get('emails_sent', 0)}")
            st.write(f"🧠 OpenAI Tokens Used: {usage_summary.get('openai_tokens', 0)}")
        except Exception:
            st.write("⚠️ Unable to load usage summary.")

    # Filter DataFrame by filters
    if "Class Code Title" in df.columns:
        filtered_df = df[
            df["Class Code Title"].isin(selected_codes)
            & (df["Status"].isin(selected_statuses) if statuses else True)
        ]
    else:
        filtered_df = df.copy()

    # Search bar
    search = st.text_input("🔍 Search client name or email").strip().lower()
    if search:
        filtered_df = filtered_df[
            filtered_df[NAME_COLUMN].str.lower().str.contains(search)
            | filtered_df[EMAIL_COLUMN].str.lower().str.contains(search)
        ]

    # Multi-select clients (auto-select all if data came from Litigation Dashboard)
    default_clients = []
    if "dashboard_df" in st.session_state:
        default_clients = filtered_df[NAME_COLUMN].tolist()

    selected_clients = st.multiselect(
        "Select Clients to Email",
        filtered_df[NAME_COLUMN].tolist(),
        default=default_clients
    )

    # Initialize state
    if "email_previews" not in st.session_state:
        st.session_state.email_previews = []
    if "email_status" not in st.session_state:
        st.session_state.email_status = {}

    # Preview Emails
    if st.button("🔍 Preview Emails"):
        st.session_state.email_previews = []
        st.session_state.email_status = {}

        for i, (_, row) in enumerate(
            filtered_df[filtered_df[NAME_COLUMN].isin(selected_clients)].iterrows()
        ):
            try:
                row_data = row.to_dict()
                row_data["Client Name"] = row_data.get(NAME_COLUMN, "")
                row_data["Email"] = row_data.get(EMAIL_COLUMN, "")

                if not row_data["Email"]:
                    st.warning(f"⚠️ Skipping {row_data['Client Name']} - missing email.")
                    continue

                subject, body, cc, sanitized, _, recipient_email = asyncio.run(
                    build_email(row_data, template_path, attachments)
                )

                # Merge global CC into per-email CC
                combined_cc = list(filter(None, cc + global_cc))

                subject_key = f"subject_{i}"
                body_key = f"body_{i}"
                cc_key = f"cc_{i}"
                status_key = f"status_{i}"

                st.markdown(f"**{sanitized['name']}** — _{recipient_email}_")
                st.text_input("✏️ Subject", subject, key=subject_key)

                st.text_input("📧 CC (comma-separated)", ", ".join(combined_cc), key=cc_key)

                st.markdown("📄 Email Body Preview:")
                st.components.v1.html(body, height=350, scrolling=True)

                st.markdown(
                    f"**Status**: {st.session_state.email_status.get(status_key, '⏳ Ready')}"
                )

                if st.button(f"📧 Send to {sanitized['name']}", key=f"send_{i}"):
                    try:
                        check_quota(tenant_id, get_user_id(), "emails_sent", 1)
                        cc_list = [email.strip() for email in st.session_state[cc_key].split(",") if email.strip()]
                        with st.spinner(f"📧 Sending email to {sanitized['name']}..."):
                            status = asyncio.run(
                                send_email_and_update(row_data, subject, body, cc_list, template_path, attachments)
                            )
                            st.session_state.email_status[status_key] = status

                            log_usage(
                                "emails_sent",
                                tenant_id,
                                get_user_id(),
                                1,
                                {"template_path": template_path},
                            )
                            log_audit_event(
                                "Email Sent",
                                {
                                    "client_name": sanitized["name"],
                                    "template_path": template_path,
                                    "tenant_id": tenant_id,
                                },
                            )
                    except Exception as send_err:
                        err_msg = handle_error(send_err, code="EMAIL_UI_002")
                        st.session_state.email_status[status_key] = err_msg

                st.session_state.email_previews.append(
                    {
                        "client": row_data,
                        "subject_key": subject_key,
                        "body_key": body_key,
                        "cc_key": cc_key,
                        "status_key": status_key,
                    }
                )

            except Exception as e:
                msg = handle_error(e, code="EMAIL_UI_003")
                st.error(
                    f"❌ Error building email for {row.get(NAME_COLUMN, 'Unknown')}: {msg}"
                )

    # Send All
    if st.session_state.email_previews and st.button("📤 Send All"):
        with st.spinner("📤 Sending all emails..."):

            async def send_all():
                tasks = []
                for preview in st.session_state.email_previews:
                    if "✅" in st.session_state.email_status.get(preview["status_key"], ""):
                        continue

                    client = preview["client"]
                    subject = st.session_state.get(preview["subject_key"], "")
                    body = st.session_state.get(preview["body_key"], "")
                    cc_list = [
                        email.strip()
                        for email in st.session_state.get(preview["cc_key"], "").split(",")
                        if email.strip()
                    ]

                    async def send_one(preview_item, client_data, subj, bod, cc_list):
                        try:
                            check_quota(tenant_id, get_user_id(), "emails_sent", 1)
                            status = await send_email_and_update(
                                client_data, subj, bod, cc_list, template_path, attachments
                            )
                            st.session_state.email_status[preview_item["status_key"]] = status

                            log_usage(
                                "emails_sent",
                                tenant_id,
                                get_user_id(),
                                1,
                                {"template_path": template_path},
                            )
                            log_audit_event(
                                "Batch Email Sent",
                                {
                                    "client_name": client_data.get("Client Name", "Unknown"),
                                    "template_path": template_path,
                                    "tenant_id": tenant_id,
                                },
                            )
                        except Exception as e:
                            err_msg = handle_error(e, code="EMAIL_UI_004")
                            st.session_state.email_status[preview_item["status_key"]] = err_msg

                    tasks.append(send_one(preview, client, subject, body, cc_list))

                if tasks:
                    await asyncio.gather(*tasks)

            asyncio.run(send_all())

    # Export Logs
    log_dir = os.path.join("email_automation", "logs")
    csv_path = os.path.join(log_dir, f"{tenant_id}_sent_email_log.csv")
    json_path = os.path.join(log_dir, f"{tenant_id}_sent_email_log.json")

    st.markdown("### 📂 Email Log Export")
    if os.path.exists(csv_path):
        with open(csv_path, "rb") as f:
            st.download_button(
                "⬇️ Download Email Log (CSV)", f, file_name=os.path.basename(csv_path)
            )
    if os.path.exists(json_path):
        with open(json_path, "rb") as f:
            st.download_button(
                "⬇️ Download Email Log (JSON)", f, file_name=os.path.basename(json_path)
            )
