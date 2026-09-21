import uuid
import json
import datetime
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from backend.database import get_db
from backend.models import (
    Application, Student, StudentProfile, JobPosting, ResumeVariant,
    Achievement, ApplicationAnswer, SubmissionConfirmation
)
from backend.schemas import (
    SubmissionExecutionPayload, SubmissionConfirmationPayload
)
from backend.services.deadline_engine import evaluate_deadline, assert_deadline_valid_for_submission
from backend.services.eligibility_engine import evaluate_eligibility
from backend.services.normalization import normalize_job_data, compute_hash
from backend.services.resume_selector import select_best_resume
from backend.services.answer_engine import generate_grounded_answer
from backend.services.verification_engine import execute_pre_submission_verification
from backend.services.authorization_engine import (
    create_submission_authorization, validate_submission_authorization
)
from backend.services.state_machine import transition_state
from backend.services.audit_logger import log_application_event

router = APIRouter(prefix="/applications", tags=["Applications"])

@router.get("")
def list_applications(student_id: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(Application)
    if student_id:
        query = query.filter(Application.student_id == student_id)
    apps = query.order_by(Application.created_at.desc()).all()

    results = []
    for a in apps:
        job = a.job
        dead_info = evaluate_deadline(job.deadline) if job else None
        results.append({
            "id": a.id,
            "student_id": a.student_id,
            "job_id": a.job_id,
            "company": job.company if job else "Unknown",
            "title": job.title if job else "Unknown",
            "state": a.state,
            "resume_id": a.resume_id,
            "deadline_report": dead_info.model_dump() if dead_info else None,
            "created_at": a.created_at.isoformat() if a.created_at else None,
            "updated_at": a.updated_at.isoformat() if a.updated_at else None
        })
    return results

@router.get("/{id}")
def get_application_details(id: str, db: Session = Depends(get_db)):
    app = db.query(Application).filter(Application.id == id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    job = app.job
    resume = db.query(ResumeVariant).filter(ResumeVariant.id == app.resume_id).first() if app.resume_id else None
    answers = db.query(ApplicationAnswer).filter(ApplicationAnswer.application_id == app.id).all()
    events = [
        {
            "event_type": e.event_type,
            "timestamp": e.timestamp.isoformat(),
            "metadata": e.get_metadata()
        }
        for e in app.events
    ]

    conf = app.confirmation
    conf_data = None
    if conf:
        conf_data = {
            "portal_application_id": conf.portal_application_id,
            "confirmed_at": conf.confirmed_at.isoformat(),
            "evidence": conf.get_evidence()
        }

    return {
        "id": app.id,
        "student_id": app.student_id,
        "job_id": app.job_id,
        "company": job.company if job else "",
        "title": job.title if job else "",
        "state": app.state,
        "resume": {
            "id": resume.id,
            "role_tag": resume.role_tag,
            "file_reference": resume.file_reference
        } if resume else None,
        "application_hash": app.application_hash,
        "answers": [
            {
                "key": ans.question_key,
                "question": ans.question_text,
                "answer": ans.answer_text,
                "type": ans.question_type,
                "source": ans.source,
                "confidence": ans.confidence,
                "requires_review": ans.requires_review
            }
            for ans in answers
        ],
        "events": events,
        "confirmation": conf_data,
        "created_at": app.created_at.isoformat() if app.created_at else None
    }

@router.post("/initiate")
def initiate_application(
    student_id: str = Body(..., embed=True),
    job_id: str = Body(..., embed=True),
    autonomy_mode: Optional[str] = Body("CONFIRM", embed=True),
    db: Session = Depends(get_db)
):
    """
    Step 1-4 of Pipeline:
    Detects duplicate, checks deadline, verifies eligibility, selects resume, drafts grounded answers.
    Transitions: DISCOVERED -> PARSED -> ELIGIBILITY_CHECKED -> APPLICATION_PLANNED -> DRAFTED.
    """
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    profile = student.profile
    if not profile:
        raise HTTPException(status_code=400, detail="Student profile not configured")

    job = db.query(JobPosting).filter(JobPosting.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job posting not found")

    # 1. Duplicate Application Check
    existing_app = db.query(Application).filter(
        Application.student_id == student_id,
        Application.job_id == job_id
    ).first()

    if existing_app:
        if existing_app.state in ["COMPLETED", "SUBMISSION_CONFIRMED"]:
            raise HTTPException(
                status_code=409,
                detail=f"Duplicate rejected: Application already completed for job {job.haveloc_job_id}."
            )
        # Return existing ongoing application
        return {"message": "Application already in progress", "application_id": existing_app.id, "state": existing_app.state}

    # 2. Check Deadline
    deadline_report = evaluate_deadline(job.deadline)
    if deadline_report.is_expired:
        raise HTTPException(status_code=400, detail="Application deadline has already expired.")

    # 3. Create Application record in DISCOVERED
    app_id = f"APP-{uuid.uuid4().hex[:8]}"
    app = Application(
        id=app_id,
        student_id=student_id,
        job_id=job_id,
        state="DISCOVERED",
        autonomy_mode=autonomy_mode or "CONFIRM"
    )
    db.add(app)
    db.flush()
    log_application_event(db, app.id, "JOB_DISCOVERED", {"haveloc_job_id": job.haveloc_job_id})

    # 4. Parse & Normalize Requirements
    reqs = normalize_job_data(job.raw_snapshot, job.get_normalized())
    app.state = "PARSED"
    log_application_event(db, app.id, "JOB_PARSED", {"skills": reqs.skills, "min_cgpa": reqs.min_cgpa})

    # 5. Check Eligibility
    elig_report = evaluate_eligibility(profile, reqs)
    if not elig_report.eligible:
        app.state = "INELIGIBLE"
        db.commit()
        log_application_event(db, app.id, "ELIGIBILITY_FAILED", {"reasons": elig_report.failed_reasons})
        return {
            "application_id": app.id,
            "state": "INELIGIBLE",
            "eligible": False,
            "reasons": elig_report.failed_reasons
        }

    app.state = "ELIGIBILITY_CHECKED"
    log_application_event(db, app.id, "ELIGIBILITY_CHECKED", {"status": "PASS"})

    # 6. Select Resume
    resumes = student.resumes
    if not resumes:
        app.state = "REQUIRES_REVIEW"
        db.commit()
        raise HTTPException(status_code=400, detail="Student has no resume variants uploaded.")

    resume_report = select_best_resume(resumes, reqs, job.title)
    app.resume_id = resume_report.selected_resume_id
    app.state = "APPLICATION_PLANNED"
    log_application_event(db, app.id, "RESUME_SELECTED", {
        "resume_id": resume_report.selected_resume_id,
        "score": resume_report.confidence
    })

    # 7. Generate Grounded Answers
    achievements = student.achievements
    questions_to_ask = reqs.questions
    if not questions_to_ask:
        # Standard placement questions tailored to student profile
        questions_to_ask = [
            {"key": "cgpa_q", "text": "What is your current CGPA?"},
            {"key": "branch_q", "text": "Confirm your branch/department of study."},
            {"key": "skills_q", "text": "Which programming languages and core skills do you know?"},
            {"key": "project_q", "text": "Describe your most relevant project and its impact."},
            {"key": "why_company", "text": f"Why do you want to join {job.company}?"},
            {"key": "relocate_q", "text": "Are you willing to relocate to company office locations?"}
        ]

    for q in questions_to_ask:
        q_key = q.get("key", f"q_{uuid.uuid4().hex[:4]}")
        q_text = q.get("text", "")
        classified = generate_grounded_answer(
            question_key=q_key,
            question_text=q_text,
            student=student,
            profile=profile,
            achievements=achievements,
            company_name=job.company,
            job_title=job.title
        )
        ans_record = ApplicationAnswer(
            id=f"ANS-{uuid.uuid4().hex[:8]}",
            application_id=app.id,
            question_key=classified.key,
            question_text=classified.text,
            answer_text=classified.draft_answer,
            question_type=classified.question_type.value,
            source=classified.source,
            confidence=classified.confidence,
            requires_review=classified.requires_review
        )
        db.add(ans_record)

    app.state = "DRAFTED"
    log_application_event(db, app.id, "ANSWERS_GENERATED", {"questions_count": len(questions_to_ask)})
    db.commit()

    return {
        "message": "Application drafted successfully",
        "application_id": app.id,
        "state": app.state,
        "autonomy_mode": app.autonomy_mode,
        "selected_resume": resume_report.selected_file_reference,
        "questions_drafted": len(questions_to_ask)
    }

@router.post("/live-prepare")
def live_prepare_application(
    payload: dict = Body(...),
    db: Session = Depends(get_db)
):
    """
    100% Adaptable Real-time application preparation for https://placements.haveloc.com/.
    Scrapes or receives live job and form metadata, selects optimal resume,
    handles resume-only workflows (zero synthetic Q&A), and readies application.
    """
    student_id = payload.get("student_id")
    if not student_id:
        raise HTTPException(status_code=400, detail="student_id is required.")
    
    company = payload.get("company") or "Recruiting Partner"
    title = payload.get("title") or "Placement Opportunity"
    haveloc_job_id = payload.get("haveloc_job_id") or f"HVL-LIVE-{uuid.uuid4().hex[:6]}"
    raw_text = payload.get("raw_text") or f"{company} hiring for {title} on Haveloc portal."
    is_resume_only = payload.get("is_resume_only", False)
    detected_fields = payload.get("detected_fields") or []
    autonomy_mode = payload.get("autonomy_mode") or "CONFIRM"

    # 1. Verify Student Profile
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail=f"Student {student_id} not found")
    profile = student.profile
    if not profile:
        raise HTTPException(status_code=400, detail=f"Student profile incomplete")

    # 2. Ingest or fetch Job
    existing_job = db.query(JobPosting).filter(JobPosting.haveloc_job_id == haveloc_job_id).first()
    deadline_val = payload.get("deadline")
    if deadline_val:
        try:
            deadline = datetime.datetime.fromisoformat(deadline_val.replace("Z", "+00:00")) if isinstance(deadline_val, str) else deadline_val
        except Exception:
            deadline = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=72)
    else:
        deadline = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=72)

    parsed_meta = {
        "questions": detected_fields if not is_resume_only else [],
        "is_resume_only": is_resume_only
    }
    norm = normalize_job_data(raw_text, parsed_meta)
    snapshot_hash = compute_hash(raw_text)

    if existing_job:
        existing_job.title = title
        existing_job.company = company
        existing_job.raw_snapshot = raw_text
        existing_job.deadline = deadline
        existing_job.normalized_requirements = json.dumps(norm.model_dump())
        existing_job.snapshot_hash = snapshot_hash
        job = existing_job
    else:
        job = JobPosting(
            id=f"JOB-{uuid.uuid4().hex[:8]}",
            haveloc_job_id=haveloc_job_id,
            title=title,
            company=company,
            posted_at=datetime.datetime.now(datetime.timezone.utc),
            deadline=deadline,
            raw_snapshot=raw_text,
            normalized_requirements=json.dumps(norm.model_dump()),
            snapshot_hash=snapshot_hash
        )
        db.add(job)
    db.flush()

    # 3. Check / manage Application
    existing_app = db.query(Application).filter(Application.student_id == student_id, Application.job_id == job.id).first()
    if existing_app:
        if existing_app.state in ["COMPLETED", "SUBMISSION_CONFIRMED"]:
            raise HTTPException(status_code=409, detail=f"Duplicate rejected: Already submitted to {company}.")
        app = existing_app
        app.autonomy_mode = autonomy_mode
        # Clear previous answers if re-preparing
        for ans in app.answers:
            db.delete(ans)
        db.flush()
    else:
        app = Application(
            id=f"APP-{uuid.uuid4().hex[:8]}",
            student_id=student_id,
            job_id=job.id,
            state="DISCOVERED",
            autonomy_mode=autonomy_mode
        )
        db.add(app)
        db.flush()

    log_application_event(db, app.id, "LIVE_JOB_DISCOVERED", {"haveloc_job_id": haveloc_job_id, "is_resume_only": is_resume_only})

    # 4. Check Eligibility
    elig_report = evaluate_eligibility(profile, norm)
    if not elig_report.eligible:
        app.state = "INELIGIBLE"
        db.commit()
        log_application_event(db, app.id, "ELIGIBILITY_FAILED", {"reasons": elig_report.failed_reasons})
        return {
            "application_id": app.id,
            "state": "INELIGIBLE",
            "eligible": False,
            "reasons": elig_report.failed_reasons
        }

    # 5. Select Best Resume Variant
    resumes = student.resumes
    if not resumes:
        app.state = "REQUIRES_REVIEW"
        db.commit()
        raise HTTPException(status_code=400, detail="Student has no resume variants uploaded.")

    resume_report = select_best_resume(resumes, norm, job.title)
    app.resume_id = resume_report.selected_resume_id
    app.state = "APPLICATION_PLANNED"

    # 6. Generate Grounded Answers (if questions exist)
    generated_answers = []
    if not is_resume_only and detected_fields:
        for fld in detected_fields:
            q_key = fld.get("key") or fld.get("name") or fld.get("id") or f"q_{uuid.uuid4().hex[:4]}"
            q_text = fld.get("label") or fld.get("placeholder") or fld.get("text") or q_key
            classified = generate_grounded_answer(
                question_key=q_key,
                question_text=q_text,
                student=student,
                profile=profile,
                achievements=student.achievements,
                company_name=company,
                job_title=title
            )
            ans_record = ApplicationAnswer(
                id=f"ANS-{uuid.uuid4().hex[:8]}",
                application_id=app.id,
                question_key=classified.key,
                question_text=classified.text,
                answer_text=classified.draft_answer,
                question_type=classified.question_type.value,
                source=classified.source,
                confidence=classified.confidence,
                requires_review=classified.requires_review
            )
            db.add(ans_record)
            generated_answers.append({
                "key": classified.key,
                "question_key": classified.key,
                "text": classified.text,
                "question_text": classified.text,
                "answer": classified.draft_answer,
                "answer_text": classified.draft_answer,
                "source": classified.source,
                "requires_review": classified.requires_review
            })

    app.state = "DRAFTED"
    db.commit()

    selected_res = next((r for r in resumes if r.id == app.resume_id), None)

    return {
        "message": "Live application prepared successfully",
        "application_id": app.id,
        "state": app.state,
        "autonomy_mode": app.autonomy_mode,
        "is_resume_only": is_resume_only,
        "company": company,
        "title": title,
        "selected_resume": {
            "id": selected_res.id if selected_res else None,
            "role_tag": selected_res.role_tag if selected_res else None,
            "file_reference": selected_res.file_reference if selected_res else None,
            "version": selected_res.version if selected_res else None,
            "confidence": resume_report.confidence
        },
        "answers": generated_answers,
        "answers_count": len(generated_answers)
    }

@router.post("/turbo-prepare")
def turbo_prepare_application(
    payload: dict = Body(...),
    db: Session = Depends(get_db)
):
    """
    TURBO MODE: Single batched endpoint that performs the ENTIRE pipeline in one call.
    Combines: Job Ingestion + Eligibility + Resume Selection + Answer Generation +
    9-Point Verification + Authorization Token into ONE response.
    Eliminates 4 sequential API round-trips → ~80% latency reduction.
    """
    import time
    t_start = time.perf_counter()

    student_id = payload.get("student_id")
    scraped_profile = payload.get("scraped_profile")

    if scraped_profile and "roll_no" in scraped_profile:
        # Just-In-Time Registration
        roll_no = scraped_profile["roll_no"].upper()
        student_id = roll_no
        name = scraped_profile.get("name") or "Unknown Student"
        branch = scraped_profile.get("branch") or "Unknown Branch"
        cgpa = scraped_profile.get("cgpa") or 0.0

        student = db.query(Student).filter(Student.id == student_id).first()
        if not student:
            student = Student(
                id=student_id,
                name=name,
                email=f"{student_id.lower()}@student.srmist.edu.in",
                notification_channel_id=f"fcm-token-{student_id}-chrome-ext"
            )
            db.add(student)
            db.flush()
        else:
            student.name = name

        profile = student.profile
        if not profile:
            profile = StudentProfile(student_id=student.id)
            db.add(profile)
        
        name_parts = name.split(" ", 1)
        profile.first_name = name_parts[0] if name_parts else ""
        profile.last_name = name_parts[1] if len(name_parts) > 1 else ""
        profile.branch = branch
        profile.degree = "B.Tech"
        profile.cgpa = cgpa
        profile.graduation_year = 2027
        profile.skills = json.dumps(["Programming", branch])

        # Create/Update Resumes
        resumes = scraped_profile.get("resumes", [])
        for res in resumes:
            file_ref = res.get("file_reference")
            if not file_ref: continue
            
            existing = db.query(ResumeVariant).filter(ResumeVariant.student_id == student_id, ResumeVariant.file_reference == file_ref).first()
            if not existing:
                new_res = ResumeVariant(
                    id=f"RES-{uuid.uuid4().hex[:6]}",
                    student_id=student.id,
                    role_tag=res.get("role_tag", "general"),
                    file_reference=file_ref,
                    version=res.get("version", "1.0"),
                    skills=json.dumps(res.get("skills", [])),
                    experience_tags=json.dumps(res.get("experience_tags", [])),
                    project_tags=json.dumps(res.get("project_tags", []))
                )
                db.add(new_res)

        db.commit()

    if not student_id:
        raise HTTPException(status_code=400, detail="student_id could not be determined. Please ensure you are logged into Haveloc.")

    company = payload.get("company") or "Recruiting Partner"
    title = payload.get("title") or "Placement Opportunity"
    haveloc_job_id = payload.get("haveloc_job_id") or f"HVL-LIVE-{uuid.uuid4().hex[:6]}"
    raw_text = payload.get("raw_text") or f"{company} hiring for {title} on Haveloc portal."
    is_resume_only = payload.get("is_resume_only", False)
    detected_fields = payload.get("detected_fields") or []
    autonomy_mode = payload.get("autonomy_mode") or "CONFIRM"

    # 1. Verify Student
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail=f"Student {student_id} not found.")
    profile = student.profile
    if not profile:
        raise HTTPException(status_code=400, detail="Student profile incomplete.")

    # Build student_facts for frontend auto-fill (dynamic, not hardcoded)
    student_facts = {
        "roll_number": student.id,
        "registration_number": student.id,
        "full_name": student.name,
        "first_name": profile.first_name or student.name.split()[0] if student.name else "",
        "last_name": profile.last_name or (student.name.split()[-1] if len(student.name.split()) > 1 else ""),
        "email": student.email,
        "phone": profile.phone or "",
        "branch": profile.branch,
        "degree": profile.degree,
        "cgpa": str(profile.cgpa),
        "graduation_year": str(profile.graduation_year),
        "backlogs": str(profile.backlogs)
    }

    # 2. Ingest or fetch Job
    existing_job = db.query(JobPosting).filter(JobPosting.haveloc_job_id == haveloc_job_id).first()
    deadline_val = payload.get("deadline")
    if deadline_val:
        try:
            deadline = datetime.datetime.fromisoformat(deadline_val.replace("Z", "+00:00")) if isinstance(deadline_val, str) else deadline_val
        except Exception:
            deadline = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=72)
    else:
        deadline = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=72)

    parsed_meta = {
        "questions": detected_fields if not is_resume_only else [],
        "is_resume_only": is_resume_only
    }
    norm = normalize_job_data(raw_text, parsed_meta)
    snapshot_hash = compute_hash(raw_text)

    if existing_job:
        existing_job.title = title
        existing_job.company = company
        existing_job.raw_snapshot = raw_text
        existing_job.deadline = deadline
        existing_job.normalized_requirements = json.dumps(norm.model_dump())
        existing_job.snapshot_hash = snapshot_hash
        job = existing_job
    else:
        job = JobPosting(
            id=f"JOB-{uuid.uuid4().hex[:8]}",
            haveloc_job_id=haveloc_job_id,
            title=title,
            company=company,
            posted_at=datetime.datetime.now(datetime.timezone.utc),
            deadline=deadline,
            raw_snapshot=raw_text,
            normalized_requirements=json.dumps(norm.model_dump()),
            snapshot_hash=snapshot_hash
        )
        db.add(job)
    db.flush()

    # 3. Create / fetch Application
    existing_app = db.query(Application).filter(Application.student_id == student_id, Application.job_id == job.id).first()
    if existing_app:
        if existing_app.state in ["COMPLETED", "SUBMISSION_CONFIRMED"]:
            raise HTTPException(status_code=409, detail=f"Duplicate rejected: Already submitted to {company}.")
        app = existing_app
        app.autonomy_mode = autonomy_mode
        for ans in app.answers:
            db.delete(ans)
        db.flush()
    else:
        app = Application(
            id=f"APP-{uuid.uuid4().hex[:8]}",
            student_id=student_id,
            job_id=job.id,
            state="DISCOVERED",
            autonomy_mode=autonomy_mode
        )
        db.add(app)
        db.flush()

    log_application_event(db, app.id, "TURBO_PREPARE_STARTED", {"haveloc_job_id": haveloc_job_id, "is_resume_only": is_resume_only})

    # 4. Eligibility Check
    elig_report = evaluate_eligibility(profile, norm)
    if not elig_report.eligible:
        app.state = "INELIGIBLE"
        db.commit()
        t_elapsed = (time.perf_counter() - t_start) * 1000
        return {
            "application_id": app.id,
            "state": "INELIGIBLE",
            "is_resume_only": is_resume_only,
            "company": company,
            "title": title,
            "autonomy_mode": autonomy_mode,
            "student_facts": student_facts,
            "eligible": False,
            "reasons": elig_report.failed_reasons,
            "all_verified": False,
            "pipeline_ms": round(t_elapsed, 1)
        }

    # 5. Select Best Resume
    resumes = student.resumes
    if not resumes:
        app.state = "REQUIRES_REVIEW"
        db.commit()
        raise HTTPException(status_code=400, detail="No resume variants found. Add resumes in the setup wizard.")

    resume_report = select_best_resume(resumes, norm, job.title)
    app.resume_id = resume_report.selected_resume_id

    # 6. Generate Grounded Answers (skip for resume-only)
    generated_answers = []
    if not is_resume_only and detected_fields:
        non_standard_fields = [f for f in detected_fields if not f.get("is_standard", False)]
        for fld in non_standard_fields:
            q_key = fld.get("key") or fld.get("name") or fld.get("id") or f"q_{uuid.uuid4().hex[:4]}"
            q_text = fld.get("label") or fld.get("placeholder") or fld.get("text") or q_key
            classified = generate_grounded_answer(
                question_key=q_key,
                question_text=q_text,
                student=student,
                profile=profile,
                achievements=student.achievements,
                company_name=company,
                job_title=title
            )
            ans_record = ApplicationAnswer(
                id=f"ANS-{uuid.uuid4().hex[:8]}",
                application_id=app.id,
                question_key=classified.key,
                question_text=classified.text,
                answer_text=classified.draft_answer,
                question_type=classified.question_type.value,
                source=classified.source,
                confidence=classified.confidence,
                requires_review=classified.requires_review
            )
            db.add(ans_record)
            generated_answers.append({
                "key": classified.key,
                "question_key": classified.key,
                "text": classified.text,
                "answer": classified.draft_answer,
                "answer_text": classified.draft_answer,
                "source": classified.source,
                "requires_review": classified.requires_review
            })

    app.state = "DRAFTED"
    db.flush()

    # 7. Run 9-Point Verification (inline, no separate API call)
    verification_report = execute_pre_submission_verification(db, app.id)

    # 8. If all verified, issue authorization token (inline)
    auth_token = None
    if verification_report.all_passed:
        try:
            auth_payload = create_submission_authorization(db, app.id)
            auth_token = auth_payload.auth_token
            log_application_event(db, app.id, "TURBO_AUTHORIZED", {"auth_token_prefix": auth_token[:10] + "..."})
        except ValueError:
            pass  # Authorization failed, user must review

    db.commit()

    selected_res = next((r for r in resumes if r.id == app.resume_id), None)
    t_elapsed = (time.perf_counter() - t_start) * 1000

    log_application_event(db, app.id, "TURBO_PREPARE_COMPLETE", {"pipeline_ms": round(t_elapsed, 1), "all_verified": verification_report.all_passed})

    return {
        "application_id": app.id,
        "state": app.state,
        "is_resume_only": is_resume_only,
        "company": company,
        "title": title,
        "autonomy_mode": app.autonomy_mode,
        "student_facts": student_facts,
        "selected_resume": {
            "id": selected_res.id if selected_res else None,
            "role_tag": selected_res.role_tag if selected_res else None,
            "file_reference": selected_res.file_reference if selected_res else None,
            "version": selected_res.version if selected_res else None,
            "confidence": resume_report.confidence
        },
        "answers": generated_answers,
        "answers_count": len(generated_answers),
        "verification_report": {
            "all_passed": verification_report.all_passed,
            "application_hash": verification_report.application_hash,
            "gate_checks": [
                {"gate_name": g.check_name, "passed": g.passed, "details": g.details}
                for g in verification_report.gate_checks
            ],
            "failure_messages": verification_report.failure_messages
        },
        "auth_token": auth_token,
        "application_hash": verification_report.application_hash,
        "all_verified": verification_report.all_passed,
        "pipeline_ms": round(t_elapsed, 1)
    }

@router.post("/{id}/read-back-verify")
def read_back_verify(
    id: str,
    payload: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db)
):
    """Phase 12: Reads form fields back from DOM and checks for FIELD_MISMATCH."""
    from backend.services.read_back_validator import validate_form_read_back
    filled_map = payload.get("filled_fields", {})
    report = validate_form_read_back(db, id, filled_map)
    log_application_event(db, id, "READ_BACK_VERIFICATION", {
        "passed": report.passed,
        "mismatches": report.mismatches
    })
    return report

@router.post("/{id}/fill")
def mark_form_filled(id: str, db: Session = Depends(get_db)):
    """Extension notifies backend that form fields have been populated."""
    app = db.query(Application).filter(Application.id == id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    transition_state(app.state, "FORM_FILLED")
    app.state = "FORM_FILLED"
    log_application_event(db, app.id, "FORM_FILLED")
    db.commit()
    return {"message": "State updated to FORM_FILLED", "application_id": app.id}

@router.post("/{id}/verify")
def verify_application(id: str, db: Session = Depends(get_db)):
    """Runs the 9-point Pre-Submission Verification Gate."""
    report = execute_pre_submission_verification(db, id)
    log_application_event(db, id, "PRE_SUBMISSION_VERIFIED", {
        "all_passed": report.all_passed,
        "application_hash": report.application_hash
    })
    return report

@router.post("/{id}/authorize")
def authorize_application(id: str, db: Session = Depends(get_db)):
    """Issues short-lived submission authorization token."""
    try:
        auth_payload = create_submission_authorization(db, id)
        log_application_event(db, id, "SUBMISSION_AUTHORIZED", {
            "expires_at": auth_payload.expires_at.isoformat()
        })
        return auth_payload
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{id}/submit")
def prepare_submission_payload(
    id: str,
    payload: SubmissionExecutionPayload,
    db: Session = Depends(get_db)
):
    """
    Submits application authorization verification and final deadline recheck.
    Transitions state to SUBMITTING.
    """
    app = db.query(Application).filter(Application.id == id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    job = app.job
    # 1. Final Deadline Recheck immediately before submission
    try:
        assert_deadline_valid_for_submission(job.deadline)
    except ValueError as e:
        app.state = "EXPIRED"
        db.commit()
        raise HTTPException(status_code=400, detail=str(e))

    # 2. Validate Authorization Token & Integrity Hash
    try:
        validate_submission_authorization(
            db=db,
            application_id=app.id,
            auth_token=payload.auth_token,
            current_application_hash=payload.application_hash
        )
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))

    transition_state(app.state, "SUBMITTING")
    app.state = "SUBMITTING"
    log_application_event(db, app.id, "SUBMITTING")
    db.commit()

    return {
        "message": "Submission authorized and underway in browser session",
        "application_id": app.id,
        "state": app.state
    }

@router.post("/{id}/confirm")
def confirm_submission(
    id: str,
    payload: SubmissionConfirmationPayload,
    db: Session = Depends(get_db)
):
    """
    Step 11: Submission Confirmation.
    Captures portal confirmation receipt and Application ID.
    Transitions state from SUBMITTING -> SUBMISSION_CONFIRMED -> COMPLETED.
    """
    app = db.query(Application).filter(Application.id == id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    if app.state != "SUBMITTING":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot confirm submission: Application is in '{app.state}', must be 'SUBMITTING'."
        )

    # Check if status code indicates network timeout / portal server error / ambiguous response
    if payload.status_code in [500, 502, 503, 504, 0]:
        transition_state(app.state, "SUBMISSION_UNKNOWN")
        app.state = "SUBMISSION_UNKNOWN"
        log_application_event(db, app.id, "SUBMISSION_UNKNOWN", {
            "status_code": payload.status_code,
            "evidence": payload.confirmation_evidence
        })
        db.commit()
        return {
            "message": "Submission status ambiguous. Marked SUBMISSION_UNKNOWN to strictly prohibit auto-retries.",
            "application_id": app.id,
            "state": "SUBMISSION_UNKNOWN",
            "retry_prohibited": True
        }

    # Record Confirmation Evidence
    conf = SubmissionConfirmation(
        id=f"CONF-{uuid.uuid4().hex[:8]}",
        application_id=app.id,
        portal_application_id=payload.portal_application_id,
        evidence=json.dumps(payload.confirmation_evidence)
    )
    db.add(conf)

    transition_state(app.state, "SUBMISSION_CONFIRMED")
    app.state = "SUBMISSION_CONFIRMED"
    log_application_event(db, app.id, "SUBMISSION_CONFIRMED", {
        "portal_application_id": payload.portal_application_id
    })

    # Move to COMPLETED
    transition_state(app.state, "COMPLETED")
    app.state = "COMPLETED"
    log_application_event(db, app.id, "COMPLETED")

    db.commit()
    return {
        "message": "Submission confirmed by portal. Application marked COMPLETED.",
        "application_id": app.id,
        "portal_application_id": payload.portal_application_id,
        "state": "COMPLETED"
    }

@router.post("/{id}/resolve-review")
def resolve_review(
    id: str,
    question_key: str = Body(..., embed=True),
    confirmed_answer: str = Body(..., embed=True),
    db: Session = Depends(get_db)
):
    """Allows student to confirm or override sensitive question responses."""
    app = db.query(Application).filter(Application.id == id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    ans = (
        db.query(ApplicationAnswer)
        .filter(ApplicationAnswer.application_id == id, ApplicationAnswer.question_key == question_key)
        .first()
    )
    if not ans:
        raise HTTPException(status_code=404, detail="Question key not found")

    ans.answer_text = confirmed_answer
    ans.requires_review = False
    ans.source = "STUDENT_MANUAL"
    ans.confidence = 1.0

    # If all answers reviewed, reset state to DRAFTED/FORM_FILLED for re-verification
    unresolved = (
        db.query(ApplicationAnswer)
        .filter(ApplicationAnswer.application_id == id, ApplicationAnswer.requires_review == True)
        .count()
    )
    if unresolved == 0 and app.state in ["REQUIRES_REVIEW", "VERIFICATION_FAILED"]:
        app.state = "DRAFTED"

    db.commit()
    return {"message": "Question review resolved", "question_key": question_key, "remaining_reviews": unresolved}
