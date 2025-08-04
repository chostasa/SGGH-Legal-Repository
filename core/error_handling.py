import traceback
from logger import logger

class AppError(Exception):
    """
    Standardized application error that carries a code and user-facing message.
    """
    def __init__(self, code: str, message: str, details: str = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or ""

    def __str__(self):
        return f"[{self.code}] {self.message}"


def handle_error(e: Exception, code: str = "GENERIC_000", user_message: str = None, raise_it: bool = False):
    """
    Centralized error handler.
    """
    try:
        from core.auth import get_tenant_id, get_user_id
        tenant_id = get_tenant_id() or "UNKNOWN_TENANT"
        user_id = get_user_id() or "UNKNOWN_USER"
    except ImportError:
        tenant_id = "UNKNOWN_TENANT"
        user_id = "UNKNOWN_USER"

    # Lazy import for mask_phi and redact_log
    try:
        from core.security import mask_phi, redact_log
        error_str = mask_phi(redact_log(str(e)))
        tb_str = mask_phi(redact_log(traceback.format_exc()))
    except ImportError:
        error_str = str(e)
        tb_str = traceback.format_exc()

    logger.error(
        f"[{code}] ❌ Error for tenant={tenant_id}, user={user_id}\n"
        f"→ Exception: {error_str}\n"
        f"→ Traceback: {tb_str}"
    )

    user_friendly = user_message or "An unexpected error occurred. Please contact support."
    user_friendly = f"❌ {user_friendly} (Error Code: {code})"

    if raise_it:
        raise AppError(code=code, message=user_friendly, details=error_str)

    return user_friendly


def log_warning(msg: str, code: str = "GENERIC_WARN", context: dict = None):
    try:
        from core.auth import get_tenant_id, get_user_id
        tenant_id = get_tenant_id() or "UNKNOWN_TENANT"
        user_id = get_user_id() or "UNKNOWN_USER"
    except ImportError:
        tenant_id = "UNKNOWN_TENANT"
        user_id = "UNKNOWN_USER"

    ctx = f" ctx={context}" if context else ""

    try:
        from core.security import mask_phi, redact_log
        msg = mask_phi(redact_log(msg))
    except ImportError:
        pass

    logger.warning(f"[{code}] ⚠️ Warning for tenant={tenant_id}, user={user_id}{ctx}: {msg}")


def log_info(msg: str, code: str = "GENERIC_INFO", context: dict = None):
    try:
        from core.auth import get_tenant_id, get_user_id
        tenant_id = get_tenant_id() or "UNKNOWN_TENANT"
        user_id = get_user_id() or "UNKNOWN_USER"
    except ImportError:
        tenant_id = "UNKNOWN_TENANT"
        user_id = "UNKNOWN_USER"

    ctx = f" ctx={context}" if context else ""

    try:
        from core.security import mask_phi, redact_log
        msg = mask_phi(redact_log(msg))
    except ImportError:
        pass

    logger.info(f"[{code}] ℹ️ Info for tenant={tenant_id}, user={user_id}{ctx}: {msg}")
