import os
import uuid
import datetime
from fastapi import FastAPI, Request, Form, Response, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware

mock_portal = FastAPI(title="Haveloc SRMIST Placement Portal (Authentic Simulation)")

mock_portal.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SESSION_COOKIE_NAME = "haveloc_session_token"

STUDENT_CONTEXT = {
    "name": "SHUBHAM PUTITUNDI",
    "first_name": "Shubham",
    "last_name": "Putitundi",
    "roll_no": "RA2311028010135",
    "branch": "Computer Science and Engineering - Cloud Computing",
    "degree": "B.Tech",
    "batch": 2027,
    "applied_count": 59,
    "email": "sp9643@srmist.edu.in",
    "phone": "9142899360",
    "cgpa": 8.85
}

JOBS_DB = {
    "HVL-LTM-2026": {
        "id": "HVL-LTM-2026",
        "company": "LTM",
        "role": "Graduate Engineer Trainee",
        "salary": "4.1L",
        "salary_type": "Full Time",
        "stipend": "—",
        "apply_before": "23 Sept 2026",
        "date_of_visit": "8 Oct 2026 Tentative",
        "status": "OPEN",
        "status_label": "Open For Applications",
        "batch": "—",
        "posted": "21 Sept 2026",
        "min_cgpa": 7.5,
        "branches": ["Computer Science and Engineering - Cloud Computing", "CSE", "IT"]
    },
    "HVL-CISCO-2026": {
        "id": "HVL-CISCO-2026",
        "company": "Cisco Systems",
        "role": "Cloud Consulting Engineer",
        "salary": "14.5L",
        "salary_type": "Full Time",
        "stipend": "45K Per Month",
        "apply_before": "24 Sept 2026",
        "date_of_visit": "10 Oct 2026 Tentative",
        "status": "OPEN",
        "status_label": "Open For Applications",
        "batch": "—",
        "posted": "21 Sept 2026",
        "min_cgpa": 8.0,
        "branches": ["Computer Science and Engineering - Cloud Computing", "CSE"],
        "is_resume_only": True
    },
    "HVL-BROADRIDGE-2026": {
        "id": "HVL-BROADRIDGE-2026",
        "company": "Broadridge Financial Solutions",
        "role": "GenAI / Machine Learning Intern / Software Developer",
        "salary": "10L",
        "salary_type": "Intern Leads to Ful...",
        "stipend": "30K Per Month",
        "apply_before": "21 Sept 2026",
        "date_of_visit": "22 Sept 2026 Tentative",
        "status": "IN_PROGRESS",
        "status_label": "In Progress",
        "batch": "—",
        "posted": "19 Sept 2026",
        "min_cgpa": 8.0,
        "branches": ["Computer Science and Engineering - Cloud Computing", "CSE", "Data Science"]
    },
    "HVL-KINAXIS-2026": {
        "id": "HVL-KINAXIS-2026",
        "company": "Kinaxis",
        "role": "Software Engineer",
        "salary": "8.8L",
        "salary_type": "Intern Leads to Ful...",
        "stipend": "35K Per Month",
        "apply_before": "21 Sept 2026",
        "date_of_visit": "25 Sept 2026 Tentative",
        "status": "CLOSED",
        "status_label": "Closed For Applications",
        "batch": "—",
        "posted": "19 Sept 2026",
        "min_cgpa": 8.0,
        "branches": ["CSE"]
    },
    "HVL-PREDIGLE-2026": {
        "id": "HVL-PREDIGLE-2026",
        "company": "Predigle India Private Limited",
        "role": "Associate Product Engineer",
        "salary": "6L – 9L",
        "salary_type": "Intern Leads to Ful...",
        "stipend": "15K - 20K Per Month",
        "apply_before": "19 Sept 2026",
        "date_of_visit": "24 Sept 2026 Tentative",
        "status": "CLOSED",
        "status_label": "Closed For Applications",
        "batch": "—",
        "posted": "18 Sept 2026",
        "min_cgpa": 7.0,
        "branches": ["All Branches"]
    },
    "HVL-KOTAK-2026": {
        "id": "HVL-KOTAK-2026",
        "company": "Kotak Asset Management Company",
        "role": "Data Science Intern",
        "salary": "—",
        "salary_type": "Regular Intern",
        "stipend": "50K+ Per Month",
        "apply_before": "18 Sept 2026",
        "date_of_visit": "5 Oct 2026 Tentative",
        "status": "CLOSED",
        "status_label": "Closed For Applications",
        "batch": "—",
        "posted": "17 Sept 2026",
        "min_cgpa": 8.5,
        "branches": ["CSE", "Data Science"]
    },
    "HVL-NAVIKENZ-2026": {
        "id": "HVL-NAVIKENZ-2026",
        "company": "Navikenz Inc.",
        "role": "Software Engineer - Fullstack, AI, ML, DevOps",
        "salary": "7L",
        "salary_type": "Intern Leads to Ful...",
        "stipend": "25K Per Month",
        "apply_before": "16 Sept 2026",
        "date_of_visit": "21 Sept 2026 Tentative",
        "status": "CLOSED",
        "status_label": "Closed For Applications",
        "batch": "—",
        "posted": "15 Sept 2026",
        "min_cgpa": 7.5,
        "branches": ["Computer Science and Engineering - Cloud Computing"]
    }
}

SUBMISSIONS = {}

def render_header(active_nav="Home"):
    nav_items = ["Home", "Companies", "Jobs", "Profile", "Tracker", "Chat", "Survey", "Requests", "Calendar", "Notice", "Policy"]
    links_html = ""
    for item in nav_items:
        is_active = (item.lower() == active_nav.lower())
        active_style = "background:#1e293b; color:#fff; border-radius:9999px;" if is_active else "color:#94a3b8;"
        href = f"/{item.lower()}" if item in ["Home", "Jobs", "Profile"] else "#"
        links_html += f'<a href="{href}" style="text-decoration:none; padding:6px 14px; font-size:13px; font-weight:500; {active_style}">{item}</a>'

    return f"""
    <header style="background:#000000; border-bottom:1px solid #1f2937; padding:10px 24px; display:flex; justify-content:space-between; align-items:center; position:sticky; top:0; z-index:100;">
        <div style="display:flex; align-items:center; gap:28px;">
            <a href="/home" style="font-family:'Georgia',serif; font-size:24px; font-weight:bold; font-style:italic; color:#ffffff; text-decoration:none;">h</a>
            <nav style="display:flex; gap:4px; align-items:center;">
                {links_html}
            </nav>
        </div>
        <div style="display:flex; align-items:center; gap:16px;">
            <span style="font-size:13px; color:#94a3b8; font-family:monospace;">{STUDENT_CONTEXT['roll_no']}</span>
            <div style="width:28px; height:28px; border-radius:50%; background:#2563eb; color:#fff; display:flex; align-items:center; justify-content:center; font-size:12px; font-weight:bold;">SP</div>
        </div>
    </header>
    """

@mock_portal.get("/", response_class=HTMLResponse)
@mock_portal.get("/home", response_class=HTMLResponse)
def home_page():
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Haveloc - Home</title>
        <style>
            body {{ background:#000000; color:#f3f4f6; font-family:-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin:0; padding:0; }}
            .hero {{ min-height:75vh; display:flex; flex-direction:column; align-items:center; justify-content:center; text-align:center; padding:2rem; }}
            h1 {{ font-size:2.8rem; font-weight:800; margin:0 0 1rem 0; letter-spacing:-0.5px; }}
            p {{ color:#9ca3af; font-size:1.1rem; max-width:600px; line-height:1.6; margin:0; }}
            .quick-actions {{ margin-top:2.5rem; display:flex; gap:14px; }}
            .btn {{ text-decoration:none; padding:10px 20px; border-radius:8px; font-weight:600; font-size:0.9rem; transition:0.2s; }}
            .btn-green {{ background:#16a34a; color:#fff; }}
            .btn-green:hover {{ background:#15803d; }}
            .btn-dark {{ background:#18181b; color:#cbd5e1; border:1px solid #27272a; }}
            .btn-dark:hover {{ background:#27272a; }}
        </style>
    </head>
    <body>
        {render_header("Home")}
        <div class="hero">
            <h1>Good evening, {STUDENT_CONTEXT['name']}</h1>
            <p>Welcome to your placement hub. Use the menu above to browse jobs, companies, and your profile.</p>
            <div class="quick-actions">
                <a href="/jobs" class="btn btn-green">Browse Active Jobs →</a>
                <a href="/profile" class="btn btn-dark">View Student Profile</a>
            </div>
        </div>
    </body>
    </html>
    """

@mock_portal.get("/profile", response_class=HTMLResponse)
def profile_page():
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Haveloc - Profile: {STUDENT_CONTEXT['name']}</title>
        <style>
            body {{ background:#000000; color:#f3f4f6; font-family:-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin:0; padding:0; }}
            .container {{ max-width:1100px; margin:2rem auto; padding:0 1.5rem; }}
            .profile-card {{ display:flex; gap:24px; align-items:flex-start; padding-bottom:2rem; border-bottom:1px solid #1f2937; }}
            .avatar-box {{ width:110px; height:110px; border-radius:12px; background:#18181b; border:1px solid #27272a; display:flex; align-items:center; justify-content:center; font-size:32px; font-weight:bold; color:#60a5fa; }}
            .name-row {{ display:flex; align-items:center; gap:8px; }}
            .name-row h2 {{ margin:0; font-size:1.6rem; letter-spacing:-0.3px; }}
            .verified-badge {{ color:#22c55e; font-size:1.2rem; }}
            .meta-text {{ color:#94a3b8; font-size:0.85rem; margin-top:4px; }}
            .stats-line {{ display:flex; gap:18px; margin-top:10px; font-size:0.85rem; color:#cbd5e1; }}
            .links-row {{ display:flex; gap:10px; margin-top:14px; }}
            .link-pill {{ background:#18181b; border:1px solid #27272a; color:#93c5fd; padding:4px 10px; border-radius:9999px; font-size:12px; text-decoration:none; }}
            .action-pills {{ display:flex; gap:10px; margin-top:14px; }}
            .pill-btn {{ background:#18181b; color:#cbd5e1; border:1px solid #27272a; padding:6px 14px; border-radius:9999px; font-size:12px; cursor:pointer; }}
            .pill-green {{ background:#16a34a; color:#fff; border:none; font-weight:600; }}
            .tab-nav {{ display:flex; gap:24px; border-bottom:1px solid #1f2937; margin-top:1.5rem; padding-bottom:8px; }}
            .tab-link {{ color:#94a3b8; text-decoration:none; font-size:13px; font-weight:500; padding-bottom:8px; }}
            .tab-link.active {{ color:#22c55e; border-bottom:2px solid #22c55e; font-weight:600; }}
            .overview-grid {{ display:grid; grid-template-columns:repeat(2, 1fr); gap:16px; margin-top:1.5rem; background:#0a0a0a; border:1px solid #1f2937; padding:1.5rem; border-radius:10px; }}
            .ov-item label {{ display:block; font-size:11px; color:#6b7280; text-transform:uppercase; margin-bottom:4px; }}
            .ov-item div {{ font-size:14px; color:#f3f4f6; font-weight:500; }}
        </style>
    </head>
    <body>
        {render_header("Profile")}
        <div class="container" id="haveloc-profile-view">
            <div class="profile-card">
                <div class="avatar-box">SP</div>
                <div style="flex:1;">
                    <div class="name-row">
                        <h2>{STUDENT_CONTEXT['name']}</h2>
                        <span class="verified-badge">●</span>
                    </div>
                    <div class="meta-text">{STUDENT_CONTEXT['roll_no']}</div>
                    <div class="meta-text" style="color:#e2e8f0; margin-top:6px;">{STUDENT_CONTEXT['branch']}  {STUDENT_CONTEXT['degree']} · {STUDENT_CONTEXT['batch']}</div>
                    <div class="stats-line">
                        <span><strong>{STUDENT_CONTEXT['applied_count']}</strong> applied</span>
                        <span>✉ {STUDENT_CONTEXT['email']}</span>
                        <span>📞 {STUDENT_CONTEXT['phone']}</span>
                    </div>
                    <div class="links-row">
                        <span class="link-pill">🌐 LinkedIn</span>
                        <span class="link-pill">💻 GitHub</span>
                        <span class="link-pill">⚡ CodeChef</span>
                    </div>
                    <div class="action-pills">
                        <span class="pill-btn">0 Offers</span>
                        <span class="pill-btn pill-green">Job Tracker</span>
                        <span class="pill-btn">Surveys</span>
                        <span class="pill-btn">Resumes</span>
                        <span class="pill-btn">Reports</span>
                    </div>
                </div>
            </div>

            <div class="tab-nav">
                <span class="tab-link active">Details</span>
                <span class="tab-link">Academics</span>
                <span class="tab-link">Freeze</span>
                <span class="tab-link">Skills</span>
                <span class="tab-link">More</span>
                <span class="tab-link">Evidence</span>
                <span class="tab-link">Documents</span>
                <span class="tab-link">Settings</span>
            </div>

            <h3 style="margin-top:2rem; font-size:1.1rem; color:#f3f4f6;">Student Overview</h3>
            <div class="overview-grid">
                <div class="ov-item"><label>Full Name</label><div>{STUDENT_CONTEXT['name']}</div></div>
                <div class="ov-item"><label>First Name</label><div>{STUDENT_CONTEXT['first_name']}</div></div>
                <div class="ov-item"><label>Last Name</label><div>{STUDENT_CONTEXT['last_name']}</div></div>
                <div class="ov-item"><label>Roll Number</label><div id="student-roll-number">{STUDENT_CONTEXT['roll_no']}</div></div>
                <div class="ov-item"><label>Branch</label><div id="student-branch-name">{STUDENT_CONTEXT['branch']}</div></div>
                <div class="ov-item"><label>Course</label><div>{STUDENT_CONTEXT['degree']}</div></div>
                <div class="ov-item"><label>CGPA</label><div id="student-cgpa-score">{STUDENT_CONTEXT['cgpa']}</div></div>
            </div>
            
            <h3 style="margin-top:2rem; font-size:1.1rem; color:#f3f4f6;">Uploaded Resumes</h3>
            <div class="overview-grid" id="student-resumes-list">
                <div class="ov-item"><label>Software Engineering</label><div class="resume-item">Shubham_Putitundi_SDE_Resume.pdf</div></div>
                <div class="ov-item"><label>Cloud Computing</label><div class="resume-item">Shubham_Putitundi_Cloud_Computing_Resume.pdf</div></div>
                <div class="ov-item"><label>GenAI & ML</label><div class="resume-item">Shubham_Putitundi_GenAI_ML_Resume.pdf</div></div>
            </div>
        </div>
    </body>
    </html>
    """

@mock_portal.get("/jobs", response_class=HTMLResponse)
def jobs_page():
    rows_html = ""
    for j_id, j in JOBS_DB.items():
        if j['status'] == 'OPEN':
            badge = '<span style="background:rgba(37,99,235,0.2); color:#60a5fa; padding:3px 8px; border-radius:9999px; font-size:11px; font-weight:600;">● Open For Applications</span>'
            action = f'<a href="/jobs/{j["id"]}/apply" style="background:#16a34a; color:#fff; text-decoration:none; padding:4px 10px; border-radius:4px; font-size:11px; font-weight:600;">Apply</a>'
        elif j['status'] == 'IN_PROGRESS':
            badge = '<span style="background:rgba(234,179,8,0.2); color:#fbbf24; padding:3px 8px; border-radius:9999px; font-size:11px; font-weight:600;">● In Progress</span>'
            action = f'<a href="/jobs/{j["id"]}/apply" style="background:#2563eb; color:#fff; text-decoration:none; padding:4px 10px; border-radius:4px; font-size:11px; font-weight:600;">View / Apply</a>'
        else:
            badge = '<span style="background:rgba(239,68,68,0.2); color:#f87171; padding:3px 8px; border-radius:9999px; font-size:11px; font-weight:600;">● Closed For Applications</span>'
            action = '<span style="color:#6b7280; font-size:11px;">Closed</span>'

        rows_html += f"""
        <tr style="border-bottom:1px solid #18181b;" data-job-id="{j['id']}">
            <td style="padding:14px 12px;">
                <div style="font-weight:700; color:#f3f4f6; font-size:13px;">{j['company']}</div>
                <div style="color:#94a3b8; font-size:11px; margin-top:2px;">{j['role']}</div>
            </td>
            <td style="padding:14px 12px; font-size:12px; color:#cbd5e1;">
                <div>{j['salary']}</div>
                <div style="font-size:10px; color:#64748b;">{j['salary_type']}</div>
            </td>
            <td style="padding:14px 12px; font-size:12px; color:#cbd5e1;">{j['stipend']}</td>
            <td style="padding:14px 12px; font-size:12px; color:#38bdf8; font-family:monospace;">{j['apply_before']}</td>
            <td style="padding:14px 12px; font-size:12px; color:#94a3b8;">{j['date_of_visit']}</td>
            <td style="padding:14px 12px;">{badge}</td>
            <td style="padding:14px 12px; font-size:12px; color:#94a3b8;">{j['batch']}</td>
            <td style="padding:14px 12px; font-size:12px; color:#94a3b8;">{j['posted']}</td>
            <td style="padding:14px 12px; text-align:right;">{action}</td>
        </tr>
        """

    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Haveloc - Jobs</title>
        <style>
            body {{ background:#000000; color:#f3f4f6; font-family:-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin:0; padding:0; }}
            .container {{ max-width:1200px; margin:2rem auto; padding:0 1.5rem; }}
            h2 {{ font-size:1.8rem; margin:0; }}
            .sub {{ color:#16a34a; font-size:12px; font-weight:600; margin-top:4px; }}
            .search-bar {{ display:flex; gap:8px; margin-top:1.5rem; align-items:center; }}
            .search-input {{ flex:1; background:#18181b; border:1px solid #27272a; color:#fff; padding:8px 14px; border-radius:6px; font-size:13px; }}
            .btn-green-icon {{ background:#16a34a; border:none; color:#fff; width:36px; height:36px; border-radius:6px; cursor:pointer; display:flex; align-items:center; justify-content:center; }}
            .filters-row {{ display:flex; gap:10px; margin-top:1rem; flex-wrap:wrap; }}
            .filter-pill {{ background:#18181b; border:1px solid #27272a; color:#cbd5e1; padding:5px 12px; border-radius:9999px; font-size:12px; }}
            .filter-active {{ border-color:#16a34a; color:#16a34a; }}
            table {{ width:100%; border-collapse:collapse; margin-top:1.5rem; text-align:left; }}
            th {{ background:#0a0a0a; color:#6b7280; font-size:11px; text-transform:uppercase; padding:10px 12px; border-bottom:1px solid #1f2937; }}
        </style>
    </head>
    <body>
        {render_header("Jobs")}
        <div class="container" id="haveloc-jobs-view">
            <h2>Jobs</h2>
            <div class="sub">141 Jobs Listed</div>

            <div class="search-bar">
                <select class="filter-pill" style="border-radius:6px;"><option>Company Name</option></select>
                <input type="text" class="search-input" placeholder="Search here..." />
                <button class="btn-green-icon">🔍</button>
            </div>

            <div class="filters-row">
                <span class="filter-pill filter-active">Apply By (Desc) ▾</span>
                <span class="filter-pill">Job Type ▾</span>
                <span class="filter-pill">Job Status ▾</span>
                <span class="filter-pill">Date Of Visit ▾</span>
                <span class="filter-pill filter-active">Eligible Jobs</span>
                <span class="filter-pill">Applied Jobs</span>
                <span class="filter-pill">Eligible But Not Applied Jobs</span>
                <span class="filter-pill">Rejected Jobs</span>
                <span class="filter-pill">Offered Jobs</span>
            </div>

            <table>
                <thead>
                    <tr>
                        <th>Title</th>
                        <th>Salary</th>
                        <th>Stipend</th>
                        <th>Apply Before</th>
                        <th>Date Of Visit</th>
                        <th>Status</th>
                        <th>Batch</th>
                        <th>Job Posted</th>
                        <th style="text-align:right;">Action</th>
                    </tr>
                </thead>
                <tbody>
                    {rows_html}
                </tbody>
            </table>
        </div>
    </body>
    </html>
    """

@mock_portal.get("/jobs/{job_id}/apply", response_class=HTMLResponse)
def apply_page(job_id: str):
    job = JOBS_DB.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Apply - {job['company']}</title>
        <style>
            body {{ background:#000000; color:#f3f4f6; font-family:-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin:0; padding:0; }}
            .form-box {{ max-width:700px; margin:2rem auto; background:#0a0a0a; border:1px solid #1f2937; border-radius:12px; padding:2rem; }}
            h2 {{ color:#60a5fa; margin-top:0; }}
            label {{ display:block; font-size:12px; color:#9ca3af; margin-top:1rem; margin-bottom:4px; font-weight:600; text-transform:uppercase; }}
            input[type="text"], textarea, select {{ width:100%; padding:8px 12px; background:#18181b; border:1px solid #27272a; border-radius:6px; color:#fff; box-sizing:border-box; font-size:13px; }}
            textarea {{ min-height:80px; }}
            .btn-green {{ background:#16a34a; color:#fff; border:none; padding:10px 22px; border-radius:6px; font-weight:600; cursor:pointer; font-size:13px; }}
            .btn-green:hover {{ background:#15803d; }}
            .captcha-box {{ background:#18181b; border:1px dashed #eab308; padding:1rem; border-radius:8px; margin-top:1.5rem; display:none; }}
        </style>
    </head>
    <body>
        {render_header("Jobs")}
        <div class="form-box" id="haveloc-application-form">
            <h2>{job['company']} — Application</h2>
            <p style="color:#94a3b8; font-size:13px;">Role: {job['role']} | Apply Before: {job['apply_before']}</p>

            {f'''
            <!-- Resume-Only Placement Application Form -->
            <form id="placement-application-form" action="/jobs/{job['id']}/submit" method="post">
                <input type="hidden" name="job_id" id="job_id" value="{job['id']}" />

                <div style="background:#18181b; padding:12px; border-radius:8px; margin-bottom:1rem; border:1px solid #27272a;">
                    <div style="font-size:12px; color:#9ca3af;">Candidate: <strong style="color:#fff;">{STUDENT_CONTEXT['name']}</strong> ({STUDENT_CONTEXT['roll_no']})</div>
                    <div style="font-size:12px; color:#9ca3af; margin-top:4px;">Department: <span style="color:#60a5fa;">{STUDENT_CONTEXT['branch']}</span> | CGPA: <span style="color:#34d399;">{STUDENT_CONTEXT['cgpa']}</span></div>
                </div>

                <div style="background:rgba(16,185,129,0.1); border:1px solid rgba(16,185,129,0.3); padding:10px 12px; border-radius:6px; margin-bottom:1.2rem; font-size:12px; color:#6ee7b7;">
                    ✓ <strong>Direct Resume Submission:</strong> No additional questions or essays required by {job['company']}. Select your resume variant below.
                </div>

                <label for="resume_variant">Select Resume Variant</label>
                <select name="resume_variant" id="resume_variant" style="padding:10px; font-size:13px; border-color:#3b82f6;">
                    <option value="Shubham_Putitundi_Cloud_Computing_Resume.pdf">Shubham_Putitundi_Cloud_Computing_Resume.pdf (Cloud Computing & AWS)</option>
                    <option value="Shubham_Putitundi_SDE_Resume.pdf">Shubham_Putitundi_SDE_Resume.pdf (Software Engineering)</option>
                    <option value="Shubham_Putitundi_GenAI_ML_Resume.pdf">Shubham_Putitundi_GenAI_ML_Resume.pdf (GenAI & ML)</option>
                </select>

                <div style="margin-top:1.5rem; display:flex; align-items:flex-start; gap:8px;">
                    <input type="checkbox" id="declaration_terms" name="declaration_terms" required style="width:18px; height:18px; margin-top:2px; cursor:pointer;" />
                    <label for="declaration_terms" style="font-size:12px; color:#cbd5e1; text-transform:none; margin:0; cursor:pointer;">
                        I hereby declare that all details in my profile are true and accurate, and I undertake to adhere to SRMIST & {job['company']} recruitment guidelines.
                    </label>
                </div>

                <div style="margin-top:1.5rem; display:flex; gap:10px; align-items:center;">
                    <button type="submit" id="submit-application-btn" class="btn-green">Submit Application</button>
                </div>
            </form>
            ''' if job.get("is_resume_only") else f'''
            <form id="placement-application-form" action="/jobs/{job['id']}/submit" method="post">
                <input type="hidden" name="job_id" id="job_id" value="{job['id']}" />

                <label for="cgpa_q">Current CGPA</label>
                <input type="text" name="cgpa_q" id="cgpa_q" required />

                <label for="branch_q">Branch / Department</label>
                <input type="text" name="branch_q" id="branch_q" required />

                <label for="skills_q">Key Technical Skills & Cloud Proficiencies</label>
                <textarea name="skills_q" id="skills_q" required></textarea>

                <label for="project_q">Most Relevant Engineering Project & Metrics</label>
                <textarea name="project_q" id="project_q" required></textarea>

                <label for="why_company">Why do you want to join {job['company']}?</label>
                <textarea name="why_company" id="why_company" required></textarea>

                <label for="relocate_q">Are you willing to relocate to company work locations?</label>
                <input type="text" name="relocate_q" id="relocate_q" value="Yes" required />

                <label for="resume_variant">Resume Variant</label>
                <select name="resume_variant" id="resume_variant">
                    <option value="Shubham_Putitundi_Cloud_Computing_Resume.pdf">Shubham_Putitundi_Cloud_Computing_Resume.pdf</option>
                    <option value="Shubham_Putitundi_SDE_Resume.pdf">Shubham_Putitundi_SDE_Resume.pdf</option>
                    <option value="Shubham_Putitundi_GenAI_ML_Resume.pdf">Shubham_Putitundi_GenAI_ML_Resume.pdf</option>
                </select>

                <!-- Simulated CAPTCHA challenge -->
                <div id="captcha-container" class="captcha-box">
                    <span style="color:#eab308; font-weight:600;">⚠ Security Verification Required</span>
                    <p style="font-size:12px; color:#94a3b8; margin:6px 0;">Haveloc anti-automation challenge. Agent pauses immediately until solved.</p>
                    <button type="button" style="background:#eab308; color:#000; border:none; padding:5px 12px; border-radius:4px; font-weight:600; cursor:pointer;" onclick="document.getElementById('captcha-container').style.display='none';">I am Human (Verify)</button>
                </div>

                <div style="margin-top:1.5rem; display:flex; gap:10px; align-items:center;">
                    <button type="submit" id="submit-application-btn" class="btn-green">Confirm & Submit Application</button>
                    <button type="button" style="background:#27272a; color:#9ca3af; border:none; padding:8px 12px; border-radius:6px; font-size:12px; cursor:pointer;" onclick="document.getElementById('captcha-container').style.display='block';">Simulate CAPTCHA</button>
                </div>
            </form>
            '''}
        </div>
    </body>
    </html>
    """

@mock_portal.post("/jobs/{job_id}/submit", response_class=HTMLResponse)
def submit_form(
    job_id: str,
    resume_variant: str = Form(""),
    cgpa_q: str = Form(""),
    branch_q: str = Form(""),
    skills_q: str = Form(""),
    project_q: str = Form(""),
    why_company: str = Form(""),
    declaration_terms: str = Form("")
):
    receipt_id = f"HVL-SRM-2026-{uuid.uuid4().hex[:6].upper()}"
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    SUBMISSIONS[receipt_id] = {
        "job_id": job_id,
        "receipt_id": receipt_id,
        "timestamp": timestamp,
        "student": STUDENT_CONTEXT["name"],
        "roll_no": STUDENT_CONTEXT["roll_no"]
    }

    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Haveloc - Application Confirmation</title>
        <style>
            body {{ background:#000000; color:#f3f4f6; font-family:-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; display:flex; align-items:center; justify-content:center; height:100vh; margin:0; }}
            .card {{ background:#0a0a0a; border:1px solid #16a34a; border-radius:14px; padding:2.5rem; text-align:center; max-width:480px; box-shadow:0 10px 30px rgba(0,0,0,0.8); }}
            h2 {{ color:#22c55e; margin:0 0 10px 0; }}
            .receipt-box {{ background:#052e16; color:#86efac; padding:12px; border-radius:8px; font-family:monospace; font-size:1.2rem; font-weight:700; margin:1.5rem 0; border:1px solid #16a34a; }}
            a {{ color:#38bdf8; text-decoration:none; font-size:13px; }}
        </style>
    </head>
    <body>
        <div class="card" id="submission-confirmation-card">
            <h2>✓ Application Successfully Submitted</h2>
            <p style="color:#94a3b8; font-size:13px; line-height:1.5;">Haveloc portal has officially accepted your application for {job_id}.</p>
            <div class="receipt-box" id="portal-application-receipt-id">{receipt_id}</div>
            <p style="font-size:11px; color:#6b7280;">Timestamp: {timestamp} | Student: {STUDENT_CONTEXT['name']} ({STUDENT_CONTEXT['roll_no']})</p>
            <a href="/jobs">Return to Notice Board →</a>
        </div>
    </body>
    </html>
    """

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(mock_portal, host="0.0.0.0", port=8080)
