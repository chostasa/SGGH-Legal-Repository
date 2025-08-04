import streamlit as st
import pandas as pd
import asyncio
from io import BytesIO

from services.style_transfer_service import run_batch_style_transfer
from core.security import sanitize_filename
from core.auth import get_tenant_id, get_user_role
from core.audit import log_audit_event
from core.error_handling import handle_error
from core.usage_tracker import check_quota, decrement_quota
from logger import logger

from core.db import get_examples, upload_example
from services.dropbox_client import download_example_file


def run_style_transfer_ui():
    st.title("🧠 Style Mimic Generator")
    st.markdown("""
Upload one or more **example paragraphs**, then either upload an Excel file of inputs **or** paste them directly into the app.
Each input will be rewritten to match the **tone, structure, and legal voice** of the example(s).

- Separate multiple example paragraphs with `---`
- Pasted inputs should also be separated with `---`
""")

    tenant_id = get_tenant_id()
    user_role = get_user_role()

    st.subheader("🎨 Choose or Add Example Paragraph(s)")

    # Load examples from Dropbox
    try:
        available_examples = get_examples(tenant_id, "style_transfer")
        example_names = [ex["name"] for ex in available_examples]
    except Exception as e:
        msg = handle_error(e, code="STYLE_UI_001")
        st.error(msg)
        return

    selected_example = st.selectbox("📂 Select Existing Example (optional)", ["None"] + example_names)

    example_text = ""
    if selected_example != "None":
        try:
            local_path = download_example_file("style_transfer", selected_example)
            if not local_path or not isinstance(local_path, str):
                raise FileNotFoundError(f"Example file not found for: {selected_example}")

            with open(local_path, "r", encoding="utf-8") as f:
                example_text = f.read()

            with st.expander("🧠 Preview Selected Example"):
                st.code(example_text[:3000], language="markdown")

        except Exception as e:
            msg = handle_error(e, code="STYLE_UI_002")
            st.error(msg)

    example_input = st.text_area(
        "✍️ Paste Example Paragraph(s) (separate with '---')",
        height=250,
        value=example_text
    )
    example_list = [p.strip() for p in example_input.split("---") if p.strip()]

    # Save example (Admin only)
    if example_input.strip() and st.button("💾 Save as Example"):
        try:
            if user_role.lower() != "admin":
                st.error("❌ Only Admins can save style examples.")
            else:
                filename = sanitize_filename(f"example_{len(example_names)+1}.txt")
                upload_example("style_transfer", filename, example_input.encode("utf-8"))

                st.success(f"✅ Saved example as {filename}")
                log_audit_event("Style Example Uploaded", {
                    "filename": filename,
                    "tenant_id": tenant_id,
                    "module": "style_transfer"
                })
                st.rerun()
        except Exception as e:
            msg = handle_error(e, code="STYLE_UI_003")
            st.error(msg)

    # Input method: Excel or pasted text
    input_method = st.radio("📥 Select Input Method", ["Upload Excel", "Paste Text Inputs"])
    inputs_df = None

    # Excel upload path
    if input_method == "Upload Excel":
        uploaded_file = st.file_uploader("📤 Upload Excel File", type=["xlsx"])
        input_col = st.text_input("🔎 Column to Rewrite", value="Input")

        if uploaded_file:
            try:
                df = pd.read_excel(uploaded_file)
                if input_col not in df.columns:
                    st.error(f"Column '{input_col}' not found in uploaded file. Available columns: {list(df.columns)}")
                else:
                    inputs_df = df[[input_col]].rename(columns={input_col: "Input"})
            except Exception as e:
                msg = handle_error(e, code="STYLE_UI_004")
                st.error(msg)

    # Paste text path
    elif input_method == "Paste Text Inputs":
        pasted_text = st.text_area("📋 Paste Inputs Here (separate with '---')", height=300)
        if pasted_text.strip():
            input_list = [x.strip() for x in pasted_text.split('---') if x.strip()]
            inputs_df = pd.DataFrame({"Input": input_list})

    # Single generate button for both methods
    if st.button("🔄 Generate Styled Outputs"):
        if inputs_df is not None and not inputs_df.empty and example_list:
            with st.spinner("Generating styled outputs..."):
                try:
                    check_quota("openai_tokens", amount=len(inputs_df))
                    result_df = asyncio.run(run_batch_style_transfer(example_list, inputs_df, input_col="Input"))
                    decrement_quota("openai_tokens", amount=len(result_df))
                    st.success(f"✅ Successfully rewrote {len(result_df)} inputs.")
                    st.dataframe(result_df)

                    buffer = BytesIO()
                    result_df.to_excel(buffer, index=False, engine='openpyxl')
                    buffer.seek(0)

                    st.download_button(
                        "📥 Download Results as Excel",
                        data=buffer,
                        file_name="styled_outputs.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )

                    log_audit_event("Style Transfer Generated", {
                        "tenant_id": tenant_id,
                        "input_count": len(result_df),
                        "example_used": selected_example if selected_example != "None" else "pasted",
                        "module": "style_transfer"
                    })
                except Exception as e:
                    msg = handle_error(e, code="STYLE_UI_005")
                    st.error(msg)
        else:
            st.warning("Please provide both example paragraphs and at least one input.")
