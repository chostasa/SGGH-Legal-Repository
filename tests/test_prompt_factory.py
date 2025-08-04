from prompts.prompt_factory import build_prompt

def test_build_prompt_includes_safety_notes():
    prompt = build_prompt("Demand", "Plaintiff was injured while exiting the truck.", "Jane Roe")

    assert "Demand" in prompt
    assert "Jane Roe" in prompt
    assert "Plaintiff was injured" in prompt

    assert "Do not fabricate or assume any facts." in prompt
    assert "Use the tone and clarity of a senior litigator." in prompt
    assert "Ban any phrasing that introduces speculation" in prompt
    assert "Every sentence must use active voice." in prompt
