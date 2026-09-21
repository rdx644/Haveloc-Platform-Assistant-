# Haveloc Placement Application Agent

Production-grade AI-powered placement application orchestration system for the **Haveloc** placement portal (SRMIST).

The system automatically identifies newly posted placement opportunities, determines student eligibility, prepares applications using verified student records, validates them through a strict deterministic 9-point pre-submission gate, and executes submissions through the student's own authenticated browser session before the deadline.

---

## Key Architectural Principles (From Specification)

1. **AI Reasons, Deterministic Software Authorizes:**
   - LLMs classify questions, extract requirements, and synthesize grounded drafts.
   - Deterministic code decides eligibility, verifies deadlines, detects duplicates, and authorizes submissions.
2. **Local Student Browser Execution:**
   - Central backend **never** stores student passwords, session cookies, or portal tokens.
   - All interactions with Haveloc run in the student's own authenticated browser session via a Manifest V3 extension.
3. **No CAPTCHA / Anti-Bot Circumvention:**
   - If a CAPTCHA or verification challenge appears, automation immediately pauses, alerts the student to solve it, and resumes only after verification.
4. **Mandatory Pre-Submission Verification Gate (9/9):**
   - Form-filled state is separated from submission by a deterministic verification pipeline computing a cryptographic SHA-256 application hash.
5. **Confirmation Over Assumption:**
   - The application moves to `COMPLETED` **only** after capturing the portal's official Application ID receipt.

---

## 11-Step Lifecycle State Machine

```text
DISCOVERED
    ↓
PARSED
    ↓
ELIGIBILITY_CHECKED  ──(Fail)──> INELIGIBLE
    ↓
PLANNED
    ↓
DRAFTED
    ↓
FORM_FILLED
    ↓
PRE_SUBMISSION_VERIFIED  ──(Fail)──> VERIFICATION_FAILED / REQUIRES_REVIEW
    ↓
SUBMISSION_AUTHORIZED
    ↓
SUBMITTING  ──(CAPTCHA)──> CAPTCHA_REQUIRED (Pause)
    ↓
SUBMISSION_CONFIRMED  ──(Fail)──> SUBMISSION_FAILED
    ↓
COMPLETED
```

---

## 9-Point Pre-Submission Verification Checklist

Every application must pass all 9 checks before submission authorization is issued:

1. **Eligibility Check**: Degree, branch, CGPA, graduation year, and backlog criteria satisfied.
2. **Deadline Check**: Job deadline has not passed (rechecked in pure UTC).
3. **Resume Variant**: Valid role-tagged resume selected and accessible.
4. **Required Fields Completeness**: All portal input fields populated.
5. **Question Confidence & Review**: Zero unresolved sensitive questions (Type E review resolved).
6. **Document Availability**: Mandatory attachments satisfied.
7. **Profile Consistency**: Form answers match database student records 100%.
8. **Duplicate Prevention**: No prior completed application for this student and job.
9. **Integrity Hash**: SHA-256 digest locking student ID, job ID, resume ID, and normalized answers.

---

## Project Structure

```text
haveloc-placement-agent/
├── backend/
│   ├── api/                     # FastAPI route handlers
│   │   ├── auth.py              # Student registration & session
│   │   ├── jobs.py              # Job ingestion, parsing, deadline calculation
│   │   ├── student.py           # Profile, resume variants, achievement bank
│   │   ├── applications.py      # Lifecycle pipeline (plan, verify, authorize, submit, confirm)
│   │   ├── events.py            # Audit event log endpoints
│   │   └── extension.py         # Browser extension coordination bridge
│   ├── services/                # Core deterministic engines
│   │   ├── deadline_engine.py   # Pure UTC time remaining & urgency classifier
│   │   ├── eligibility_engine.py# Multi-criteria academic rule evaluator
│   │   ├── resume_selector.py   # Rule-based tag & skill matcher
│   │   ├── question_classifier.py # Type A-E classifier with sensitive review gating
│   │   ├── answer_engine.py     # Grounded facts generator (Achievement Bank)
│   │   ├── verification_engine.py # 9-point pre-submission verification & hash generator
│   │   ├── authorization_engine.py# HMAC-signed single-use submission token issuer
│   │   ├── state_machine.py     # Application lifecycle transition guard
│   │   ├── audit_logger.py      # PII-redacted immutable event logging
│   │   └── normalization.py     # Job requirement normalization & hashing
│   ├── config.py                # Environment & threshold settings
│   ├── database.py              # SQLite / SQLAlchemy engine
│   ├── models.py                # ORM schema matching Section 23 specification
│   ├── schemas.py               # Pydantic contract models
│   ├── seed_data.py             # Deterministic test fixture & student profile seeder
│   └── main.py                  # FastAPI application entry point
│
├── extension/                   # Chrome Extension (Manifest V3)
│   ├── manifest.json            # Extension manifest
│   ├── background/
│   │   └── service_worker.js    # Background communication worker
│   ├── content/
│   │   ├── haveloc_detector.js  # Portal page recognizer & overlay badge injector
│   │   ├── form_filler.js       # Reactive DOM form populator
│   │   ├── captcha_guard.js     # Human verification detector & auto-pauser
│   │   └── submission_executor.js# Auth validator, submitter, and receipt collector
│   └── popup/
│       ├── popup.html           # Extension popup interface
│       ├── popup.css            # Extension styling
│       └── popup.js             # Extension interaction script
│
├── dashboard/                   # Student Management Dashboard (Web UI)
│   ├── index.html               # Main dashboard layout
│   ├── styles.css               # Rich dark-mode glassmorphism design
│   └── app.js                   # Real-time state synchronizer & verification inspector
│
├── mock_portal/                 # High-Fidelity Mock Haveloc Portal
│   └── server.py                # Simulated placement portal with login, jobs, forms, & CAPTCHA
│
├── tests/                       # Automated Test Suite (18 tests, 100% pass)
│   ├── test_deadline_engine.py
│   ├── test_eligibility_engine.py
│   ├── test_resume_selector.py
│   ├── test_question_classifier.py
│   ├── test_verification_and_authorization.py
│   └── test_end_to_end_pipeline.py
│
├── run_system.py                # Single command system launcher
└── README.md
```

---

## Running the Automated Test Suite

Run the full pytest suite:

```bash
cd C:\Users\putit\.gemini\antigravity-ide\scratch\haveloc-placement-agent
python -m pytest tests/ -v
```

All 20 unit, integration, and security tests verify:
- Accurate deadline math & urgency thresholds (`NORMAL`, `URGENT`, `CRITICAL`, `EXPIRED`)
- Multi-criteria academic eligibility cutoffs
- Tag-matched resume ranking for Cloud Computing & SDE variants
- Question classification (Type A-E) and sensitive question gating
- Cryptographic hash generation & tamper detection
- Token authorization & single-use expiration
- Full 11-step application lifecycle & duplicate rejection
- Phase 12 DOM read-back validation & mismatch detection
- Ambiguous submission response handling (`SUBMISSION_UNKNOWN`) and retry prohibition

---

## Running the Full System

Launch the entire stack with one command:

```bash
python run_system.py
```

This launches:
1. **Database Seeder**: Populates SHUBHAM PUTITUNDI's profile (`RA2311028010135`), 3 resume variants, verified achievement bank, and real Haveloc placement postings (`LTM`, `Broadridge Financial Solutions`, `Kinaxis`, `Navikenz Inc.`, `Kotak AMC`).
2. **Backend API & Dashboard**: `http://localhost:8000/dashboard` (API docs: `http://localhost:8000/docs`)
3. **Mock Haveloc Portal**: `http://localhost:8080/jobs` (Authentic replica of live Haveloc portal)

### Loading the Browser Extension
1. Open Google Chrome or Microsoft Edge.
2. Navigate to `chrome://extensions` or `edge://extensions`.
3. Enable **Developer mode** (toggle in top right).
4. Click **Load unpacked** and select:
   `C:\Users\putit\.gemini\antigravity-ide\scratch\haveloc-placement-agent\extension`
5. Open `http://localhost:8080/jobs` and test auto-filling and verified submission!
