NO_HALLUCINATION_NOTE = """
Do not fabricate or assume any facts. Use only the facts provided in the case synopsis or other inputs.
"""

LEGAL_FLUENCY_NOTE = """
Use the tone and clarity of a senior litigator when drafting.
"""

NO_PASSIVE_LANGUAGE_NOTE = """
Every sentence must use active voice for clarity and strength.
"""

BAN_PHRASES_NOTE = """
Avoid any speculative, uncertain, or weak language. Do not hedge facts or conclusions.
"""

FULL_SAFETY_PROMPT = "\n\n".join([
    NO_HALLUCINATION_NOTE,
    LEGAL_FLUENCY_NOTE,
    NO_PASSIVE_LANGUAGE_NOTE,
    BAN_PHRASES_NOTE,
])

FOIA_BULLET_POINTS_PROMPT_TEMPLATE = """
You are drafting FOIA bullet points for a civil legal claim.

Case synopsis:
{case_synopsis}

Case type: {case_type}
Facility or system involved: {facility}
Defendant role: {defendant_role}

Explicit instructions:
{explicit_instructions}

Common requests or priorities:
{potential_requests}

Please return a detailed and **role-specific** list of records, documents, media, and internal communications that a skilled civil attorney would request from this type of facility or entity. 
Only include items that would reasonably be within the possession, custody, or control of a {defendant_role} operating within a {facility}. 

DO NOT include irrelevant medical, financial, or third-party institutional records if they would not be held by this entity. 
DO NOT copy any facts, dates, or case numbers from examples. Examples (if any) are for tone and style only and should not influence the actual facts of this case.

Format output as Word-style bullet points using asterisks (*).
Only return the list.
"""

FOIA_SYNOPSIS_PROMPT = """
Summarize the following case background in exactly 2 sentences:
1. First sentence: describe what happened.
2. Second sentence: describe the resulting harm or damages.

DO NOT use bullet points, lists, or include any names or personal identifiers.
DO NOT pull details, dates, or case numbers from examples. Base your summary only on the facts provided in the case synopsis.

Case synopsis:
{case_synopsis}
"""
