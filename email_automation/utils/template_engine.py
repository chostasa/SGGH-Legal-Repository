import os
from typing import Tuple, List

def merge_template(template_path: str, replacements: dict) -> Tuple[str, str, List[str]]:
    """
    Loads an email template and substitutes {{placeholders}} with values.
    Template must contain:
    - Subject: line (only once)
    - Body: followed by full body content (HTML or plaintext)

    Example format:
    Subject: Welcome {{ClientName}}
    Body:
    <html>...</html>

    Returns: (subject, body_html, cc_list)
    """
    if not os.path.exists(template_path):
        raise FileNotFoundError(f"Template '{template_path}' not found.")

    with open(template_path, "r", encoding="utf-8") as f:
        content = f.read()

    if "Subject:" not in content or "Body:" not in content:
        raise ValueError("Template must contain both 'Subject:' and 'Body:' sections")

    # Safely split on first occurrence of "Body:" (to preserve body HTML)
    subject_raw, body_raw = content.split("Body:", 1)

    subject = subject_raw.replace("Subject:", "").strip()
    body = body_raw.strip()

    # Replace all {{placeholders}} in subject and body
    for key, value in replacements.items():
        subject = subject.replace(f"{{{{{key}}}}}", str(value))
        body = body.replace(f"{{{{{key}}}}}", str(value))

    # Wrap plain text in HTML if needed
    body_lower = body.strip().lower()
    if not body_lower.startswith("<html") and not body_lower.startswith("<!doctype"):
        body = f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body>
{body}
</body>
</html>"""

    # Optional CC
    cc_email = replacements.get("ReferringAttorneyEmail")
    cc_list = [cc_email] if cc_email else []

    return subject, body, cc_list
