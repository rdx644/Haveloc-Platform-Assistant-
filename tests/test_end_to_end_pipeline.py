import json
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.database import SessionLocal
from backend.models import JobPosting, Application
from backend.schemas import AutonomyMode, ApplicationState

client = TestClient(app)

def test_full_application_lifecycle_with_real_portal_data():
    # 1. Check health
    health_resp = client.get("/health")
    assert health_resp.status_code == 200
    assert health_resp.json()["deterministic_gates"] == "enforced"

    # 2. Get list of seeded jobs from Haveloc
    jobs_resp = client.get("/jobs")
    assert jobs_resp.status_code == 200
    jobs = jobs_resp.json()
    assert len(jobs) >= 3

    # Find the LTM job from Shubham's portal screenshot
    ltm_job = next((j for j in jobs if j["haveloc_job_id"] == "HVL-LTM-2026"), None)
    assert ltm_job is not None

    student_id = "RA2311028010135"

    # Reset any previous test runs for clean idempotency
    db = SessionLocal()
    for a in db.query(Application).filter(Application.student_id == student_id, Application.job_id == ltm_job["id"]).all():
        db.delete(a)
    db.commit()
    db.close()

    # 3. Step 1-4: Initiate Application with CONFIRM Autonomy Mode
    init_resp = client.post("/applications/initiate", json={
        "student_id": student_id,
        "job_id": ltm_job["id"],
        "autonomy_mode": "CONFIRM"
    })
    assert init_resp.status_code == 200
    init_data = init_resp.json()
    app_id = init_data["application_id"]
    assert init_data["state"] == "DRAFTED"
    assert "selected_resume" in init_data

    # 4. Step 5: Mark Form Filled (from extension) -> FORM_FILLED
    fill_resp = client.post(f"/applications/{app_id}/fill")
    assert fill_resp.status_code == 200
    assert fill_resp.json()["message"] == "State updated to FORM_FILLED"

    # 5. Read-Back Validation (Phase 12)
    # Simulate reading back DOM values from the Haveloc portal form
    app_details = client.get(f"/applications/{app_id}").json()
    expected_answers = app_details["answers"]
    dom_read_back = {ans["key"]: ans["answer"] for ans in expected_answers}
    read_back_resp = client.post(f"/applications/{app_id}/read-back-verify", json={
        "application_id": app_id,
        "filled_fields": dom_read_back
    })
    assert read_back_resp.status_code == 200
    read_back_report = read_back_resp.json()
    assert read_back_report["passed"] is True

    # 6. Step 6: Pre-Submission Verification (9-Point Gate)
    verify_resp = client.post(f"/applications/{app_id}/verify")
    assert verify_resp.status_code == 200
    verify_data = verify_resp.json()

    # If sensitive question 'relocate_q' requires confirmation
    if not verify_data["all_passed"]:
        resolve_resp = client.post(f"/applications/{app_id}/resolve-review", json={
            "question_key": "relocate_q",
            "confirmed_answer": "Yes, I am fully open to relocating to company work locations."
        })
        assert resolve_resp.status_code == 200

        # Mark filled and re-verify
        client.post(f"/applications/{app_id}/fill")
        verify_resp = client.post(f"/applications/{app_id}/verify")
        verify_data = verify_resp.json()

    assert verify_data["all_passed"] is True
    assert len(verify_data["gate_checks"]) == 9
    app_hash = verify_data["application_hash"]

    # 7. Step 7: Submission Authorization
    auth_resp = client.post(f"/applications/{app_id}/authorize")
    assert auth_resp.status_code == 200
    auth_data = auth_resp.json()
    auth_token = auth_data["auth_token"]
    assert auth_token.startswith("AUTH-")

    # 8. Step 8: Submission Executor (Verifies auth, deadline, transitions to SUBMITTING)
    submit_resp = client.post(f"/applications/{app_id}/submit", json={
        "application_id": app_id,
        "auth_token": auth_token,
        "application_hash": app_hash,
        "portal_session_verified": True
    })
    assert submit_resp.status_code == 200
    assert submit_resp.json()["state"] == "SUBMITTING"

    # 9. Step 9: Submission Confirmation (Haveloc portal receipt captured)
    confirm_resp = client.post(f"/applications/{app_id}/confirm", json={
        "application_id": app_id,
        "auth_token": auth_token,
        "portal_application_id": "HVL-APP-SRM-2026-98124",
        "status_code": 200,
        "confirmation_evidence": {
            "status": "ACCEPTED",
            "receipt_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "timestamp": "2026-09-21T19:00:00Z"
        }
    })
    assert confirm_resp.status_code == 200
    confirm_data = confirm_resp.json()
    assert confirm_data["state"] == "COMPLETED"
    assert confirm_data["portal_application_id"] == "HVL-APP-SRM-2026-98124"

    # 10. Duplicate protection test: Attempting to re-apply must be rejected
    dup_resp = client.post("/applications/initiate", json={
        "student_id": student_id,
        "job_id": ltm_job["id"]
    })
    assert dup_resp.status_code == 409
    assert "Duplicate rejected" in dup_resp.json()["detail"]


def test_read_back_validation_mismatch_triggers_field_mismatch():
    student_id = "RA2311028010135"
    jobs_resp = client.get("/jobs")
    broadridge_job = next((j for j in jobs_resp.json() if j["haveloc_job_id"] == "HVL-BROADRIDGE-2026"), None)
    assert broadridge_job is not None

    db = SessionLocal()
    for a in db.query(Application).filter(Application.student_id == student_id, Application.job_id == broadridge_job["id"]).all():
        db.delete(a)
    db.commit()
    db.close()

    init_resp = client.post("/applications/initiate", json={
        "student_id": student_id,
        "job_id": broadridge_job["id"],
        "autonomy_mode": "CONFIRM"
    })
    app_id = init_resp.json()["application_id"]
    client.post(f"/applications/{app_id}/fill")

    # Introduce intentional mismatch in DOM read-back
    corrupted_read_back = {
        "cgpa_q": "3.20"
    }
    rb_resp = client.post(f"/applications/{app_id}/read-back-verify", json={
        "application_id": app_id,
        "filled_fields": corrupted_read_back
    })
    assert rb_resp.status_code == 200
    rb_report = rb_resp.json()
    assert rb_report["passed"] is False
    assert len(rb_report["mismatches"]) > 0

    # Verify state machine transitioned to FIELD_MISMATCH
    app_state = client.get(f"/applications/{app_id}").json()["state"]
    assert app_state == "FIELD_MISMATCH"


def test_ambiguous_submission_transitions_to_submission_unknown_and_blocks_retry():
    student_id = "RA2311028010135"
    jobs_resp = client.get("/jobs")
    broadridge_job = next((j for j in jobs_resp.json() if j["haveloc_job_id"] == "HVL-BROADRIDGE-2026"), None)
    assert broadridge_job is not None

    db = SessionLocal()
    for a in db.query(Application).filter(Application.student_id == student_id, Application.job_id == broadridge_job["id"]).all():
        db.delete(a)
    db.commit()
    db.close()

    init_resp = client.post("/applications/initiate", json={
        "student_id": student_id,
        "job_id": broadridge_job["id"],
        "autonomy_mode": "CONFIRM"
    })
    app_id = init_resp.json()["application_id"]
    client.post(f"/applications/{app_id}/fill")

    # Run pre-submission verification (gate checks)
    verify_resp = client.post(f"/applications/{app_id}/verify")
    if not verify_resp.json()["all_passed"]:
        client.post(f"/applications/{app_id}/resolve-review", json={
            "question_key": "bond_q",
            "confirmed_answer": "Yes, I acknowledge and accept the standard institutional terms."
        })
        client.post(f"/applications/{app_id}/fill")
        verify_resp = client.post(f"/applications/{app_id}/verify")

    app_hash = verify_resp.json()["application_hash"]

    # Authorize submission
    auth_resp = client.post(f"/applications/{app_id}/authorize")
    auth_token = auth_resp.json()["auth_token"]

    # Move to SUBMITTING
    submit_resp = client.post(f"/applications/{app_id}/submit", json={
        "application_id": app_id,
        "auth_token": auth_token,
        "application_hash": app_hash,
        "portal_session_verified": True
    })
    assert submit_resp.status_code == 200
    assert submit_resp.json()["state"] == "SUBMITTING"

    # Simulate portal HTTP 504 Gateway Timeout
    confirm_resp = client.post(f"/applications/{app_id}/confirm", json={
        "application_id": app_id,
        "auth_token": auth_token,
        "portal_application_id": "UNKNOWN_RECEIPT",
        "status_code": 504,
        "confirmation_evidence": {"error": "Gateway Timeout during form processing"}
    })
    assert confirm_resp.status_code == 200
    confirm_data = confirm_resp.json()
    assert confirm_data["state"] == "SUBMISSION_UNKNOWN"
    assert confirm_data["retry_prohibited"] is True

    # Critical Guardrail Check: Attempting to automatically submit again MUST fail
    retry_submit_resp = client.post(f"/applications/{app_id}/submit", json={
        "application_id": app_id,
        "auth_token": auth_token,
        "application_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "portal_session_verified": True
    })
    assert retry_submit_resp.status_code in [400, 403]


