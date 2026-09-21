import uuid
import json
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import Student, StudentProfile, ResumeVariant, Achievement
from backend.schemas import StudentProfileCreate, ResumeVariantCreate, AchievementCreate

router = APIRouter(prefix="/student", tags=["Student Profile"])

@router.get("/{id}/profile")
def get_student_profile(id: str, db: Session = Depends(get_db)):
    student = db.query(Student).filter(Student.id == id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    profile = student.profile
    if not profile:
        raise HTTPException(status_code=404, detail="Student profile not configured")
    
    return {
        "student_id": student.id,
        "name": student.name,
        "email": student.email,
        "degree": profile.degree,
        "branch": profile.branch,
        "cgpa": profile.cgpa,
        "graduation_year": profile.graduation_year,
        "backlogs": profile.backlogs,
        "skills": profile.get_skills_list(),
        "preferences": profile.get_preferences_dict(),
        "updated_at": profile.updated_at.isoformat() if profile.updated_at else None
    }

@router.put("/{id}/profile")
def update_student_profile(id: str, payload: StudentProfileCreate, db: Session = Depends(get_db)):
    student = db.query(Student).filter(Student.id == id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    profile = student.profile
    if not profile:
        profile = StudentProfile(student_id=student.id)
        db.add(profile)
    
    profile.degree = payload.degree
    profile.branch = payload.branch
    profile.cgpa = payload.cgpa
    profile.graduation_year = payload.graduation_year
    profile.backlogs = payload.backlogs
    profile.skills = json.dumps(payload.skills)
    profile.preferences = json.dumps(payload.preferences)
    
    db.commit()
    return {"message": "Profile updated successfully"}

@router.get("/{id}/resumes")
def list_resumes(id: str, db: Session = Depends(get_db)):
    resumes = db.query(ResumeVariant).filter(ResumeVariant.student_id == id).all()
    return [
        {
            "id": r.id,
            "role_tag": r.role_tag,
            "file_reference": r.file_reference,
            "version": r.version,
            "skills": r.get_skills(),
            "experience_tags": r.get_experience_tags()
        }
        for r in resumes
    ]

@router.post("/{id}/resumes")
def add_resume(id: str, payload: ResumeVariantCreate, db: Session = Depends(get_db)):
    resume_id = payload.id or f"RES-{uuid.uuid4().hex[:6]}"
    resume = ResumeVariant(
        id=resume_id,
        student_id=id,
        role_tag=payload.role_tag,
        file_reference=payload.file_reference,
        version=payload.version,
        skills=json.dumps(payload.skills),
        experience_tags=json.dumps(payload.experience_tags),
        project_tags=json.dumps(payload.project_tags)
    )
    db.add(resume)
    db.commit()
    return {"message": "Resume added successfully", "resume_id": resume_id}

@router.get("/{id}/achievements")
def list_achievements(id: str, db: Session = Depends(get_db)):
    achs = db.query(Achievement).filter(Achievement.student_id == id).all()
    return [
        {
            "id": a.id,
            "project": a.project,
            "role": a.role,
            "metric": a.metric,
            "outcome": a.outcome,
            "tech_stack": a.get_tech_stack(),
            "verified": a.verified
        }
        for a in achs
    ]

@router.post("/{id}/achievements")
def add_achievement(id: str, payload: AchievementCreate, db: Session = Depends(get_db)):
    ach_id = payload.id or f"ACH-{uuid.uuid4().hex[:6]}"
    ach = Achievement(
        id=ach_id,
        student_id=id,
        project=payload.project,
        role=payload.role,
        metric=payload.metric,
        outcome=payload.outcome,
        tech_stack=json.dumps(payload.tech_stack),
        verified=payload.verified
    )
    db.add(ach)
    db.commit()
    return {"message": "Achievement recorded in bank", "achievement_id": ach_id}

@router.post("/register")
def register_student(payload: dict = Body(...), db: Session = Depends(get_db)):
    """
    General-purpose student registration for the Chrome extension setup wizard.
    Idempotent: creates or updates the student profile.
    """
    from backend.schemas import StudentRegistrationPayload
    reg = StudentRegistrationPayload(**payload)

    student_id = reg.registration_number.strip().upper()
    name_parts = reg.full_name.strip().split(" ", 1)
    first_name = name_parts[0] if name_parts else ""
    last_name = name_parts[1] if len(name_parts) > 1 else ""

    # Create or update Student
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        student = Student(
            id=student_id,
            name=reg.full_name.strip().upper(),
            email=reg.email.strip().lower(),
            notification_channel_id=f"fcm-token-{student_id}-chrome-ext"
        )
        db.add(student)
        db.flush()
    else:
        student.name = reg.full_name.strip().upper()
        student.email = reg.email.strip().lower()

    # Create or update Profile
    profile = student.profile
    if not profile:
        profile = StudentProfile(student_id=student.id)
        db.add(profile)

    profile.first_name = first_name
    profile.last_name = last_name
    profile.phone = reg.phone
    profile.degree = reg.degree
    profile.branch = reg.branch
    profile.specialization = reg.specialization or (reg.branch.split(" - ")[-1] if " - " in reg.branch else "")
    profile.cgpa = reg.cgpa
    profile.graduation_year = reg.graduation_year
    profile.backlogs = reg.backlogs
    profile.skills = json.dumps(reg.skills)
    profile.preferences = json.dumps({
        "willing_to_relocate": reg.willing_to_relocate,
        "phone": reg.phone,
        "email": reg.email
    })

    # Create resume variants if provided
    for rv in reg.resumes:
        res_id = rv.id or f"RES-{uuid.uuid4().hex[:6]}"
        existing_res = db.query(ResumeVariant).filter(ResumeVariant.id == res_id).first()
        if not existing_res:
            new_res = ResumeVariant(
                id=res_id,
                student_id=student.id,
                role_tag=rv.role_tag,
                file_reference=rv.file_reference,
                version=rv.version,
                skills=json.dumps(rv.skills),
                experience_tags=json.dumps(rv.experience_tags),
                project_tags=json.dumps(rv.project_tags)
            )
            db.add(new_res)

    db.commit()
    return {
        "message": "Student registered successfully",
        "student_id": student.id,
        "name": student.name,
        "email": student.email,
        "profile_complete": True
    }

