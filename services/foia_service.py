import os
from services.openai_client import safe_generate
from utils.docx_utils import replace_text_in_docx_all
from core.security import sanitize_text, redact_log, mask_phi
from core.error_handling import handle_error
from core.usage_tracker import check_quota_and_decrement
from core.auth import get_tenant_id
from logger import logger
from core.prompts.prompt_factory import build_prompt
from services.dropbox_client import download_template_file  # Dropbox template download
from utils.thread_utils import run_in_thread  # Threaded blocking task execution


async def generate_synopsis(casesynopsis: str) -> str:
    """
    Generate a summary synopsis from the provided case synopsis text.
    """
    try:
        if not casesynopsis or not isinstance(casesynopsis, str):
            raise ValueError("Case synopsis is missing or invalid.")

        prompt = build_prompt("foia", "Synopsis", casesynopsis)
        logger.debug(f"[FOIA_SYNOPSIS_PROMPT] Prompt being sent:\n{prompt}")
        summary = await safe_generate(prompt=prompt)
        logger.debug(f"[FOIA_SYNOPSIS_RESULT] Raw result:\n{summary}")

        if not summary or "legal summarization assistant" in summary.lower():
            return "[Synopsis failed to generate. Check input.]"
        return summary.strip()

    except Exception as e:
        handle_error(
            e,
            code="FOIA_SYNOPSIS_001",
            user_message="Failed to generate case synopsis.",
            raise_it=True,
        )


async def generate_foia_request(
    data: dict, template_path: str, output_path: str, example_text: str = ""
) -> tuple:
    """
    Generates a FOIA request letter (.docx) and returns the file path, body text, and bullet list.
    Downloads template from Dropbox if it's not already present locally.
    """
    try:
        if not isinstance(data, dict):
            raise ValueError("FOIA input data is invalid.")
        if not template_path:
            raise ValueError("Template path is missing.")
        if not output_path:
            raise ValueError("Output path is required for FOIA letter generation.")

        # Ensure template is downloaded if missing locally
        if not os.path.exists(template_path):
            template_path = download_template_file("foia", template_path, "foia_templates_cache")

        if not template_path or not os.path.exists(template_path):
            handle_error(
                FileNotFoundError(f"Template not found: {template_path}"),
                code="FOIA_GEN_TEMPLATE_001",
                user_message="FOIA template is missing or inaccessible.",
                raise_it=True,
            )

        tenant_id = get_tenant_id()
        check_quota_and_decrement(tenant_id, "foia_requests")

        # Sanitize inputs
        for k, v in data.items():
            if isinstance(v, str):
                data[k] = sanitize_text(v)

        raw_synopsis = data.get("synopsis", "").strip()
        data["synopsis_summary"] = await generate_synopsis(raw_synopsis) if raw_synopsis else "[No synopsis provided]"

        # Build bullet request list
        bullet_prompt = build_prompt(
            "foia",
            data.get("case_type", "FOIA Request"),
            data.get("synopsis_summary", ""),
            client_name=data.get("client_id", ""),
            extra_instructions=data.get("explicit_instructions", ""),
        )
        logger.debug(f"[FOIA_BULLET_PROMPT] Prompt being sent:\n{bullet_prompt}")
        request_list = await safe_generate(prompt=bullet_prompt)

        if not request_list:
            raise ValueError("Failed to generate FOIA request list.")

        bullet_lines = request_list.splitlines() if isinstance(request_list, str) else []
        if not bullet_lines:
            logger.warning(redact_log("[FOIA_GEN_005] FOIA request list is empty after generation."))

        # Build FOIA body letter
        letter_prompt = build_prompt(
            "foia",
            "FOIA Letter",
            data.get("synopsis_summary", ""),
            client_name=data.get("client_id", ""),
            extra_instructions=data.get("explicit_instructions", ""),
            example=example_text,
        )
        logger.debug(f"[FOIA_LETTER_PROMPT] Prompt being sent:\n{letter_prompt}")
        foia_body = await safe_generate(prompt=letter_prompt)
        foia_body = sanitize_text(foia_body)
        if not foia_body:
            raise ValueError("Failed to generate FOIA letter body text.")

        # Build replacements dict
        replacements = {
            "date": data.get("formatted_date", ""),
            "clientid": data.get("client_id", ""),
            "defendantname": data.get("recipient_name", ""),
            "defendantline1": data.get("recipient_address_1", ""),
            "defendantline2": data.get("recipient_address_2", ""),
            "location": data.get("location", ""),
            "doi": data.get("doi", ""),
            "synopsis": data.get("synopsis_summary", ""),
            "statecitation": data.get("state_citation", ""),
            "stateresponsetime": data.get("state_response_time", ""),
            "bulletpoints": "\n\n".join(f"• {line.lstrip('*• ').strip()}" for line in bullet_lines)
            if bullet_lines
            else "[No bullet points generated]",
        }

        logger.info("[FOIA_GEN_000] Rendering FOIA template with replacements:")
        for k, v in replacements.items():
            logger.debug(f"  - {k}: {v[:100]!r}{'...' if len(v) > 100 else ''}")

        try:
            # Run template replacement in a thread (blocking I/O)
            run_in_thread(replace_text_in_docx_all, template_path, replacements, output_path)
        except Exception as docx_error:
            logger.warning(redact_log(mask_phi(f"[FOIA_GEN_002] ⚠️ DOCX rendering error: {docx_error}")))
            with open(output_path.replace(".docx", "_FAILED.txt"), "w", encoding="utf-8") as f:
                f.write("⚠️ Failed to render DOCX — inspect the following:\n\n")
                for k, v in replacements.items():
                    f.write(f"<<{k}>>: {v}\n\n")
            handle_error(
                docx_error,
                code="FOIA_GEN_003",
                user_message="Template render failed. A fallback debug file has been created.",
                raise_it=True,
            )

        if not os.path.exists(output_path):
            handle_error(
                FileNotFoundError(f"Output file not found at {output_path}"),
                code="FOIA_GEN_004",
                user_message="FOIA letter generation failed (no file was created).",
                raise_it=True,
            )

        return output_path, foia_body, bullet_lines

    except Exception as e:
        handle_error(
            e,
            code="FOIA_GEN_001",
            user_message="FOIA request generation failed. Please try again or contact support.",
            raise_it=True,
        )
