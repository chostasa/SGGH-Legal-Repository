import os

# ----------------------------
# 📌 Status Labels (UI/Logic)
# ----------------------------
STATUS_INTAKE_COMPLETED = "Intake Completed"
STATUS_QUESTIONNAIRE_SENT = "Questionnaire Sent"

STATUS_CHOICES = [
    STATUS_INTAKE_COMPLETED,
    STATUS_QUESTIONNAIRE_SENT
]

# ----------------------------
# 📄 Template Paths (Local)
# ----------------------------
TEMPLATE_DEMAND = "templates/demand_template.docx"
TEMPLATE_FOIA = "templates/foia_template.docx"
TEMPLATE_DIR = "templates"

# Backward compatibility for legacy imports
demand_template = TEMPLATE_DEMAND
foia_template = TEMPLATE_FOIA

# ----------------------------
# 📧 Default Email Settings
# ----------------------------
DEFAULT_SENDER_EMAIL = os.getenv("DEFAULT_SENDER_EMAIL", "noreply@yourdomain.com")

# ----------------------------
# 📂 Dropbox Root Paths
# ----------------------------
DROPBOX_TEMPLATES_ROOT = "/Templates"
DROPBOX_EXAMPLES_ROOT = "/Examples"
DROPBOX_TRAINING_VIDEO_DIR = "/Training Videos"


# ----------------------------
# 📂 Dropbox Template Folders
# ----------------------------
DROPBOX_EMAIL_TEMPLATE_DIR = f"{DROPBOX_TEMPLATES_ROOT}/Email"
DROPBOX_DEMAND_TEMPLATE_DIR = f"{DROPBOX_TEMPLATES_ROOT}/Demand"
DROPBOX_MEDIATION_TEMPLATE_DIR = f"{DROPBOX_TEMPLATES_ROOT}/Mediation_Memo"
DROPBOX_FOIA_TEMPLATE_DIR = f"{DROPBOX_TEMPLATES_ROOT}/FOIA"

# ----------------------------
# 📂 Dropbox Example Folders
# ----------------------------
DROPBOX_DEMAND_EXAMPLES_DIR = f"{DROPBOX_EXAMPLES_ROOT}/Demand"
DROPBOX_FOIA_EXAMPLES_DIR = f"{DROPBOX_EXAMPLES_ROOT}/FOIA"
DROPBOX_MEDIATION_EXAMPLES_DIR = f"{DROPBOX_EXAMPLES_ROOT}/Mediation"
DROPBOX_STYLE_EXAMPLES_DIR = f"{DROPBOX_EXAMPLES_ROOT}/Style_Transfer"
