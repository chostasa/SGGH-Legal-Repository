import os
import pytest
from email_automation.utils.template_engine import merge_template
from core.usage_tracker import check_quota, get_usage_summary

def test_merge_template_basic():
    template_dir = os.path.join("email_automation", "templates")
    os.makedirs(template_dir, exist_ok=True)

    template_path = os.path.join(template_dir, "test_template.txt")
    with open(template_path, "w", encoding="utf-8") as f:
        f.write("Subject: Hello {{ClientName}}\nBody:\nWelcome {{ClientName}}!")

    replacements = {"ClientName": "Jane Roe"}
    subject, body, cc = merge_template("test_template", replacements)

    assert "Jane Roe" in subject
    assert "Jane Roe" in body
    assert isinstance(cc, list)

def test_quota_enforcement(monkeypatch):
    monkeypatch.setattr("core.usage_tracker.get_usage_summary", lambda tenant_id, user_id: {"openai_tokens": 0})
    with pytest.raises(Exception):
        check_quota("openai_tokens")