from typing import Dict, Any, List
from sqlalchemy.orm import Session
from backend.models import Application, ApplicationAnswer
from backend.schemas import ReadBackValidationReport, ReadBackFieldResult

def validate_form_read_back(
    db: Session,
    application_id: str,
    filled_fields: Dict[str, Any]
) -> ReadBackValidationReport:
    """
    Phase 12: Read-Back Verification.
    Reads form fields back from DOM and compares Expected answers vs Actual observed DOM inputs.
    Detects any FIELD_MISMATCH before pre-submission verification proceeds.
    """
    app = db.query(Application).filter(Application.id == application_id).first()
    if not app:
        raise ValueError(f"Application {application_id} not found.")

    answers = db.query(ApplicationAnswer).filter(ApplicationAnswer.application_id == application_id).all()
    results: List[ReadBackFieldResult] = []
    mismatches: List[str] = []

    for ans in answers:
        expected = ans.answer_text.strip()
        actual = str(filled_fields.get(ans.question_key, "")).strip()

        # Fuzzy or normalized comparison for whitespace / numbers
        matched = False
        if expected.lower() == actual.lower():
            matched = True
        else:
            try:
                if abs(float(expected) - float(actual)) < 0.001:
                    matched = True
            except ValueError:
                matched = False

        if not matched:
            disc = f"Field '{ans.question_key}' mismatch: Expected '{expected}', but DOM had '{actual}'"
            mismatches.append(disc)
            results.append(ReadBackFieldResult(
                field_key=ans.question_key,
                expected_value=expected,
                actual_value=actual,
                matched=False,
                discrepancy=disc
            ))
        else:
            results.append(ReadBackFieldResult(
                field_key=ans.question_key,
                expected_value=expected,
                actual_value=actual,
                matched=True,
                discrepancy=None
            ))

    passed = len(mismatches) == 0
    if not passed:
        app.state = "FIELD_MISMATCH"
        db.commit()

    return ReadBackValidationReport(
        application_id=application_id,
        passed=passed,
        results=results,
        mismatches=mismatches
    )
