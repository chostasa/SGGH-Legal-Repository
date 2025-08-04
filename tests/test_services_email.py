import pytest
import pandas as pd
import asyncio
from services import style_transfer_service, foia_service, email_service
from core.usage_tracker import check_quota

def test_run_batch_style_transfer_empty_inputs():
    with pytest.raises(Exception):
        asyncio.run(style_transfer_service.run_batch_style_transfer([], pd.DataFrame()))

def test_quota_check_failure(monkeypatch):
    monkeypatch.setattr("core.usage_tracker.get_usage_summary", lambda tenant_id, user_id: {"openai_tokens": 0})
    with pytest.raises(Exception):
        check_quota("openai_tokens")

def test_generate_foia_invalid_template():
    with pytest.raises(Exception):
        foia_service.generate_foia_letter(
            data={}, template_path="missing.docx", output_path="output.docx"
        )

def test_send_email_invalid_inputs():
    with pytest.raises(Exception):
        email_service.send_email(
            sender="", recipients=[], subject="", body=""
        )