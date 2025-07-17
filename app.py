import streamlit as st
import os
import json

st.set_page_config(page_title="Legal Automation Hub", layout="wide")

TEMPLATE_CONFIG = json.loads(os.environ.get("TEMPLATE_CONFIG", "{}"))
CLASS_CODES = json.loads(os.environ.get("CLASS_CODES", "{}"))

from email_automation.scripts.email_utilities import merge_template
from email_automation.scripts.send_email import send_email
from email_automation.scripts.update_neos import update_class_code

import os

NEOS_COMPANY_ID = os.environ.get("NEOS_COMPANY_ID")
NEOS_API_KEY = os.environ.get("NEOS_API_KEY")
NEOS_INTEGRATION_ID = os.environ.get("NEOS_INTEGRATION_ID")

import pandas as pd
import datetime
import os


from scripts.run_foia import run_foia
from scripts.run_demand import run
from scripts.run_mediation import polish_text_for_legal_memo
from scripts.run_mediation import (
    generate_with_openai,
    generate_introduction,
    generate_plaintiff_statement,
    generate_defendant_statement,
    generate_demand_section,
    generate_facts_liability_section,
    generate_causation_injuries,
    generate_additional_harms,
    generate_future_medical,
    generate_conclusion_section,
    generate_quotes_in_chunks,
    fill_mediation_template,
    safe_generate,
    split_and_combine,
    trim_to_token_limit,
    polish_text_for_legal_memo,  
    chunk_text                    
)

used_quotes = set()

def get_unique_quotes(quotes, count=3):
    selected = []
    for quote in quotes.splitlines():
        quote = quote.strip()
        if quote and quote not in used_quotes:
            selected.append(quote)
            used_quotes.add(quote)
        if len(selected) == count:
            break
    return "\n".join(selected)

import pandas as pd
import os
import dropbox
from io import BytesIO
import zipfile
import io
import tempfile
from docx import Document
from datetime import datetime

from lxml import etree
import zipfile

def replace_text_in_docx_all(docx_path, replacements, save_path):
    with zipfile.ZipFile(docx_path, 'r') as zin:
        temp_zip = zipfile.ZipFile(save_path, 'w')
        for item in zin.infolist():
            buffer = zin.read(item.filename)
            if item.filename == 'word/document.xml':
                xml = etree.fromstring(buffer)
                ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}

                # Replace in ALL text nodes, not just textboxes
                for node in xml.xpath('//w:t', namespaces=ns):
                    text = node.text
                    if text:
                        for key, val in replacements.items():
                            text = text.replace(f'{{{{{key}}}}}', str(val))
                        node.text = text

                buffer = etree.tostring(xml, xml_declaration=True, encoding='utf-8')
            temp_zip.writestr(item, buffer)
        temp_zip.close()

import time
import openai
try:
    from openai.error import RateLimitError  # older SDKs
except ImportError:
    try:
        from openai.errors import RateLimitError  # newer SDKs
    except ImportError:
        RateLimitError = Exception  # fallback

def preview_first_page(template_path):
    """
    Loads the first page of a Word document and returns its text.
    """
    try:
        doc = Document(template_path)
        text_lines = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        first_page_text = "\n".join(text_lines[:25])  # Adjust line count as needed
        return first_page_text
    except Exception as e:
        return f"❌ Error loading preview: {e}"


def safe_generate(func, *args, max_retries=3, delay=5, **kwargs):
    """
    Retry wrapper to safely call GPT-powered functions like generate_xxx with backoff on RateLimitError.
    """
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except RateLimitError:
            if attempt < max_retries - 1:
                time.sleep(delay * (attempt + 1))  # Exponential backoff
            else:
                raise
        except Exception as e:
            raise RuntimeError(f"Generation failed: {e}")

# === Parse and Label GPT-Extracted Quotes ===
import re

def parse_and_label_quotes(result: str, depo_name: str):
    result = result.strip()
    sections = {"Liability": "", "Damages": ""}

    current_section = None
    current_pair = []

    for line in result.splitlines():
        if "**Liability**" in line or "**Liability:**" in line:
            current_section = "Liability"
            continue
        elif "**Damages**" in line or "**Damages:**" in line:
            current_section = "Damages"
            continue

        if current_section and line.strip():
            match = re.match(r"^(\d{4}:\d{2})\s+(Q:|A:)\s+(.*)", line.strip())
            if match:
                page_line, role, content = match.groups()
                formatted_line = f"{page_line} {role} {content}"
                current_pair.append(formatted_line)

                # If we have both Q and A, bundle them and reset
                if role == "A:" and len(current_pair) == 2:
                    full_quote = "\n".join(current_pair)
                    sections[current_section] += f"📑 {depo_name} {full_quote}\n\n"
                    current_pair = []

    return sections["Liability"].strip(), sections["Damages"].strip()



def extract_quotes_from_text(ocr_text, user_instructions=""):
    base_prompt = """
You are a legal assistant. Given this deposition or record text, extract the most relevant direct quotes (verbatim, in quotes) that support either:
- liability,
- injuries,
- or harm to quality of life.
"""
    if user_instructions.strip():
        base_prompt += f"\n\nThe user has provided the following additional instructions:\n{user_instructions.strip()}\n"

    full_prompt = f"""{base_prompt}

Only return a list of quotes. Do not paraphrase. Only use what is in the input.

Input:
{ocr_text}
"""
    return generate_with_openai(full_prompt)

st.markdown("""
<style>
.stButton > button {
    background-color: #B08B48;
    color: white;
    border: none;
    padding: 0.5rem 1rem;
    font-weight: 600;
}
.stTextInput > div > input {
    border: 1px solid #0A1D3B;
}
.stTextArea > div > textarea {
    border: 1px solid #0A1D3B;
}
</style>
""", unsafe_allow_html=True)

# === Branding: Logo inside navy header bar ===
import base64

def load_logo_base64(file_path):
    with open(file_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode()

logo_base64 = load_logo_base64("sggh_logo.png")

st.markdown(f"""
<div style="background-color: #0A1D3B; padding: 2rem 0; text-align: center;">
    <img src="data:image/png;base64,{logo_base64}" width="360" style="margin-bottom: 1rem;" />
    <h1 style="color: white; font-size: 2.2rem; margin: 0;">Stinar Gould Grieco & Hensley</h1>
</div>
""", unsafe_allow_html=True)

# === Sidebar Navigation ===
with st.sidebar:
    st.markdown("### ⚖️ Legal Automation Hub")
    tool = st.radio("Choose Tool", [
        "📖 Instructions & Support",
        "📄 Batch Doc Generator",
        "📧 Welcome Email Sender",
        "📬 FOIA Requests",
        "📂 Demands",
        "📊 Litigation Dashboard",
        "🧾 Mediation Memos",
        "🚧 Complaint (In Progress)",
        "🚧 Subpoenas (In Progress)",
    ])


# === FOIA Requests ===
if tool == "📬 FOIA Requests":
    st.header("📨 Generate FOIA Letters")

    with st.form("foia_form"):
        client_id = st.text_input("Client ID")
        defendant_name = st.text_input("Recipient Name")
        abbreviation = st.text_input("Recipient Abbreviation (for file name)")
        address_line1 = st.text_input("Recipient Address Line 1")
        address_line2 = st.text_input("Recipient Address Line 2 (City, State, Zip)")
        date_of_incident = st.date_input("Date of Incident")
        location = st.text_input("Location of Incident")
        case_synopsis = st.text_area("Case Synopsis")
        potential_requests = st.text_area("Potential Requests (can be reused from another)")
        explicit_instructions = st.text_area("Explicit Instructions (optional)")
        case_type = st.text_input("Case Type")
        facility = st.text_input("Facility or System")
        defendant_role = st.text_input("Recipient Role")

        submitted = st.form_submit_button("Generate FOIA Letter")

    if submitted:
        try:
            df = pd.DataFrame([{
                "Client ID": client_id,
                "Recipient Name": defendant_name,
                "Recipient Abbreviation": abbreviation,
                "Recipient Line 1 (address)": address_line1,
                "Recipient Line 2 (City,state, zip)": address_line2,
                "DOI": date_of_incident,
                "location of incident": location,
                "Case Synopsis": case_synopsis,
                "Potential Requests": potential_requests,
                "Explicit instructions": explicit_instructions,
                "Case Type": case_type,
                "Facility or System": facility,
                "Recipient Role": defendant_role
            }])

            output_paths = run_foia(df)
            st.success("✅ FOIA letter generated!")

            from docx import Document

            for path in output_paths:
                filename = os.path.basename(path)

                # Preview contents
                doc = Document(path)
                preview_text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
                st.subheader(f"📄 {filename}")
                st.text_area("📘 Preview", preview_text, height=400)

                # Download button
                with open(path, "rb") as f:
                    st.download_button(
                        label=f"⬇️ Download {filename}",
                        data=f.read(),
                        file_name=filename,
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    )

        except Exception as e:
            st.error(f"❌ Error: {e}")

# === Demands ===
elif tool == "📂 Demands":
    st.header("📑 Generate Demand Letters")

    st.subheader("📋 Fill in Demand Letter Info")

    with st.form("demand_form"):
        client_name = st.text_input("Client Name")
        defendant = st.text_input("Defendant")
        incident_date = st.date_input("Incident Date")
        location = st.text_input("Location")
        summary = st.text_area("Summary of Incident")
        damages = st.text_area("Damages")

        submitted = st.form_submit_button("Generate Demand Letter")

    if submitted:
        import pandas as pd
        from datetime import datetime

        df = pd.DataFrame([{
            "Client Name": client_name,
            "Defendant": defendant,
            "IncidentDate": incident_date.strftime("%B %d, %Y"),
            "Location": location,
            "Summary": summary,
            "Damages": damages
        }])

        try:
            output_paths = run(df)
            st.success("✅ Letter generated!")

            for path in output_paths:
                filename = os.path.basename(path)
                with open(path, "rb") as f:
                    st.download_button(
                        label=f"Download {filename}",
                        data=f,
                        file_name=filename
                    )
        except Exception as e:
            st.error(f"❌ Error: {e}")

# === Routing ===
if tool == "📄 Batch Doc Generator":
    st.header("📄 Batch Document Generator")

    TEMPLATE_FOLDER = os.path.join("templates", "batch_docs")
    os.makedirs(TEMPLATE_FOLDER, exist_ok=True)

    try:
        campaign_df = pd.read_csv("campaigns.csv")
        CAMPAIGN_OPTIONS = sorted(campaign_df["Campaign"].dropna().unique())
    except Exception as e:
        CAMPAIGN_OPTIONS = []
        st.error(f"❌ Failed to load campaigns.csv: {e}")

    st.markdown("""
    > **How it works:**  
    > 1. Upload one or more templates with {{placeholders}}  
    > 2. Upload Excel with matching column headers  
    > 3. Enter filename format, generate, and download

    ✅ Validates fields  
    📁 Version-safe template naming  
    🔐 No coding required
    """)

    st.subheader("🔏 Template Manager")
    template_mode = st.radio("Choose an action:", ["Upload New Template", "Select Saved Templates", "Template Options"])

    def replace_text_in_docx_textboxes(docx_path, replacements, save_path):
        from lxml import etree
        with zipfile.ZipFile(docx_path, 'r') as zin:
            temp_zip = zipfile.ZipFile(save_path, 'w')
            for item in zin.infolist():
                buffer = zin.read(item.filename)
                if item.filename == 'word/document.xml':
                    xml = etree.fromstring(buffer)
                    ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
                    for node in xml.xpath('//w:txbxContent//w:t', namespaces=ns):
                        text = node.text
                        if text:
                            for key, val in replacements.items():
                                text = text.replace(f'{{{{{key}}}}}', str(val))
                            node.text = text
                    buffer = etree.tostring(xml, xml_declaration=True, encoding='utf-8')
                temp_zip.writestr(item, buffer)
            temp_zip.close()

    def process_and_zip_docs(template_paths, df, output_name_format):
        df = df.fillna("")
        if "DOB" in df.columns:
            df["DOB"] = pd.to_datetime(df["DOB"], errors="coerce").dt.strftime("%m/%d/%Y")

        with tempfile.TemporaryDirectory() as temp_dir:
            word_dir = os.path.join(temp_dir, "word_docs")
            os.makedirs(word_dir, exist_ok=True)

            for idx, row in df.iterrows():
                row_dict = row.to_dict()
                for k, v in row_dict.items():
                    if isinstance(v, (pd.Timestamp, datetime)):
                        row_dict[k] = v.strftime("%m/%d/%Y")

                folder_name = output_name_format
                for key, val in row_dict.items():
                    folder_name = folder_name.replace(f"{{{{{key}}}}}", str(val))
                folder_name = folder_name.strip().replace(" ", "_")
                folder_path = os.path.join(word_dir, folder_name)
                os.makedirs(folder_path, exist_ok=True)

                for template_path in template_paths:
                    template_filename = os.path.basename(template_path)
                    final_filename = template_filename.replace(".docx", "") + ".docx"
                    output_path = os.path.join(folder_path, final_filename)

                    temp_template_path = os.path.join(temp_dir, f"temp_{idx}_{template_filename}")
                    with open(template_path, "rb") as f_in, open(temp_template_path, "wb") as f_out:
                        f_out.write(f_in.read())

                    replace_text_in_docx_textboxes(temp_template_path, row_dict, output_path)

            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_out:
                for root, _, files in os.walk(word_dir):
                    for file in files:
                        full_path = os.path.join(root, file)
                        arcname = os.path.relpath(full_path, word_dir)
                        zip_out.write(full_path, arcname)

        return zip_buffer.getvalue()

    if template_mode == "Upload New Template":
        uploaded_templates = st.file_uploader("Upload One or More .docx Templates", type="docx", accept_multiple_files=True)
        campaign_name = st.selectbox("🏷️ Select Campaign", CAMPAIGN_OPTIONS)
        doc_type = st.text_input("📄 Document Type (e.g., HIPAA, Notice, Demand)")
        excel_file = st.file_uploader("Upload Excel Data (.xlsx)", type="xlsx", key="excel_upload_new")
        output_name_format = st.text_input("Enter filename format (e.g., {{Client Name}}_HIPAA)")

        if uploaded_templates and campaign_name and doc_type:
            if st.button("Save and Generate"):
                saved_paths = []
                for uploaded_template in uploaded_templates:
                    original_name = uploaded_template.name
                    filename = original_name.replace("/", "-").replace("\\", "-")  # sanitize filename if needed
                    save_path = os.path.join(TEMPLATE_FOLDER, filename)

                    if os.path.exists(save_path):
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        filename = f"{os.path.splitext(original_name)[0]}_{timestamp}.docx"
                        save_path = os.path.join(TEMPLATE_FOLDER, filename)

                    with open(save_path, "wb") as f:
                        f.write(uploaded_template.read())
                    saved_paths.append(save_path)
                    st.success(f"✅ Saved: {filename}")

                if excel_file and output_name_format:
                    df = pd.read_excel(excel_file)
                    zip_bytes = process_and_zip_docs(saved_paths, df, output_name_format)
                    st.success("✅ Documents generated!")

                    st.download_button(
                        label="📆 Download All Documents (ZIP)",
                        data=zip_bytes,
                        file_name="generated_documents.zip", 
                        mime="application/zip"
                    )

    elif template_mode == "Select Saved Templates":
        st.subheader("📂 Select Saved Templates")
        available_templates = [
            f for f in os.listdir(TEMPLATE_FOLDER)
            if f.endswith(".docx") and "foia" not in f.lower() and "demand" not in f.lower()
        ]

        search = st.text_input("🔍 Search Templates").lower()
        filtered_templates = [t for t in available_templates if search in t.lower()]

        selected_templates = st.multiselect("Choose Template(s)", filtered_templates)
        excel_file = st.file_uploader("Upload Excel Data (.xlsx)", type="xlsx", key="excel_upload_saved")
        output_name_format = st.text_input("Enter filename format (e.g., {{Client Name}}_HIPAA)")

        if st.button("Generate Documents"):
            if selected_templates and excel_file and output_name_format:
                template_paths = [os.path.join(TEMPLATE_FOLDER, t) for t in selected_templates]
                df = pd.read_excel(excel_file)
                zip_bytes = process_and_zip_docs(template_paths, df, output_name_format)
                st.success("✅ Documents generated!")

                st.download_button(
                    label="📆 Download All Documents (ZIP)",
                    data=zip_bytes,
                    file_name="generated_documents.zip",
                    mime="application/zip"
                )

    elif template_mode == "Template Options":
        st.subheader("⚙️ Template Options")
        available_templates = [
            f for f in os.listdir(TEMPLATE_FOLDER)
            if f.endswith(".docx") and "foia" not in f.lower() and "demand" not in f.lower()
        ]

        search_query = st.text_input("🔍 Search for template to manage").lower()
        filtered_templates = [f for f in available_templates if search_query in f.lower()]

        if filtered_templates:
            template_choice = st.selectbox("Choose Template to Rename/Delete", filtered_templates)
            template_path = os.path.join(TEMPLATE_FOLDER, template_choice)

            st.subheader("✏️ Rename Template")
            new_template_name = st.text_input("New name (no extension)", value=template_choice.replace(".docx", ""))
            if st.button("Rename Template"):
                new_path = os.path.join(TEMPLATE_FOLDER, new_template_name + ".docx")
                if os.path.exists(new_path):
                    st.warning("⚠️ A file with that name already exists.")
                else:
                    os.rename(template_path, new_path)
                    st.success(f"✅ Renamed to {new_template_name}.docx")
                    st.rerun()

            st.subheader("🗑️ Delete Template")
            confirm_delete = st.checkbox("Yes, delete this template permanently.")
            if st.button("Delete Template") and confirm_delete:
                os.remove(template_path)
                st.success(f"✅ Deleted '{template_choice}'")
                st.rerun()

        if available_templates and st.button("🚩 Delete ALL Templates (Cannot Be Undone)"):
            for t in available_templates:
                os.remove(os.path.join(TEMPLATE_FOLDER, t))
            st.success("✅ All templates deleted.")
            st.rerun()

        elif not filtered_templates:
            st.warning("⚠️ No templates found matching your search.")


# === Load Excel Data from Dropbox App Folder (Secure API Method) ===
if tool == "📊 Litigation Dashboard":
    from streamlit_autorefresh import st_autorefresh
    st.header("📊 Interactive Litigation Dashboard")
    st_autorefresh(interval=3600000, key="refresh_dashboard")

    import os
    try:
        # Authenticate with Dropbox using environment variables
        dbx = dropbox.Dropbox(
            oauth2_refresh_token=os.environ["DROPBOX_REFRESH_TOKEN"],
            app_key=os.environ["DROPBOX_APP_KEY"],
            app_secret=os.environ["DROPBOX_APP_SECRET"]
        )

        file_path = "/Master Dashboard.xlsx"
        metadata, res = dbx.files_download(file_path)
        df = pd.read_excel(BytesIO(res.content), sheet_name="Master Dashboard")

        # === Sidebar Filters ===
        with st.sidebar:
            st.markdown("### 🔎 Filter by:")

            case_types = sorted(df["Case Type"].dropna().unique())
            class_codes = sorted(df["Class Code Title"].dropna().unique())
            referred_by = sorted(df["Referred By Name (Full - Last, First)"].dropna().unique())

            selected_case_types = st.multiselect("Case Type", case_types, default=case_types)
            selected_class_codes = st.multiselect("Class Code Title", class_codes, default=class_codes)
            selected_referrers = st.multiselect("Referred By", referred_by, default=referred_by)

        # === Apply Filters ===
        filtered_df = df[
            df["Case Type"].isin(selected_case_types) &
            df["Class Code Title"].isin(selected_class_codes) &
            df["Referred By Name (Full - Last, First)"].isin(selected_referrers)
        ]

        # === Display Results ===
        st.markdown(f"### 📁 Showing {len(filtered_df)} Case(s)")
        st.dataframe(filtered_df, use_container_width=True)

        # === Metrics Summary ===
        st.markdown("### 📊 Summary")
        col1, col2, col3 = st.columns(3)
        col1.metric("Cases Shown", len(filtered_df))
        col2.metric("Unique Referrers", filtered_df['Referred By Name (Full - Last, First)'].nunique())
        col3.metric("Case Types", filtered_df['Case Type'].nunique())

        # === Counts by Referrer and Class Code ===
        st.markdown("### 📊 Counts by Referrer")
        ref_counts = filtered_df['Referred By Name (Full - Last, First)'].value_counts().reset_index()
        ref_counts.columns = ["Referred By", "# of Cases"]
        st.dataframe(ref_counts, use_container_width=True)

        st.markdown("### 📊 Counts by Class Code")
        class_counts = filtered_df['Class Code Title'].value_counts().reset_index()
        class_counts.columns = ["Class Code Title", "# of Cases"]
        st.dataframe(class_counts, use_container_width=True)

    except Exception as e:
        st.error(f"❌ Could not load dashboard: {e}")
        st.stop()

# === Mediation Memo Generator ===
if tool == "🧾 Mediation Memos":
    st.header("🧾 Generate Confidential Mediation Memo")

    # === Session State Initialization ===
    for key, default in {
        "depositions": [],
        "deposition_names": [],
        "quote_outputs": {"Liability": [], "Damages": []},
        "party_statements": {}
    }.items():
        if key not in st.session_state:
            st.session_state[key] = default

    # === Case Setup ===
    st.subheader("📜 Case Synopsis & Instructions")
    case_synopsis = st.text_area("💼 Brief Case Synopsis (optional)", height=100)
    quote_instructions = st.text_area(
        "📝 Instructions for AI (optional)",
        placeholder="E.g., Focus on quotes about emotional distress or negligent supervision...",
        height=100
    )

    # === Add Deposition ===
    st.subheader("📌 Add Deposition Excerpts One at a Time")
    new_depo_label = st.text_input("🔏 Deposition Label (e.g., Efimov Deposition)")
    new_depo_text = st.text_area("✍️ Paste New Deposition Text", height=300)

    if st.button("➕ Add Deposition"):
        if new_depo_label.strip() and new_depo_text.strip():
            st.session_state.depositions.append(new_depo_text.strip())
            st.session_state.deposition_names.append(new_depo_label.strip())
            st.success(f"✅ '{new_depo_label.strip()}' added as Deposition #{len(st.session_state.depositions)}.")
        else:
            st.warning("Please enter both a label and deposition text.")

    # === Show Depositions and Extract Quotes ===
    if st.session_state.depositions:
        st.markdown("✅ **Depositions Loaded:**")
        for i, (depo, name) in enumerate(zip(st.session_state.depositions, st.session_state.deposition_names), 1):
            st.text_area(f"{name} (Deposition {i})", depo, height=150)

        if st.button("🔎 Extract Quotes from All Depositions"):
            st.session_state.quote_outputs = {"Liability": [], "Damages": []}
            for i, (depo_text, depo_name) in enumerate(zip(st.session_state.depositions, st.session_state.deposition_names), 1):
                with st.spinner(f"Analyzing Deposition #{i}..."):
                    from scripts.run_mediation import safe_generate, generate_with_openai
                    prompt = f"""
You are a legal analyst reviewing deposition excerpts in a {case_synopsis.strip() or 'civil lawsuit'}.
Extract only **relevant Q&A quote pairs** that support **either LIABILITY or DAMAGES**.

️ Format:
0012:24 Q: "What did you observe?"
0012:25 A: "There was liquid and debris."

{f"💡 Case Notes: {quote_instructions.strip()}" if quote_instructions.strip() else ""}

📄 Deposition:
{depo_text}
"""
                    try:
                        result = safe_generate(generate_with_openai, prompt, model="gpt-3.5-turbo")
                        st.subheader(f"🧒 Raw GPT Output for {depo_name}")
                        st.code(result, language="markdown")

                        from scripts.run_mediation import parse_and_label_quotes
                        liability_quotes, damages_quotes = parse_and_label_quotes(result, depo_name)

                        st.text_area(f"🥷 Liability ({depo_name})", liability_quotes or "No Liability Quotes Found", height=150, key=f"liab_{i}")
                        st.text_area(f"🥷 Damages ({depo_name})", damages_quotes or "No Damages Quotes Found", height=150, key=f"dam_{i}")

                        if liability_quotes:
                            st.session_state.quote_outputs["Liability"].append(liability_quotes)
                        if damages_quotes:
                            st.session_state.quote_outputs["Damages"].append(damages_quotes)
                    except Exception as e:
                        st.error(f"Error processing Deposition {i}: {e}")

        st.subheader("📂 Extracted Liability Quotes")
        st.text_area("Copy-ready Liability Quotes", "\n\n".join(st.session_state.quote_outputs["Liability"]), height=300)

        st.subheader("📂 Extracted Damages Quotes")
        st.text_area("Copy-ready Damages Quotes", "\n\n".join(st.session_state.quote_outputs["Damages"]), height=300)

    # === Memo Form (Full Block: Inputs + Party Statement Preview + Submission) ===
    with st.form("simple_mediation_form"):
        court = st.text_input("🏭 Court")
        case_number = st.text_input("📁 Case Number")

        plaintiffs = {}
        for i in range(1, 4):
            label = f"👤 plaintiff {i} Name" + (" (required)" if i == 1 else " (optional)")
            plaintiffs[f"plaintiff{i}"] = st.text_input(label)

        defendants = {}
        for i in range(1, 8):
            label = f"🏢 defendant {i} Name" + (" (optional)" if i > 1 else "")
            defendants[f"defendant{i}"] = st.text_input(label)

        complaint_narrative = st.text_area("📔 Complaint Narrative", height=200)
        party_info = st.text_area("👥 Party Information from Complaint", height=200)
        settlement_summary = st.text_area("💼 Settlement Demand Summary", height=200)
        medical_summary = st.text_area("🏥 Medical Summary", height=200)
        explicit_instructions = st.text_area("📝 Additional Instructions for Memo (optional)", height=100)

        deposition_liability = "\n\n".join(st.session_state.quote_outputs["Liability"])
        deposition_damages = "\n\n".join(st.session_state.quote_outputs["Damages"])

        unique_liability_quotes = get_unique_quotes(deposition_liability)
        unique_damages_quotes = get_unique_quotes(deposition_damages)

        action = st.radio("Choose Action", ["🔍 Preview Party Paragraphs", "📂 Generate Memo"])
        submitted = st.form_submit_button("Submit")

        if submitted:
            if action == "🔍 Preview Party Paragraphs":
                st.subheader("📝 Auto-Generated Party Statements")
                for i in range(1, 4):
                    name = plaintiffs.get(f"plaintiff{i}", "").strip()
                    if name:
                        input_text = party_info.strip() + "\n\n" + settlement_summary.strip()
                        result = safe_generate(generate_plaintiff_statement, input_text, name)
                        st.markdown(f"**👤 Plaintiff {i}: {name}**")
                        st.text_area("Auto-Generated Paragraph", result, height=150, key=f"preview_plaintiff{i}")

                        # ✅ Save to session state
                        st.session_state.party_statements[f"plaintiff{i}_statement"] = result


                for i in range(1, 8):
                    name = defendants.get(f"defendant{i}", "").strip()
                    if name:
                        input_text = party_info.strip() + "\n\n" + settlement_summary.strip()
                        result = safe_generate(generate_defendant_statement, input_text, name)
                        st.markdown(f"**🏢 Defendant {i}: {name}**")
                        st.text_area("Auto-Generated Paragraph", result, height=150, key=f"preview_defendant{i}")

                        # ✅ Save to session state
                        st.session_state.party_statements[f"defendant{i}_statement"] = result


            elif action == "📂 Generate Memo":
                try:
                    output_dir = "outputs/mediation_memos"
                    os.makedirs(output_dir, exist_ok=True)

                    data = {
                        "court": court,
                        "case_number": case_number,
                        "complaint_narrative": complaint_narrative,
                        "party_info": party_info,
                        "settlement_summary": settlement_summary,
                        "medical_summary": medical_summary,
                        "deposition_liability": deposition_liability,
                        "deposition_damages": deposition_damages,
                        **plaintiffs,
                        **defendants,
                        "extracted_quotes": deposition_liability + "\n\n" + deposition_damages,
                        "all_quotes_pool": deposition_liability + "\n\n" + deposition_damages,
                    }

                    # ✅ Explicitly include formatted quotes for inline memo embedding
                    data["liability_quotes"] = deposition_liability
                    data["damages_quotes"] = deposition_damages

                    template_path = "templates/mediation_template.docx"

                    from scripts.run_mediation import (
                        safe_generate,
                        generate_introduction,
                        generate_plaintiff_statement,
                        generate_defendant_statement,
                        generate_demand_section,
                        generate_facts_liability_section,
                        generate_causation_injuries,
                        generate_additional_harms,
                        generate_future_medical,
                        generate_conclusion_section,
                        fill_mediation_template,
                    )

                    progress_text = st.empty()
                    progress_bar = st.progress(0)

                    steps = [
                        ("✍️ Generating Introduction...", "introduction"),
                        ("👤 Generating plaintiff Statement...", "plaintiff_statement")
                    ]
                    for i in range(1, 3):
                        pltf_name = data.get(f"plaintiff{i}")
                        if pltf_name:
                            steps.append((f"🏢 Generating plaintiff {i} Statement...", f"plaintiff{i}_statement"))

                    for i in range(1, 8):
                        def_name = data.get(f"defendant{i}")
                        if def_name:
                            steps.append((f"🏢 Generating defendant {i} Statement...", f"defendant{i}_statement"))

                    steps += [
                        ("💰 Generating Demand Section...", "demand"),
                        ("📄 Generating Facts / Liability Section...", "facts_liability"),
                        ("🦴 Generating Causation & Injuries...", "causation_injuries"),
                        ("⚖️ Generating Additional Harms...", "additional_harms"),
                        ("🧾 Generating Future Medical Costs...", "future_bills"),
                        ("✅ Generating Conclusion...", "conclusion")
                    ]

                    memo_data = {
                        "Court": court,
                        "Case Number": case_number,
                    }

                    for i in range(1, 3):
                        name = data.get(f"plaintiff{i}", "")
                        memo_data[f"plaintiff{i}"] = name
                        memo_data[f"plaintiff{i}_statement"] = st.session_state.party_statements.get(f"plaintiff{i}_statement", "")

                    for i in range(1, 8):
                        def_name = data.get(f"defendant{i}", "")
                        memo_data[f"defendant{i}"] = def_name
                        memo_data[f"defendant{i}_statement"] = st.session_state.party_statements.get(f"defendant{i}_statement", "")

                    # Preprocess facts once
                    facts_input = trim_to_token_limit("\n\n".join(chunk_text(data["complaint_narrative"])), 3000)

                    total = len(steps)
                    for idx, (text, key) in enumerate(steps):
                        progress = (idx + 1) / total
                        progress_text.text(f"{text} ({int(progress * 100)}%)")
                        progress_bar.progress(progress)

                        if key == "introduction":
                            memo_data[key] = safe_generate(generate_introduction, data["complaint_narrative"], data["plaintiff1"])

                        elif key == "plaintiff_statement":
                            memo_data["plaintiff1_statement"] = safe_generate(generate_plaintiff_statement, data["party_info"], data["plaintiff1"])

                        elif key.startswith("defendant") and key.endswith("_statement"):
                            i = key.replace("defendant", "").replace("_statement", "")
                            statement_key = f"defendant{i}_statement"
                            memo_data[statement_key] = safe_generate(
                                generate_defendant_statement,
                                data.get("party_info", "") + "\n\n" + data.get("settlement_summary", ""),
                                data.get(f"defendant{i}", "")
                            )

                        elif key == "demand":
                            memo_data[key] = safe_generate(generate_demand_section, data["settlement_summary"], data["plaintiff1"])

                        elif key == "facts_liability":
                            memo_data[key] = polish_text_for_legal_memo(
                                safe_generate(generate_facts_liability_section, facts_input, unique_liability_quotes)
                            )

                        elif key == "causation_injuries":
                            memo_data[key] = safe_generate(generate_causation_injuries, data["medical_summary"])

                        elif key == "additional_harms":
                            memo_data[key] = safe_generate(generate_additional_harms, data["medical_summary"], data["deposition_damages"])

                        elif key == "future_bills":
                            memo_data[key] = safe_generate(generate_future_medical, data["medical_summary"], data["deposition_damages"])

                        elif key == "conclusion":
                            memo_data[key] = safe_generate(generate_conclusion_section, data["settlement_summary"])

                    output_path = fill_mediation_template(memo_data, template_path, output_dir)
                    st.session_state.generated_file_path = output_path
                    st.success("✅ Mediation memo generated successfully!")

                except Exception as e:
                    st.error(f"❌ Error: {e}")


if "generated_file_path" in st.session_state:
    with open(st.session_state.generated_file_path, "rb") as f:
        st.download_button(
            "📂 Download Mediation Memo",
            f,
            file_name=os.path.basename(st.session_state.generated_file_path)
        )

if tool == "📖 Instructions & Support":
    st.header("📘 Instructions & Support")

    with st.expander("📄 Batch Doc Generator – How to Use", expanded=True):
        st.markdown("""
Use this tool to **automatically generate documents in bulk** by merging a Word template with an Excel sheet.

**Step-by-step:**
1. **Upload a Word Template or Select an Existing Template**
   - If uploading a new template, use placeholders inside of the document like {{ClientName}}, {{Date}}, etc.
   - These placeholders should mirror what is at the top of your excel columns
   - Save your template for reuse — it’ll appear in the dropdown.
   - If selecting an existing template, choose 'Select a Saved Template' and search for the existing template. 

2. **Upload an Excel File**
   - Must have one row per document.
   - Column names must match the placeholders in your Word template.

3. **Preview the Data**
   - View the first row to confirm the placeholder match.

4. **Set Output Filename Format**
   - Use any column name inside {{ }}.
   - Example: {{ClientName}}_Notice → JohnDoe_Notice.docx.

5. **Generate Documents**
   - Click “Generate Files.”
   - Download a ZIP file with all Word documents.
        """)

    with st.expander("📬 FOIA Requests – How to Use", expanded=False):
        st.markdown("""
Use this tool to generate **individual FOIA request letters** using form fields you fill in manually.

**Step-by-step:**
1. **Fill Out the Form**
   - Enter details like Client ID, Recipient info, Synopsis, Requested Records, and any Explicit Instructions (Optional but typically helpful to establish scope).
   - Enter the case type (Not Neos case type, get specific. Ex: Motorcycle Accident), the Facility or System (Ex: Municipal Police Department, DCFS, etc.), and the Recipient Role (Ex. Responding Officers). 
   - All inputs are required unless marked optional.

2. **Click 'Generate FOIA Letter'**
   - A personalized Word document will be created.

3. **Download**
   - You’ll see a preview and a download button for the generated letter.
        """)

    with st.expander("📂 Demand Letters – How to Use", expanded=False):
        st.markdown("""
Use this tool to generate **individual demand letters** using a manual entry form.

**Step-by-step:**
1. **Fill Out the Form**
   - Enter the client’s name, defendant, incident date, location, summary, and damages (damages should be a dollar figure. Ex. $100,000 One Hundred Thousand Dollars).

2. **Click 'Generate Demand Letter'**
   - The app will insert your responses into a Word template.

3. **Download**
   - A finished letter will be available for download after approximately a minute.
        """)

    with st.expander("🧾 Mediation Memos – How to Use", expanded=False):
        st.markdown("""
Use this tool to generate **confidential mediation memorandums** from structured prompts.

**Step-by-step:**
1. **Fill Out Each Section**
   - Court name, case number, and all memo sections (Intro through Conclusion).
   - AI will convert each input into a professional paragraph in your memo.

2. **Click 'Generate Mediation Memo'**
   - A final Word document will be created with your inputs formatted and polished.

3. **Download**
   - You'll get a download button to retrieve the complete mediation memorandum.
        """)

    with st.expander("🚧 Complaints – Coming Soon", expanded=False):
        st.markdown("""
This section will automate formal legal complaint drafting.

**Planned Features:**
- Upload structured abuse data (e.g., facility, dates, abuse summary).
- Auto-generate civil complaints using AI + custom templates.
- Optional footnotes, exhibits, and institutional history blocks.
        """)

    with st.expander("🚧 Subpoenas – Coming Soon", expanded=False):
        st.markdown("""
This tool will allow you to auto-generate subpoena forms for institutions, agencies, and record holders.

**Planned Features:**
- Upload a list of targets with addresses and requested materials.
- Pre-fill standard subpoena templates.
- Batch generate, preview, and download signed copies.
        """)

    st.subheader("🐞 Report a Bug")
    with st.form("report_form"):
        issue = st.text_area("Describe the issue:")
        submitted = st.form_submit_button("Submit")
        if submitted:
            with open("error_reports.txt", "a", encoding="utf-8") as f:
                f.write(issue + "\n---\n")
            st.success("✅ Issue submitted. Thank you!")

if tool == "📧 Welcome Email Sender":
    st.header("📧 Welcome Email Sender")

    # Load your full DataFrame (already in use for dashboard)
    import os
    import dropbox
    from io import BytesIO

    # Authenticate with Dropbox using environment variables
    dbx = dropbox.Dropbox(
        oauth2_refresh_token=os.environ["DROPBOX_REFRESH_TOKEN"],
        app_key=os.environ["DROPBOX_APP_KEY"],
        app_secret=os.environ["DROPBOX_APP_SECRET"]
    )

    # Download the latest Excel file
    file_path = "/Master Dashboard.xlsx"
    metadata, res = dbx.files_download(file_path)

    # Load the Master Dashboard sheet into DataFrame
    df = pd.read_excel(BytesIO(res.content), sheet_name="Master Dashboard")

    # Filter to show only clients with 'Intake Completed'
    intake_df = df[df["Class Code Title"] == "Intake Completed"].copy()

    # Dropdown to select template
    template_key = st.selectbox("Select Email Template", list(TEMPLATE_CONFIG.keys()))

    # === Sidebar Filters for Email Tool ===
    with st.sidebar:
        st.markdown("### 🔎 Filter Clients")

        class_code_options = sorted(intake_df["Class Code Title"].dropna().unique())
        status_options = sorted(intake_df["Status"].dropna().unique()) if "Status" in intake_df.columns else []

        selected_class_codes = st.multiselect("Class Code", class_code_options, default=class_code_options)
        selected_statuses = st.multiselect("Status", status_options, default=status_options) if status_options else []

    # Apply filters
    filtered_df = intake_df[
        intake_df["Class Code Title"].isin(selected_class_codes) &
        (intake_df["Status"].isin(selected_statuses) if status_options else True)
    ]

    # Text-based search filter
    search_term = st.text_input("🔍 Search client name or email").strip().lower()
    if search_term:
        filtered_df = filtered_df[
            filtered_df["Case Details First Party Name (Full - Last, First)"].str.lower().str.contains(search_term) |
            filtered_df["Case Details First Party Details Default Email Account Address"].str.lower().str.contains(search_term)
        ]

    # Select clients
    client_options = filtered_df["Case Details First Party Name (Full - Last, First)"].tolist()
    selected_clients = st.multiselect("Select Clients to Email", client_options)

    # Initialize session state
    if "email_previews" not in st.session_state:
        st.session_state.email_previews = []
    if "email_status" not in st.session_state:
        st.session_state.email_status = {}

    # === Preview Emails ===
    if st.button("🔍 Preview Emails"):
        st.session_state.email_previews = []
        st.session_state.email_status = {}

        for i, (_, row) in enumerate(filtered_df[filtered_df["Case Details First Party Name (Full - Last, First)"].isin(selected_clients)].iterrows()):
            client_data = {
                "ClientName": row["Case Details First Party Name (Full - Last, First)"],
                "ReferringAttorney": row.get("Referring Attorney", "N/A"),
                "CaseID": row.get("Case ID", "N/A"),
                "Email": row["Case Details First Party Details Default Email Account Address"]
            }

            try:
                subject, body, cc = merge_template(template_key, client_data)

                subject_key = f"subject_{i}"
                body_key = f"body_{i}"
                status_key = f"status_{i}"

                st.markdown(f"**{client_data['ClientName']}** — _{client_data['Email']}_")
                st.text_input("✏️ Subject", subject, key=subject_key)
                st.text_area("📄 Body", body, height=300, key=body_key)
                st.markdown(f"**Status**: {st.session_state.email_status.get(status_key, '⏳ Ready to send')}")

                if st.button(f"📧 Send Email to {client_data['ClientName']}", key=f"send_{i}"):
                    try:
                        with st.spinner("Sending..."):
                            send_email(
                                to=client_data["Email"],
                                subject=st.session_state[subject_key],
                                body=st.session_state[body_key],
                                cc=cc
                            )

                            update_class_code(
                                case_id=client_data["CaseID"],
                                new_class_code_title="Questionnaire Sent",
                                welcome_email_field_key="CustomField_WelcomeEmailSent"
                            )

                            st.session_state.email_status[status_key] = "✅ Sent successfully"

                            log_entry = {
                                "Timestamp": datetime.now().isoformat(),
                                "Client Name": client_data["ClientName"],
                                "Email": client_data["Email"],
                                "Subject": st.session_state[subject_key],
                                "Body": st.session_state[body_key],
                                "Template": template_key,
                                "CC List": ", ".join(cc),
                                "Case ID": client_data["CaseID"],
                                "Class Code Before": "Intake Completed",
                                "Class Code After": "Questionnaire Sent"
                            }

                            if "log_results" not in st.session_state:
                                st.session_state.log_results = []
                            st.session_state.log_results.append(log_entry)

                    except Exception as e:
                        st.session_state.email_status[status_key] = f"❌ Error: {e}"

                st.markdown("---")

                st.session_state.email_previews.append({
                    "client_data": client_data,
                    "subject_key": subject_key,
                    "body_key": body_key,
                    "cc": cc,
                    "status_key": status_key
                })

            except Exception as e:
                st.error(f"❌ Error generating preview for {client_data['ClientName']}: {e}")

    # === Send All Button ===
    if st.session_state.email_previews and st.button("📧 Send All Edited Emails"):
        with st.spinner("Sending all emails..."):
            results = []
            for preview in st.session_state.email_previews:
                status = st.session_state.email_status.get(preview["status_key"], "")
                if "✅" in status:
                    continue  # Skip already sent

                client_data = preview["client_data"]
                subject = st.session_state[preview["subject_key"]]
                body = st.session_state[preview["body_key"]]
                cc = preview["cc"]
                status_key = preview["status_key"]

                try:
                    send_email(to=client_data["Email"], subject=subject, body=body, cc=cc)

                    update_class_code(
                        case_id=client_data["CaseID"],
                        new_class_code_title="Questionnaire Sent",
                        welcome_email_field_key="CustomField_WelcomeEmailSent"
                    )

                    log_entry = {
                        "Timestamp": datetime.now().isoformat(),
                        "Client Name": client_data["ClientName"],
                        "Email": client_data["Email"],
                        "Subject": subject,
                        "Body": body,
                        "Template": template_key,
                        "CC List": ", ".join(cc),
                        "Case ID": client_data["CaseID"],
                        "Class Code Before": "Intake Completed",
                        "Class Code After": "Questionnaire Sent"
                    }

                    results.append(log_entry)
                    st.session_state.email_status[status_key] = "✅ Sent successfully"

                except Exception as e:
                    st.session_state.email_status[status_key] = f"❌ Error: {e}"

            if results:
                log_df = pd.DataFrame(results)
                log_path = "email_automation/data/sent_email_log.csv"
                if os.path.exists(log_path):
                    existing = pd.read_csv(log_path)
                    updated = pd.concat([existing, log_df], ignore_index=True)
                else:
                    updated = log_df

                updated.to_csv(log_path, index=False)
                st.info("📘 Email log saved.")

# Footer
st.markdown("""
<hr style="margin-top: 2rem;">
<div style="text-align: center; font-size: 0.85rem; color: gray;">
&copy; 2025 Stinar Gould Grieco & Hensley. All rights reserved.
</div>
""", unsafe_allow_html=True)

