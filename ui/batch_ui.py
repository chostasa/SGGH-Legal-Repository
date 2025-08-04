import streamlit as st
import pandas as pd
import zipfile
import os
import json
from datetime import datetime
from io import BytesIO

from utils.docx_utils import replace_text_in_docx_all
from core.session_utils import get_session_temp_dir
from utils.file_utils import clean_temp_dir
from core.security import sanitize_text, redact_log, mask_phi
from utils.file_utils import sanitize_filename
from core.error_handling import handle_error
from logger import logger
from core.audit import log_audit_event
from core.auth import get_tenant_id
from core.cache_utils import clear_caches


clean_temp_dir()

TENANT_ID = get_tenant_id()
TEMPLATE_DIR = os.path.join("templates", "batch_docs", TENANT_ID)
os.makedirs(TEMPLATE_DIR, exist_ok=True)

def run_ui():
    st.header("📄 Batch Document Generator (Saved Templates + Guided Merge)")
    error_code = "BATCH_GEN_001"
    df = None

    try:
        if "dashboard_df" in st.session_state:
            df = st.session_state.dashboard_df.copy()
            st.success(f"✅ Using filtered data from dashboard: {len(df)} rows")
        else:
            uploaded_excel = st.file_uploader("📊 Upload Excel Sheet (.xlsx)", type=["xlsx"])
            if uploaded_excel:
                try:
                    df = pd.read_excel(uploaded_excel)
                    if df.empty:
                        st.error("❌ Spreadsheet is empty.")
                        df = None
                    else:
                        st.success(f"✅ Loaded {len(df)} rows.")
                except Exception as e:
                    msg = handle_error(e, code="BATCH_UI_001")
                    st.error(msg)

        if df is not None:
            st.subheader("🔍 Column Headers (Placeholders)")
            st.dataframe(df.head(1), use_container_width=True)

            st.subheader("📎 Placeholders to Use in Word Template")
            for col in df.columns:
                st.code(f"{{{{{col}}}}}", language="jinja")

            removable_cols = st.multiselect("🧹 Remove columns before merge:", df.columns.tolist())
            if removable_cols:
                df.drop(columns=removable_cols, inplace=True)
                st.success(f"✅ Removed columns: {', '.join(removable_cols)}")

        if df is not None:
            st.markdown("---")
            st.subheader("📁 Template Manager")

            template_mode = st.radio("Choose Template Mode:", ["Upload New Template", "Select Saved Template", "Template Options"])
            filename_pattern = st.text_input("Output Filename Pattern", value="Letter_{{Client Name}}.docx")
            folder_pattern = st.text_input("📁 Folder Name Pattern", value="Petitions for {{Client Name}}")
            docname_pattern = st.text_input("📄 Document Name Pattern", value="{{index}} {{Client Name}}.docx")
            template_paths, selected_templates = [], []

            if template_mode == "Upload New Template":
                uploaded_template = st.file_uploader("Upload Word Template (.docx)", type=["docx"])
                tags = st.text_input("🏷️ Add tags (comma-separated)", key="upload_tags")

                if uploaded_template:
                    template_path = os.path.join(TEMPLATE_DIR, sanitize_filename(uploaded_template.name))
                    with open(template_path, "wb") as f:
                        f.write(uploaded_template.read())

                    meta = {
                        "filename": os.path.basename(template_path),
                        "tags": [t.strip() for t in tags.split(",") if t.strip()],
                        "uploaded_at": datetime.utcnow().isoformat(),
                        "tenant_id": TENANT_ID
                    }
                    with open(template_path.replace(".docx", ".json"), "w") as f:
                        json.dump(meta, f, indent=2)

                    clear_caches()

                    st.success(f"✅ Uploaded and saved as: {os.path.basename(template_path)}")
                    try:
                        log_audit_event("Template Uploaded", {
                            "filename": os.path.basename(template_path),
                            "tags": meta["tags"],
                            "tenant_id": TENANT_ID,
                            "module": "batch_generator"
                        })
                    except Exception as audit_err:
                        logger.warning(redact_log(mask_phi(f"⚠️ Failed to write audit log: {audit_err}")))

                    template_paths = [template_path]
                    selected_templates = [os.path.basename(template_path)]

            elif template_mode == "Select Saved Template":
                tag_filter = st.text_input("🔍 Filter by tag or name (optional)").lower()
                available_templates = []
                template_info = {}

                for f in os.listdir(TEMPLATE_DIR):
                    if f.endswith(".docx"):
                        path = os.path.join(TEMPLATE_DIR, f)
                        meta_path = path.replace(".docx", ".json")
                        tags = []
                        if os.path.exists(meta_path):
                            try:
                                with open(meta_path, "r") as mf:
                                    meta = json.load(mf)
                                    tags = meta.get("tags", [])
                                    template_info[f] = meta
                            except:
                                pass
                        label = f"{f} {'| ' + ', '.join(tags) if tags else ''}"
                        if tag_filter in label.lower():
                            available_templates.append(label)

                available_templates.sort(key=lambda name: os.path.getmtime(os.path.join(TEMPLATE_DIR, name.split(" | ")[0])), reverse=True)
                selected = st.multiselect("📂 Choose Template(s)", available_templates)
                selected_templates = [s.split(" | ")[0] for s in selected]
                template_paths = [os.path.join(TEMPLATE_DIR, t) for t in selected_templates]

            elif template_mode == "Template Options":
                available_templates = sorted([f for f in os.listdir(TEMPLATE_DIR) if f.endswith(".docx")])
                search_term = st.text_input("🔍 Search for template to manage")
                filtered_templates = [f for f in available_templates if search_term.lower() in f.lower()]

                if filtered_templates:
                    template_choice = st.selectbox("Choose Template to Rename/Delete", filtered_templates)
                    template_path = os.path.join(TEMPLATE_DIR, template_choice)

                    st.subheader("✏️ Rename Template")
                    new_name = st.text_input("New name (no extension)", value=template_choice.replace(".docx", ""))
                    if st.button("Rename Template"):
                        new_path = os.path.join(TEMPLATE_DIR, new_name + ".docx")
                        if os.path.exists(new_path):
                            st.warning("⚠️ A file with that name already exists.")
                        else:
                            os.rename(template_path, new_path)
                            try:
                                os.rename(template_path.replace(".docx", ".json"), new_path.replace(".docx", ".json"))
                            except:
                                pass

                            clear_caches()

                            st.success(f"✅ Renamed to {new_name}.docx")
                            log_audit_event("Template Renamed", {
                                "from": template_choice,
                                "to": new_name + ".docx",
                                "tenant_id": TENANT_ID,
                                "module": "batch_generator"
                            })
                            st.rerun()

                    st.subheader("🗑️ Delete Template")
                    confirm_delete = st.checkbox("Yes, delete this template permanently.")
                    if st.button("Delete Template") and confirm_delete:
                        os.remove(template_path)
                        try:
                            os.remove(template_path.replace(".docx", ".json"))
                        except:
                            pass

                        clear_caches()

                        st.success(f"✅ Deleted '{template_choice}'")
                        log_audit_event("Template Deleted", {
                            "filename": template_choice,
                            "tenant_id": TENANT_ID,
                            "module": "batch_generator"
                        })
                        st.rerun()
                else:
                    st.warning("⚠️ No templates found matching your search.")

            if selected_templates and template_mode != "Template Options":
                if st.button("⚙️ Generate Documents"):
                    with st.spinner("Generating documents..."):
                        try:
                            temp_dir = get_session_temp_dir()
                            zip_buffer = BytesIO()
                            total_success, total_fail = 0, 0

                            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_out:
                                for i, row in df.iterrows():
                                    try:
                                        replacements = {
                                            str(k).strip(): sanitize_text(str(v)) if pd.notnull(v) else ""
                                            for k, v in row.items()
                                        }
                                        replacements["index"] = str(i + 1)

                                        folder_name = folder_pattern
                                        for key, val in replacements.items():
                                            folder_name = folder_name.replace(f"{{{{{key}}}}}", val.strip())
                                        folder_name = sanitize_filename(folder_name)

                                        for template_path in template_paths:
                                            output_filename = docname_pattern
                                            for key, val in replacements.items():
                                                output_filename = output_filename.replace(f"{{{{{key}}}}}", val.strip())
                                            output_filename = sanitize_filename(output_filename.replace(".docx", "") + ".docx")

                                            output_path = os.path.join(temp_dir, f"{folder_name}_{output_filename}")
                                            replace_text_in_docx_all(template_path, replacements, output_path)

                                            zip_entry_path = os.path.join(folder_name, output_filename)
                                            with open(output_path, "rb") as f:
                                                zip_out.writestr(zip_entry_path, f.read())

                                            total_success += 1
                                    except Exception as doc_err:
                                        logger.error(redact_log(mask_phi(f"[{error_code}] ❌ Failed on row {i}: {doc_err}")))
                                        total_fail += 1

                            if total_success:
                                st.success(f"✅ {total_success} documents generated.")
                                st.download_button(
                                    label="⬇️ Download ZIP of Letters",
                                    data=zip_buffer.getvalue(),
                                    file_name="batch_output.zip",
                                    mime="application/zip"
                                )

                                st.caption("⚠️ Files will be deleted after 1 hour. Please download promptly.")
                                log_audit_event("Batch Docs Generated", {
                                    "rows_processed": len(df),
                                    "template_count": len(template_paths),
                                    "tenant_id": TENANT_ID,
                                    "module": "batch_generator"
                                })

                            if total_fail:
                                st.warning(f"⚠️ {total_fail} documents failed. See logs.")

                        except Exception as e:
                            msg = handle_error(e, code="BATCH_UI_002")
                            st.error(msg)

    except Exception as e:
        msg = handle_error(e, code="BATCH_UI_003")
        st.error(msg)
