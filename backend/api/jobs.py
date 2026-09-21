import uuid
import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from backend.database import get_db
from backend.models import JobPosting
from backend.schemas import JobPostingCreate, JobPostingResponse
from backend.services.normalization import compute_hash, normalize_job_data
from backend.services.deadline_engine import evaluate_deadline

router = APIRouter(prefix="/jobs", tags=["Jobs"])

@router.post("/ingest", response_model=JobPostingResponse)
def ingest_job(payload: JobPostingCreate, db: Session = Depends(get_db)):
    """
    Ingests or updates a job posting from feed, polling, or browser detection.
    Deduplicates based on haveloc_job_id.
    """
    snapshot_hash = compute_hash(payload.raw_snapshot)
    existing = db.query(JobPosting).filter(JobPosting.haveloc_job_id == payload.haveloc_job_id).first()

    norm_dict = payload.normalized_requirements.model_dump()

    if existing:
        # Check if updated
        if existing.snapshot_hash != snapshot_hash:
            existing.title = payload.title
            existing.company = payload.company
            existing.deadline = payload.deadline
            existing.raw_snapshot = payload.raw_snapshot
            existing.normalized_requirements = json.dumps(norm_dict)
            existing.snapshot_hash = snapshot_hash
            db.commit()
            db.refresh(existing)
        return JobPostingResponse(
            id=existing.id,
            haveloc_job_id=existing.haveloc_job_id,
            title=existing.title,
            company=existing.company,
            posted_at=existing.posted_at,
            deadline=existing.deadline,
            normalized_requirements=existing.get_normalized(),
            snapshot_hash=existing.snapshot_hash,
            first_seen_at=existing.first_seen_at
        )

    job_id = f"JOB-{uuid.uuid4().hex[:8]}"
    new_job = JobPosting(
        id=job_id,
        haveloc_job_id=payload.haveloc_job_id,
        title=payload.title,
        company=payload.company,
        posted_at=payload.posted_at,
        deadline=payload.deadline,
        raw_snapshot=payload.raw_snapshot,
        normalized_requirements=json.dumps(norm_dict),
        snapshot_hash=snapshot_hash
    )
    db.add(new_job)
    db.commit()
    db.refresh(new_job)

    return JobPostingResponse(
        id=new_job.id,
        haveloc_job_id=new_job.haveloc_job_id,
        title=new_job.title,
        company=new_job.company,
        posted_at=new_job.posted_at,
        deadline=new_job.deadline,
        normalized_requirements=new_job.get_normalized(),
        snapshot_hash=new_job.snapshot_hash,
        first_seen_at=new_job.first_seen_at
    )

@router.get("", response_model=List[dict])
def list_jobs(db: Session = Depends(get_db)):
    jobs = db.query(JobPosting).order_by(JobPosting.posted_at.desc()).all()
    results = []
    for j in jobs:
        dead_info = evaluate_deadline(j.deadline)
        results.append({
            "id": j.id,
            "haveloc_job_id": j.haveloc_job_id,
            "title": j.title,
            "company": j.company,
            "posted_at": j.posted_at.isoformat(),
            "deadline": j.deadline.isoformat(),
            "deadline_report": dead_info.model_dump(),
            "normalized_requirements": j.get_normalized()
        })
    return results

@router.get("/{id}")
def get_job(id: str, db: Session = Depends(get_db)):
    job = db.query(JobPosting).filter(JobPosting.id == id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job posting not found")
    dead_info = evaluate_deadline(job.deadline)
    return {
        "id": job.id,
        "haveloc_job_id": job.haveloc_job_id,
        "title": job.title,
        "company": job.company,
        "posted_at": job.posted_at.isoformat(),
        "deadline": job.deadline.isoformat(),
        "deadline_report": dead_info.model_dump(),
        "normalized_requirements": job.get_normalized(),
        "snapshot_hash": job.snapshot_hash
    }

@router.post("/live-discover")
def live_discover_job(
    payload: dict,
    db: Session = Depends(get_db)
):
    """
    Real-time dynamic ingestion of jobs scraped directly from https://placements.haveloc.com/.
    No pre-seeding needed. Automatically registers or updates the live posting.
    """
    import datetime
    haveloc_job_id = payload.get("haveloc_job_id") or f"HVL-LIVE-{uuid.uuid4().hex[:6]}"
    title = payload.get("title") or "Placement Opportunity"
    company = payload.get("company") or "Recruiting Partner"
    raw_text = payload.get("raw_text") or f"{company} hiring for {title} on Haveloc portal."
    
    # Parse deadline or default to 72 hours from now
    deadline_val = payload.get("deadline")
    if deadline_val:
        try:
            if isinstance(deadline_val, str):
                deadline = datetime.datetime.fromisoformat(deadline_val.replace("Z", "+00:00"))
            else:
                deadline = deadline_val
        except Exception:
            deadline = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=72)
    else:
        deadline = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=72)

    is_resume_only = payload.get("is_resume_only", False)
    questions = [] if is_resume_only else (payload.get("questions") or [])

    parsed_meta = {
        "questions": questions,
        "is_resume_only": is_resume_only
    }

    norm = normalize_job_data(raw_text, parsed_meta)
    snapshot_hash = compute_hash(raw_text)

    existing = db.query(JobPosting).filter(JobPosting.haveloc_job_id == haveloc_job_id).first()
    if existing:
        existing.title = title
        existing.company = company
        existing.raw_snapshot = raw_text
        existing.deadline = deadline
        existing.normalized_requirements = json.dumps(norm.model_dump())
        existing.snapshot_hash = snapshot_hash
        db.commit()
        db.refresh(existing)
        target_job = existing
    else:
        job_id = f"JOB-{uuid.uuid4().hex[:8]}"
        target_job = JobPosting(
            id=job_id,
            haveloc_job_id=haveloc_job_id,
            title=title,
            company=company,
            posted_at=datetime.datetime.now(datetime.timezone.utc),
            deadline=deadline,
            raw_snapshot=raw_text,
            normalized_requirements=json.dumps(norm.model_dump()),
            snapshot_hash=snapshot_hash
        )
        db.add(target_job)
        db.commit()
        db.refresh(target_job)

    dead_info = evaluate_deadline(target_job.deadline)
    norm_dict = target_job.get_normalized()
    return {
        "discovered": True,
        "id": target_job.id,
        "job_id": target_job.haveloc_job_id,
        "haveloc_job_id": target_job.haveloc_job_id,
        "title": target_job.title,
        "company": target_job.company,
        "deadline": target_job.deadline.isoformat(),
        "deadline_report": dead_info.model_dump(),
        "normalized_requirements": norm_dict,
        "min_cgpa": norm_dict.get("min_cgpa", 0.0),
        "branch_requirements": norm_dict.get("branch_requirements", []),
        "allowed_branches": norm_dict.get("branch_requirements", []),
        "is_resume_only": is_resume_only
    }


