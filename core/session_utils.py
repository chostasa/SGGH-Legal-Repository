import streamlit as st
import uuid
import os
from core.error_handling import handle_error
from core.audit import log_audit_event


def get_session_id() -> str:
    try:
        if "session_id" not in st.session_state:
            st.session_state["session_id"] = str(uuid.uuid4())
        return st.session_state["session_id"]
    except Exception as e:
        handle_error(e, "SESSION_UTILS_001")
        raise


def get_session_temp_dir(base_dir: str = "data/tmp") -> str:
    try:
        # Lazy imports to avoid circular import
        from core.auth import get_tenant_id, get_user_id
        from utils.file_utils import sanitize_filename  

        tenant_id = get_tenant_id()
        user_id = get_user_id()
        session_id = get_session_id()

        safe_tenant = sanitize_filename(tenant_id)
        safe_user = sanitize_filename(user_id)
        safe_session = sanitize_filename(session_id)

        path = os.path.join(base_dir, safe_tenant, safe_user, safe_session)
        os.makedirs(path, exist_ok=True)

        log_audit_event("Session Temp Dir Created", {
            "tenant_id": tenant_id,
            "user_id": user_id,
            "session_id": session_id,
            "path": path
        })
        return path
    except Exception as e:
        handle_error(e, "SESSION_UTILS_002")
        raise


def enforce_quota(event_type: str, amount: int = 1) -> None:
    try:
        # Lazy import
        from core.auth import get_tenant_id, get_user_id
        from core.usage_tracker import check_quota, increment_quota_usage

        tenant_id = get_tenant_id()
        user_id = get_user_id()
        if not check_quota(tenant_id, user_id, event_type, amount):
            handle_error(
                Exception(f"Quota exceeded for {event_type}"),
                "SESSION_UTILS_003"
            )
            raise RuntimeError(f"Quota exceeded for {event_type}")
        increment_quota_usage(tenant_id, user_id, event_type, amount)
    except Exception as e:
        handle_error(e, "SESSION_UTILS_004")
        raise


def require_admin_role() -> None:
    try:
        # Lazy import
        from core.auth import get_user_role
        role = get_user_role()
        if role.lower() != "admin":
            handle_error(Exception("Admin privileges required."), "SESSION_UTILS_005")
            raise PermissionError("Admin privileges required.")
    except Exception as e:
        handle_error(e, "SESSION_UTILS_006")
        raise
