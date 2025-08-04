import streamlit as st
import os
import hashlib
import time
from datetime import datetime
from io import BytesIO
import zipfile

from core.session_utils import get_session_temp_dir
from core.security import sanitize_text, sanitize_filename, redact_log, mask_phi
from services.demand_service import generate_demand_letter
from services.dropbox_client import DropboxClient
from core.constants import DROPBOX_TEMPLATES_ROOT
from core.usage_tracker import log_usage, check_quota, decrement_quota
from core.auth import get_user_id, get_tenant_id
from core.audit import log_audit_event
from logger import logger
from core.cache_utils import clear_caches
from core.error_handling import handle_error
from utils.file_utils import clean_temp_dir
from utils.thread_utils import run_async  # To safely handle async tasks

# Clean temp directory scoped by tenant/user
clean_temp_dir()

# Dropbox client setup
client = DropboxClient()

tenant_id = get_tenant_id()
user_id = get_user_id()

# Local style example directory
EXAMPLE_DIR = os.path.join("examples", tenant_id, "demand")
os.makedirs(EXAMPLE_DIR, exist_ok=True)


def load_binary_file(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


def load_with_retry(path: str, retries: int = 5, delay: float = 0.5) -> bytes:
    """Retry-safe loader for generated demand letters."""
    for attempt in range(retries):
        if os.path.exists(path):
            return load_binary_file(path)
        time.sleep(delay)
    raise FileNotFoundError(f"Demand letter not found after {retries} retries: {path}")


def run_ui():
    st.header("📂 Demand Letter Generator")

    # === STYLE EXAMPLES ===
    st.markdown("### 🎨 Optional: Style / Tone Example")

    uploaded_example = st.file_uploader(
        "Upload New Style Example (.txt)", type=["txt"], key="upload_example"
    )
    if uploaded_example:
        try:
            example_filename = sanitize_filename(uploaded_example.name)
            example_path = os.path.join(EXAMPLE_DIR, example_filename)
            with open(example_path, "wb") as f:
                f.write(uploaded_example.read())
            st.success(f"✅ Uploaded example: {example_filename}")

            clear_caches()
            log_audit_event("Demand Style Example Uploaded", {
                "filename": example_filename,
                "tenant_id": tenant_id,
                "user_id": user_id,
                "module": "demand"
            })
        except Exception as e:
            msg = handle_error(e, code="DEMAND_UI_004")
            st.error(msg)

    example_text = ""
    selected_example = None
    example_files = sorted([f for f in os.listdir(EXAMPLE_DIR) if f.endswith(".txt")])
    if example_files:
        selected_example = st.selectbox("Choose Example to Apply Style", ["None"] + example_files)
        if selected_example != "None":
            try:
                path = os.path.join(EXAMPLE_DIR, selected_example)
                with open(path, "r", encoding="utf-8") as f:
                    example_text = f.read()
                with st.expander("🧐 Preview Example Text"):
                    st.code(example_text[:3000], language="markdown")
            except Exception as e:
                msg = handle_error(e, code="DEMAND_UI_001")
                st.error(msg)
    else:
        st.info(f"No style examples found in {EXAMPLE_DIR}")

    # === TEMPLATES (Dropbox) ===
    st.markdown("### 📄 Select Demand Template")

    uploaded_template = st.file_uploader(
        "Upload New Demand Template (.docx)", type=["docx"], key="upload_template"
    )
    if uploaded_template:
        try:
            if not uploaded_template.name.lower().endswith(".docx"):
                st.error("❌ Only .docx templates are supported.")
            else:
                timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
                template_filename = f"{timestamp}_{sanitize_filename(uploaded_template.name)}"
                dropbox_path = f"{DROPBOX_TEMPLATES_ROOT}/demand/{template_filename}"

                client.dbx.files_upload(
                    uploaded_template.getvalue(),
                    dropbox_path,
                    mode=client.dbx.files.WriteMode.overwrite
                )
                st.success(f"✅ Uploaded template: {template_filename}")

                clear_caches()
                log_audit_event("Demand Template Uploaded", {
                    "filename": template_filename,
                    "tenant_id": tenant_id,
                    "user_id": user_id,
                    "module": "demand"
                })
        except Exception as e:
            msg = handle_error(e, code="DEMAND_UI_005")
            st.error(msg)

    selected_template = None
    try:
        template_files = client.list_files(f"{DROPBOX_TEMPLATES_ROOT}/demand")
        if template_files:
            selected_template = st.selectbox("Choose Template to Use", template_files)
        else:
            st.warning("⚠️ No templates found. Please upload one above.")
    except Exception as e:
        msg = handle_error(e, code="DEMAND_UI_002")
        st.error(msg)

    # === FORM ===
    with st.form("demand_form"):
        client_name = st.text_input("Client Name")
        defendant = st.text_input("Defendant Name")
        incident_date = st.date_input("Incident Date")
        location = st.text_input("Location of Incident")
        summary = st.text_area("Summary of Incident")
        damages = st.text_area("Damages Summary")
        submitted = st.form_submit_button("⚙️ Generate Demand Letter")

    # Demand cache
    if "demand_cache" not in st.session_state:
        st.session_state.demand_cache = {}

    if submitted:
        errors = []
        if not client_name.strip():
            errors.append("Client name is required.")
        if not summary.strip():
            errors.append("Incident summary is required.")
        if not damages.strip():
            errors.append("Damages summary is required.")
        if not defendant.strip():
            errors.append("Defendant name is required.")
        if not location.strip():
            errors.append("Incident location is required.")
        if not selected_template:
            errors.append("You must select a demand template.")

        if errors:
            for msg in errors:
                st.error(f"❌ {msg}")
            return

        try:
            check_quota("demand_letters", amount=1)
            full_name = sanitize_text(client_name)
            formatted_date = incident_date.strftime("%B %d, %Y")
            summary = sanitize_text(summary)
            damages = sanitize_text(damages)
            defendant = sanitize_text(defendant)
            location = sanitize_text(location)

            example_hash = hashlib.md5(example_text.encode()).hexdigest() if example_text else "noexample"
            fingerprint = "|".join([
                tenant_id, user_id, full_name, formatted_date,
                summary, damages, example_hash, selected_template
            ])
            form_key = hashlib.md5(fingerprint.encode()).hexdigest()

            if form_key in st.session_state.demand_cache:
                paths = st.session_state.demand_cache[form_key]
                st.info("🔄 Using previously generated demand letter from cache.")
            else:
                with st.spinner("🧠 Generating demand letter..."):
                    temp_dir = get_session_temp_dir()
                    template_path = client.download_file(
                        f"{DROPBOX_TEMPLATES_ROOT}/demand/{selected_template}",
                        "templates_preview"
                    )

                    if not template_path.lower().endswith(".docx"):
                        st.error("❌ The demand template must be a .docx file.")
                        return

                    clear_caches()

                    paths = run_async(
                        generate_demand_letter,
                        client_name=full_name,
                        defendant=defendant,
                        location=location,
                        incident_date=formatted_date,
                        summary=summary,
                        damages=damages,
                        template_path=template_path,
                        output_path=os.path.join(temp_dir, "temp.docx"),
                        example_text=example_text
                    )

                    st.session_state.demand_cache[form_key] = paths
                    time.sleep(1)

                    try:
                        log_usage(
                            event="demand_letters",
                            amount=1,
                            metadata={"client_name": full_name, "template_used": selected_template}
                        )
                    except Exception as log_err:
                        logger.warning(redact_log(mask_phi(f"⚠️ Failed to log demand usage: {log_err}")))

            decrement_quota("demand_letters", amount=1)
            st.success("✅ Demand letters generated!")

            unpolished_path = paths["unpolished"]
            polished_path = paths["polished"]

            try:
                unpolished_data = load_with_retry(unpolished_path)
                polished_data = load_with_retry(polished_path)
            except FileNotFoundError as e:
                st.error(f"❌ Demand letters could not be located: {e}")
                return

            zip_buffer = BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
                zipf.writestr(os.path.basename(unpolished_path), unpolished_data)
                zipf.writestr(os.path.basename(polished_path), polished_data)
            zip_buffer.seek(0)

            st.download_button(
                "⬇️ Download Both Demand Letters (.zip)",
                data=zip_buffer,
                file_name=f"Demand_Letters_{full_name.replace(' ', '_')}.zip",
                mime="application/zip"
            )

            try:
                log_usage(
                    event="demand_letters",
                    amount=1,
                    metadata={"client_name": full_name, "template_used": selected_template}
                )
            except Exception as log_err:
                logger.warning(redact_log(mask_phi(f"⚠️ Failed to log demand usage: {log_err}")))

            try:
                log_audit_event("Demand Letters Generated", {
                    "client_name": full_name,
                    "incident_date": formatted_date,
                    "used_example": selected_example if example_text else "None",
                    "used_template": selected_template,
                    "tenant_id": tenant_id,
                    "user_id": user_id,
                    "module": "demand"
                })
            except Exception as audit_err:
                logger.warning(redact_log(mask_phi(f"⚠️ Failed to write audit log: {audit_err}")))

        except Exception as e:
            msg = handle_error(e, code="DEMAND_UI_003")
            st.error(msg)
