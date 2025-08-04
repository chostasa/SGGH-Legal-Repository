import os
from datetime import datetime
from openpyxl import load_workbook
import pandas as pd
from demand_service import fill_template

# === Batch Generation from DataFrame ===
def run(df):
    output_dir = "outputs/demands"
    template_path = "templates/demand_template.docx"
    os.makedirs(output_dir, exist_ok=True)
    output_paths = []

    for _, row in df.iterrows():
        data = {
            "Client Name": row.get("Client Name", ""),
            "IncidentDate": row.get("IncidentDate", ""),
            "Summary": row.get("Summary", ""),
            "Damages": row.get("Damages", ""),
            "RecipientName": row.get("RecipientName", "")
        }
        if data["Client Name"].strip():
            path = fill_template(data, template_path, output_dir)
            output_paths.append(path)

    return output_paths

# === Batch Generation from Excel ===
def generate_all_demands(template_path, excel_path, output_dir):
    wb = load_workbook(excel_path)
    sheet = wb.active
    headers = [str(cell.value).strip() for cell in sheet[1]]
    os.makedirs(output_dir, exist_ok=True)

    for row in sheet.iter_rows(min_row=2, values_only=True):
        data = dict(zip(headers, row))
        if not data.get("Client Name", "").strip():
            continue
        if "Incident Date" in data:  # Rename to match demand_service
            data["IncidentDate"] = data.pop("Incident Date")
        fill_template(data, template_path, output_dir)

# === Main Execution for Excel ===
if __name__ == "__main__":
    TEMPLATE_PATH = "templates/demand_template.docx"
    EXCEL_PATH = "data_demand_requests.xlsx"
    OUTPUT_DIR = "outputs/demands"
    generate_all_demands(TEMPLATE_PATH, EXCEL_PATH, OUTPUT_DIR)
