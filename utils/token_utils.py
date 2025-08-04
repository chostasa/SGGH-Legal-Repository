def trim_to_token_limit(text: str, max_tokens: int = 4000) -> str:
    """
    Naive token limiter for GPT-3.5/4. Assumes 4 characters ≈ 1 token.
    Truncates the input string if estimated tokens exceed the limit.
    """
    max_chars = max_tokens * 4
    return text[:max_chars]
