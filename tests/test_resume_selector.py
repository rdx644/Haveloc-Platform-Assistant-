import json
import pytest
from backend.models import ResumeVariant
from backend.schemas import NormalizedRequirements
from backend.services.resume_selector import select_best_resume

@pytest.fixture
def sample_resumes():
    r_sde = ResumeVariant(
        id="RES-SDE",
        student_id="STU-01",
        role_tag="software_engineer",
        file_reference="resume_sde.pdf",
        skills=json.dumps(["Python", "FastAPI", "React", "PostgreSQL"]),
        experience_tags=json.dumps(["backend", "api", "database"])
    )
    r_cloud = ResumeVariant(
        id="RES-CLOUD",
        student_id="STU-01",
        role_tag="cloud_devops",
        file_reference="resume_cloud.pdf",
        skills=json.dumps(["Docker", "AWS", "Kubernetes", "Linux"]),
        experience_tags=json.dumps(["devops", "cloud", "infrastructure"])
    )
    return [r_sde, r_cloud]

def test_resume_selector_sde(sample_resumes):
    reqs = NormalizedRequirements(
        skills=["Python", "FastAPI", "PostgreSQL", "SQL"],
        degree_requirements=["B.Tech"]
    )
    report = select_best_resume(sample_resumes, reqs, job_title="Software Development Engineer")
    assert report.selected_resume_id == "RES-SDE"
    assert report.selected_file_reference == "resume_sde.pdf"
    assert report.confidence > 0.6

def test_resume_selector_cloud(sample_resumes):
    reqs = NormalizedRequirements(
        skills=["Docker", "AWS", "Kubernetes", "Linux"],
        degree_requirements=["B.Tech"]
    )
    report = select_best_resume(sample_resumes, reqs, job_title="Cloud DevOps Engineer")
    assert report.selected_resume_id == "RES-CLOUD"
    assert report.selected_file_reference == "resume_cloud.pdf"
