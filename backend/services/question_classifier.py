import re
from typing import Tuple
from backend.schemas import QuestionType

# Sensitive/Consequential patterns for Type E
SENSITIVE_PATTERNS = [
    r'\brelocat(?:e|ion)\b',
    r'\bbond\b',
    r'\bagreement\b',
    r'\baccommodation\b',
    r'\bexisting offer\b',
    r'\bnotice period\b',
    r'\bcriminal\b',
    r'\bdisciplinary\b',
    r'\bmedical condition\b',
    r'\bwork permit\b',
    r'\bvika\b',
    r'\bshift\b'
]

# Deterministic Profile patterns for Type A
DETERMINISTIC_PATTERNS = [
    r'\bcgpa\b',
    r'\bgpa\b',
    r'\bpercentage\b',
    r'\broll\s*(?:no|number)\b',
    r'\breg(?:istration)?\s*(?:no|number)\b',
    r'\bdegree\b',
    r'\bbranch\b',
    r'\bdepartment\b',
    r'\bgraduation\s*year\b',
    r'\bpassing\s*year\b',
    r'\bbacklog\b',
    r'\barrear\b',
    r'\bemail\b',
    r'\bphone\b',
    r'\bmobile\b',
    r'\bfull\s*name\b'
]

# Profile-based skills patterns for Type B
SKILL_PATTERNS = [
    r'\bprogramming\s+languages?\b',
    r'\blanguages?\b',
    r'\bskills?\b',
    r'\btechnolog(?:y|ies)\b',
    r'\bframeworks?\b',
    r'\btools?\b',
    r'\bdatabases?\b'
]

# Experience/Project patterns for Type C
EXPERIENCE_PATTERNS = [
    r'\bproject\b',
    r'\binternship\b',
    r'\bexperience\b',
    r'\bachievement\b',
    r'\bchallenge\b',
    r'\bleadership\b'
]

def classify_question(question_text: str) -> Tuple[QuestionType, bool]:
    """
    Deterministically classifies application questions into Type A, B, C, D, or E.
    Returns (QuestionType, requires_review: bool).
    """
    text_clean = question_text.strip().lower()

    # 1. Check for Sensitive / Consequential questions (Type E)
    for pat in SENSITIVE_PATTERNS:
        if re.search(pat, text_clean):
            return QuestionType.TYPE_E, True

    # 2. Check for Deterministic Profile questions (Type A)
    for pat in DETERMINISTIC_PATTERNS:
        if re.search(pat, text_clean):
            return QuestionType.TYPE_A, False

    # 3. Check for Profile Skills questions (Type B)
    for pat in SKILL_PATTERNS:
        if re.search(pat, text_clean):
            return QuestionType.TYPE_B, False

    # 4. Check for Experience/Project questions (Type C)
    for pat in EXPERIENCE_PATTERNS:
        if re.search(pat, text_clean):
            return QuestionType.TYPE_C, False

    # 5. Default to Open-ended questions (Type D)
    return QuestionType.TYPE_D, False
