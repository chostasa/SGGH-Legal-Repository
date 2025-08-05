import os

def merge_template(template_path: str, replacements: dict) -> tuple[str, str, list[str]]:
    """
    Loads a .txt or .html template using the full template_path and substitutes {{placeholders}} with values.

    Template format:
    Subject: Welcome {{ClientName}}
    Body:
    <html or text content with {{placeholders}}>

    Returns: (subject, body, cc_list)
    """
    # Ensure the template exists
    if not os.path.exists(template_path):
        raise FileNotFoundError(f"Template '{template_path}' not found")

    # Read file contents
    with open(template_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Ensure required sections exist
    if "Subject:" not in content or "Body:" not in content:
        raise ValueError("Template must contain both 'Subject:' and 'Body:' sections")

    # Parse subject and body
    subject_line = content.split("Subject:")[1].split("Body:")[0].strip()
    body_content = content.split("Body:")[1].strip()

    # Perform placeholder replacements
    for key, value in replacements.items():
        subject_line = subject_line.replace(f"{{{{{key}}}}}", str(value))
        body_content = body_content.replace(f"{{{{{key}}}}}", str(value))

    # Ensure the body is valid HTML if not already
    body_lower = body_content.strip().lower()
    if not body_lower.startswith("<html") and not body_lower.startswith("<!doctype"):
        body_content = f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body>
{body_content}
</body>
</html>"""

    # Optional CC list if ReferringAttorneyEmail is present
    cc_email = replacements.get("ReferringAttorneyEmail")
    cc_list = [cc_email] if cc_email else []

    return subject_line, body_content, cc_list
