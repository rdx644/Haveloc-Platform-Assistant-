from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import Student, StudentProfile
from backend.schemas import StudentCreate

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register")
def register_student(payload: StudentCreate, db: Session = Depends(get_db)):
    existing = db.query(Student).filter(Student.email == payload.email).first()
    if existing:
        return {"message": "Student already registered", "student_id": existing.id}

    student = Student(
        id=payload.id,
        name=payload.name,
        email=payload.email,
        notification_channel_id=payload.notification_channel_id
    )
    db.add(student)
    db.flush()

    if payload.profile:
        import json
        prof = StudentProfile(
            student_id=student.id,
            degree=payload.profile.degree,
            branch=payload.profile.branch,
            cgpa=payload.profile.cgpa,
            graduation_year=payload.profile.graduation_year,
            backlogs=payload.profile.backlogs,
            skills=json.dumps(payload.profile.skills),
            preferences=json.dumps(payload.profile.preferences)
        )
        db.add(prof)

    db.commit()
    return {"message": "Student registered successfully", "student_id": student.id}

@router.get("/me/{student_id}")
def get_current_student(student_id: str, db: Session = Depends(get_db)):
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    return {
        "id": student.id,
        "name": student.name,
        "email": student.email,
        "notification_channel_id": student.notification_channel_id
    }
