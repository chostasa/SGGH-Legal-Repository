import streamlit as st
import pandas as pd
import datetime
import json

from core.auth import get_tenant_id, get_user_id, get_user_role, get_tenant_branding
from core.audit import fetch_audit_events
from core.error_handling import handle_error
from core.usage_tracker import get_usage_summary
from logger import logger


def run_ui():
    try:
        # Get tenant and branding info
        tenant_id = get_tenant_id()
        branding = get_tenant_branding(tenant_id)

        st.title(f"📜 Audit Log Viewer – {branding.get('firm_name', tenant_id)}")

        # Role-based filtering logic
        user_role = get_user_role()
        if user_role != "admin":
            st.warning("You do not have permission to view all audit logs. Showing your logs only.")
            user_id_filter = get_user_id()
        else:
            user_id_filter = st.text_input("🔎 Filter by User ID (optional)")

        action_filter = st.text_input("🔎 Filter by Action (optional)")
        limit = st.slider("Results Limit", min_value=10, max_value=200, value=50, step=10)

        # Metrics section
        with st.expander("📊 Audit Log Metrics"):
            try:
                # Fix: get_usage_summary does not accept arguments
                usage_summary = get_usage_summary() or {}
                st.write("🔹 Total Audit Events:", usage_summary.get("audit_events", 0))
                st.write("🔹 Failed Audit Events:", usage_summary.get("audit_failures", 0))
            except Exception as metric_err:
                logger.warning(f"[AUDIT_UI] Failed to load audit metrics: {metric_err}")
                st.write("⚠️ Unable to load audit metrics.")

        # Load audit logs - remove tenant_id arg if fetch_audit_events doesn't support it
        with st.spinner("Loading audit logs..."):
            logs = fetch_audit_events(
                user_id=user_id_filter.strip() if isinstance(user_id_filter, str) else user_id_filter,
                action=action_filter.strip() or None,
                limit=limit
            )

        # Enforce tenant-level isolation here (in case the fetch function doesn't filter by tenant)
        if logs:
            logs = [log for log in logs if log.get("tenant_id") == tenant_id]

        # Display results
        if logs:
            st.success(f"✅ Found {len(logs)} audit events")
            st.dataframe(logs, use_container_width=True)

            export_ready = []
            for log in logs:
                export_ready.append(log)
                # Display each log's JSON with expandable details
                with st.expander(
                    f"{log.get('timestamp', 'Unknown')} – {log.get('action', 'No Action')} "
                    f"(User: {log.get('user_id', '-')})"
                ):
                    st.json(log)

            # Export Buttons
            col1, col2 = st.columns(2)
            with col1:
                csv_data = pd.DataFrame(export_ready).to_csv(index=False).encode("utf-8")
                st.download_button(
                    label="⬇️ Download Logs as CSV",
                    data=csv_data,
                    file_name=f"audit_logs_{datetime.datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
            with col2:
                json_data = json.dumps(export_ready, indent=2).encode("utf-8")
                st.download_button(
                    label="⬇️ Download Logs as JSON",
                    data=json_data,
                    file_name=f"audit_logs_{datetime.datetime.now().strftime('%Y%m%d')}.json",
                    mime="application/json"
                )

        else:
            st.info("No audit events match your filter.")

    except Exception as e:
        # Log and show user-friendly error
        logger.exception(f"[AUDIT_UI] Unexpected error: {e}")
        msg = handle_error(e, code="AUDIT_UI_001")
        st.error(msg)
