from jinja2 import Environment, BaseLoader, select_autoescape
import json
import os
from datetime import datetime
from core.auth import get_tenant_id
from core.security import sanitize_filename
from core.audit import log_audit_event
from logger import logger

from core.prompts.demand_guidelines import (
    NO_HALLUCINATION_NOTE as DEMAND_NO_HALLUCINATION,
    LEGAL_FLUENCY_NOTE as DEMAND_LEGAL_FLUENCY,
    STRUCTURE_GUIDE_NOTE as DEMAND_STRUCTURE,
    LEGAL_TRANSITION_NOTE as DEMAND_TRANSITION,
    NO_PASSIVE_LANGUAGE_NOTE as DEMAND_NO_PASSIVE,
    BAN_PHRASES_NOTE as DEMAND_BAN_PHRASES,
)
from core.prompts.demand_example import EXAMPLE_DEMAND, SETTLEMENT_EXAMPLE

from core.prompts.foia_guidelines import (
    FULL_SAFETY_PROMPT as FOIA_SAFETY_PROMPT,
    FOIA_BULLET_POINTS_PROMPT_TEMPLATE,
    FOIA_SYNOPSIS_PROMPT,
)
from core.prompts.foia_example import FOIA_BULLET_POINTS_EXAMPLES

from core.prompts.memo_guidelines import FULL_SAFETY_PROMPT as MEMO_SAFETY_PROMPT
from core.prompts.memo_examples import (
    INTRO_EXAMPLE,
    PLAINTIFF_STATEMENT_EXAMPLE,
    DEFENDANT_STATEMENT_EXAMPLE,
    DEMAND_EXAMPLE as MEMO_DEMAND_EXAMPLE,
    FACTS_LIABILITY_EXAMPLE,
    CAUSATION_EXAMPLE,
    HARMS_EXAMPLE,
    FUTURE_BILLS_EXAMPLE,
    CONCLUSION_EXAMPLE,
)

from core.prompts.style_transfer import build_style_transfer_prompt

jinja_env = Environment(
    loader=BaseLoader(),
    autoescape=select_autoescape(enabled_extensions=("txt", "j2"))
)

BASE_PROMPT_TEMPLATE = """
{{ safety_notes }}

You are drafting the **{{ section }}** section for {{ client_name }}.

Facts and content to use:
{{ summary }}

{% if example %}
Use the following as a tone/style example:
{{ example }}
{% endif %}

{{ extra_instructions }}
""".strip()

PROMPT_REGISTRY_FILE = "prompt_registry.json"

def _load_prompt_registry() -> dict:
    if os.path.exists(PROMPT_REGISTRY_FILE):
        with open(PROMPT_REGISTRY_FILE, "r") as f:
            return json.load(f)
    return {}

def _save_prompt_registry(registry: dict):
    with open(PROMPT_REGISTRY_FILE, "w") as f:
        json.dump(registry, f, indent=2)

def register_prompt(prompt_type: str, prompt: str):
    registry = _load_prompt_registry()
    tenant_id = get_tenant_id()
    if tenant_id not in registry:
        registry[tenant_id] = {}
    if prompt_type not in registry[tenant_id]:
        registry[tenant_id][prompt_type] = []
    registry[tenant_id][prompt_type].append({
        "timestamp": datetime.utcnow().isoformat(),
        "prompt": prompt
    })
    _save_prompt_registry(registry)
    try:
        log_audit_event("Prompt Registered", {
            "tenant_id": tenant_id,
            "prompt_type": prompt_type,
            "timestamp": datetime.utcnow().isoformat()
        })
    except Exception as e:
        logger.warning(f"Failed to audit prompt registration: {e}")

def build_prompt(
    prompt_type: str,
    section: str,
    summary: str,
    client_name: str = "Jane Doe",
    extra_instructions: str = "",
    example: str = ""
) -> str:
    if prompt_type == "demand":
        safety_notes = "\n\n".join([
            DEMAND_NO_HALLUCINATION,
            DEMAND_LEGAL_FLUENCY,
            DEMAND_STRUCTURE,
            DEMAND_TRANSITION,
            DEMAND_NO_PASSIVE,
            DEMAND_BAN_PHRASES
        ])
        template = jinja_env.from_string(BASE_PROMPT_TEMPLATE)
        prompt = template.render(
            safety_notes=safety_notes,
            section=section,
            summary=summary.strip(),
            client_name=client_name.strip(),
            example=example.strip() or EXAMPLE_DEMAND,
            extra_instructions=extra_instructions.strip(),
        )
        register_prompt(prompt_type, prompt)
        return prompt

    elif prompt_type == "memo":
        template = jinja_env.from_string(BASE_PROMPT_TEMPLATE)
        prompt = template.render(
            safety_notes=MEMO_SAFETY_PROMPT,
            section=section,
            summary=summary.strip(),
            client_name=client_name.strip(),
            example=example.strip(),
            extra_instructions=extra_instructions.strip(),
        )
        register_prompt(prompt_type, prompt)
        return prompt

    elif prompt_type == "foia":
        if section.lower() == "synopsis":
            # Use a short summary prompt
            prompt = FOIA_SYNOPSIS_PROMPT.format(
                case_synopsis=summary
            )
        elif section.lower() == "foia letter":
            # Use a general letter generation prompt
            prompt = f"""
    {FOIA_SAFETY_PROMPT}

    You are drafting the FOIA request letter for {client_name}.
    Facts and case summary:
    {summary}

    Explicit instructions (if any): {extra_instructions}

    Use a professional legal tone.
    """
        else:
            # Default: bullet points
            prompt = FOIA_BULLET_POINTS_PROMPT_TEMPLATE.format(
                case_synopsis=summary,
                case_type=section,
                facility="facility/system info",
                defendant_role="defendant role",
                explicit_instructions=extra_instructions,
                potential_requests=FOIA_BULLET_POINTS_EXAMPLES
            )

        register_prompt(prompt_type, prompt)
        return prompt

    elif prompt_type == "style_transfer":
        examples = example.split("---") if example else []
        prompt = build_style_transfer_prompt(examples, summary)
    
        if not prompt or not prompt.strip():
            logger.error("[STYLE_TRANSFER] build_prompt() returned invalid prompt: None or empty")
            return ""  # explicitly return an empty string for the service to handle
    
        register_prompt(prompt_type, prompt)
        return prompt

