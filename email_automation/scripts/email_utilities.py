# email_utilities.py

import os
from jinja2 import Template


def merge_template(template_key, client_data):
    """
    Loads a .txt-based template file from the templates directory.
    The first line is used as the subject line, and the remainder as the email body.
    Jinja2-style {{placeholders}} are replaced using client_data.
    """
    template_path = os.path.join("email_automation", "templates", f"{template_key}.txt")

    with open(template_path, "r", encoding="utf-8") as file:
        lines = file.read().splitlines()

    if not lines:
        raise ValueError(f"Template '{template_key}' is empty.")

    subject_template = lines[0].strip()
    body_template = "\n".join(lines[1:]).strip()

    subject = Template(subject_template).render(**client_data)
    body = Template(body_template).render(**client_data)

    # You can make this dynamic if needed
    cc = ["athrush@sgghlaw.com"]

    return subject, body, cc
