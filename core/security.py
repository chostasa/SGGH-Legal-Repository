import re
import html
import functools
import time
from core.error_handling import handle_error

SAFE_FILENAME_CHARS = r"[^a-zA-Z0-9_\-\.]"
SAFE_TEXT_CHARS = r"[^a-zA-Z0-9\s,\.\-_'\"\(\)\[\]@:]" 
RATE_LIMIT_WINDOW = 60
RATE_LIMIT_REQUESTS = 100

_rate_limit_cache = {}


def sanitize_email(email: str) -> str:
    try:
        if not isinstance(email, str):
            raise ValueError("sanitize_email expects a string")
        email = email.strip()
        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            return "invalid@example.com"
        return email
    except Exception as e:
        handle_error(e, code="SECURITY_SANITIZE_EMAIL_ERR")
        return "invalid@example.com"


def sanitize_text(text: str) -> str:
    try:
        if not isinstance(text, str):
            raise ValueError("sanitize_text expects a string")
        text = html.escape(text)
        return re.sub(SAFE_TEXT_CHARS, "", text).strip()
    except Exception as e:
        handle_error(e, code="SECURITY_SANITIZE_TEXT_ERR")
        return ""


def redact_log(text: str) -> str:
    try:
        if not isinstance(text, str):
            raise ValueError("redact_log expects a string")
        return re.sub(
            r"(api|key|token|secret)[^\s\"']+", "***REDACTED***", text, flags=re.IGNORECASE
        )
    except Exception as e:
        handle_error(e, code="SECURITY_REDACT_LOG_ERR")
        return "***REDACTED***"


PHI_FIELDS = ["client", "email", "phone", "narrative", "summary"]


def mask_phi(text: str) -> str:
    try:
        if not isinstance(text, str):
            raise ValueError("mask_phi expects a string")
        for field in PHI_FIELDS:
            text = re.sub(
                rf"({field}\s*[:=].*?)(?=,|$)", "[REDACTED]", text, flags=re.IGNORECASE
            )
        return text
    except Exception as e:
        handle_error(e, code="SECURITY_MASK_PHI_ERR")
        return "[REDACTED]"


def enforce_quota(event_type: str):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Lazy import to avoid circular import
            from core.usage_tracker import check_quota, increment_quota
            if not check_quota(event_type):
                raise RuntimeError(f"Quota exceeded for {event_type}")
            result = func(*args, **kwargs)
            increment_quota(event_type)
            return result
        return wrapper
    return decorator


def rate_limit(key: str):
    now = time.time()
    requests = _rate_limit_cache.get(key, [])
    requests = [req for req in requests if now - req < RATE_LIMIT_WINDOW]
    if len(requests) >= RATE_LIMIT_REQUESTS:
        raise RuntimeError("Rate limit exceeded")
    requests.append(now)
    _rate_limit_cache[key] = requests

def sanitize_filename(filename: str) -> str:
    """
    Remove invalid characters from filenames and ensure a safe output.
    """
    cleaned = re.sub(r'[<>:"/\\|?*]', '', filename)  # remove illegal characters
    return cleaned.strip() or "untitled"
