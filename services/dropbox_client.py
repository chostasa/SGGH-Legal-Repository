import os
import dropbox
import pandas as pd
from io import BytesIO
from config import AppConfig, get_config
from core.error_handling import handle_error
from logger import logger
from core.constants import (
    DROPBOX_TEMPLATES_ROOT,
    DROPBOX_EXAMPLES_ROOT,
    DROPBOX_EMAIL_TEMPLATE_DIR,
    DROPBOX_DEMAND_TEMPLATE_DIR,
    DROPBOX_MEDIATION_TEMPLATE_DIR,
    DROPBOX_FOIA_TEMPLATE_DIR,
    DROPBOX_DEMAND_EXAMPLES_DIR,
    DROPBOX_FOIA_EXAMPLES_DIR,
    DROPBOX_MEDIATION_EXAMPLES_DIR,
    DROPBOX_STYLE_EXAMPLES_DIR
)

def normalize_path(path: str) -> str:
    """
    Normalize a Dropbox or local file path by fixing duplicate folders and extensions.
    """
    normalized_path = os.path.normpath(path)

    # Fix duplicate folder names
    if "templates/templates" in normalized_path:
        normalized_path = normalized_path.replace("templates/templates", "templates")

    # Fix duplicate extensions (.txt.txt, .html.html, .docx.docx, .docx.txt, etc.)
    while normalized_path.endswith((".txt.txt", ".html.html", ".docx.docx", ".docx.txt", ".txt.docx", ".txt.html", ".html.txt")):
        if ".txt" in normalized_path:
            normalized_path = normalized_path.rsplit(".", 1)[0] + ".txt"
        elif ".html" in normalized_path:
            normalized_path = normalized_path.rsplit(".", 1)[0] + ".html"
        else:
            normalized_path = normalized_path.rsplit(".", 1)[0] + ".docx"

    return normalized_path


class DropboxClient:
    def __init__(self, config: AppConfig = None):
        self.config = config or get_config()

        try:
            # Create Dropbox client using refresh token (auto-refresh access token)
            self.dbx = dropbox.Dropbox(
                app_key=self.config.DROPBOX_APP_KEY,
                app_secret=self.config.DROPBOX_APP_SECRET,
                oauth2_refresh_token=self.config.DROPBOX_REFRESH_TOKEN,
            )
            logger.info("[DROPBOX_INIT] ✅ Dropbox client initialized with refresh token")
        except Exception as e:
            handle_error(e, code="DROPBOX_INIT_001", raise_it=True)

    def download_dashboard_df(
        self, file_path: str = None, sheet_name: str = "Master Dashboard"
    ) -> pd.DataFrame:
        """Download the dashboard Excel from Dropbox and return as DataFrame."""
        path = normalize_path(file_path or self.config.DROPBOX_MASTER_DASHBOARD_PATH)

        try:
            metadata, res = self.dbx.files_download(path)
            if not res or not res.content:
                raise ValueError(f"No content returned from Dropbox for path: {path}")

            df = pd.read_excel(BytesIO(res.content), sheet_name=sheet_name)
            if df.empty:
                raise ValueError(f"Downloaded Excel is empty for path: {path}")

            logger.info(
                f"[DROPBOX_DOWNLOAD] 📥 Downloaded dashboard from {path} ({len(df)} rows)"
            )
            return df

        except Exception as e:
            handle_error(e, code="DROPBOX_DOWNLOAD_001", raise_it=True)

    def list_files(self, folder_path: str):
        """
        List all files in a Dropbox folder. Auto-create folder if it doesn't exist.
        """
        folder_path = normalize_path(folder_path)
        try:
            # Ensure the folder exists (create if missing)
            try:
                self.dbx.files_get_metadata(folder_path)
            except dropbox.exceptions.ApiError as e:
                if (
                    hasattr(e.error, "is_path")
                    and e.error.is_path()
                    and e.error.get_path().is_not_found()
                ):
                    # Folder missing: create it
                    logger.info(f"[DROPBOX] Creating missing folder: {folder_path}")
                    self.dbx.files_create_folder_v2(folder_path)
                else:
                    raise

            result = self.dbx.files_list_folder(folder_path)
            files = [normalize_path(entry.name) for entry in result.entries if hasattr(entry, "name")]

            logger.info(
                f"[DROPBOX_LIST] 📂 Listed {len(files)} files in folder: {folder_path}"
            )
            return files

        except Exception as e:
            handle_error(e, code="DROPBOX_LIST_001", raise_it=True)

    def download_file(self, dropbox_path: str, local_dir: str = "downloads") -> str:
        """
        Download a file from Dropbox to a local directory and return the local path.
        Ensures that duplicate paths and extensions are cleaned.
        """
        dropbox_path = normalize_path(dropbox_path)
        try:
            os.makedirs(local_dir, exist_ok=True)
            filename = normalize_path(os.path.basename(dropbox_path))

            # Enforce only supported template extensions (.txt, .html, .docx)
            if not filename.endswith((".txt", ".html", ".docx")):
                raise ValueError(f"Unsupported template type: {filename}")

            local_path = os.path.join(local_dir, filename)

            metadata, res = self.dbx.files_download(dropbox_path)
            with open(local_path, "wb") as f:
                f.write(res.content)

            logger.info(
                f"[DROPBOX_DOWNLOAD] 📄 Downloaded {dropbox_path} → {local_path}"
            )
            return local_path
        except Exception as e:
            handle_error(e, code="DROPBOX_DOWNLOAD_FILE_001", raise_it=True)

    def ensure_base_folders(self):
        """
        Ensure the full folder tree for templates/examples exists in Dropbox.
        """
        base_folders = [
            DROPBOX_EMAIL_TEMPLATE_DIR,
            DROPBOX_DEMAND_TEMPLATE_DIR,
            DROPBOX_MEDIATION_TEMPLATE_DIR,
            DROPBOX_FOIA_TEMPLATE_DIR,
            f"{DROPBOX_TEMPLATES_ROOT}/Batch_Docs",
            DROPBOX_DEMAND_EXAMPLES_DIR,
            DROPBOX_FOIA_EXAMPLES_DIR,
            DROPBOX_MEDIATION_EXAMPLES_DIR,
            DROPBOX_STYLE_EXAMPLES_DIR 
        ]
        for folder in base_folders:
            folder = normalize_path(folder)
            try:
                self.dbx.files_get_metadata(folder)
            except dropbox.exceptions.ApiError:
                logger.info(f"[DROPBOX] Creating base folder: {folder}")
                self.dbx.files_create_folder_v2(folder)


# === Global helper functions (used by modules) ===

def download_dashboard_df(
    file_path: str = None, sheet_name: str = "Master Dashboard"
) -> pd.DataFrame:
    client = DropboxClient()
    return client.download_dashboard_df(file_path=file_path, sheet_name=sheet_name)


def list_templates(category: str):
    """
    Return list of template files for a category (email, demand, mediation, foia, batch_docs).
    """
    from core.constants import (
        DROPBOX_EMAIL_TEMPLATE_DIR,
        DROPBOX_DEMAND_TEMPLATE_DIR,
        DROPBOX_MEDIATION_TEMPLATE_DIR,
        DROPBOX_FOIA_TEMPLATE_DIR
    )
    folder_map = {
        "email": DROPBOX_EMAIL_TEMPLATE_DIR,
        "demand": DROPBOX_DEMAND_TEMPLATE_DIR,
        "mediation": DROPBOX_MEDIATION_TEMPLATE_DIR,      
        "mediation_memo": DROPBOX_MEDIATION_TEMPLATE_DIR,
        "foia": DROPBOX_FOIA_TEMPLATE_DIR,
        "batch_docs": f"{DROPBOX_TEMPLATES_ROOT}/Batch_Docs"
    }
    client = DropboxClient()
    return client.list_files(folder_map[category])


def download_template_file(category: str, filename: str, local_dir="templates"):
    """
    Download a template file by category.
    Sanitizes the filename to avoid duplicate paths/extensions.
    """
    folder_map = {
        "email": DROPBOX_EMAIL_TEMPLATE_DIR,
        "demand": DROPBOX_DEMAND_TEMPLATE_DIR,
        "mediation": DROPBOX_MEDIATION_TEMPLATE_DIR,
        "foia": DROPBOX_FOIA_TEMPLATE_DIR,
        "batch_docs": f"{DROPBOX_TEMPLATES_ROOT}/Batch_Docs"
    }
    client = DropboxClient()
    filename = normalize_path(os.path.basename(filename))

    # Enforce supported extensions (.txt or .html for emails)
    if category == "email" and not filename.endswith((".txt", ".html")):
        raise ValueError(f"Email templates must be .txt or .html (got {filename})")

    path = normalize_path(f"{folder_map[category]}/{filename}")
    return client.download_file(path, local_dir)


def list_examples(module: str):
    """
    List style example files for a module (demand, foia, mediation).
    """
    folder_map = {
        "demand": DROPBOX_DEMAND_EXAMPLES_DIR,
        "foia": DROPBOX_FOIA_EXAMPLES_DIR,
        "mediation": DROPBOX_MEDIATION_EXAMPLES_DIR,
        "style_transfer": DROPBOX_STYLE_EXAMPLES_DIR
    }
    client = DropboxClient()
    return client.list_files(folder_map[module])


def download_example_file(module: str, filename: str, local_dir="examples"):
    """
    Download example files safely, avoiding duplicate paths.
    """
    folder_map = {
        "demand": DROPBOX_DEMAND_EXAMPLES_DIR,
        "foia": DROPBOX_FOIA_EXAMPLES_DIR,
        "mediation": DROPBOX_MEDIATION_EXAMPLES_DIR,
        "style_transfer": DROPBOX_STYLE_EXAMPLES_DIR 
    }
    client = DropboxClient()
    filename = normalize_path(os.path.basename(filename))
    path = normalize_path(f"{folder_map[module]}/{filename}")
    return client.download_file(path, local_dir)


def upload_file_to_dropbox(path: str, file_bytes: bytes):
    """
    Upload a file to Dropbox, creating folders if needed.
    """
    client = DropboxClient()
    try:
        path = normalize_path(path)

        # Validate supported template extensions
        if path.endswith((".txt", ".html", ".docx")) is False:
            raise ValueError(f"Unsupported file extension for upload: {path}")

        folder = os.path.dirname(path)
        client.list_files(folder)  # ensure folder exists
        client.dbx.files_upload(file_bytes, path, mode=dropbox.files.WriteMode.overwrite)
        logger.info(f"[DROPBOX_UPLOAD] 📤 Uploaded file to {path}")
    except Exception as e:
        handle_error(e, code="DROPBOX_UPLOAD_001", raise_it=True)


def delete_file_from_dropbox(path: str):
    """
    Delete a file from Dropbox.
    """
    client = DropboxClient()
    try:
        path = normalize_path(path)
        client.dbx.files_delete_v2(path)
        logger.info(f"[DROPBOX_DELETE] 🗑️ Deleted {path}")
    except Exception as e:
        handle_error(e, code="DROPBOX_DELETE_001", raise_it=True)


def move_file_in_dropbox(old_path: str, new_path: str):
    """
    Move or rename a file in Dropbox.
    """
    client = DropboxClient()
    try:
        old_path = normalize_path(old_path)
        new_path = normalize_path(new_path)
        client.dbx.files_move_v2(old_path, new_path, autorename=False)
        logger.info(f"[DROPBOX_MOVE] 🔄 Renamed/relocated {old_path} → {new_path}")
    except Exception as e:
        handle_error(e, code="DROPBOX_MOVE_001", raise_it=True)


def download_file_from_dropbox(dropbox_path: str) -> bytes:
    """
    Download a file from Dropbox and return its bytes (used for training videos, etc).
    """
    client = DropboxClient()
    try:
        dropbox_path = normalize_path(dropbox_path)
        metadata, res = client.dbx.files_download(dropbox_path)
        return res.content
    except Exception as e:
        handle_error(e, code="DROPBOX_DOWNLOAD_BYTES_001", raise_it=True)
