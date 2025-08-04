# core/cache_utils.py

import streamlit as st
import time
from core.auth import get_tenant_id
from core.session_utils import get_session_id
from core.error_handling import handle_error
from core.security import redact_log, mask_phi

# Expiration window for caches (in seconds)
CACHE_EXPIRY_SECONDS = 3600  # 1 hour


def _now() -> float:
    return time.time()


def _is_expired(entry: dict) -> bool:
    """
    Check if a cache entry is expired.
    Each cache entry is stored as: {"value": ..., "ts": timestamp}
    """
    return (_now() - entry.get("ts", 0)) > CACHE_EXPIRY_SECONDS


def clear_caches():
    """
    Clear all tenant/session-level caches for demand, FOIA, memo, and party edits.
    Scopes by tenant_id + session_id to prevent accidental cross-tenant leaks.
    """
    try:
        tenant_id = get_tenant_id()
        session_id = get_session_id()

        cache_keys = [
            f"{tenant_id}_{session_id}_demand_cache",
            f"{tenant_id}_{session_id}_foia_cache",
            f"{tenant_id}_{session_id}_memo_cache",
            f"{tenant_id}_{session_id}_party_edits"
        ]

        for key in cache_keys:
            if key in st.session_state:
                del st.session_state[key]

    except Exception as e:
        handle_error(e, "CACHE_CLEAR_001")


def get_cache(key: str):
    """
    Get a value from the tenant/session-scoped cache, respecting expiration.
    """
    try:
        tenant_id = get_tenant_id()
        session_id = get_session_id()
        scoped_key = f"{tenant_id}_{session_id}_{key}"

        entry = st.session_state.get(scoped_key)
        if entry and not _is_expired(entry):
            return entry["value"]

        # Clear expired cache
        if scoped_key in st.session_state:
            del st.session_state[scoped_key]

        return None

    except Exception as e:
        handle_error(e, "CACHE_GET_001")
        return None


def set_cache(key: str, value):
    """
    Set a tenant/session-scoped cache entry with timestamp for expiry tracking.
    """
    try:
        tenant_id = get_tenant_id()
        session_id = get_session_id()
        scoped_key = f"{tenant_id}_{session_id}_{key}"

        st.session_state[scoped_key] = {"value": value, "ts": _now()}

    except Exception as e:
        handle_error(e, "CACHE_SET_001")


def get_cache_summary() -> dict:
    """
    Return a summary of all cache keys for the current tenant/session.
    Useful for Phase 5 test coverage and debugging.
    """
    try:
        tenant_id = get_tenant_id()
        session_id = get_session_id()
        scoped_prefix = f"{tenant_id}_{session_id}_"

        return {
            key: {
                "is_expired": _is_expired(value),
                "timestamp": value.get("ts"),
            }
            for key, value in st.session_state.items()
            if key.startswith(scoped_prefix)
        }
    except Exception as e:
        handle_error(e, "CACHE_SUMMARY_001")
        return {}
