import streamlit as st
import os
import json
import yaml
from io import BytesIO

from utils.docx_utils import replace_text_in_docx_all
from core.session import get_session_temp_dir
from utils.file_utils import clean_temp_dir
from core.security import redact_log, mask_phi, sanitize_filename
from core.auth import get_tenant_id, get_user_role
from core.error_handling import handle_error
from core.audit import log_audit_event
from core.usage_tracker import check_quota, decrement_quota
from logger import logger

# Clean temp directory at the start
clean_temp_dir()

TENANT_ID = get_tenant_id()
TEMPLATE_DIR = os.path.join("templates", "tester_docs", TENANT_ID)
os.makedirs(TEMPLATE_DIR, exist_ok=True)


def parse_input_replacements(input_str: str) -> dict:
    """Parse the key-value replacements from JSON or YAML."""
    try:
        return json.loads(input_str)
    except json.JSONDecodeError:
        try:
            return yaml.safe_load(input_str)
        except yaml.YAMLError as e:
            handle_error(
                e,
                code="TEMPLATE_TESTER_001",
                user_message="Invalid JSON or YAML format.",
                raise_it=True
            )


def run_ui():
    """Render the Template Tester UI."""
    st.header("🧪 Template Tester")

    with st.form("tester_form"):
        uploaded_template = st.file_uploader("Upload Template (.docx)", type=["docx"])
        key_value_input = st.text_area(
            "Key-Value Replacements (YAML or JSON format)",
            placeholder='''{
  "Client Name": "Jane Roe",
  "IncidentDate": "June 15, 2023",
  "Facility": "Springfield Center"
}''',
            height=200
        )
        submitted = st.form_submit_button("🔍 Generate Preview")

    if submitted:
        if not uploaded_template or not key_value_input.strip():
            st.error("❌ Please upload a .docx template and provide replacements.")
            return

        try:
            # Save uploaded template
            saved_template_path = os.path.join(
                TEMPLATE_DIR, sanitize_filename(uploaded_template.name)
            )
            with open(saved_template_path, "wb") as f:
                f.write(uploaded_template.read())

            # Parse replacements
            replacements = parse_input_replacements(key_value_input.strip())
            if not isinstance(replacements, dict):
                st.error("❌ Parsed input must be a dictionary.")
                return

            # Quota checks
            check_quota("template_tester_runs", amount=1)
            temp_dir = get_session_temp_dir()
            output_path = os.path.join(temp_dir, "preview_output.docx")

            # Replace placeholders in the template
            with st.spinner("🔄 Generating preview..."):
                replace_text_in_docx_all(saved_template_path, replacements, output_path)
            decrement_quota("template_tester_runs", amount=1)

            st.success("✅ Preview generated!")

            # Read file as bytes (fixes generator error)
            with open(output_path, "rb") as f:
                output_bytes = f.read()

            st.download_button(
                label="⬇️ Download Rendered Preview",
                data=output_bytes,
                file_name="preview_output.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )

            # Audit event
            log_audit_event("Template Preview Generated", {
                "tenant_id": TENANT_ID,
                "template": uploaded_template.name
            })

        except Exception as e:
            msg = handle_error(
                e,
                code="TEMPLATE_TESTER_002",
                user_message="Failed to generate preview.",
            )
            st.error(msg)
