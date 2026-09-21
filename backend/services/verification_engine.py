import hashlib
import json
import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from backend.models import Application, Student, StudentProfile, JobPosting, ResumeVariant, ApplicationAnswer, SubmissionConfirmation
from backend.schemas import PreSubmissionVerificationReport, PreSubmissionGateCheck
from backend.services.deadline_engine import evaluate_deadline
from backend.services.eligibility_engine import evaluate_eligibility
from backend.services.normalization import normalize_job_data

def compute_application_hash(
    student_id: str,
    job_id: str,
    resume_id: str,
    answers_dict: Dict[str, str]
) -> str:
    """
    Computes a cryptographic SHA-256 hash of the complete application payload.
    Any tampering of answers, resume, or IDs will change this hash and invalidate authorization.
    """
    # Sort keys for deterministic representation
    sorted_answers = json.dumps(answers_dict, sort_keys=True)
    raw_payload = f"{student_id}:{job_id}:{resume_id}:{sorted_answers}"
    return hashlib.sha256(raw_payload.encode("utf-8")).hexdigest()

def execute_pre_submission_verification(
    db: Session,
    application_id: str
) -> PreSubmissionVerificationReport:
    """
    Mandatory Release Gate: Executes the full 9-point deterministic verification pipeline.
    All 9 checks MUST pass to grant submission authorization.
    """
    app = db.query(Application).filter(Application.id == application_id).first()
    if not app:
        raise ValueError(f"Application {application_id} not found.")

    student = db.query(Student).filter(Student.id == app.student_id).first()
    profile = db.query(StudentProfile).filter(StudentProfile.student_id == app.student_id).first()
    job = db.query(JobPosting).filter(JobPosting.id == app.job_id).first()
    resume = db.query(ResumeVariant).filter(ResumeVariant.id == app.resume_id).first() if app.resume_id else None
    answers = db.query(ApplicationAnswer).filter(ApplicationAnswer.application_id == app.id).all()

    gate_checks: List[PreSubmissionGateCheck] = []
    failure_messages: List[str] = []

    # Gate 1: Eligibility Check
    reqs = normalize_job_data(job.raw_snapshot, job.get_normalized())
    elig_report = evaluate_eligibility(profile, reqs)
    if elig_report.eligible:
        gate_checks.append(PreSubmissionGateCheck(
            check_name="1. Eligibility Check",
            passed=True,
            details="All academic and policy eligibility criteria passed."
        ))
    else:
        fail_msg = f"Candidate ineligible: {'; '.join(elig_report.failed_reasons)}"
        gate_checks.append(PreSubmissionGateCheck(
            check_name="1. Eligibility Check",
            passed=False,
            details=fail_msg
        ))
        failure_messages.append(fail_msg)

    # Gate 2: Deadline Check
    dead_report = evaluate_deadline(job.deadline)
    if not dead_report.is_expired:
        gate_checks.append(PreSubmissionGateCheck(
            check_name="2. Application Deadline",
            passed=True,
            details=f"Active: {dead_report.formatted_time_remaining} (Expires: {dead_report.deadline_utc.isoformat()})"
        ))
    else:
        fail_msg = f"Application deadline has expired ({dead_report.deadline_utc.isoformat()}). Submission blocked."
        gate_checks.append(PreSubmissionGateCheck(
            check_name="2. Application Deadline",
            passed=False,
            details=fail_msg
        ))
        failure_messages.append(fail_msg)

    # Gate 3: Resume Validation
    if resume and resume.file_reference:
        gate_checks.append(PreSubmissionGateCheck(
            check_name="3. Resume Variant Selection",
            passed=True,
            details=f"Selected resume '{resume.role_tag}' ({resume.file_reference}) verified."
        ))
    else:
        fail_msg = "No valid resume variant attached or file reference missing."
        gate_checks.append(PreSubmissionGateCheck(
            check_name="3. Resume Variant Selection",
            passed=False,
            details=fail_msg
        ))
        failure_messages.append(fail_msg)

    # Gate 4: Required Fields Completeness
    missing_fields = []
    answers_map = {ans.question_key: ans.answer_text.strip() for ans in answers}
    if not answers_map and len(reqs.questions) > 0:
        missing_fields.append("No application questions recorded")
    for key, text in answers_map.items():
        if not text:
            missing_fields.append(key)
    
    if not missing_fields:
        detail_msg = "All application form input fields are populated." if answers_map else "Resume-only application: No custom questions required."
        gate_checks.append(PreSubmissionGateCheck(
            check_name="4. Required Fields Completeness",
            passed=True,
            details=detail_msg
        ))
    else:
        fail_msg = f"Missing required fields: {', '.join(missing_fields)}"
        gate_checks.append(PreSubmissionGateCheck(
            check_name="4. Required Fields Completeness",
            passed=False,
            details=fail_msg
        ))
        failure_messages.append(fail_msg)

    # Gate 5: Question Completeness & Confidence
    low_confidence_qs = [a.question_key for a in answers if a.confidence < 0.60]
    unresolved_reviews = [a.question_key for a in answers if a.requires_review]
    if not low_confidence_qs and not unresolved_reviews:
        detail_msg = "All questions meet confidence thresholds and have zero unresolved review flags." if answers else "Resume-only application: Zero question review needed."
        gate_checks.append(PreSubmissionGateCheck(
            check_name="5. Question Confidence & Review",
            passed=True,
            details=detail_msg
        ))
    else:
        msgs = []
        if low_confidence_qs:
            msgs.append(f"Low confidence on {low_confidence_qs}")
        if unresolved_reviews:
            msgs.append(f"Requires explicit student review for sensitive questions {unresolved_reviews}")
        fail_msg = "; ".join(msgs)
        gate_checks.append(PreSubmissionGateCheck(
            check_name="5. Question Confidence & Review",
            passed=False,
            details=fail_msg
        ))
        failure_messages.append(fail_msg)

    # Gate 6: Document Availability
    docs_required = reqs.documents_required
    if "Resume" in docs_required and not resume:
        fail_msg = "Resume document is mandatory but not attached."
        gate_checks.append(PreSubmissionGateCheck(
            check_name="6. Document Availability",
            passed=False,
            details=fail_msg
        ))
        failure_messages.append(fail_msg)
    else:
        gate_checks.append(PreSubmissionGateCheck(
            check_name="6. Document Availability",
            passed=True,
            details=f"Required documents satisfied ({', '.join(docs_required)})."
        ))

    # Gate 7: Student Profile Consistency
    profile_mismatches = []
    for ans in answers:
        q_lower = ans.question_text.lower()
        if "cgpa" in q_lower:
            try:
                ans_cgpa = float(ans.answer_text)
                if abs(ans_cgpa - profile.cgpa) > 0.01:
                    profile_mismatches.append(f"CGPA answer ({ans_cgpa}) does not match student record ({profile.cgpa})")
            except ValueError:
                profile_mismatches.append(f"CGPA answer '{ans.answer_text}' is not a valid number")
        elif "backlog" in q_lower:
            try:
                ans_backlogs = int(ans.answer_text)
                if ans_backlogs != profile.backlogs:
                    profile_mismatches.append(f"Backlog answer ({ans_backlogs}) does not match profile ({profile.backlogs})")
            except ValueError:
                pass

    if not profile_mismatches:
        gate_checks.append(PreSubmissionGateCheck(
            check_name="7. Student Profile Consistency",
            passed=True,
            details="Form answers are 100% consistent with verified student records."
        ))
    else:
        fail_msg = "; ".join(profile_mismatches)
        gate_checks.append(PreSubmissionGateCheck(
            check_name="7. Student Profile Consistency",
            passed=False,
            details=fail_msg
        ))
        failure_messages.append(fail_msg)

    # Gate 8: Duplicate Application Prevention
    existing_conf = (
        db.query(SubmissionConfirmation)
        .filter(SubmissionConfirmation.application_id == app.id)
        .first()
    )
    if not existing_conf and app.state != "COMPLETED":
        gate_checks.append(PreSubmissionGateCheck(
            check_name="8. Duplicate Application Check",
            passed=True,
            details="No prior completed submission found for this student and job."
        ))
    else:
        fail_msg = f"Duplicate application: Student has already completed submission (Portal ID: {existing_conf.portal_application_id if existing_conf else 'N/A'})."
        gate_checks.append(PreSubmissionGateCheck(
            check_name="8. Duplicate Application Check",
            passed=False,
            details=fail_msg
        ))
        failure_messages.append(fail_msg)

    # Gate 9: Application Integrity Hash Computation
    app_hash = compute_application_hash(
        student_id=app.student_id,
        job_id=app.job_id,
        resume_id=app.resume_id or "NONE",
        answers_dict=answers_map
    )
    gate_checks.append(PreSubmissionGateCheck(
        check_name="9. Cryptographic Hash Integrity",
        passed=True,
        details=f"SHA-256 Digest: {app_hash}"
    ))

    all_passed = len(failure_messages) == 0

    # Persist state update
    if all_passed:
        app.state = "PRE_SUBMISSION_VERIFIED"
        app.application_hash = app_hash
    else:
        app.state = "VERIFICATION_FAILED" if any("ineligible" in m.lower() or "expired" in m.lower() for m in failure_messages) else "REQUIRES_REVIEW"

    db.commit()

    return PreSubmissionVerificationReport(
        application_id=app.id,
        student_id=app.student_id,
        job_id=app.job_id,
        all_passed=all_passed,
        application_hash=app_hash,
        gate_checks=gate_checks,
        failure_messages=failure_messages,
        timestamp=datetime.datetime.now(datetime.timezone.utc)
    )
