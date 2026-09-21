from typing import Dict, List, Any
from backend.models import StudentProfile
from backend.schemas import NormalizedRequirements, EligibilityReport, CheckCriterion

def evaluate_eligibility(
    profile: StudentProfile,
    requirements: NormalizedRequirements
) -> EligibilityReport:
    """
    Deterministic rule engine checking student eligibility against job requirements.
    Rules are verified sequentially; any mandatory failure marks the candidate ineligible.
    """
    checks: Dict[str, CheckCriterion] = {}
    failed_reasons: List[str] = []

    # 1. Degree Check
    req_degrees = [d.strip().lower() for d in requirements.degree_requirements]
    student_degree = profile.degree.strip().lower()
    if not req_degrees or "any" in req_degrees or any(d in student_degree or student_degree in d for d in req_degrees):
        checks["degree"] = CheckCriterion(
            criterion="Degree",
            passed=True,
            required=requirements.degree_requirements,
            actual=profile.degree,
            reason="Student degree matches eligible degrees."
        )
    else:
        checks["degree"] = CheckCriterion(
            criterion="Degree",
            passed=False,
            required=requirements.degree_requirements,
            actual=profile.degree,
            reason=f"Student degree '{profile.degree}' is not in required list {requirements.degree_requirements}."
        )
        failed_reasons.append(checks["degree"].reason)

    # 2. Branch Check
    req_branches = [b.strip().lower() for b in requirements.branch_requirements]
    student_branch = profile.branch.strip().lower()
    if not req_branches or "all branches" in req_branches or "any" in req_branches or any(b in student_branch or student_branch in b for b in req_branches):
        checks["branch"] = CheckCriterion(
            criterion="Branch",
            passed=True,
            required=requirements.branch_requirements,
            actual=profile.branch,
            reason="Student branch is accepted."
        )
    else:
        checks["branch"] = CheckCriterion(
            criterion="Branch",
            passed=False,
            required=requirements.branch_requirements,
            actual=profile.branch,
            reason=f"Student branch '{profile.branch}' does not match required branches {requirements.branch_requirements}."
        )
        failed_reasons.append(checks["branch"].reason)

    # 3. CGPA Cutoff Check
    if requirements.min_cgpa is not None:
        if profile.cgpa >= requirements.min_cgpa:
            checks["cgpa"] = CheckCriterion(
                criterion="CGPA",
                passed=True,
                required=requirements.min_cgpa,
                actual=profile.cgpa,
                reason=f"CGPA {profile.cgpa} satisfies minimum requirement of {requirements.min_cgpa}."
            )
        else:
            checks["cgpa"] = CheckCriterion(
                criterion="CGPA",
                passed=False,
                required=requirements.min_cgpa,
                actual=profile.cgpa,
                reason=f"CGPA {profile.cgpa} is below minimum threshold of {requirements.min_cgpa}."
            )
            failed_reasons.append(checks["cgpa"].reason)
    else:
        checks["cgpa"] = CheckCriterion(
            criterion="CGPA",
            passed=True,
            required="None",
            actual=profile.cgpa,
            reason="No minimum CGPA required."
        )

    # 4. Graduation Year Check
    if requirements.graduation_years:
        if profile.graduation_year in requirements.graduation_years:
            checks["graduation_year"] = CheckCriterion(
                criterion="Graduation Year",
                passed=True,
                required=requirements.graduation_years,
                actual=profile.graduation_year,
                reason=f"Graduation year {profile.graduation_year} is eligible."
            )
        else:
            checks["graduation_year"] = CheckCriterion(
                criterion="Graduation Year",
                passed=False,
                required=requirements.graduation_years,
                actual=profile.graduation_year,
                reason=f"Batch {profile.graduation_year} not in eligible graduation years {requirements.graduation_years}."
            )
            failed_reasons.append(checks["graduation_year"].reason)
    else:
        checks["graduation_year"] = CheckCriterion(
            criterion="Graduation Year",
            passed=True,
            required="Any",
            actual=profile.graduation_year,
            reason="No specific graduation year restriction."
        )

    # 5. Backlogs / Arrears Check
    if profile.backlogs <= requirements.max_backlogs:
        checks["backlogs"] = CheckCriterion(
            criterion="Active Backlogs",
            passed=True,
            required=f"<= {requirements.max_backlogs}",
            actual=profile.backlogs,
            reason=f"Active backlogs count ({profile.backlogs}) is within allowed limit ({requirements.max_backlogs})."
        )
    else:
        checks["backlogs"] = CheckCriterion(
            criterion="Active Backlogs",
            passed=False,
            required=f"<= {requirements.max_backlogs}",
            actual=profile.backlogs,
            reason=f"Student has {profile.backlogs} standing backlogs, maximum permitted is {requirements.max_backlogs}."
        )
        failed_reasons.append(checks["backlogs"].reason)

    is_eligible = len(failed_reasons) == 0

    return EligibilityReport(
        eligible=is_eligible,
        status="PASS" if is_eligible else "FAIL",
        checks=checks,
        failed_reasons=failed_reasons
    )
