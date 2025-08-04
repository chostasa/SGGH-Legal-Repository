def build_style_transfer_prompt(example_paragraphs: list[str], new_input: str) -> str:
    if not new_input or not example_paragraphs:
        return ""

    examples = "\n\n---\n\n".join(example_paragraphs)
    return f"""
You are rewriting factual inputs to match the tone, structure, and style of the provided examples.

--- Example Paragraph(s) ---
{examples}

--- New Input ---
{new_input}

--- Instruction ---
Rephrase the new input to match the same style, voice, and structure as the example(s). 
Do not copy the text. Make it sound like the same author wrote it, with professional and persuasive legal tone.
"""
