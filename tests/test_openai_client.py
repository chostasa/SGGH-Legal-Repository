from services.openai_client import safe_generate
from unittest.mock import patch, MagicMock
from core.usage_tracker import check_quota, decrement_quota

@patch("services.openai_client.client.chat.completions.create")
def test_safe_generate_returns_string(mock_create):
    mock_message = MagicMock()
    mock_message.content = "Negligence is the failure to exercise reasonable care."

    mock_choice = MagicMock()
    mock_choice.message = mock_message

    mock_create.return_value = MagicMock(choices=[mock_choice])

    check_quota("openai_tokens", amount=1)
    output = safe_generate("What is negligence?")
    decrement_quota("openai_tokens", amount=1)
    assert isinstance(output, str)
    assert "Negligence" in output