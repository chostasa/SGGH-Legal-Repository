NO_HALLUCINATION_NOTE = """
Do not fabricate or assume any facts. Use only what is provided. Avoid headings, greetings, and signoffs — the template handles those. Keep all naming, pronouns, and chronology consistent. Do not repeat injury or treatment details across sections.
"""

LEGAL_FLUENCY_NOTE = """
Use the tone and clarity of a senior litigator. Frame facts persuasively using legal reasoning: duty, breach, causation, and harm. Eliminate redundancy, vague phrases, and casual storytelling. Maintain formal, polished, and precise language. Quantify damages where possible. Refer to witnesses, police, or records only once. Avoid restating injuries.
"""

BAN_PHRASES_NOTE = """
Ban any phrasing that introduces speculation or weakens factual strength. Do not use: “may,” “might,” “potential,” “appears to,” “possibly,” or “believes that.” Replace with: “The evidence shows...”, “The footage depicts...”, “Plaintiff reports...”
"""

NO_PASSIVE_LANGUAGE_NOTE = """
Every sentence must use active voice. Do not say “was struck” or “has been advised.” Instead: “The snowplow struck Jane.” “Jane reports...”
"""

FORBIDDEN_PHRASES = [
    "continues to uncover injuries",
    "a host of",
    "significant emotional hardship",
    "cannot be overlooked",
    "ongoing discomfort",
    "found herself",
    "left her with",
    "had to",
    "was forced to",
    "engrossed in conversation",
    "was caught off guard"
]
