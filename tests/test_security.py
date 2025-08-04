import pytest
import pandas as pd
import asyncio
from services import style_transfer_service, foia_service, email_service, demand_service, memo_service
from core.usage_tracker import check_quota
from core.security import sanitize_filename, sanitize_email, sanitize_text, redact_log, mask_phi

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

def test_generate_demand_invalid_inputs():
    with pytest.raises(Exception):
        demand_service.generate_demand_letter(
            client_name="", defendant="", location="", incident_date="", summary="", damages="",
            template_path="missing.docx", output_path="output.docx", example_text=""
        )

def test_generate_memo_fields_missing_template():
    with pytest.raises(Exception):
        memo_service.generate_memo_from_fields(
            data={}, template_path="missing.docx", output_dir="."
        )

def test_sanitize_filename_valid():
    assert sanitize_filename("valid-file.txt") == "valid-file.txt"

def test_sanitize_filename_invalid_type():
    assert sanitize_filename(1234) == "invalid_filename"

def test_sanitize_email_valid():
    assert sanitize_email("test@example.com") == "test@example.com"

def test_sanitize_email_invalid():
    assert sanitize_email("invalid") == "invalid@example.com"

def test_sanitize_text_html_escape():
    assert sanitize_text("<b>bold</b>") == "bbolddbb"

def test_redact_log_sensitive():
    text = "apiKey=12345"
    result = redact_log(text)
    assert "***REDACTED***" in result

def test_mask_phi_fields():
    sample = "client: John Doe, email: test@example.com"
    masked = mask_phi(sample)
    assert "[REDACTED]" in masked
