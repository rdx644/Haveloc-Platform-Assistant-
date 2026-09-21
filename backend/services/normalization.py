import hashlib
import json
import re
from typing import Dict, Any, List
from backend.schemas import NormalizedRequirements

def compute_hash(content: str) -> str:
    """Compute SHA-256 hash of a string content."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()

def normalize_job_data(
    raw_text: str,
    parsed_meta: Dict[str, Any] = None
) -> NormalizedRequirements:
    """
    Deterministic normalization pipeline converting raw job snapshot
    and parsed metadata into canonical NormalizedRequirements.
    """
    if parsed_meta is None:
        parsed_meta = {}

    # Extract or fallback degrees
    degrees: List[str] = parsed_meta.get("degree_requirements") or parsed_meta.get("degrees", [])
    if not degrees:
        raw_upper = raw_text.upper()
        if "B.TECH" in raw_upper or "BTECH" in raw_upper or "BACHELOR OF TECHNOLOGY" in raw_upper:
            degrees.append("B.Tech")
        if "M.TECH" in raw_upper or "MTECH" in raw_upper:
            degrees.append("M.Tech")
        if "BCA" in raw_upper:
            degrees.append("BCA")
        if "MCA" in raw_upper:
            degrees.append("MCA")
        if not degrees:
            degrees.append("Any")

    # Extract branches
    branches: List[str] = parsed_meta.get("branch_requirements") or parsed_meta.get("branches", [])
    if not branches:
        text_lower = raw_text.lower()
        if any(b in text_lower for b in ["computer science", "cse", "cs & e", "computer engineering"]):
            branches.append("Computer Science and Engineering")
        if re.search(r'\b(information technology|it)\b', text_lower):
            branches.append("Information Technology")
        if any(b in text_lower for b in ["cloud computing", "cloud"]):
            branches.append("Cloud Computing")
        if any(b in text_lower for b in ["electronics", "ece"]):
            branches.append("Electronics and Communication Engineering")
        if any(b in text_lower for b in ["data science", "aiml", "ai & ml"]):
            branches.append("Data Science")
        if not branches:
            branches.append("All Branches")

    # Extract CGPA requirement
    min_cgpa: float = parsed_meta.get("min_cgpa")
    if min_cgpa is None:
        cgpa_match = re.search(r'(?:cgpa|gpa|cutoff|pointer)\s*(?:of|is|>=|:|\-)?\s*([0-9](?:\.[0-9]+)?)', raw_text, re.IGNORECASE)
        if cgpa_match:
            try:
                val = float(cgpa_match.group(1))
                if 0.0 <= val <= 10.0:
                    min_cgpa = val
            except ValueError:
                min_cgpa = None

    # Extract max backlogs allowed
    max_backlogs: int = parsed_meta.get("max_backlogs", 0)
    if "no backlogs" in raw_text.lower() or "0 backlogs" in raw_text.lower() or "no standing arrears" in raw_text.lower():
        max_backlogs = 0

    # Extract graduation years
    grad_years: List[int] = parsed_meta.get("graduation_years", [])
    if not grad_years:
        for year in [2024, 2025, 2026, 2027]:
            if str(year) in raw_text:
                grad_years.append(year)

    # Extract skills
    skills: List[str] = parsed_meta.get("skills", [])
    if not skills:
        common_skills = [
            "Python", "Java", "C++", "JavaScript", "TypeScript", "React", "Node.js",
            "SQL", "PostgreSQL", "Docker", "Kubernetes", "AWS", "Azure", "GCP",
            "Machine Learning", "FastAPI", "Linux", "Git", "REST APIs"
        ]
        raw_words = set(re.findall(r'\b[A-Za-z\+\#\.\-]+\b', raw_text))
        for skill in common_skills:
            if skill.lower() in [w.lower() for w in raw_words]:
                skills.append(skill)

    # Required documents
    docs: List[str] = parsed_meta.get("documents_required", ["Resume"])
    if "transcript" in raw_text.lower() and "Transcript" not in docs:
        docs.append("Academic Transcript")
    if "bonafide" in raw_text.lower() and "Bonafide Certificate" not in docs:
        docs.append("Bonafide Certificate")

    # Questions
    questions: List[Dict[str, Any]] = parsed_meta.get("questions", [])

    return NormalizedRequirements(
        degree_requirements=degrees,
        branch_requirements=branches,
        min_cgpa=min_cgpa,
        max_backlogs=max_backlogs,
        graduation_years=grad_years,
        skills=skills,
        experience_requirements=parsed_meta.get("experience_requirements", ["0-1 years"]),
        location=parsed_meta.get("location", ["India"]),
        documents_required=docs,
        questions=questions
    )
