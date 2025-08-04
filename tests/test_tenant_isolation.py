import os
from core import session_utils
from core.usage_tracker import check_quota

def test_tenant_scoped_directories(tmp_path, monkeypatch):
    monkeypatch.setattr("core.auth.get_tenant_id", lambda: "tenantA")
    dir_a = session_utils.get_session_temp_dir(str(tmp_path))
    assert "tenantA" in dir_a
    check_quota("openai_tokens", amount=0)

    monkeypatch.setattr("core.auth.get_tenant_id", lambda: "tenantB")
    dir_b = session_utils.get_session_temp_dir(str(tmp_path))
    assert "tenantB" in dir_b
    assert dir_a != dir_b
    check_quota("openai_tokens", amount=0)
