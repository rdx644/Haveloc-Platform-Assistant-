from pydantic import BaseModel, Field, ConfigDict

# ...
from typing import List, Dict, Optional, Any
from datetime import datetime
from enum import Enum

class UrgencyLevel(str, Enum):
    NORMAL = "NORMAL"
    URGENT = "URGENT"
    CRITICAL = "CRITICAL"
    EXPIRED = "EXPIRED"

class AutonomyMode(str, Enum):
    ASSIST = "ASSIST"
    CONFIRM = "CONFIRM"
    AUTONOMOUS = "AUTONOMOUS"

class ApplicationState(str, Enum):
    DISCOVERED = "DISCOVERED"
    PARSED = "PARSED"
    ELIGIBILITY_CHECKED = "ELIGIBILITY_CHECKED"
    APPLICATION_PLANNED = "APPLICATION_PLANNED"
    PLANNED = "PLANNED"
    DRAFTED = "DRAFTED"
    FORM_FILLED = "FORM_FILLED"
    PRE_SUBMISSION_VERIFIED = "PRE_SUBMISSION_VERIFIED"
    SUBMISSION_AUTHORIZED = "SUBMISSION_AUTHORIZED"
    SUBMITTING = "SUBMITTING"
    SUBMISSION_CONFIRMED = "SUBMISSION_CONFIRMED"
    COMPLETED = "COMPLETED"
    
    # Failure & uncertain states
    INELIGIBLE = "INELIGIBLE"
    EXPIRED = "EXPIRED"
    REQUIRES_REVIEW = "REQUIRES_REVIEW"
    CAPTCHA_REQUIRED = "CAPTCHA_REQUIRED"
    SUBMISSION_FAILED = "SUBMISSION_FAILED"
    PORTAL_ERROR = "PORTAL_ERROR"
    FIELD_MISMATCH = "FIELD_MISMATCH"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    SUBMISSION_UNKNOWN = "SUBMISSION_UNKNOWN"

class QuestionType(str, Enum):
    TYPE_A = "TYPE_A"  # Deterministic (e.g. CGPA, Roll No)
    TYPE_B = "TYPE_B"  # Profile-based (e.g. Skills list)
    TYPE_C = "TYPE_C"  # Experience-based (e.g. Project description)
    TYPE_D = "TYPE_D"  # Open-ended (e.g. Why Join)
    TYPE_E = "TYPE_E"  # Sensitive / Consequential (e.g. Relocate, Bonds)

# Normalized Job Requirements
class NormalizedRequirements(BaseModel):
    degree_requirements: List[str] = Field(default_factory=list)
    branch_requirements: List[str] = Field(default_factory=list)
    min_cgpa: Optional[float] = None
    max_backlogs: int = 0
    graduation_years: List[int] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)
    experience_requirements: List[str] = Field(default_factory=list)
    location: List[str] = Field(default_factory=list)
    documents_required: List[str] = Field(default_factory=list)
    questions: List[Dict[str, Any]] = Field(default_factory=list)

class JobPostingCreate(BaseModel):
    haveloc_job_id: str
    title: str
    company: str
    posted_at: datetime
    deadline: datetime
    raw_snapshot: str
    normalized_requirements: NormalizedRequirements

class JobPostingResponse(BaseModel):
    id: str
    haveloc_job_id: str
    title: str
    company: str
    posted_at: datetime
    deadline: datetime
    normalized_requirements: Dict[str, Any]
    snapshot_hash: str
    first_seen_at: datetime

    model_config = ConfigDict(from_attributes=True)

# Student & Profile
class StudentProfileCreate(BaseModel):
    degree: str
    branch: str
    cgpa: float
    graduation_year: int
    backlogs: int = 0
    skills: List[str] = Field(default_factory=list)
    preferences: Dict[str, Any] = Field(default_factory=dict)

class StudentCreate(BaseModel):
    id: str
    name: str
    email: str
    notification_channel_id: Optional[str] = None
    profile: Optional[StudentProfileCreate] = None

class ResumeVariantCreate(BaseModel):
    id: Optional[str] = None
    role_tag: str
    file_reference: str
    version: str = "1.0"
    skills: List[str] = Field(default_factory=list)
    experience_tags: List[str] = Field(default_factory=list)
    project_tags: List[str] = Field(default_factory=list)

class AchievementCreate(BaseModel):
    id: Optional[str] = None
    project: str
    role: str = "Developer"
    metric: Optional[str] = None
    outcome: str
    tech_stack: List[str] = Field(default_factory=list)
    verified: bool = True

# Deadline Engine
class DeadlineReport(BaseModel):
    deadline_utc: datetime
    current_time_utc: datetime
    seconds_remaining: float
    hours_remaining: float
    is_expired: bool
    urgency: UrgencyLevel
    formatted_time_remaining: str

# Eligibility Engine
class CheckCriterion(BaseModel):
    criterion: str
    passed: bool
    required: Any
    actual: Any
    reason: str

class EligibilityReport(BaseModel):
    eligible: bool
    status: str # "PASS" or "FAIL"
    checks: Dict[str, CheckCriterion]
    failed_reasons: List[str] = Field(default_factory=list)

# Resume Selection
class ResumeRankItem(BaseModel):
    resume_id: str
    role_tag: str
    file_reference: str
    score: float
    matched_skills: List[str]
    matched_tags: List[str]
    rationale: str

class ResumeSelectionReport(BaseModel):
    selected_resume_id: str
    selected_file_reference: str
    confidence: float
    ranked_resumes: List[ResumeRankItem]

# Application Planning & Answers
class ClassifiedQuestion(BaseModel):
    key: str
    text: str
    question_type: QuestionType
    draft_answer: str
    source: str
    confidence: float
    requires_review: bool

class ApplicationPlan(BaseModel):
    job_id: str
    student_id: str
    selected_resume_id: str
    answers: List[ClassifiedQuestion]
    required_documents: List[str]
    manual_review_needed: bool
    confidence_score: float

# Pre-Submission Verification (9-Point Gate)
class PreSubmissionGateCheck(BaseModel):
    check_name: str
    passed: bool
    details: str

class PreSubmissionVerificationReport(BaseModel):
    application_id: str
    student_id: str
    job_id: str
    all_passed: bool
    application_hash: str
    gate_checks: List[PreSubmissionGateCheck]
    failure_messages: List[str] = Field(default_factory=list)
    timestamp: datetime

# Submission Authorization
class AuthorizationTokenPayload(BaseModel):
    auth_token: str
    application_id: str
    application_hash: str
    expires_at: datetime
    ttl_seconds: int
    status: str

# Submission Request & Confirmation
class SubmissionExecutionPayload(BaseModel):
    application_id: str
    auth_token: str
    application_hash: str
    portal_session_verified: bool = True

class SubmissionConfirmationPayload(BaseModel):
    application_id: str
    auth_token: str
    portal_application_id: str
    status_code: int
    confirmation_evidence: Dict[str, Any]

class ReadBackValidationPayload(BaseModel):
    application_id: str
    filled_fields: Dict[str, Any] # Map of key -> observed DOM value

class ReadBackFieldResult(BaseModel):
    field_key: str
    expected_value: Any
    actual_value: Any
    matched: bool
    discrepancy: Optional[str] = None

class ReadBackValidationReport(BaseModel):
    application_id: str
    passed: bool
    results: List[ReadBackFieldResult]
    mismatches: List[str]

# Student Registration (General-Purpose Setup Wizard)
class StudentRegistrationPayload(BaseModel):
    registration_number: str
    full_name: str
    email: str
    phone: str = ""
    degree: str = "B.Tech"
    branch: str = "Computer Science and Engineering"
    specialization: str = ""
    cgpa: float = 0.0
    graduation_year: int = 2027
    backlogs: int = 0
    skills: List[str] = Field(default_factory=list)
    willing_to_relocate: bool = True
    resumes: List[ResumeVariantCreate] = Field(default_factory=list)

# Turbo Prepare — Single batched response
class ScrapedProfile(BaseModel):
    name: str = ""
    roll_no: str = ""
    branch: str = ""
    cgpa: float = 0.0
    resumes: List[dict] = []

class TurboPreparePayload(BaseModel):
    student_id: Optional[str] = None
    company: str
    title: str
    haveloc_job_id: str
    raw_text: str
    is_resume_only: bool = False
    detected_fields: List[Dict[str, Any]] = []
    autonomy_mode: str = "CONFIRM"
    scraped_profile: Optional[ScrapedProfile] = None

class TurboPrepareResponse(BaseModel):
    application_id: str
    state: str
    is_resume_only: bool
    company: str
    title: str
    autonomy_mode: str
    student_facts: Dict[str, Any]
    selected_resume: Optional[Dict[str, Any]] = None
    answers: List[Dict[str, Any]] = Field(default_factory=list)
    answers_count: int = 0
    verification_report: Optional[Dict[str, Any]] = None
    auth_token: Optional[str] = None
    application_hash: Optional[str] = None
    all_verified: bool = False
    pipeline_ms: float = 0.0
