import os

def get_user_id() -> str:
    """
    Return the current user's ID.
    In production, extract from Azure SSO headers.
    In local/dev mode, return 'internal-user'.
    """
    if os.getenv("ENV", "").lower() == "production":
        return os.environ.get("X-MS-CLIENT-PRINCIPAL-NAME", "unknown-user")
    return "internal-user"


def get_tenant_id() -> str:
    """
    Return the current tenant's ID.
    In production, derive from email domain.
    In local/dev mode, return 'internal-tenant'.
    """
    if os.getenv("ENV", "").lower() == "production":
        email = os.environ.get("X-MS-CLIENT-PRINCIPAL-NAME", "")
        domain = email.split("@")[-1] if "@" in email else "unknown-tenant"
        return domain.replace(".", "-")
    return "internal-tenant"


def get_user_role() -> str:
    """
    Determine the user's role.
    Default to 'admin' for internal use.
    """
    # Optionally extend this later based on group membership
    return "admin"


def user_has_permission(permission: str) -> bool:
    """
    All users have permission by default.
    """
    return True


def enforce_permission(permission: str):
    """
    Decorator that allows all actions by default.
    """
    def decorator(func):
        return func
    return decorator


def enforce_tenant_scope(path: str) -> str:
    """
    Prefix file paths with tenant for isolation (if needed).
    Currently passes unchanged for internal use.
    """
    return path


def enforce_quota(event_type: str, amount: int = 1):
    """
    Decorator that disables quota enforcement by default.
    """
    def decorator(func):
        return func
    return decorator


def map_domain_to_tenant(domain: str) -> str:
    """
    Map a domain to a tenant-safe ID.
    """
    return domain.replace(".", "-") if domain else "internal-tenant"


def get_tenant_branding(tenant_id: str = "internal-tenant") -> dict:
    """
    Return firm-specific branding.
    Can be extended per tenant if needed.
    """
    return {
        "firm_name": "Legal Automation Hub (Internal)",
        "logo": "",
        "primary_color": "#0A1D3B"
    }
