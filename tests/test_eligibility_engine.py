import pytest
from backend.models import StudentProfile
from backend.schemas import NormalizedRequirements
from backend.services.eligibility_engine import evaluate_eligibility

@pytest.fixture
def sample_profile():
    return StudentProfile(
        student_id="STU-01",
        degree="B.Tech",
        branch="Computer Science and Engineering",
        cgpa=8.5,
        graduation_year=2026,
        backlogs=0
    )

def test_eligibility_pass(sample_profile):
    reqs = NormalizedRequirements(
        degree_requirements=["B.Tech"],
        branch_requirements=["Computer Science and Engineering", "Information Technology"],
        min_cgpa=8.0,
        max_backlogs=0,
        graduation_years=[2026]
    )
    report = evaluate_eligibility(sample_profile, reqs)
    assert report.eligible is True
    assert report.status == "PASS"
    assert len(report.failed_reasons) == 0

def test_eligibility_fail_cgpa(sample_profile):
    reqs = NormalizedRequirements(
        degree_requirements=["B.Tech"],
        branch_requirements=["Computer Science and Engineering"],
        min_cgpa=9.0, # Student has 8.5
        max_backlogs=0,
        graduation_years=[2026]
    )
    report = evaluate_eligibility(sample_profile, reqs)
    assert report.eligible is False
    assert report.status == "FAIL"
    assert any("CGPA" in r for r in report.failed_reasons)

def test_eligibility_fail_branch(sample_profile):
    reqs = NormalizedRequirements(
        degree_requirements=["B.Tech"],
        branch_requirements=["Mechanical Engineering", "Civil Engineering"],
        min_cgpa=7.5,
        max_backlogs=0
    )
    report = evaluate_eligibility(sample_profile, reqs)
    assert report.eligible is False
    assert any("branch" in r.lower() for r in report.failed_reasons)

def test_eligibility_fail_backlogs(sample_profile):
    sample_profile.backlogs = 2
    reqs = NormalizedRequirements(
        min_cgpa=7.5,
        max_backlogs=0
    )
    report = evaluate_eligibility(sample_profile, reqs)
    assert report.eligible is False
    assert any("backlog" in r.lower() for r in report.failed_reasons)
