const API_BASE = "http://localhost:8000";
const STUDENT_ID = "RA2311028010135";

let currentActiveAppId = null;
let currentActiveHash = null;

document.addEventListener("DOMContentLoaded", () => {
  setupNavigation();
  setupModal();
  loadAllData();

  document.getElementById("refresh-btn").addEventListener("click", () => {
    loadAllData();
  });

  // Auto-refresh every 6 seconds
  setInterval(loadAllData, 6000);
});

function setupNavigation() {
  const navButtons = document.querySelectorAll(".nav-item");
  const tabPanes = document.querySelectorAll(".tab-pane");

  navButtons.forEach(btn => {
    btn.addEventListener("click", () => {
      const targetTab = btn.getAttribute("data-tab");
      navButtons.forEach(b => b.classList.remove("active"));
      tabPanes.forEach(p => p.classList.remove("active"));

      btn.classList.add("active");
      const targetEl = document.getElementById(`tab-${targetTab}`);
      if (targetEl) targetEl.classList.add("active");

      // Update titles
      const titles = {
        applications: ["Placement Applications", "Real-time orchestration pipeline with deterministic 9-point verification gates"],
        opportunities: ["Active Placement Opportunities", "Normalized job notices discovered from Haveloc portal"],
        profile: ["Student Profile & Achievement Bank", "Verified ground-truth facts preventing hallucinations"],
        resumes: ["Resume Variants", "Role-tagged resume files ranked by deterministic rule engine"],
        audit: ["Security & Application Audit Trail", "Immutable event history with sensitive credentials redacted"]
      };

      if (titles[targetTab]) {
        document.getElementById("page-title").innerText = titles[targetTab][0];
        document.getElementById("page-subtitle").innerText = titles[targetTab][1];
      }
    });
  });
}

function loadAllData() {
  loadApplications();
  loadOpportunities();
  loadProfile();
  loadResumes();
  loadAuditEvents();
}

async function loadApplications() {
  try {
    const res = await fetch(`${API_BASE}/applications?student_id=${STUDENT_ID}`);
    const apps = await res.json();

    document.getElementById("app-counter").innerText = apps.length;
    document.getElementById("stat-total-apps").innerText = apps.length;

    let verifiedCount = 0;
    let completedCount = 0;
    let reviewCount = 0;

    const tbody = document.getElementById("applications-tbody");
    if (!apps || apps.length === 0) {
      tbody.innerHTML = `<tr><td colspan="5" class="text-center text-muted py-4">No active applications. Select an opportunity to apply.</td></tr>`;
      return;
    }

    tbody.innerHTML = "";
    apps.forEach(app => {
      if (app.state === "PRE_SUBMISSION_VERIFIED" || app.state === "SUBMISSION_AUTHORIZED") verifiedCount++;
      if (app.state === "COMPLETED" || app.state === "SUBMISSION_CONFIRMED") completedCount++;
      if (app.state === "REQUIRES_REVIEW" || app.state === "VERIFICATION_FAILED" || app.state === "FIELD_MISMATCH") reviewCount++;

      const tr = document.createElement("tr");

      let badgeClass = "badge-info";
      if (app.state === "COMPLETED") badgeClass = "badge-green";
      else if (app.state === "INELIGIBLE" || app.state === "VERIFICATION_FAILED" || app.state === "FIELD_MISMATCH") badgeClass = "badge-red";
      else if (app.state === "REQUIRES_REVIEW" || app.state === "SUBMISSION_UNKNOWN") badgeClass = "badge-amber";
      else if (app.state === "PRE_SUBMISSION_VERIFIED" || app.state === "SUBMISSION_AUTHORIZED") badgeClass = "badge-indigo";

      const timeText = app.deadline_report ? app.deadline_report.formatted_time_remaining : "Active";
      const mode = app.autonomy_mode || "CONFIRM";

      tr.innerHTML = `
        <td>
          <div style="font-weight:600; color:#fff;">${app.company}</div>
          <div style="font-size:0.75rem; color:#94a3b8;">${app.title}</div>
        </td>
        <td>
          <span style="font-size:0.8rem; font-family:var(--font-mono); color:${app.deadline_report?.urgency === 'CRITICAL' ? '#f87171' : '#38bdf8'};">
            ${timeText}
          </span>
        </td>
        <td>
          <span style="font-size:0.8rem; color:#cbd5e1;">${app.resume_id || 'Auto-Selecting'}</span>
        </td>
        <td>
          <div style="display:flex; flex-direction:column; gap:3px;">
            <span class="badge ${badgeClass}">${app.state}</span>
            <span style="font-size:0.68rem; color:#94a3b8;">Mode: ${mode}</span>
          </div>
        </td>
        <td>
          <button class="btn btn-secondary" style="padding:4px 10px; font-size:0.75rem;" onclick="openVerificationModal('${app.id}')">
            🔍 Inspect / Gate (9/9)
          </button>
        </td>
      `;
      tbody.appendChild(tr);
    });

    document.getElementById("stat-verified-apps").innerText = verifiedCount;
    document.getElementById("stat-completed-apps").innerText = completedCount;
    document.getElementById("stat-review-apps").innerText = reviewCount;
  } catch (err) {
    console.error("Error loading applications:", err);
  }
}

async function loadOpportunities() {
  try {
    const res = await fetch(`${API_BASE}/jobs`);
    const jobs = await res.json();

    document.getElementById("job-counter").innerText = jobs.length;
    const container = document.getElementById("jobs-cards-grid");
    container.innerHTML = "";

    jobs.forEach(job => {
      const card = document.createElement("div");
      card.className = "job-card";

      const urgencyColor = job.deadline_report?.urgency === 'CRITICAL' ? 'badge-red' : (job.deadline_report?.urgency === 'URGENT' ? 'badge-amber' : 'badge-info');

      card.innerHTML = `
        <div>
          <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:0.5rem;">
            <h4 style="margin:0; font-size:1.1rem; color:#60a5fa;">${job.company}</h4>
            <span class="badge ${urgencyColor}">${job.deadline_report?.formatted_time_remaining || 'Open'}</span>
          </div>
          <h5 style="margin:0 0 0.5rem 0; font-size:0.9rem; color:#f1f5f9;">${job.title}</h5>
          <div style="font-size:0.75rem; color:#94a3b8; margin-bottom:0.75rem;">
            Portal ID: <code style="font-family:var(--font-mono);">${job.haveloc_job_id}</code> | Min CGPA: ${job.normalized_requirements.min_cgpa || 'None'}
          </div>
          <div style="font-size:0.8rem; color:#cbd5e1; margin-bottom:1rem;">
            Skills: ${job.normalized_requirements.skills.slice(0, 5).join(", ")}
          </div>
        </div>
        <div style="display:flex; gap:8px; align-items:center;">
          <button class="btn btn-primary" style="flex:1;" onclick="initiateApplication('${job.id}')">⚡ Initiate Application</button>
          <a href="http://localhost:8080/jobs/${job.haveloc_job_id}/apply" target="_blank" class="btn btn-secondary">Portal Form ↗</a>
        </div>
      `;
      container.appendChild(card);
    });
  } catch (err) {
    console.error("Error loading jobs:", err);
  }
}

async function initiateApplication(jobId) {
  try {
    const res = await fetch(`${API_BASE}/applications/initiate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ student_id: STUDENT_ID, job_id: jobId, autonomy_mode: "CONFIRM" })
    });
    const data = await res.json();
    if (res.ok) {
      alert(`Application initiated! State: ${data.state}. Resume selected: ${data.selected_resume}`);
      loadApplications();
    } else {
      alert(`Notice: ${data.detail}`);
    }
  } catch (err) {
    alert(`Error initiating: ${err.message}`);
  }
}

async function loadProfile() {
  try {
    const res = await fetch(`${API_BASE}/student/${STUDENT_ID}/profile`);
    const prof = await res.json();

    const summaryEl = document.getElementById("profile-summary");
    summaryEl.innerHTML = `
      <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px; font-size:0.85rem;">
        <div><strong style="color:#94a3b8;">Full Name:</strong> ${prof.name}</div>
        <div><strong style="color:#94a3b8;">Registration:</strong> ${prof.student_id}</div>
        <div><strong style="color:#94a3b8;">Degree:</strong> ${prof.degree}</div>
        <div><strong style="color:#94a3b8;">Branch:</strong> ${prof.branch}</div>
        <div><strong style="color:#94a3b8;">CGPA:</strong> <span style="color:#34d399; font-weight:700;">${prof.cgpa}</span></div>
        <div><strong style="color:#94a3b8;">Batch Year:</strong> ${prof.graduation_year}</div>
        <div><strong style="color:#94a3b8;">Standing Backlogs:</strong> ${prof.backlogs}</div>
        <div><strong style="color:#94a3b8;">Relocation:</strong> ${prof.preferences.willing_to_relocate ? 'Open' : 'No'}</div>
      </div>
      <div style="margin-top:1rem;">
        <strong style="color:#94a3b8; font-size:0.85rem;">Verified Technical Skills:</strong>
        <div style="display:flex; flex-wrap:wrap; gap:6px; margin-top:6px;">
          ${prof.skills.map(s => `<span class="badge badge-info">${s}</span>`).join('')}
        </div>
      </div>
    `;

    // Load achievements
    const achRes = await fetch(`${API_BASE}/student/${STUDENT_ID}/achievements`);
    const achs = await achRes.json();
    const achContainer = document.getElementById("achievements-container");
    achContainer.innerHTML = "";

    achs.forEach(a => {
      const item = document.createElement("div");
      item.style.cssText = "background:rgba(255,255,255,0.02); border:1px solid var(--border-color); border-radius:8px; padding:12px; margin-bottom:10px;";
      item.innerHTML = `
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <h5 style="margin:0; color:#38bdf8; font-size:0.95rem;">${a.project}</h5>
          <span style="font-size:0.75rem; color:#34d399;">✓ Verified Ground Fact</span>
        </div>
        <p style="font-size:0.8rem; color:#cbd5e1; margin:6px 0;">${a.outcome}</p>
        <div style="font-size:0.75rem; color:#fbbf24;">Metric: ${a.metric || 'N/A'}</div>
        <div style="font-size:0.72rem; color:#94a3b8; margin-top:4px;">Stack: ${a.tech_stack.join(", ")}</div>
      `;
      achContainer.appendChild(item);
    });
  } catch (err) {
    console.error("Error loading profile:", err);
  }
}

async function loadResumes() {
  try {
    const res = await fetch(`${API_BASE}/student/${STUDENT_ID}/resumes`);
    const resumes = await res.json();
    const container = document.getElementById("resumes-cards-grid");
    container.innerHTML = "";

    resumes.forEach(r => {
      const card = document.createElement("div");
      card.className = "job-card";
      card.innerHTML = `
        <div>
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.5rem;">
            <h4 style="margin:0; color:#38bdf8; font-size:1rem;">${r.file_reference}</h4>
            <span class="badge badge-indigo">v${r.version}</span>
          </div>
          <div style="font-size:0.8rem; color:#94a3b8; margin-bottom:0.5rem;">Role Tag: <strong>${r.role_tag}</strong></div>
          <div style="font-size:0.75rem; color:#cbd5e1; margin-bottom:0.5rem;">
            Skills: ${r.skills.join(", ")}
          </div>
          <div style="font-size:0.72rem; color:#64748b;">Domain: ${r.experience_tags.join(", ")}</div>
        </div>
      `;
      container.appendChild(card);
    });
  } catch (err) {
    console.error("Error loading resumes:", err);
  }
}

async function loadAuditEvents() {
  try {
    const res = await fetch(`${API_BASE}/events?limit=30`);
    const events = await res.json();
    const container = document.getElementById("audit-timeline");
    container.innerHTML = "";

    events.forEach(e => {
      const item = document.createElement("div");
      item.className = "timeline-item";
      const timeStr = e.timestamp.replace("T", " ").substring(0, 19);
      item.innerHTML = `
        <div class="timeline-time">${timeStr}</div>
        <div>
          <span class="timeline-badge">${e.event_type}</span>
          <span class="timeline-meta">${JSON.stringify(e.metadata)}</span>
        </div>
      `;
      container.appendChild(item);
    });
  } catch (err) {
    console.error("Error loading audit events:", err);
  }
}

function setupModal() {
  const modal = document.getElementById("verification-modal");
  const closeBtn = document.getElementById("modal-close-btn");
  const secBtn = document.getElementById("modal-secondary-btn");
  const authBtn = document.getElementById("modal-authorize-btn");

  const hide = () => { modal.style.display = "none"; };
  closeBtn.addEventListener("click", hide);
  secBtn.addEventListener("click", hide);

  authBtn.addEventListener("click", async () => {
    if (!currentActiveAppId) return;
    try {
      const res = await fetch(`${API_BASE}/applications/${currentActiveAppId}/authorize`, { method: "POST" });
      const data = await res.json();
      if (res.ok) {
        alert(`✓ Application authorized! Single-use token: ${data.auth_token}`);
        hide();
        loadApplications();
      } else {
        alert(`Authorization error: ${data.detail}`);
      }
    } catch (err) {
      alert(`Error: ${err.message}`);
    }
  });

  document.getElementById("modal-resolve-review-btn").addEventListener("click", async () => {
    const inputVal = document.getElementById("modal-review-input").value;
    const qKey = document.getElementById("modal-resolve-review-btn").dataset.key;
    if (!qKey || !inputVal) return;

    await fetch(`${API_BASE}/applications/${currentActiveAppId}/resolve-review`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question_key: qKey,
        confirmed_answer: inputVal
      })
    });

    document.getElementById("modal-review-section").style.display = "none";
    // Re-run verification
    openVerificationModal(currentActiveAppId);
  });
}

window.openVerificationModal = async function(appId) {
  currentActiveAppId = appId;
  const modal = document.getElementById("verification-modal");
  modal.style.display = "flex";

  document.getElementById("modal-app-title").innerText = `Pre-Submission Gate: ${appId}`;
  document.getElementById("modal-hash-val").innerText = "Executing 9-point verification checks...";
  const gateList = document.getElementById("modal-gate-list");
  gateList.innerHTML = `<div style="padding:1rem; text-align:center; color:#94a3b8;">Verifying deterministic criteria...</div>`;

  try {
    // 1. Ensure form filled state or execute verify
    const res = await fetch(`${API_BASE}/applications/${appId}/verify`, { method: "POST" });
    const rep = await res.json();

    currentActiveHash = rep.application_hash;
    document.getElementById("modal-hash-val").innerText = rep.application_hash;

    gateList.innerHTML = "";
    rep.gate_checks.forEach(chk => {
      const div = document.createElement("div");
      div.className = `gate-item ${chk.passed ? 'pass' : 'fail'}`;
      div.innerHTML = `
        <div>
          <div class="gate-name" style="color:${chk.passed ? '#34d399' : '#f87171'}">${chk.check_name}</div>
          <div class="gate-desc">${chk.details}</div>
        </div>
        <span class="badge ${chk.passed ? 'badge-green' : 'badge-red'}">${chk.passed ? 'PASS' : 'FAIL'}</span>
      `;
      gateList.appendChild(div);
    });

    // Check if sensitive review is required
    const appDetailsRes = await fetch(`${API_BASE}/applications/${appId}`);
    const appData = await appDetailsRes.json();
    const pendingReview = appData.answers.find(a => a.requires_review);

    const reviewSec = document.getElementById("modal-review-section");
    if (pendingReview) {
      reviewSec.style.display = "block";
      document.getElementById("modal-review-q").innerText = `Question: "${pendingReview.question}"`;
      document.getElementById("modal-review-input").value = pendingReview.answer;
      document.getElementById("modal-resolve-review-btn").dataset.key = pendingReview.key;
    } else {
      reviewSec.style.display = "none";
    }

    const authBtn = document.getElementById("modal-authorize-btn");
    authBtn.disabled = !rep.all_passed;
    authBtn.style.opacity = rep.all_passed ? "1" : "0.5";
  } catch (err) {
    gateList.innerHTML = `<div style="color:#f87171;">Failed to execute verification: ${err.message}</div>`;
  }
};
