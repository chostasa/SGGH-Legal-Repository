import streamlit as st
import os
import pytest
from core import cache_utils
from config import get_env
from core.usage_tracker import check_quota, decrement_quota

def test_set_get_clear_cache(monkeypatch):
    st.session_state.clear()
    cache_utils.set_cache("testkey", "value")
    assert cache_utils.get_cache("testkey") == "value"

    cache_utils.clear_caches()
    assert cache_utils.get_cache("testkey") is None

def test_get_env_returns_value(monkeypatch):
    monkeypatch.setenv("MY_TEST_KEY", "foo")
    assert get_env("MY_TEST_KEY") == "foo"

def test_get_env_raises_if_missing(monkeypatch):
    monkeypatch.delenv("SOME_MISSING_KEY", raising=False)
    with pytest.raises(Exception):
        get_env("SOME_MISSING_KEY")

def test_quota_check_and_decrement():
    try:
        check_quota("openai_tokens", amount=1)
        decrement_quota("openai_tokens", amount=1)
        assert True
    except Exception:
        pytest.fail("Quota check or decrement failed unexpectedly")