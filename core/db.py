import sqlite3
import json
import os
import hashlib
from datetime import datetime
from core.error_handling import handle_error
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

DB_PATH = os.path.join("data", "legal_automation_hub.db")
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)


def get_connection():
    try:
        conn = sqlite3.connect(DB_PATH, timeout=30, isolation_level=None)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        handle_error(e, code="DB_CONN_001", raise_it=True)


def init_db():
    """Initialize DB tables for audit logs and quotas."""
    try:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id TEXT NOT NULL,
            user_id TEXT,
            action TEXT NOT NULL,
            metadata TEXT,
            hash TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS quotas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id TEXT NOT NULL,
            key TEXT NOT NULL,
            limit_value INTEGER NOT NULL,
            used_value INTEGER DEFAULT 0,
            reset_at TEXT NOT NULL
        )
        """)

        conn.commit()
        conn.close()

    except Exception as e:
        handle_error(e, code="DB_INIT_001", raise_it=True)


# ---------------------------
# Templates (Dropbox)
# ---------------------------

def get_templates(tenant_id: str, category: str = None, include_deleted: bool = False):
    """Directly list templates from Dropbox instead of SQLite."""
    from services.dropbox_client import list_templates   # Lazy import

    folder_map = {
        "email": DROPBOX_EMAIL_TEMPLATE_DIR,
        "demand": DROPBOX_DEMAND_TEMPLATE_DIR,
        "mediation_memo": DROPBOX_MEDIATION_TEMPLATE_DIR,
        "mediation": DROPBOX_MEDIATION_TEMPLATE_DIR,      
        "foia": DROPBOX_FOIA_TEMPLATE_DIR,
        "batch_docs": f"{DROPBOX_TEMPLATES_ROOT}/Batch_Docs"
    }

    if not category:
        categories = folder_map.keys()
        templates = []
        for cat in categories:
            templates += [
                {"name": f, "path": f"{folder_map[cat]}/{f}"}
                for f in list_templates(cat)
            ]
        return templates

    return [
        {"name": f, "path": f"{folder_map[category]}/{f}"}
        for f in list_templates(category)
    ]


def upload_template(category: str, filename: str, file_bytes: bytes):
    """Upload a template to Dropbox."""
    from services.dropbox_client import upload_file_to_dropbox  # Lazy import
    folder_map = {
        "email": DROPBOX_EMAIL_TEMPLATE_DIR,
        "demand": DROPBOX_DEMAND_TEMPLATE_DIR,
        "mediation_memo": DROPBOX_MEDIATION_TEMPLATE_DIR,
        "foia": DROPBOX_FOIA_TEMPLATE_DIR,
        "batch_docs": f"{DROPBOX_TEMPLATES_ROOT}/Batch_Docs"
    }
    try:
        path = f"{folder_map[category]}/{filename}"
        upload_file_to_dropbox(path, file_bytes)
        return {"name": filename, "path": path}
    except Exception as e:
        handle_error(e, code="DB_TEMPLATE_UPLOAD_001", raise_it=True)


def delete_template(category: str, filename: str):
    """Delete a template from Dropbox."""
    from services.dropbox_client import delete_file_from_dropbox  # Lazy import
    folder_map = {
        "email": DROPBOX_EMAIL_TEMPLATE_DIR,
        "demand": DROPBOX_DEMAND_TEMPLATE_DIR,
        "mediation_memo": DROPBOX_MEDIATION_TEMPLATE_DIR,
        "foia": DROPBOX_FOIA_TEMPLATE_DIR,
        "batch_docs": f"{DROPBOX_TEMPLATES_ROOT}/Batch_Docs"
    }
    try:
        path = f"{folder_map[category]}/{filename}"
        delete_file_from_dropbox(path)
    except Exception as e:
        handle_error(e, code="DB_TEMPLATE_DELETE_001", raise_it=True)


def rename_template(category: str, old_name: str, new_name: str):
    """Rename or move a template in Dropbox."""
    from services.dropbox_client import move_file_in_dropbox  # Lazy import
    folder_map = {
        "email": DROPBOX_EMAIL_TEMPLATE_DIR,
        "demand": DROPBOX_DEMAND_TEMPLATE_DIR,
        "mediation_memo": DROPBOX_MEDIATION_TEMPLATE_DIR,
        "foia": DROPBOX_FOIA_TEMPLATE_DIR,
        "batch_docs": f"{DROPBOX_TEMPLATES_ROOT}/Batch_Docs"
    }
    try:
        old_path = f"{folder_map[category]}/{old_name}"
        new_path = f"{folder_map[category]}/{new_name}"
        move_file_in_dropbox(old_path, new_path)
        return new_path
    except Exception as e:
        handle_error(e, code="DB_TEMPLATE_RENAME_001", raise_it=True)


# ---------------------------
# Examples (Dropbox)
# ---------------------------

def get_examples(tenant_id: str, category: str = None):
    """Retrieve examples directly from Dropbox."""
    from services.dropbox_client import list_examples  # Lazy import
    folder_map = {
        "demand": DROPBOX_DEMAND_EXAMPLES_DIR,
        "foia": DROPBOX_FOIA_EXAMPLES_DIR,
        "mediation": DROPBOX_MEDIATION_EXAMPLES_DIR,
        "style_transfer": DROPBOX_STYLE_EXAMPLES_DIR
    }
    try:
        if not category:
            categories = folder_map.keys()
            examples = []
            for cat in categories:
                files = list_examples(cat)
                examples += [
                    {"name": f, "path": f"{folder_map[cat]}/{f}"}
                    for f in files
                ]
            return examples

        files = list_examples(category)
        return [{"name": f, "path": f"{folder_map[category]}/{f}"} for f in files]

    except Exception as e:
        handle_error(e, code="DB_EXAMPLES_LIST_001", raise_it=True)


def upload_example(category: str, filename: str, file_bytes: bytes):
    """Upload an example to Dropbox."""
    from services.dropbox_client import upload_file_to_dropbox  # Lazy import
    folder_map = {
        "demand": DROPBOX_DEMAND_EXAMPLES_DIR,
        "foia": DROPBOX_FOIA_EXAMPLES_DIR,
        "mediation": DROPBOX_MEDIATION_EXAMPLES_DIR,
        "style_transfer": DROPBOX_STYLE_EXAMPLES_DIR 
    }
    try:
        path = f"{folder_map[category]}/{filename}"
        upload_file_to_dropbox(path, file_bytes)
        return {"name": filename, "path": path}
    except Exception as e:
        handle_error(e, code="DB_EXAMPLES_UPLOAD_001", raise_it=True)


def delete_example(category: str, filename: str):
    """Delete an example from Dropbox."""
    from services.dropbox_client import delete_file_from_dropbox  # Lazy import
    folder_map = {
        "demand": DROPBOX_DEMAND_EXAMPLES_DIR,
        "foia": DROPBOX_FOIA_EXAMPLES_DIR,
        "mediation": DROPBOX_MEDIATION_EXAMPLES_DIR,
        "style_transfer": DROPBOX_STYLE_EXAMPLES_DIR
    }
    try:
        path = f"{folder_map[category]}/{filename}"
        delete_file_from_dropbox(path)
    except Exception as e:
        handle_error(e, code="DB_EXAMPLES_DELETE_001", raise_it=True)


def rename_example(category: str, old_name: str, new_name: str):
    """Rename an example in Dropbox."""
    from services.dropbox_client import move_file_in_dropbox  # Lazy import
    folder_map = {
        "demand": DROPBOX_DEMAND_EXAMPLES_DIR,
        "foia": DROPBOX_FOIA_EXAMPLES_DIR,
        "mediation": DROPBOX_MEDIATION_EXAMPLES_DIR,
        "style_transfer": DROPBOX_STYLE_EXAMPLES_DIR 
    }
    try:
        old_path = f"{folder_map[category]}/{old_name}"
        new_path = f"{folder_map[category]}/{new_name}"
        move_file_in_dropbox(old_path, new_path)
        return new_path
    except Exception as e:
        handle_error(e, code="DB_EXAMPLES_RENAME_001", raise_it=True)


# ---------------------------
# Audit Log
# ---------------------------

def insert_audit_event(tenant_id: str, user_id: str, action: str, metadata: dict = None):
    try:
        ts = datetime.utcnow().isoformat()
        metadata_str = json.dumps(metadata or {})
        record_string = f"{tenant_id}|{user_id}|{action}|{metadata_str}|{ts}"
        record_hash = hashlib.sha256(record_string.encode()).hexdigest()

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO audit_log (tenant_id, user_id, action, metadata, hash, timestamp)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (
            tenant_id,
            user_id,
            action,
            metadata_str,
            record_hash,
            ts
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        handle_error(e, code="DB_AUDIT_INSERT_001", raise_it=True)


def get_audit_events(tenant_id: str, user_id: str = None, action: str = None, limit: int = 50):
    try:
        conn = get_connection()
        cur = conn.cursor()

        query = "SELECT * FROM audit_log WHERE tenant_id = ?"
        params = [tenant_id]

        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)
        if action:
            query += " AND action = ?"
            params.append(action)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        cur.execute(query, params)
        rows = []
        for row in cur.fetchall():
            row_dict = dict(row)
            record_string = f"{row_dict['tenant_id']}|{row_dict.get('user_id')}|{row_dict['action']}|{row_dict.get('metadata', '{}')}|{row_dict['timestamp']}"
            expected_hash = hashlib.sha256(record_string.encode()).hexdigest()
            row_dict["tampered"] = (row_dict["hash"] != expected_hash)
            rows.append(row_dict)
        conn.close()
        return rows

    except Exception as e:
        handle_error(e, code="DB_AUDIT_GET_001", raise_it=True)


# ---------------------------
# Quotas
# ---------------------------

def get_quota(tenant_id: str, key: str):
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
        SELECT * FROM quotas WHERE tenant_id = ? AND key = ?
        """, (tenant_id, key))
        row = cur.fetchone()
        conn.close()
        return dict(row) if row else None
    except Exception as e:
        handle_error(e, code="DB_QUOTA_GET_001", raise_it=True)


def set_quota(tenant_id: str, key: str, limit_value: int, reset_at: str):
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO quotas (tenant_id, key, limit_value, used_value, reset_at)
        VALUES (?, ?, ?, 0, ?)
        ON CONFLICT(tenant_id, key) DO UPDATE SET limit_value = excluded.limit_value, reset_at = excluded.reset_at
        """, (tenant_id, key, limit_value, reset_at))
        conn.commit()
        conn.close()
    except Exception as e:
        handle_error(e, code="DB_QUOTA_SET_001", raise_it=True)


def increment_quota_usage(tenant_id: str, key: str, amount: int = 1):
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
        UPDATE quotas SET used_value = used_value + ? WHERE tenant_id = ? AND key = ?
        """, (amount, tenant_id, key))
        conn.commit()
        conn.close()
    except Exception as e:
        handle_error(e, code="DB_QUOTA_INCREMENT_001", raise_it=True)

def get_training_videos():
    """List all training videos from Dropbox folder."""
    from services.dropbox_client import list_files  # lazy import
    try:
        files = list_files(DROPBOX_TRAINING_VIDEO_DIR)
        return [{"name": f, "path": f"{DROPBOX_TRAINING_VIDEO_DIR}/{f}"} for f in files]
    except Exception as e:
        handle_error(e, code="DB_TRAINING_VIDEOS_LIST_001", raise_it=True)



# Initialize DB
init_db()
