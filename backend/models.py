import datetime
import json
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, Text, ForeignKey, UniqueConstraint, Index
)
from sqlalchemy.orm import relationship
from backend.database import Base

def utcnow():
    return datetime.datetime.now(datetime.timezone.utc)

class Student(Base):
    __tablename__ = "students"

    id = Column(String(64), primary_key=True, index=True)
    name = Column(String(128), nullable=False)
    email = Column(String(128), unique=True, index=True, nullable=False)
    notification_channel_id = Column(String(128), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    profile = relationship("StudentProfile", back_populates="student", uselist=False, cascade="all, delete-orphan")
    resumes = relationship("ResumeVariant", back_populates="student", cascade="all, delete-orphan")
    achievements = relationship("Achievement", back_populates="student", cascade="all, delete-orphan")
    applications = relationship("Application", back_populates="student", cascade="all, delete-orphan")

class StudentProfile(Base):
    __tablename__ = "student_profiles"

    student_id = Column(String(64), ForeignKey("students.id"), primary_key=True)
    first_name = Column(String(64), default="")
    last_name = Column(String(64), default="")
    phone = Column(String(32), default="")
    degree = Column(String(64), nullable=False) # e.g. "B.Tech"
    branch = Column(String(128), nullable=False) # e.g. "Computer Science and Engineering - Cloud Computing"
    specialization = Column(String(64), default="Cloud Computing")
    cgpa = Column(Float, nullable=False)        # e.g. 8.85
    graduation_year = Column(Integer, nullable=False) # e.g. 2027
    backlogs = Column(Integer, default=0, nullable=False)
    skills = Column(Text, default="[]") # JSON list of strings
    preferences = Column(Text, default="{}") # JSON dict
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    student = relationship("Student", back_populates="profile")

    def get_skills_list(self):
        try:
            return json.loads(self.skills)
        except Exception:
            return []

    def get_preferences_dict(self):
        try:
            return json.loads(self.preferences)
        except Exception:
            return {}

class ResumeVariant(Base):
    __tablename__ = "resume_variants"

    id = Column(String(64), primary_key=True, index=True)
    student_id = Column(String(64), ForeignKey("students.id"), nullable=False)
    role_tag = Column(String(64), nullable=False) # e.g. "software_engineer", "cloud_devops", "data_science"
    file_reference = Column(String(256), nullable=False) # e.g. "resume_sde_v2.pdf"
    version = Column(String(32), default="1.0")
    skills = Column(Text, default="[]") # JSON list
    experience_tags = Column(Text, default="[]") # JSON list
    project_tags = Column(Text, default="[]") # JSON list
    metadata_json = Column(Text, default="{}")

    student = relationship("Student", back_populates="resumes")

    def get_skills(self):
        try:
            return json.loads(self.skills)
        except Exception:
            return []

    def get_experience_tags(self):
        try:
            return json.loads(self.experience_tags)
        except Exception:
            return []

class Achievement(Base):
    __tablename__ = "achievement_bank"

    id = Column(String(64), primary_key=True, index=True)
    student_id = Column(String(64), ForeignKey("students.id"), nullable=False)
    project = Column(String(256), nullable=False)
    role = Column(String(128), default="Developer")
    metric = Column(String(256), nullable=True) # e.g. "Reduced API latency by 45%"
    outcome = Column(Text, nullable=False) # e.g. "Built distributed ingestion service handling 10k req/s"
    tech_stack = Column(Text, default="[]") # JSON list
    verified = Column(Boolean, default=True)

    student = relationship("Student", back_populates="achievements")

    def get_tech_stack(self):
        try:
            return json.loads(self.tech_stack)
        except Exception:
            return []

class JobPosting(Base):
    __tablename__ = "job_postings"

    id = Column(String(64), primary_key=True, index=True)
    haveloc_job_id = Column(String(64), unique=True, index=True, nullable=False)
    title = Column(String(256), nullable=False)
    company = Column(String(256), nullable=False)
    posted_at = Column(DateTime(timezone=True), nullable=False)
    deadline = Column(DateTime(timezone=True), nullable=False)
    raw_snapshot = Column(Text, nullable=False)
    normalized_requirements = Column(Text, nullable=False) # JSON dict
    snapshot_hash = Column(String(64), nullable=False) # SHA-256 hash of raw snapshot
    first_seen_at = Column(DateTime(timezone=True), default=utcnow)

    applications = relationship("Application", back_populates="job", cascade="all, delete-orphan")

    def get_normalized(self):
        try:
            return json.loads(self.normalized_requirements)
        except Exception:
            return {}

class Application(Base):
    __tablename__ = "applications"

    id = Column(String(64), primary_key=True, index=True)
    student_id = Column(String(64), ForeignKey("students.id"), nullable=False)
    job_id = Column(String(64), ForeignKey("job_postings.id"), nullable=False)
    state = Column(String(64), default="DISCOVERED", index=True, nullable=False)
    autonomy_mode = Column(String(32), default="CONFIRM") # ASSIST, CONFIRM, AUTONOMOUS
    resume_id = Column(String(64), nullable=True)
    application_hash = Column(String(64), nullable=True) # SHA-256 integrity hash
    haveloc_application_id = Column(String(128), nullable=True) # Portal confirmation ID
    submission_attempt_id = Column(String(64), nullable=True)
    started_at = Column(DateTime(timezone=True), default=utcnow)
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    __table_args__ = (
        UniqueConstraint("student_id", "job_id", name="uq_student_job"),
    )

    student = relationship("Student", back_populates="applications")
    job = relationship("JobPosting", back_populates="applications")
    answers = relationship("ApplicationAnswer", back_populates="application", cascade="all, delete-orphan")
    events = relationship("ApplicationEvent", back_populates="application", cascade="all, delete-orphan")
    authorizations = relationship("SubmissionAuthorization", back_populates="application", cascade="all, delete-orphan")
    confirmation = relationship("SubmissionConfirmation", back_populates="application", uselist=False, cascade="all, delete-orphan")

class ApplicationAnswer(Base):
    __tablename__ = "application_answers"

    id = Column(String(64), primary_key=True, index=True)
    application_id = Column(String(64), ForeignKey("applications.id"), nullable=False)
    question_key = Column(String(128), nullable=False)
    question_text = Column(Text, nullable=False)
    answer_text = Column(Text, nullable=False)
    question_type = Column(String(32), nullable=False) # TYPE_A, TYPE_B, TYPE_C, TYPE_D, TYPE_E
    source = Column(String(64), nullable=False) # PROFILE, SKILLS, ACHIEVEMENT_BANK, LLM_SYNTHESIS, STUDENT_MANUAL
    confidence = Column(Float, default=1.0)
    requires_review = Column(Boolean, default=False)

    application = relationship("Application", back_populates="answers")

class ApplicationEvent(Base):
    __tablename__ = "application_events"

    id = Column(String(64), primary_key=True, index=True)
    application_id = Column(String(64), ForeignKey("applications.id"), nullable=False)
    event_type = Column(String(64), index=True, nullable=False)
    timestamp = Column(DateTime(timezone=True), default=utcnow)
    metadata_json = Column(Text, default="{}")

    application = relationship("Application", back_populates="events")

    def get_metadata(self):
        try:
            return json.loads(self.metadata_json)
        except Exception:
            return {}

class SubmissionAuthorization(Base):
    __tablename__ = "submission_authorizations"

    id = Column(String(64), primary_key=True, index=True)
    application_id = Column(String(64), ForeignKey("applications.id"), nullable=False)
    application_hash = Column(String(64), nullable=False)
    auth_token = Column(String(256), nullable=False, unique=True)
    verified_at = Column(DateTime(timezone=True), default=utcnow)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    status = Column(String(32), default="AUTHORIZED") # AUTHORIZED, USED, EXPIRED, REVOKED

    application = relationship("Application", back_populates="authorizations")

class SubmissionConfirmation(Base):
    __tablename__ = "submission_confirmations"

    id = Column(String(64), primary_key=True, index=True)
    application_id = Column(String(64), ForeignKey("applications.id"), unique=True, nullable=False)
    portal_application_id = Column(String(128), nullable=False)
    confirmed_at = Column(DateTime(timezone=True), default=utcnow)
    evidence = Column(Text, default="{}") # JSON containing response headers, confirmation snapshot, status code

    application = relationship("Application", back_populates="confirmation")

    def get_evidence(self):
        try:
            return json.loads(self.evidence)
        except Exception:
            return {}
