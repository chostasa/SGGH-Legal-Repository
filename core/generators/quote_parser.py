import re
from typing import List, Dict
from services.openai_client import OpenAIClient
from utils.token_utils import trim_to_token_limit
from core.security import redact_log, mask_phi
from core.error_handling import handle_error
from logger import logger

openai = OpenAIClient()

QUOTE_PROMPT_SYSTEM_MSG = "You are a legal assistant extracting deposition quotes for a mediation memo."

# -----------------------------
# 1. Normalize Deposition Lines
# -----------------------------
def normalize_deposition_lines(text: str) -> List[str]:
    """
    Split deposition text into clean, normalized lines.
    """
    try:
        if not text or not isinstance(text, str):
            raise ValueError("Input text is empty or not a string.")

        lines = text.splitlines()
        return [line.strip() for line in lines if line.strip()]

    except Exception as e:
        handle_error(
            e,
            code="QUOTE_PARSER_001",
            user_message="Failed to process deposition lines.",
            raise_it=True,
        )


# -----------------------------
# 2. Merge Q&A Blocks
# -----------------------------
def merge_multiline_qas(lines: List[str]) -> str:
    """
    Merge multiline deposition Q&A blocks into a structured string.
    """
    try:
        if not lines or not isinstance(lines, list):
            raise ValueError("Input lines are empty or invalid.")

        merged = []
        current_q = ""
        current_a = ""

        for line in lines:
            # Remove line numbers
            if re.match(r"^\d{1,5}[:\s\-]", line):
                line = re.sub(r"^\d{1,5}[:\s\-]+", "", line).strip()

            if line.startswith("Q:"):
                if current_q or current_a:
                    merged.append(f"Q: {current_q.strip()}\nA: {current_a.strip()}")
                    current_q, current_a = "", ""
                current_q += line[2:].strip()
            elif line.startswith("A:"):
                current_a += line[2:].strip() + " "
            else:
                if current_a:
                    current_a += line + " "
                elif current_q:
                    current_q += " " + line

        if current_q or current_a:
            merged.append(f"Q: {current_q.strip()}\nA: {current_a.strip()}")

        return "\n\n".join(merged)

    except Exception as e:
        handle_error(
            e,
            code="QUOTE_PARSER_002",
            user_message="Failed to merge deposition Q&A blocks.",
            raise_it=True,
        )


# -----------------------------
# 3. GPT-Powered Quote Extraction
# -----------------------------
def generate_quotes_in_chunks(chunks: List[str], categories: List[str]) -> Dict[str, str]:
    """
    Extract categorized quotes from deposition chunks using GPT.
    Each quote is tagged by category and returned in a structured dict.
    """
    try:
        if not chunks or not categories:
            raise ValueError("Chunks or categories are empty.")

        # Initialize category keys
        results = {cat.lower().replace(" ", "_") + "_quotes": [] for cat in categories}

        for chunk in chunks:
            try:
                category_list = ", ".join(categories)
                prompt = f"""
You are reviewing a deposition transcript.

The following text contains Q&A excerpts:

{trim_to_token_limit(chunk)}

Please extract up to 3 quotes per category from this list: {category_list}

Each quote must match this format exactly:

Category: [Category Name]  
"Q: ... A: ..."

Only include relevant quotes. Skip any category if no strong quote exists.
"""
                response = openai.safe_generate(
                    prompt=prompt,
                    system_msg=QUOTE_PROMPT_SYSTEM_MSG,
                )

                for cat in categories:
                    key = cat.lower().replace(" ", "_") + "_quotes"
                    matches = re.findall(
                        rf'Category: {re.escape(cat)}\s+"(.*?)"',
                        response,
                        re.DOTALL,
                    )
                    results[key].extend([m.strip() for m in matches])

            except Exception as gpt_err:
                handle_error(
                    gpt_err,
                    code="QUOTE_PARSER_003",
                    user_message="Failed to extract deposition quotes from GPT.",
                )

        # Deduplicate and clean results
        return {k: "\n\n".join(sorted(set(v))) for k, v in results.items()}

    except Exception as e:
        handle_error(
            e,
            code="QUOTE_PARSER_004",
            user_message="Quote extraction failed.",
            raise_it=True,
        )
