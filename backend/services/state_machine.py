from typing import Set, Dict
from backend.schemas import ApplicationState

# Legal forward transitions
ALLOWED_TRANSITIONS: Dict[str, Set[str]] = {
    "DISCOVERED": {"PARSED", "INELIGIBLE", "EXPIRED"},
    "PARSED": {"ELIGIBILITY_CHECKED", "INELIGIBLE", "EXPIRED"},
    "ELIGIBILITY_CHECKED": {"APPLICATION_PLANNED", "PLANNED", "INELIGIBLE", "REQUIRES_REVIEW", "EXPIRED"},
    "APPLICATION_PLANNED": {"DRAFTED", "REQUIRES_REVIEW", "EXPIRED"},
    "PLANNED": {"DRAFTED", "REQUIRES_REVIEW", "EXPIRED"},
    "DRAFTED": {"FORM_FILLED", "REQUIRES_REVIEW", "EXPIRED"},
    "FORM_FILLED": {"PRE_SUBMISSION_VERIFIED", "FIELD_MISMATCH", "VERIFICATION_FAILED", "REQUIRES_REVIEW", "EXPIRED"},
    "PRE_SUBMISSION_VERIFIED": {"SUBMISSION_AUTHORIZED", "REQUIRES_REVIEW", "VERIFICATION_FAILED", "EXPIRED"},
    "SUBMISSION_AUTHORIZED": {"SUBMITTING", "CAPTCHA_REQUIRED", "EXPIRED", "VERIFICATION_FAILED"},
    "SUBMITTING": {"SUBMISSION_CONFIRMED", "SUBMISSION_UNKNOWN", "SUBMISSION_FAILED", "PORTAL_ERROR", "CAPTCHA_REQUIRED"},
    "SUBMISSION_CONFIRMED": {"COMPLETED"},
    "COMPLETED": set(),  # Terminal state
    
    # Failure recovery paths
    "INELIGIBLE": set(), # Terminal
    "EXPIRED": set(),    # Terminal
    "REQUIRES_REVIEW": {"APPLICATION_PLANNED", "PLANNED", "DRAFTED", "FORM_FILLED", "PRE_SUBMISSION_VERIFIED"},
    "CAPTCHA_REQUIRED": {"SUBMITTING", "SUBMISSION_FAILED"},
    "SUBMISSION_FAILED": {"SUBMITTING", "PRE_SUBMISSION_VERIFIED"},
    "PORTAL_ERROR": {"SUBMITTING", "PRE_SUBMISSION_VERIFIED"},
    "FIELD_MISMATCH": {"FORM_FILLED", "REQUIRES_REVIEW"},
    "VERIFICATION_FAILED": {"APPLICATION_PLANNED", "PLANNED", "DRAFTED", "FORM_FILLED"},
    # SUBMISSION_UNKNOWN requires human verification on portal; strictly forbids automatic retry
    "SUBMISSION_UNKNOWN": {"COMPLETED", "SUBMISSION_FAILED", "REQUIRES_REVIEW"}
}

def transition_state(current_state: str, new_state: str) -> None:
    """
    Validates state machine transitions.
    Prevents bypassing gates (e.g. going straight from FORM_FILLED to SUBMITTING or COMPLETED).
    """
    allowed = ALLOWED_TRANSITIONS.get(current_state, set())
    if new_state not in allowed:
        raise ValueError(
            f"Illegal state transition from '{current_state}' to '{new_state}'. "
            f"Allowed next states are: {list(allowed)}."
        )
