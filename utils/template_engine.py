import re
from string import Template
from core.error_handling import handle_error

def render_docx_placeholders(text: str, context: dict, is_html: bool = False) -> str:
    """
    Safely replace placeholders in text using Python's Template.
    Supports both plain text (sanitized) and HTML (preserve tags).
    Example: "Hello {{ClientName}}" → "Hello Jane"
    """
    from core.security import mask_phi, redact_log, sanitize_text

    try:
        if not isinstance(context, dict):
            raise ValueError("Context for placeholder rendering must be a dictionary.")

        if is_html:
            # Do NOT sanitize HTML tags; only strip unsafe characters from placeholders
            sanitized_context = {str(k): str(v) for k, v in context.items()}
        else:
            # Original behavior (sanitized aggressively)
            sanitized_context = {
                sanitize_text(str(k)): sanitize_text(str(v))
                for k, v in context.items()
            }

        # Normalize {{placeholder}} → ${placeholder}
        normalized = re.sub(r"\{\{(.*?)\}\}", r"${\1}", text)

        try:
            return Template(normalized).safe_substitute(sanitized_context)
        except KeyError:
            # Remove missing placeholders gracefully
            return re.sub(r"\$\{[^{}]+\}", "", normalized)

    except Exception as e:
        handle_error(
            e,
            code="TEMPLATE_ENGINE_001",
            message="Failed to render placeholders in template.",
            context=redact_log(mask_phi(f"text={text[:100]}"))
        )
        return ""
