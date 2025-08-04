from services.openai_client import OpenAIClient
from prompts.prompt_factory import build_prompt
from core.security import redact_log
from logger import logger

openai = OpenAIClient()

def generate_foia_sections(case_synopsis: str, case_type: str, facility: str, defendant_role: str, potential_requests: str, explicit_instructions: str) -> dict:
    """
    Generates bullet-point FOIA request section and formal synopsis from GPT.
    """
    try:
        # 🧠 Build FOIA request prompt
        foia_prompt = build_prompt(
            section="FOIA Request",
            summary=case_synopsis,
            client_name="",  # no name needed in GPT output
            extra_instructions=f"""
Case type: {case_type}
Facility involved: {facility}
Defendant role: {defendant_role}
Explicit instructions: {explicit_instructions or "None provided"}
Common requests: {potential_requests or "None listed"}
""".strip()
        )

        # 💬 Ask GPT for bullet points and a formal 2-sentence summary
        bullet_points = openai.safe_generate(foia_prompt).replace("* ", "").strip()
        synopsis_prompt = f"Summarize the following incident in 2 professional, objective sentences without using any names:\n\n{case_synopsis}"
        formal_synopsis = openai.safe_generate(synopsis_prompt)

        return {
            "foia_request_bullet_points": bullet_points,
            "synopsis": formal_synopsis
        }

    except Exception as e:
        logger.error(redact_log(f"❌ FOIA generation failed: {e}"))
        raise RuntimeError("GPT generation for FOIA letter failed.")
