from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from typing import Dict, Any, List
from backend.database import get_db
from backend.models import Student, JobPosting, Application
from backend.services.deadline_engine import evaluate_deadline

router = APIRouter(prefix="/extension", tags=["Extension Bridge"])

@router.get("/status")
def get_extension_status():
    return {
        "status": "online",
        "version": "1.0.0",
        "agent": "Haveloc Browser Agent"
    }

@router.get("/context/{student_id}")
def get_extension_context(student_id: str, db: Session = Depends(get_db)):
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    # Fetch active applications
    active_apps = (
        db.query(Application)
        .filter(Application.student_id == student_id)
        .all()
    )

    app_list = []
    for a in active_apps:
        job = a.job
        app_list.append({
            "application_id": a.id,
            "job_id": a.job_id,
            "haveloc_job_id": job.haveloc_job_id if job else None,
            "company": job.company if job else "",
            "state": a.state,
            "deadline": job.deadline.isoformat() if job else None
        })

    return {
        "student_id": student.id,
        "student_name": student.name,
        "active_applications": app_list
    }

@router.post("/dom-event")
def record_dom_event(
    event: str = Body(..., embed=True),
    details: Dict[str, Any] = Body(..., embed=True)
):
    """Logs browser content script telemetry (e.g. CAPTCHA detected, page navigated)."""
    return {"status": "recorded", "event": event}
