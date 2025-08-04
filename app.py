import streamlit as st
import time
import os
from logger import logger
import config
from core.auth import get_user_id, get_tenant_id, get_user_role, get_tenant_branding
from core.usage_tracker import get_usage_summary, check_quota
from utils.file_utils import clean_temp_dir
from core.security import redact_log

# === Setup ===
clean_temp_dir()
tenant_id = get_tenant_id()
user_id = get_user_id()
branding = get_tenant_branding(tenant_id)
logo_path = branding.get("logo")
primary_color = branding.get("primary_color", "#0A1D3B")

st.set_page_config(
    page_title=f"{branding.get('firm_name', 'Legal Automation Hub')} – V3", layout="wide"
)

header_html = f"""
<div style="background-color:{primary_color};padding:2rem;text-align:center;">
  <h1 style="color:white;">{branding.get('firm_name', 'Legal Automation Hub')} – V3</h1>
  <p style="color:white;">Streamlined document generation and legal automation at scale.</p>
</div>
"""
if logo_path and os.path.exists(logo_path):
    st.image(logo_path, width=150)
st.markdown(header_html, unsafe_allow_html=True)

# === Sidebar ===
st.sidebar.title("🛠️ Tools")
tool = st.sidebar.radio(
    "Select a module:",
    [
        "📖 Instructions",
        "🎥 Training Videos", 
        "📊 Litigation Dashboard",
        "📧 Welcome Email Sender",
        "📄 Batch Doc Generator",
        "🧠 Style Mimic Generator",
        "📬 FOIA Requests",
        "📂 Demands",
        "🧾 Mediation Memos",
        "📪 Template & Style Example Manager",
        "🧪 Template Tester",
        "📜 Audit Log Viewer",
    ],
)

with st.sidebar.expander("📊 Usage Summary"):
    try:
        usage = get_usage_summary()  # If updated, pass tenant_id, user_id
        st.write("🧠 OpenAI Tokens:", usage.get("openai_tokens", 0))
        st.write("📨 Emails Sent:", usage.get("emails_sent", 0))
        st.progress(
            min(usage.get("openai_tokens", 0) / usage.get("openai_tokens_quota", 1), 1.0)
        )
        check_quota("openai_tokens")  # pass tenant_id, user_id if required
    except Exception as e:
        logger.warning(f"Usage summary failed: {e}")
        st.write("⚠️ Unable to load usage summary.")

with st.sidebar.expander("📈 System Health"):
    try:
        st.write("⏱️ Uptime:", f"{round(time.perf_counter(), 2)}s")
        st.write("👤 User Role:", get_user_role())
        st.write("Tenant:", tenant_id)
    except Exception as e:
        logger.warning(f"System health panel failed: {e}")
        st.write("⚠️ Unable to load system health.")

# === Tool Selection ===
try:
    if tool == "📖 Instructions":
        from ui.instructions_ui import run_ui
    elif tool == "🎥 Training Videos":
        from ui.training_videos_ui import run_ui
    elif tool == "🧾 Mediation Memos":
        from ui.mediation_ui import run_ui
    elif tool == "📂 Demands":
        from ui.demand_ui import run_ui
    elif tool == "📬 FOIA Requests":
        from ui.foia_ui import run_ui
    elif tool == "📄 Batch Doc Generator":
        from ui.batch_ui import run_ui
    elif tool == "📊 Litigation Dashboard":
        from ui.dashboard_ui import run_ui
    elif tool == "📧 Welcome Email Sender":
        from ui.email_ui import run_ui
    elif tool == "🧠 Style Mimic Generator":
        from ui.style_transfer_ui import run_style_transfer_ui as run_ui
    elif tool == "📪 Template & Style Example Manager":
        from ui.template_manager_ui import run_ui
    elif tool == "🧪 Template Tester":
        from ui.template_tester_ui import run_ui
    elif tool == "📜 Audit Log Viewer":
        from ui.audit_ui import run_ui
    else:
        st.error("❌ Unknown module selected.")

    run_ui()

except Exception as e:
    import traceback

    st.error("❌ Failed to load selected module. See below.")
    st.exception(e)
    st.code(redact_log(traceback.format_exc()))
