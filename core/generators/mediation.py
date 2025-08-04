import os
from services.openai_client import OpenAIClient
from core.security import redact_log, sanitize_text, sanitize_filename
from utils.docx_utils import replace_text_in_docx_all
from logger import logger

DEFAULT_SYSTEM_MSG = "You are a professional legal writer preparing a confidential mediation memo."

openai = OpenAIClient()

def generate_memo_sections(data: dict) -> dict:
    """
    Generates all sections of the mediation memo using GPT and returns a replacements dict.
    """
    try:
        intro_prompt = f"""Write a 2-sentence introduction for a mediation memo. 
Court: {data['court']}
Case Number: {data['case_number']}
Summarize the purpose and neutral tone of the mediation.
"""
        facts_prompt = f"""Summarize the facts and liability discussion based on:
{data['complaint_narrative']}

Quotes (if any): {data.get('liability_quotes', '')}
"""
        causation_prompt = f"""Explain how the incident led to medical injuries and treatment.
Medical summary:
{data['medical_summary']}
"""
        harms_prompt = f"""Summarize the additional harms and losses, including pain, mental anguish, vocational impact.

Quotes (if any): {data.get('damages_quotes', '')}
"""
        future_bills_prompt = f"""State whether the plaintiff will incur future medical expenses and treatment needs, based on:

{data['medical_summary']}
"""
        conclusion_prompt = "Write a single sentence summarizing the memo and transition into settlement discussions."

        return {
            "Introduction": openai.safe_generate(intro_prompt, system_msg=DEFAULT_SYSTEM_MSG),
            "Facts_Liability": openai.safe_generate(facts_prompt, system_msg=DEFAULT_SYSTEM_MSG),
            "Causation_Injuries_Treatment": openai.safe_generate(causation_prompt, system_msg=DEFAULT_SYSTEM_MSG),
            "Additional_Harms_Losses": openai.safe_generate(harms_prompt, system_msg=DEFAULT_SYSTEM_MSG),
            "Future_Medical_Bills": openai.safe_generate(future_bills_prompt, system_msg=DEFAULT_SYSTEM_MSG),
            "Conclusion": openai.safe_generate(conclusion_prompt, system_msg=DEFAULT_SYSTEM_MSG),
        }

    except Exception as e:
        logger.error(redact_log(f"❌ Mediation section generation failed: {e}"))
        raise RuntimeError("Failed to generate mediation memo sections.")

def generate_plaintext_memo(memo_data: dict) -> str:
    """
    Returns a simple plaintext version of the memo for display or backup.
    """
    sections = [
        f"Court: {memo_data.get('Court', '')}",
        f"Case Number: {memo_data.get('Case_Number', '')}",
        f"\nIntroduction:\n{memo_data.get('Introduction', '')}",
        f"\nFacts & Liability:\n{memo_data.get('Facts_Liability', '')}",
        f"\nCausation, Injuries & Treatment:\n{memo_data.get('Causation_Injuries_Treatment', '')}",
        f"\nAdditional Harms & Losses:\n{memo_data.get('Additional_Harms_Losses', '')}",
        f"\nFuture Medical Bills:\n{memo_data.get('Future_Medical_Bills', '')}",
        f"\nConclusion:\n{memo_data.get('Conclusion', '')}"
    ]
    return "\n\n".join(sections)

def generate_mediation_memo(data: dict, template_path: str, output_dir: str) -> (str, dict):
    """
    Main entry point. Accepts raw data and a template, returns output path and memo_data dict.
    """
    try:
        # 🔐 Sanitize fields
        cleaned = {
            k: sanitize_text(str(v)) for k, v in data.items()
        }

        # 🧠 Generate all sections
        memo_sections = generate_memo_sections(cleaned)

        # 🧱 Merge fields for template replacement
        memo_data = {
            "Court": cleaned["court"],
            "Case_Number": cleaned["case_number"],
            "Introduction": memo_sections["Introduction"],
            "Facts_Liability": memo_sections["Facts_Liability"],
            "Causation_Injuries_Treatment": memo_sections["Causation_Injuries_Treatment"],
            "Additional_Harms_Losses": memo_sections["Additional_Harms_Losses"],
            "Future_Medical_Bills": memo_sections["Future_Medical_Bills"],
            "Conclusion": memo_sections["Conclusion"],
            "Plaintiffs": cleaned.get("plaintiffs", ""),
            "Defendants": cleaned.get("defendants", ""),
            "Parties": cleaned.get("party_information_from_complaint", ""),
            "Demand": cleaned.get("settlement_summary", ""),
        }

        # 📁 Generate output
        filename = sanitize_filename(f"Mediation_{cleaned['case_number']}.docx")
        output_path = os.path.join(output_dir, filename)

        replace_text_in_docx_all(template_path, memo_data, output_path)

        logger.info(f"✅ Mediation memo generated at {output_path}")
        return output_path, memo_data

    except Exception as e:
        logger.error(redact_log(f"❌ Mediation memo generation failed: {e}"))
        raise RuntimeError("Failed to generate mediation memo.")
