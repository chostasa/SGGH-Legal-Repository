import streamlit as st
import pandas as pd
import html  
import plotly.express as px
from services.dropbox_client import DropboxClient
from core.security import sanitize_text, redact_log, mask_phi
from utils.file_utils import clean_temp_dir
from core.error_handling import handle_error
from logger import logger
import time

clean_temp_dir()

@st.cache_data(ttl=300)
def load_dashboard_data():
    client = DropboxClient()
    return client.download_dashboard_df()

def run_ui():
    st.title("📊 Litigation Dashboard")

    error_code = "DASH_001"
    try:
        with st.spinner("📥 Loading dashboard data..."):
            start_time = time.time()
            df = load_dashboard_data()
            load_duration = round(time.time() - start_time, 2)
            logger.info(f"[METRICS] Dashboard data loaded in {load_duration}s")

        if df.empty:
            st.warning("⚠️ The dashboard is currently empty.")
            return

    except Exception as e:
        msg = handle_error(e, code=error_code, user_message="Could not load dashboard data.")
        st.error(msg)
        return

    try:
        df.columns = df.columns.str.strip()
        CAMPAIGN_COL = "Case Type"
        STATUS_COL = "Class Code Title"
        REFERRAL_COL = "Referred By Name (Full - Last, First)"
        NAME_COL = "Case Details First Party Name (First, Last)"

        required_cols = [
            NAME_COL,
            "Case Details First Party Name (Full - Last, First)",
            "Case Details First Party Details Default Phone Number",
            "Case Details First Party Details Default Email Account Address",
            "Date Opened"
        ]
        for col in required_cols:
            if col not in df.columns:
                df[col] = ""

        # Campaign selector
        st.markdown("### 🎯 Select Campaign")
        campaign_list = sorted(df[CAMPAIGN_COL].dropna().unique())
        selected_campaign = st.selectbox("Campaign", ["(All Campaigns)"] + campaign_list)
        if selected_campaign != "(All Campaigns)":
            df = df[df[CAMPAIGN_COL] == selected_campaign]

        # Flagged cases section for selected campaign
        flagged_cases_for_campaign = df[df[STATUS_COL].astype(str).str.contains("FLAGGED", case=False, na=False)]
        if not flagged_cases_for_campaign.empty:
            st.markdown("### 🚩 Flagged Cases for Selected Campaign")
            st.dataframe(flagged_cases_for_campaign[[NAME_COL, STATUS_COL]].reset_index(drop=True), use_container_width=True)

        # Smart case categories
        flagged_cases = df[df[STATUS_COL].astype(str).str.contains("FLAGGED", case=False, na=False)]
        litigation_cases = df[df[STATUS_COL].astype(str).str.contains("LITIGATION", case=False, na=False)]

        # KPIs
        st.markdown("### 📊 Key Metrics")
        st.metric("📁 Total Cases", len(df))
        st.metric("✅ Questionnaire Received", df[STATUS_COL].eq("Questionnaire Received").sum())
        st.metric("🚩 Flagged Cases", len(flagged_cases))
        st.metric("⚖️ Litigation Cases", len(litigation_cases))

        # Cumulative trendline
        st.markdown("### 📈 Cumulative Cases Over Time")
        df_sorted = df.sort_values("Date Opened").dropna(subset=["Date Opened"])
        df_sorted["Cumulative"] = range(1, len(df_sorted) + 1)
        st.plotly_chart(px.line(df_sorted, x="Date Opened", y="Cumulative", markers=True), use_container_width=True)

        # Contact health score
        def contact_score(row):
            phone = row.get("Case Details First Party Details Default Phone Number", "")
            email = row.get("Case Details First Party Details Default Email Account Address", "")
            if phone and email:
                return "✅ Full"
            elif phone or email:
                return "⚠️ Partial"
            return "❌ Missing"
        df["Contact Health"] = df.apply(contact_score, axis=1)

        # Sidebar filters
        st.sidebar.header("🔍 Base Filters")
        campaign_filter = st.sidebar.multiselect("📁 Campaign", sorted(df[CAMPAIGN_COL].dropna().unique()))
        referring_filter = st.sidebar.multiselect("👤 Referring Attorney", sorted(df[REFERRAL_COL].dropna().unique()))
        status_filter = st.sidebar.multiselect("📌 Case Status", sorted(df[STATUS_COL].dropna().unique()))

        filtered_df = df.copy()
        if campaign_filter:
            filtered_df = filtered_df[filtered_df[CAMPAIGN_COL].isin(campaign_filter)]
        if referring_filter:
            filtered_df = filtered_df[filtered_df[REFERRAL_COL].isin(referring_filter)]
        if status_filter:
            filtered_df = filtered_df[filtered_df[STATUS_COL].isin(status_filter)]

        # Charts for filtered view
        st.subheader("📌 Case Status Overview")
        if STATUS_COL in filtered_df.columns:
            status_counts = filtered_df[STATUS_COL].value_counts().reset_index()
            status_counts.columns = ["Case Status", "Count"]
            st.plotly_chart(px.bar(status_counts, x="Case Status", y="Count", text="Count"), use_container_width=True)

        st.subheader("👤 Referring Attorney Overview")
        if REFERRAL_COL in filtered_df.columns:
            referral_counts = filtered_df[REFERRAL_COL].value_counts().reset_index()
            referral_counts.columns = ["Referring Attorney", "Count"]
            st.plotly_chart(px.bar(referral_counts, x="Referring Attorney", y="Count", text="Count"), use_container_width=True)

        # Optional columns
        st.subheader("➕ Add Optional Columns")
        optional_display_cols = []
        optional_filtered_cols = []

        with st.expander("Show/Filter Additional Columns"):
            candidate_cols = [
                col for col in df.columns
                if col not in [CAMPAIGN_COL, STATUS_COL, REFERRAL_COL]
                and col not in [
                    "Date Opened",
                    "Case Details First Party Name (Full - Last, First)",
                    "Case Details First Party Details Default Phone Number",
                    "Case Details First Party Details Default Email Account Address"
                ]
            ]
            selected_display_cols = st.multiselect("📌 Choose columns to ADD to the table", candidate_cols)

            for col in selected_display_cols:
                optional_display_cols.append(col)
                try:
                    if 1 < df[col].nunique() < 50:
                        vals = df[col].dropna().astype(str).unique().tolist()
                        selected_vals = st.multiselect(f"Filter values for {col}", sorted(vals), key=col)
                        if selected_vals:
                            filtered_df = filtered_df[filtered_df[col].astype(str).isin(selected_vals)]
                            optional_filtered_cols.append(col)
                    else:
                        search_term = st.text_input(f"Search for value in {col} (contains)", key=f"{col}_search")
                        if search_term:
                            filtered_df = filtered_df[filtered_df[col].astype(str).str.contains(search_term, case=False, na=False)]
                            optional_filtered_cols.append(col)
                except Exception as e:
                    logger.warning(redact_log(mask_phi(f"⚠️ Could not filter column {col}: {e}")))

        # Case table
        st.subheader(f"📋 Case Table ({len(filtered_df)} records)")
        base_display_cols = [
            "Case Type",
            "Class Code Title",
            "Date Opened",
            "Referred By Name (Full - Last, First)",
            "Case Details First Party Name (First, Last)",
            "Case Details First Party Name (Full - Last, First)",
            "Case Details First Party Details Default Phone Number",
            "Case Details First Party Details Default Email Account Address",
            "Contact Health"
        ]
        all_display_cols = [col for col in base_display_cols if col in filtered_df.columns] + optional_display_cols
        clean_df = filtered_df[all_display_cols].copy()
        for col in clean_df.columns:
            clean_df[col] = clean_df[col].apply(lambda x: html.unescape(sanitize_text(str(x))))

        st.dataframe(clean_df.reset_index(drop=True), use_container_width=True)

        # Filter preset buttons
        st.markdown("### 🧷 Filter Presets")
        if st.button("💾 Save Filter Preset"):
            st.session_state.saved_filter = {
                "campaign": selected_campaign,
            }
            st.success("Preset saved.")
        if st.button("📂 Load Filter Preset"):
            preset = st.session_state.get("saved_filter", {})
            if preset:
                selected_campaign = preset.get("campaign", selected_campaign)
                st.success(f"Loaded preset for campaign: {selected_campaign}")

        if st.button("📤 Send to Batch Generator"):
            st.session_state.dashboard_df = filtered_df[all_display_cols].copy()
            st.success("✅ Data sent! Go to the '📄 Batch Doc Generator' to merge.")

        if st.button("📧 Send to Email Tool"):
            st.session_state.dashboard_df = filtered_df[all_display_cols].copy()
            st.success("✅ Filtered clients sent! Go to the '📧 Welcome Email Sender' to continue.")

        st.download_button(
            label="⬇️ Download Filtered Results as CSV",
            data=filtered_df[all_display_cols].to_csv(index=False).encode("utf-8"),
            file_name="filtered_dashboard.csv",
            mime="text/csv"
        )


    except Exception as e:
        msg = handle_error(e, code="DASH_003", user_message="An error occurred in the Dashboard UI.")
        logger.error(redact_log(mask_phi(f"[METRICS] Dashboard UI error: {e}")))
        st.error(msg)