import json
import uuid
import datetime
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database import Base
from backend.models import Student, StudentProfile, ResumeVariant, JobPosting, Application, ApplicationAnswer, SubmissionConfirmation
from backend.services.verification_engine import execute_pre_submission_verification, compute_application_hash
from backend.services.authorization_engine import create_submission_authorization, validate_submission_authorization

@pytest.fixture
def in_memory_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    # Seed student
    student = Student(id="STU-TEST", name="Test Student", email="test@test.edu")
    db.add(student)
    db.flush()

    profile = StudentProfile(
        student_id="STU-TEST",
        degree="B.Tech",
        branch="Computer Science and Engineering",
        cgpa=8.5,
        graduation_year=2026,
        backlogs=0,
        skills=json.dumps(["Python", "FastAPI"])
    )
    db.add(profile)

    resume = ResumeVariant(
        id="RES-01",
        student_id="STU-TEST",
        role_tag="software_engineer",
        file_reference="resume.pdf",
        skills=json.dumps(["Python"])
    )
    db.add(resume)

    now = datetime.datetime.now(datetime.timezone.utc)
    job = JobPosting(
        id="JOB-TEST",
        haveloc_job_id="HVL-TEST",
        title="Software Engineer",
        company="TechCorp",
        posted_at=now,
        deadline=now + datetime.timedelta(hours=10),
        raw_snapshot="B.Tech CSE with CGPA >= 8.0.",
        normalized_requirements=json.dumps({
            "degree_requirements": ["B.Tech"],
            "branch_requirements": ["Computer Science and Engineering"],
            "min_cgpa": 8.0,
            "max_backlogs": 0,
            "graduation_years": [2026],
            "skills": ["Python"],
            "documents_required": ["Resume"],
            "questions": []
        }),
        snapshot_hash="dummy_hash"
    )
    db.add(job)
    db.commit()

    yield db
    db.close()

def test_verification_and_authorization_happy_path(in_memory_db):
    db = in_memory_db
    app = Application(
        id="APP-01",
        student_id="STU-TEST",
        job_id="JOB-TEST",
        resume_id="RES-01",
        state="FORM_FILLED"
    )
    db.add(app)
    db.flush()

    # Add verified answer consistent with profile
    ans = ApplicationAnswer(
        id="ANS-01",
        application_id=app.id,
        question_key="cgpa_key",
        question_text="What is your current CGPA?",
        answer_text="8.5",
        question_type="TYPE_A",
        source="PROFILE",
        confidence=1.0,
        requires_review=False
    )
    db.add(ans)
    db.commit()

    # 1. Run 9-point verification
    report = execute_pre_submission_verification(db, app.id)
    assert report.all_passed is True
    assert app.state == "PRE_SUBMISSION_VERIFIED"
    assert len(report.gate_checks) == 9
    assert report.application_hash is not None

    # 2. Issue Authorization Token
    auth = create_submission_authorization(db, app.id)
    assert auth.status == "AUTHORIZED"
    assert auth.auth_token.startswith("AUTH-")
    assert app.state == "SUBMISSION_AUTHORIZED"

    # 3. Validate Authorization
    validated = validate_submission_authorization(
        db=db,
        application_id=app.id,
        auth_token=auth.auth_token,
        current_application_hash=report.application_hash
    )
    assert validated.status == "AUTHORIZED"

def test_tamper_detection_invalidates_authorization(in_memory_db):
    db = in_memory_db
    app = Application(
        id="APP-02",
        student_id="STU-TEST",
        job_id="JOB-TEST",
        resume_id="RES-01",
        state="FORM_FILLED"
    )
    db.add(app)
    db.flush()

    ans = ApplicationAnswer(
        id="ANS-02",
        application_id=app.id,
        question_key="cgpa_key",
        question_text="What is your current CGPA?",
        answer_text="8.5",
        question_type="TYPE_A",
        source="PROFILE",
        confidence=1.0,
        requires_review=False
    )
    db.add(ans)
    db.commit()

    # Verify and authorize
    report = execute_pre_submission_verification(db, app.id)
    auth = create_submission_authorization(db, app.id)

    # Tamper payload: simulate user or extension altering the hash
    altered_hash = "tampered_hash_12345"
    with pytest.raises(ValueError, match="integrity mismatch"):
        validate_submission_authorization(
            db=db,
            application_id=app.id,
            auth_token=auth.auth_token,
            current_application_hash=altered_hash
        )
