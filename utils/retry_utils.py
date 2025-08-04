from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from functools import wraps
import requests
import asyncio
from openai import OpenAIError
from core.error_handling import handle_error


def openai_retry(func):
    """
    Decorator that retries async OpenAI calls up to 3 times on OpenAIError.
    """
    @wraps(func)
    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=10),
        retry=retry_if_exception_type(OpenAIError)
    )
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except OpenAIError as e:
            handle_error(e, "OPENAI_RETRY_FAIL")
            raise
    return wrapper


def http_retry(func):
    """
    Retry wrapper for HTTP requests.
    Supports both sync and async functions.
    """
    @wraps(func)
    def decorator(*args, **kwargs):
        # Detect if func is async
        if asyncio.iscoroutinefunction(func):
            @retry(
                reraise=True,
                stop=stop_after_attempt(3),
                wait=wait_exponential(multiplier=2, min=2, max=10)
            )
            async def async_inner(*a, **kw):
                try:
                    return await func(*a, **kw)
                except Exception as e:
                    # Handle requests and generic async exceptions
                    handle_error(e, "HTTP_RETRY_FAIL")
                    raise
            return async_inner(*args, **kwargs)
        else:
            @retry(
                reraise=True,
                stop=stop_after_attempt(3),
                wait=wait_exponential(multiplier=2, min=2, max=10),
                retry=retry_if_exception_type(requests.exceptions.RequestException)
            )
            def inner(*a, **kw):
                try:
                    return func(*a, **kw)
                except requests.exceptions.RequestException as e:
                    handle_error(e, "HTTP_RETRY_FAIL")
                    raise
            return inner(*args, **kwargs)

    return decorator
