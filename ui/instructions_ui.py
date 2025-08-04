import streamlit as st
from core.error_handling import handle_error
from core.usage_tracker import get_quota_status


def run_ui():
    try:
        st.title("📖 Legal Automation Hub: Full Instructions & Training")

        # Show quota info if available
        quota_info = get_quota_status()
        if quota_info:
            st.info(
                f"Remaining Quota - Documents: {quota_info.get('documents_generated', 'N/A')}, "
                f"Tokens: {quota_info.get('openai_tokens', 'N/A')}"
            )

        st.markdown("""
# ⚡ Welcome to the Legal Automation Hub  

The **Legal Automation Hub** is your **all-in-one powerhouse** for managing litigation campaigns at scale.  
This isn’t just a collection of tools – it’s an **end-to-end automation engine** designed to eliminate the repetitive, time-consuming tasks that drag your team down.  

## What this Hub will do for you:
- 🚀 **Speed:** Turn hours of administrative work into minutes  
- 🧠 **AI-Powered Drafting:** Generate professional-grade letters, memos, and FOIA requests in seconds  
- 🔄 **Full Automation:** Update NEOS, send emails, log documents – all from one dashboard  
- 📊 **Total Visibility:** Track every campaign live with filters, KPIs, and reports  
- 🔒 **Accuracy:** Eliminate manual errors by merging directly with data and templates  
- 📈 **Scale:** Handle **hundreds or thousands of clients at once** without breaking a sweat  

---

## **How to Use This Guide**

Each module has a **collapsible step-by-step guide** below.  
**Click the arrow (▶) next to the module name** to expand its instructions.  

""")

        with st.expander("📊 Litigation Dashboard – Your Mission Control", expanded=False):
            st.markdown("""
**What this tool does:**  
The Dashboard is your **central command center**. It pulls together **live data** on every client, case, and campaign in one place.  
You can **filter, export, and take action** (like sending filtered lists to the Batch Document Generator) in just a few clicks.  

### **Step-by-Step:**
1. Open the **Litigation Dashboard** from the sidebar.  
2. Use the filters in the sidebar on the left:  
   - **Campaign:** Select one or more campaigns to focus on.  
   - **Referring Attorney:** Narrow down by attorney.  
   - **Case Status:** Focus on specific workflow stages.  
3. Watch the tables and charts **update instantly**.  
4. Scroll down for the full table of cases.  
5. Take action:  
   - Click **Download Filtered Results as CSV** to export a clean list.  
   - OR click **Send to Batch Generator** to instantly launch mail merges using this filtered data.
""")

        with st.expander("📧 Welcome Email Sender – Automate Client Outreach", expanded=False):
            st.markdown("""
**What this tool does:**  
The Email Sender makes **client communication painless**. In minutes, you can email hundreds of clients at once, using pre-approved templates, and automatically update their case statuses in NEOS.

### **Step-by-Step:**
1. Click **Welcome Email Sender** from the sidebar.  
2. The Hub will show you a list of clients ready for outreach (e.g., Intake Completed).  
3. Narrow down the list using the filters:  
   - **Class Code** (e.g., Intake Completed)  
   - **Status** (optional, if your dashboard tracks it)  
4. Choose the email template you want to send from the dropdown.  
5. Decide how to send:  
   - **Preview each email individually:** Click "Preview Emails" and check subject lines and body text. You can edit them on the fly.  
   - **Batch send everything at once:** Once you're satisfied, click **Send All**.  
6. The Hub will:  
   - Email every client  
   - Update their NEOS status  
   - Log each email in the Email Log  
7. Done! No more copying and pasting from spreadsheets.
""")

        with st.expander("📄 Batch Document Generator – Bulk Document Creation", expanded=False):
            st.markdown("""
**What this tool does:**  
This tool is a **mail merge on steroids**. It will take your Excel spreadsheet and one or more Word templates and produce **hundreds of personalized letters** in one batch.

### **Step-by-Step:**
1. Click **Batch Document Generator** in the sidebar.  
2. Choose your data source:  
   - Upload a **new Excel spreadsheet (.xlsx)**  
   - Or use the filtered data you just exported from the Dashboard (automatically loaded if sent directly)  
3. The Hub will show you the column headers from the Excel file. These must match the placeholders in your Word template (e.g., `{{Client Name}}`).  
4. Next, choose your template:  
   - Upload a **new Word template (.docx)** from your computer, or  
   - Select a previously saved template from the library  
5. (Optional) Remove any columns you don’t want to merge by unchecking them.  
6. Click **Generate Documents**.  
7. The Hub will:  
   - Replace every placeholder with client-specific data  
   - Save all letters in a clean ZIP file  
8. Click the download button to save the ZIP to your computer.
""")

        with st.expander("🧠 Style Mimic Generator – Rewrite in Your Voice", expanded=False):
            st.markdown("""
**What this tool does:**  
Takes example paragraphs and rewrites any text inputs **to match the tone and structure** of those examples.  
Great for maintaining consistent firm branding.

### **Step-by-Step:**
1. Click **Style Mimic Generator** from the sidebar.  
2. Paste one or more example paragraphs into the box.  
   - Separate each example with three dashes: `---`  
3. Provide the text you want rewritten:  
   - Upload an Excel sheet with text inputs in a column, or  
   - Paste multiple text inputs directly into the box (separated with `---`)  
4. Click **Generate Styled Outputs**.  
5. Download the Excel file showing **Original Input** and **Styled Output**.
""")

        with st.expander("📬 FOIA Requests – Get the Records You Need", expanded=False):
            st.markdown("""
**What this tool does:**  
Generates fully compliant **Freedom of Information Act request letters** with AI assistance.

### **Step-by-Step:**
1. Click **FOIA Requests** from the sidebar.  
2. Fill in all required fields:  
   - Client name or ID  
   - Recipient agency name and address  
   - State, date of incident, location  
   - Case synopsis (2–3 sentences of what happened)  
   - Potential records you’re requesting (e.g., police reports, body cam footage)  
3. (Optional) Upload a style example to match previous FOIA letters.  
4. Click **Generate FOIA Letter**.  
5. Review the bullet-point list of records the Hub will request.  
6. Download the Word (.docx) letter to send.
""")

        with st.expander("📂 Demands – Attorney-Quality Demand Letters", expanded=False):
            st.markdown("""
**What this tool does:**  
Generates fully formatted **Demand Letters** that look like they came straight from a partner’s desk.

### **Step-by-Step:**
1. Click **Demands** from the sidebar.  
2. Fill in all fields:  
   - Client name  
   - Defendant name  
   - Date and location of incident  
   - Incident summary (one paragraph)  
   - Damages summary (one paragraph)  
3. (Optional) Add a style/tone example to match the firm's voice.  
4. Click **Generate Demand Letter**.  
5. Wait for the confirmation message, then click the **Download** button to save the Word (.docx) file.
""")

        with st.expander("🧾 Mediation Memos – Build a Case-Winning Narrative", expanded=False):
            st.markdown("""
**What this tool does:**  
Creates detailed **Mediation Memos** that combine narratives, plaintiff/defendant summaries, and deposition quotes.

### **Step-by-Step:**
1. Click **Mediation Memos** from the sidebar.  
2. Enter the case details:  
   - Court  
   - Case number  
   - Plaintiff(s) and Defendant(s) names  
3. Paste the complaint narrative, party information, settlement summary, and medical summary.  
4. (Optional) Paste deposition transcript text to automatically extract quotes.  
5. Upload your memo template (.docx).  
6. Choose whether to:  
   - Preview and edit party paragraphs first, or  
   - Generate the full memo immediately  
7. Download the memo as a Word (.docx) file or plain-text preview.
""")

        with st.expander("🧪 Template Tester – Validate Before You Merge", expanded=False):
            st.markdown("""
**What this tool does:**  
Shows you how any Word template will render with sample data **before using it live**.  
This prevents broken placeholders.

### **Step-by-Step:**
1. Click **Template Tester** from the sidebar.  
2. Upload the Word template (.docx) you want to test.  
3. Paste sample data in the box using JSON or YAML format (examples are preloaded).  
4. Click **Generate Preview**.  
5. Download the rendered Word file to check the formatting and placeholders.
""")

        st.markdown("""
---

### 🎥 Training Videos (Coming Soon)

Step-by-step **video tutorials** and screenshots will be embedded here for each module.  
""")
    except Exception as e:
        msg = handle_error(e, code="INSTRUCTIONS_UI_001")
        st.error(msg)
