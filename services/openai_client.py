import asyncio
import time
from openai import AsyncOpenAI, OpenAIError
from config_loader import AppConfig, get_config
from utils.retry_utils import openai_retry
from utils.token_utils import trim_to_token_limit
from core.security import redact_log, mask_phi
from core.usage_tracker import log_usage, check_quota
from core.auth import get_user_id, get_tenant_id, get_user_role
from core.error_handling import handle_error, AppError
from logger import logger

DEFAULT_MODEL = "gpt-4"
DEFAULT_SYSTEM_MSG = "You are a professional legal writer. Stay concise and legally fluent."


class OpenAIClient:
    def __init__(self, config: AppConfig = None):
        self.config = config or get_config()
        self.client = AsyncOpenAI(api_key=self.config.OPENAI_API_KEY)
        self.model = getattr(self.config, "OPENAI_MODEL", DEFAULT_MODEL)

    async def _generate(
        self,
        prompt: str,
        model: str,
        system_msg: str,
        temperature: float,
        test_mode: bool
    ) -> str:
        """
        Internal non-decorated async generator method.
        """
        tenant_id = get_tenant_id()
        user_id = get_user_id()
        user_role = get_user_role()

        # 🚨 Defensive check for None or empty prompt
        if not prompt or not isinstance(prompt, str):
            logger.error(f"[OPENAI_GEN] Received invalid prompt: {prompt}")
            raise AppError(
                code="OPENAI_GEN_004",
                message="Prompt for text generation is empty or invalid.",
                details=f"Tenant={tenant_id}"
            )

        trimmed = trim_to_token_limit(prompt)
        used_model = model or self.model or DEFAULT_MODEL

        if used_model not in ["gpt-3.5-turbo", "gpt-4", "gpt-4o", "gpt-4-turbo"]:
            logger.warning(
                redact_log(
                    mask_phi(f"⚠️ Invalid model requested: {used_model}. Falling back to {DEFAULT_MODEL}")
                )
            )
            used_model = DEFAULT_MODEL

        if test_mode:
            logger.info("[OPENAI_GEN_TEST] Returning deterministic test output.")
            return f"[TEST MODE] Prompt length={len(trimmed)} Model={used_model}"

        if not check_quota("openai_tokens"):
            raise AppError(
                code="OPENAI_GEN_000",
                message="Quota exceeded for tenant.",
                details=f"Tenant={tenant_id}"
            )

        start_time = time.time()
        response = await self.client.chat.completions.create(
            model=used_model,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": trimmed},
            ],
            temperature=temperature,
        )
        latency = time.time() - start_time
        logger.info(redact_log(mask_phi(f"[METRIC] OpenAI latency: {latency:.2f}s for tenant={tenant_id}")))

        choices = getattr(response, "choices", [])
        if not choices or not hasattr(choices[0], "message"):
            raise AppError(
                code="OPENAI_GEN_001",
                message="OpenAI returned no completions.",
                details=f"Model={used_model}, Prompt length={len(trimmed)}",
            )

        content = choices[0].message.content.strip()
        usage = getattr(response, "usage", None)

        if usage:
            log_usage(
                event_type="openai_tokens",
                amount=usage.total_tokens,
                metadata={
                    "model": used_model,
                    "prompt_tokens": usage.prompt_tokens,
                    "completion_tokens": usage.completion_tokens,
                    "role": user_role,
                    "latency": latency,
                },
            )

        return content


    @openai_retry
    async def safe_generate(
        self,
        prompt: str,
        model: str = None,
        system_msg: str = DEFAULT_SYSTEM_MSG,
        temperature: float = 0.4,
        test_mode: bool = False,
    ) -> str:
        """
        Wrapper for _generate with retry decorator applied safely.
        """
        try:
            return await self._generate(prompt, model, system_msg, temperature, test_mode)
        except OpenAIError as e:
            handle_error(
                e,
                code="OPENAI_GEN_002",
                user_message="OpenAI API error occurred. Please try again later.",
                raise_it=True,
            )
        except AppError:
            raise
        except Exception as e:
            handle_error(
                e,
                code="OPENAI_GEN_003",
                user_message="Unexpected error during text generation.",
                raise_it=True,
            )


# Singleton instance
openai_client_instance = OpenAIClient()


async def safe_generate_async(
    prompt: str,
    model: str = None,
    system_msg: str = DEFAULT_SYSTEM_MSG,
    temperature: float = 0.4,
    test_mode: bool = False,
) -> str:
    """
    Async wrapper for external calls (preferred for all internal code).
    """
    return await openai_client_instance.safe_generate(
        prompt=prompt,
        model=model,
        system_msg=system_msg,
        temperature=temperature,
        test_mode=test_mode,
    )


def safe_generate(
    prompt: str,
    model: str = None,
    system_msg: str = DEFAULT_SYSTEM_MSG,
    temperature: float = 0.4,
    test_mode: bool = False,
) -> str:
    """
    Legacy sync wrapper for backward compatibility.
    Uses run_until_complete but does not block async event loops.
    """
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    if loop.is_running():
        # If already inside an event loop, schedule the async call
        return asyncio.ensure_future(
            safe_generate_async(prompt, model, system_msg, temperature, test_mode)
        )
    else:
        return loop.run_until_complete(
            safe_generate_async(prompt, model, system_msg, temperature, test_mode)
        )
