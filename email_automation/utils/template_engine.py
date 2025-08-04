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
    # Accept the full path instead of rebuilding it
    if not os.path.exists(template_path):
        raise FileNotFoundError(f"Template '{template_path}' not found")

    with open(template_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Validate template sections
    if "Subject:" not in content or "Body:" not in content:
        raise ValueError("Template must contain both 'Subject:' and 'Body:' sections")

    # Split into subject and body
    subject_line = content.split("Subject:")[1].split("Body:")[0].strip()
    body_content = content.split("Body:")[1].strip()

    # Replace {{placeholders}} in subject and body
    for key, value in replacements.items():
        subject_line = subject_line.replace(f"{{{{{key}}}}}", str(value))
        body_content = body_content.replace(f"{{{{{key}}}}}", str(value))

    # Build CC list if ReferringAttorneyEmail exists
    cc_list = (
        [replacements.get("ReferringAttorneyEmail", "")]
        if "ReferringAttorneyEmail" in replacements else []
    )

    return subject_line, body_content, cc_list
