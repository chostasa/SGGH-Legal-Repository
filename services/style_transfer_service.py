import pandas as pd
import asyncio
from services.openai_client import OpenAIClient
from core.prompts.prompt_factory import build_prompt
from core.security import sanitize_text, mask_phi, redact_log
from core.error_handling import handle_error
from core.cache_utils import get_cache, set_cache
from core.usage_tracker import check_quota, decrement_quota
from logger import logger


async def generate_style_mimic_output(example_paragraphs: list[str], new_input: str, test_mode: bool = False) -> str:
    """
    Generate a style-mimicked version of the input using example paragraphs.
    Includes input sanitization, caching, error handling, and test hooks.
    """
    try:
        if not new_input or not new_input.strip():
            raise ValueError("Input text for style transfer is empty.")

        example_text = "\n---\n".join([sanitize_text(p) for p in example_paragraphs if p.strip()])
        if not example_text:
            raise ValueError("No valid example paragraphs provided for style transfer.")

        prompt = build_prompt(
            prompt_type="style_transfer",
            section="Style Rewriting",
            summary=sanitize_text(new_input),
            client_name="",
            example=example_text
        )

        if not prompt or not isinstance(prompt, str):
            logger.error(f"[STYLE_TRANSFER] build_prompt() returned invalid prompt: {prompt}")
            raise ValueError("Prompt returned from build_prompt() is empty or invalid.")

        logger.debug(f"[STYLE_TRANSFER] Prompt being sent to OpenAI (first 500 chars):\n{prompt[:500]}")

        fingerprint = f"style::{hash(example_text)}::{hash(new_input.strip())}"
        cached = get_cache(fingerprint)
        if cached:
            logger.info(f"[STYLE_CACHE_HIT] Using cached result for {fingerprint}")
            return cached

        if test_mode:
            logger.info(f"[STYLE_TEST_MODE] Returning mocked output for {fingerprint}")
            return f"[MOCKED_STYLE] {new_input}"

        check_quota("openai_tokens", amount=1)

        # Instantiate the client before calling safe_generate
        client = OpenAIClient()
        styled_output = await client.safe_generate(prompt, model="gpt-4", temperature=0.7)

        decrement_quota("openai_tokens", amount=1)

        if not styled_output.strip():
            raise ValueError("OpenAI returned an empty style transfer output.")

        set_cache(fingerprint, styled_output)
        return styled_output

    except Exception as e:
        return handle_error(
            e,
            code="STYLE_GEN_001",
            user_message="Failed to generate styled output. Please check inputs and try again.",
            raise_it=False
        )


async def run_batch_style_transfer(example_paragraphs: list[str], df: pd.DataFrame, input_col: str, test_mode: bool = False) -> pd.DataFrame:
    """
    Run style mimic generation for all rows in the dataframe.
    Includes row-level error handling so one bad row doesn't kill the entire batch.
    Adds test hooks for Phase 5 coverage.
    """
    outputs = []
    try:
        if input_col not in df.columns:
            raise ValueError(f"Column '{input_col}' not found in input DataFrame.")

        tasks = []
        for idx, row in df.iterrows():
            original = str(row.get(input_col, "")).strip()
            if not original:
                outputs.append({
                    "Original Input": "",
                    "Styled Output": "❌ No input text provided."
                })
                continue

            async def process_row(index, text):
                try:
                    styled = await generate_style_mimic_output(example_paragraphs, text, test_mode=test_mode)
                    outputs.append({
                        "Original Input": text,
                        "Styled Output": styled
                    })
                except Exception as row_err:
                    handle_error(
                        row_err,
                        code="STYLE_BATCH_ROW_001",
                        user_message=f"Failed to process row {index}.",
                        raise_it=False
                    )
                    outputs.append({
                        "Original Input": text,
                        "Styled Output": f"❌ Error processing row {index}"
                    })

            tasks.append(process_row(idx, original))

        if tasks:
            await asyncio.gather(*tasks)

        return pd.DataFrame(outputs)

    except Exception as e:
        handle_error(
            e,
            code="STYLE_BATCH_001",
            user_message="Failed to run style transfer batch process.",
            raise_it=True
        )
