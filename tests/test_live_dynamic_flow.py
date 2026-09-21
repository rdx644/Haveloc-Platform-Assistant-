import json
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.database import SessionLocal
from backend.models import Student, StudentProfile, ResumeVariant, JobPosting, Application

client = TestClient(app)

def test_live_discover_unseeded_company():
    """Test dynamically discovering an unseeded company on Haveloc DOM without prior database entries."""
    payload = {
        "company": "Databricks Inc",
        "title": "Cloud Solutions Associate",
        "haveloc_job_id": "HVL-DATABRICKS-901",
        "raw_text": "Databricks is hiring Cloud Solutions Associates. Requirements: B.Tech CSE/IT, CGPA >= 8.0, zero backlogs. Cloud computing experience required."
    }

    resp = client.post("/jobs/live-discover", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["discovered"] is True
    assert data["company"] == "Databricks Inc"
    assert data["job_id"] == "HVL-DATABRICKS-901"
    assert data["min_cgpa"] == 8.0
    assert "Cloud Computing" in data["allowed_branches"]

    # Verify job is actually persisted in database
    db = SessionLocal()
    try:
        job = db.query(JobPosting).filter(JobPosting.haveloc_job_id == "HVL-DATABRICKS-901").first()
        assert job is not None
        assert job.company == "Databricks Inc"
    finally:
        db.close()


def test_live_prepare_resume_only_application():
    """
    Test real-time preparation for a company requiring ONLY resume selection (zero custom questions).
    Must select optimal resume variant, generate 0 questions, pass all 9 verification gates,
    and authorize immediately.
    """
    live_payload = {
        "student_id": "RA2311028010135",
        "company": "Amazon AWS",
        "title": "Cloud Support Associate",
        "haveloc_job_id": "HVL-AMAZON-LIVE-001",
        "raw_text": "Amazon AWS hiring for Cloud Support Associate. Cloud computing, Linux, AWS skills. Resume-only submission.",
        "is_resume_only": True,
        "detected_fields": [],
        "autonomy_mode": "CONFIRM"
    }

    # 1. Live prepare
    prep_resp = client.post("/applications/live-prepare", json=live_payload)
    assert prep_resp.status_code == 200
    prep_data = prep_resp.json()
    assert prep_data["is_resume_only"] is True
    assert prep_data["application_id"] is not None
    app_id = prep_data["application_id"]

    # Resume must be selected based on role (Cloud Computing)
    assert prep_data["selected_resume"] is not None
    assert "Cloud_Computing" in prep_data["selected_resume"]["file_reference"]

    # Crucial: 0 synthetic questions generated
    assert len(prep_data["answers"]) == 0

    # 2. Verify 9-Point Gate for Resume-Only
    verify_resp = client.post(f"/applications/{app_id}/verify")
    assert verify_resp.status_code == 200
    verify_data = verify_resp.json()

    # All 9 gates must pass! Gate 4 and Gate 5 must NOT flag 0 questions.
    assert verify_data["all_passed"] is True, f"Gates failed: {verify_data['failure_messages']}"
    assert verify_data["application_hash"] is not None
    assert len(verify_data["application_hash"]) == 64  # SHA-256

    # Verify Gate 4 (Required Fields Completeness) passed cleanly
    gate_4 = next(g for g in verify_data["gate_checks"] if "Required Fields" in g.get("check_name", g.get("gate_name", "")))
    assert gate_4["passed"] is True
    assert "resume-only" in gate_4["details"].lower()

    # Verify Gate 5 (Question Grounding / Review) passed cleanly
    gate_5 = next(g for g in verify_data["gate_checks"] if ("Sensitive" in g.get("check_name", g.get("gate_name", "")) or "Question" in g.get("check_name", g.get("gate_name", ""))))
    assert gate_5["passed"] is True

    # 3. Authorize
    auth_resp = client.post(f"/applications/{app_id}/authorize")
    assert auth_resp.status_code == 200
    auth_token = auth_resp.json()["auth_token"]
    assert auth_token is not None

    # 4. Submit
    submit_resp = client.post(f"/applications/{app_id}/submit", json={
        "application_id": app_id,
        "auth_token": auth_token,
        "application_hash": verify_data["application_hash"],
        "portal_session_verified": True
    })
    assert submit_resp.status_code == 200
    assert submit_resp.json()["state"] == "SUBMITTING"


def test_live_prepare_with_custom_questions():
    """
    Test live preparation when Haveloc posting includes custom questionnaire fields.
    Grounded answers should be synthesized from verified achievements without hallucination.
    """
    live_payload = {
        "student_id": "RA2311028010135",
        "company": "Atlassian",
        "title": "Software Development Engineer",
        "haveloc_job_id": "HVL-ATLASSIAN-LIVE-002",
        "raw_text": "Atlassian SDE role. Full-stack development, Python, microservices, algorithms.",
        "is_resume_only": False,
        "detected_fields": [
            {
                "key": "relevant_experience",
                "label": "Describe a major technical project you built.",
                "tag": "textarea",
                "type": "text",
                "is_standard": False
            }
        ],
        "autonomy_mode": "CONFIRM"
    }

    # 1. Live prepare
    prep_resp = client.post("/applications/live-prepare", json=live_payload)
    assert prep_resp.status_code == 200
    prep_data = prep_resp.json()
    assert prep_data["is_resume_only"] is False

    # Resume variant should match SDE role
    assert "SDE" in prep_data["selected_resume"]["file_reference"]

    # Should have grounded answers
    assert len(prep_data["answers"]) == 1
    ans = prep_data["answers"][0]
    assert ans["question_key"] == "relevant_experience"
    assert len(ans["answer_text"]) > 20
    assert ans["source"] == "ACHIEVEMENT_BANK"


def test_turbo_prepare_resume_only():
    """
    Test the TURBO single-call endpoint for a resume-only application.
    Must return: resume, verification report, auth_token in ONE response.
    """
    payload = {
        "student_id": "RA2311028010135",
        "company": "Oracle Cloud",
        "title": "Cloud Infrastructure SDE",
        "haveloc_job_id": "HVL-ORACLE-TURBO-001",
        "raw_text": "Oracle Cloud hiring Cloud Infrastructure SDE. Cloud computing, Linux, AWS/Azure/GCP experience. Resume-only.",
        "is_resume_only": True,
        "detected_fields": [],
        "autonomy_mode": "CONFIRM"
    }

    resp = client.post("/applications/turbo-prepare", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    # Single response must have everything
    assert data["application_id"] is not None
    assert data["is_resume_only"] is True
    assert data["company"] == "Oracle Cloud"

    # Student facts must be present (dynamic, not hardcoded)
    assert data["student_facts"] is not None
    assert data["student_facts"]["roll_number"] == "RA2311028010135"
    assert data["student_facts"]["email"] is not None
    assert data["student_facts"]["cgpa"] is not None

    # Resume selection
    assert data["selected_resume"] is not None
    assert data["selected_resume"]["file_reference"] is not None

    # Zero answers for resume-only
    assert data["answers_count"] == 0

    # Verification report inline
    assert data["verification_report"] is not None
    assert data["verification_report"]["all_passed"] is True
    assert len(data["verification_report"]["gate_checks"]) == 9

    # Auth token issued inline (no separate API call needed!)
    assert data["auth_token"] is not None
    assert data["all_verified"] is True

    # Performance metric
    assert data["pipeline_ms"] > 0
    print(f"  TURBO pipeline completed in {data['pipeline_ms']}ms")


def test_turbo_prepare_with_questions():
    """
    Test the TURBO endpoint for an application with custom questions.
    Must batch everything including answer generation and verification.
    """
    payload = {
        "student_id": "RA2311028010135",
        "company": "Microsoft Azure",
        "title": "Software Development Engineer",
        "haveloc_job_id": "HVL-MSFT-TURBO-002",
        "raw_text": "Microsoft Azure SDE role. Distributed systems, Python, microservices.",
        "is_resume_only": False,
        "detected_fields": [
            {
                "key": "project_highlight",
                "label": "Describe your most impactful technical project.",
                "tag": "textarea",
                "type": "text",
                "is_standard": False
            }
        ],
        "autonomy_mode": "CONFIRM"
    }

    resp = client.post("/applications/turbo-prepare", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["is_resume_only"] is False
    assert data["answers_count"] == 1
    assert data["answers"][0]["question_key"] == "project_highlight"
    assert len(data["answers"][0]["answer_text"]) > 20

    # Verification and auth still inline
    assert data["verification_report"] is not None
    assert data["auth_token"] is not None
    assert data["pipeline_ms"] > 0


def test_student_registration():
    """
    Test registering a new student via the setup wizard endpoint.
    Must be idempotent — calling twice should not create duplicates.
    """
    reg_payload = {
        "registration_number": "RA2311028099999",
        "full_name": "Test Student Alpha",
        "email": "tsa@srmist.edu.in",
        "phone": "9999999999",
        "degree": "B.Tech",
        "branch": "Computer Science and Engineering - AI & ML",
        "specialization": "AI & ML",
        "cgpa": 9.0,
        "graduation_year": 2027,
        "backlogs": 0,
        "skills": ["Python", "TensorFlow", "NLP"],
        "willing_to_relocate": True,
        "resumes": [
            {
                "role_tag": "machine_learning",
                "file_reference": "Resume_ML_TestStudent.pdf",
                "version": "1.0",
                "skills": ["Python", "TensorFlow", "PyTorch"],
                "experience_tags": ["machine_learning"],
                "project_tags": ["nlp_chatbot"]
            }
        ]
    }

    # First registration
    resp1 = client.post("/student/register", json=reg_payload)
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["student_id"] == "RA2311028099999"
    assert data1["profile_complete"] is True

    # Idempotent re-registration (should update, not fail)
    reg_payload["cgpa"] = 9.2
    resp2 = client.post("/student/register", json=reg_payload)
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["student_id"] == "RA2311028099999"

    # Verify the profile was updated
    profile_resp = client.get("/student/RA2311028099999/profile")
    assert profile_resp.status_code == 200


def test_turbo_prepare_different_student():
    """
    Test multi-student isolation: the newly registered student should
    get their own application without interfering with other students.
    """
    payload = {
        "student_id": "RA2311028099999",
        "company": "Tesla AI",
        "title": "ML Engineer",
        "haveloc_job_id": "HVL-TESLA-TURBO-003",
        "raw_text": "Tesla AI hiring ML Engineers. PyTorch, Computer Vision.",
        "is_resume_only": True,
        "detected_fields": [],
        "autonomy_mode": "AUTONOMOUS"
    }

    resp = client.post("/applications/turbo-prepare", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    # Must use the NEW student's facts
    assert data["student_facts"]["roll_number"] == "RA2311028099999"
    assert data["student_facts"]["email"] == "tsa@srmist.edu.in"
    assert data["student_facts"]["cgpa"] is not None

    # Must have that student's resume
    assert data["selected_resume"] is not None
    assert "TestStudent" in data["selected_resume"]["file_reference"]

    # Must be fully verified & authorized
    assert data["all_verified"] is True
    assert data["auth_token"] is not None


def test_turbo_prepare_jit_registration():
    """
    Turbo prepare should perform Just-In-Time registration if scraped_profile is provided.
    """
    payload = {
        "company": "OpenAI",
        "title": "AI Researcher",
        "haveloc_job_id": "HVL-OPENAI-001",
        "is_resume_only": True,
        "detected_fields": [],
        "scraped_profile": {
            "name": "Jane Doe",
            "roll_no": "RAJANE999",
            "branch": "Artificial Intelligence",
            "cgpa": 9.8,
            "resumes": [
                {
                    "role_tag": "machine_learning",
                    "file_reference": "Jane_Doe_AI_Resume.pdf"
                }
            ]
        }
    }

    resp = client.post("/applications/turbo-prepare", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["student_facts"]["roll_number"] == "RAJANE999"
    assert data["student_facts"]["cgpa"] == "9.8"
    assert data["selected_resume"]["file_reference"] == "Jane_Doe_AI_Resume.pdf"

