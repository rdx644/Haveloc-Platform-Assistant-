from typing import List
from backend.models import ResumeVariant
from backend.schemas import NormalizedRequirements, ResumeSelectionReport, ResumeRankItem

def select_best_resume(
    resumes: List[ResumeVariant],
    requirements: NormalizedRequirements,
    job_title: str = ""
) -> ResumeSelectionReport:
    """
    Deterministic rules-first resume selector.
    Evaluates role similarity, required skill overlap, and domain tags.
    """
    if not resumes:
        raise ValueError("Cannot select resume: Student profile has no registered resume variants.")

    ranked_items: List[ResumeRankItem] = []
    job_skills_lower = {s.lower() for s in requirements.skills}
    job_text_lower = (job_title + " " + " ".join(requirements.skills)).lower()

    for r in resumes:
        resume_skills = r.get_skills()
        resume_tags = r.get_experience_tags()
        
        # 1. Role tag match (0 to 40 pts)
        role_score = 0.0
        r_role = r.role_tag.lower().replace("_", " ")
        if r_role in job_text_lower:
            role_score = 40.0
        elif any(part in job_text_lower for part in r_role.split()):
            role_score = 25.0
        else:
            role_score = 10.0

        # 2. Skill match (0 to 40 pts)
        matched_skills = []
        for s in resume_skills:
            if s.lower() in job_skills_lower:
                matched_skills.append(s)
        
        skill_overlap_ratio = len(matched_skills) / max(len(job_skills_lower), 1)
        skill_score = min(skill_overlap_ratio * 40.0, 40.0)

        # 3. Tag match (0 to 20 pts)
        matched_tags = []
        for t in resume_tags:
            if t.lower() in job_text_lower:
                matched_tags.append(t)
        tag_score = min(len(matched_tags) * 10.0, 20.0)

        total_score = round(role_score + skill_score + tag_score, 2)
        rationale = (
            f"Role match: {role_score}/40, Matched skills ({len(matched_skills)}): {skill_score:.1f}/40, "
            f"Domain tags: {tag_score}/20."
        )

        ranked_items.append(ResumeRankItem(
            resume_id=r.id,
            role_tag=r.role_tag,
            file_reference=r.file_reference,
            score=total_score,
            matched_skills=matched_skills,
            matched_tags=matched_tags,
            rationale=rationale
        ))

    # Sort descending by score
    ranked_items.sort(key=lambda x: x.score, reverse=True)
    best = ranked_items[0]
    confidence = min(best.score / 100.0, 1.0)

    return ResumeSelectionReport(
        selected_resume_id=best.resume_id,
        selected_file_reference=best.file_reference,
        confidence=confidence,
        ranked_resumes=ranked_items
    )
