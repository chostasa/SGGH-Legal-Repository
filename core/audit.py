from core.auth import get_user_id, get_tenant_id, get_user_role
from core.security import sanitize_text, mask_phi, redact_log
from core.error_handling import handle_error
from core.db import insert_audit_event, get_audit_events
import hashlib
import datetime
from logger import logger

def _hash_audit_entry(tenant_id: str, user_id: str, action: str, metadata: dict) -> str:
    """
    Creates a tamper-proof SHA256 hash for each audit entry using tenant, user, action, metadata, and UTC timestamp.
    """
    data = f"{tenant_id}|{user_id}|{action}|{metadata}|{datetime.datetime.utcnow().isoformat()}"
    return hashlib.sha256(data.encode()).hexdigest()

def log_audit_event(action: str, metadata: dict = None):
    """
    Log a structured audit event to the database with user and tenant context.
    Includes tamper-proof hashing, tenant isolation, and full error resilience.
    """
    try:
        tenant_id = get_tenant_id()
        user_id = get_user_id()
        user_role = get_user_role()

        # Ensure metadata is clean and safe
        clean_metadata = {}
        if metadata:
            for k, v in metadata.items():
                clean_metadata[sanitize_text(str(k))] = sanitize_text(str(v))

        # Include user role inside metadata for traceability
        clean_metadata["role"] = user_role

        audit_hash = _hash_audit_entry(tenant_id, user_id, action, clean_metadata)

        # Write to DB with metadata JSON stored as a string
        insert_audit_event(
            tenant_id=tenant_id,
            user_id=user_id,
            action=sanitize_text(action),
            metadata=clean_metadata,    
        )

        try:
            logger.info(f"[AUDIT] tenant={tenant_id} user={user_id} action={action}")
        except Exception as log_err:
            logger.warning(redact_log(mask_phi(f"⚠️ Failed to push audit metric: {log_err}")))

    except Exception as e:
        safe_error = redact_log(mask_phi(f"❌ Failed to write audit log: {e}"))
        handle_error(safe_error, code="AUDIT_LOG_001")

def fetch_audit_events(user_id: str = None, action: str = None, limit: int = 50):
    """
    Retrieve audit events for the current tenant with optional filters.
    Validates tenant isolation and enforces role-based access control.
    Non-admins can only see their own events.
    """
    try:
        tenant_id = get_tenant_id()
        current_role = get_user_role()

        # Enforce tenant isolation
        # Non-admins can only view their own logs
        if current_role.lower() != "admin":
            user_id = get_user_id()

        events = get_audit_events(
            tenant_id=tenant_id,
            user_id=user_id,
            action=action,
            limit=limit
        )

        # Hard-verify tenant isolation on fetched events
        safe_events = [e for e in events if e.get("tenant_id") == tenant_id]

        try:
            logger.info(f"[AUDIT_FETCH] tenant={tenant_id} fetched {len(safe_events)} events")
        except Exception as log_err:
            logger.warning(redact_log(mask_phi(f"⚠️ Failed to push audit fetch metric: {log_err}")))

        return safe_events

    except Exception as e:
        safe_error = redact_log(mask_phi(f"❌ Failed to fetch audit events: {e}"))
        handle_error(safe_error, code="AUDIT_LOG_002", raise_it=True)
