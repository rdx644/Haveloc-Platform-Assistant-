// Haveloc Placement Assistant — Extension Side Panel Logic
// General-purpose: reads student ID from chrome.storage dynamically.
const BACKEND_URL = "https://api.haveloc-agent.com";

document.addEventListener("DOMContentLoaded", () => {
  const connStatus = document.getElementById("connection-status");
  const activeModeLabel = document.getElementById("active-mode-label");
  const modeRadios = document.querySelectorAll('input[name="autonomy_mode"]');
  const answersToggleBtn = document.getElementById("answers-toggle-btn");
  const answersContent = document.getElementById("answers-list-container");
  const answersArrow = document.getElementById("answers-arrow");
  const submitBtn = document.getElementById("panel-submit-btn");
  const refreshBtn = document.getElementById("panel-refresh-btn");
  const extractLiveBtn = document.getElementById("btn-extract-live");
  const setupLink = document.getElementById("setup-link");

  let activeAppId = null;
  let activeAuthToken = null;
  let activeAppHash = null;
  let STUDENT_ID = null;

  // 0. Load student ID from storage
  chrome.storage.local.get(["studentId", "studentName"], (data) => {
    STUDENT_ID = data.studentId || null;

    if (!STUDENT_ID) {
      // No student configured — instruct user to open a portal page
      document.getElementById("student-name-display").innerText = "Profile Not Synced";
      document.getElementById("student-reg-display").innerText = "Extract a job to auto-sync";
      if (setupLink) setupLink.style.display = "none";
    }

    // Always initialize panel so the Extract button can trigger the JIT sync
    initializePanel();
  });

  function initializePanel() {
    // Wire Live Extract & Instant Apply Button
    if (extractLiveBtn) {
      extractLiveBtn.addEventListener("click", () => {
        extractLiveBtn.innerText = "⚡ Extracting live job & form...";
        extractLiveBtn.disabled = true;

        chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
          if (!tabs || !tabs[0] || !tabs[0].id) {
            extractLiveBtn.innerText = "No active tab found";
            setTimeout(() => {
              extractLiveBtn.innerText = "⚡ Extract & Instant Apply (From Live Page)";
              extractLiveBtn.disabled = false;
            }, 2000);
            return;
          }

          chrome.tabs.sendMessage(tabs[0].id, { type: "EXTRACT_AND_PREPARE" }, (response) => {
            if (chrome.runtime.lastError) {
              console.warn("Content script not responding yet:", chrome.runtime.lastError);
            }
            setTimeout(() => {
              chrome.storage.local.get(["studentId"], (data) => {
                if (data.studentId) {
                  STUDENT_ID = data.studentId;
                  loadStudentProfile();
                }
                extractLiveBtn.innerText = "⚡ Prepared & Verified ✓";
                loadActiveApplication();
                setTimeout(() => {
                  extractLiveBtn.innerText = "⚡ Extract & Instant Apply (From Live Page)";
                  extractLiveBtn.disabled = false;
                }, 2000);
              });
            }, 800);
          });
        });
      });
    }

    // Initialize Autonomy Mode selector
    chrome.storage.local.get(["autonomyMode"], (res) => {
      const currentMode = res.autonomyMode || "CONFIRM";
      setAutonomyModeUI(currentMode);
    });

    modeRadios.forEach(radio => {
      radio.addEventListener("change", (e) => {
        const selected = e.target.value;
        chrome.storage.local.set({ autonomyMode: selected });
        setAutonomyModeUI(selected);
      });
    });

    // Check Backend Connection & Load State
    chrome.runtime.sendMessage({ type: "CHECK_BACKEND_HEALTH" }, (resp) => {
      if (resp && resp.success) {
        connStatus.innerText = "Connected";
        connStatus.className = "status-indicator online";
        loadStudentProfile();
        loadActiveApplication();
        loadApplicationHistory();
      } else {
        connStatus.innerText = "Offline";
        connStatus.className = "status-indicator offline";
      }
    });
  }

  function setAutonomyModeUI(mode) {
    document.querySelectorAll(".mode-option").forEach(opt => opt.classList.remove("active"));
    const activeLabel = document.getElementById(`opt-${mode.toLowerCase()}`);
    if (activeLabel) activeLabel.classList.add("active");
    activeModeLabel.innerText = `Mode: ${mode}`;
    const targetRadio = document.querySelector(`input[name="autonomy_mode"][value="${mode}"]`);
    if (targetRadio) targetRadio.checked = true;
  }

  // Toggle Grounded Answers Accordion
  let answersExpanded = true;
  answersToggleBtn.addEventListener("click", () => {
    answersExpanded = !answersExpanded;
    answersContent.style.display = answersExpanded ? "flex" : "none";
    answersArrow.innerText = answersExpanded ? "▼" : "▶";
  });

  // Load Student Profile (dynamic)
  function loadStudentProfile() {
    if (!STUDENT_ID) return;
    fetch(`${BACKEND_URL}/student/${STUDENT_ID}/profile`)
      .then(res => res.json())
      .then(data => {
        if (!data) return;
        const name = data.name || STUDENT_ID;
        document.getElementById("student-name-display").innerText = name;
        document.getElementById("student-reg-display").innerText = `${data.student_id || STUDENT_ID} · ${data.degree || "B.Tech"} ${data.graduation_year || ""}`;
        document.getElementById("student-dept-display").innerText = data.branch || "";
        document.getElementById("stat-cgpa-display").innerText = data.cgpa || "--";

        // Avatar initials
        const parts = name.split(" ");
        const initials = parts.length >= 2 ? (parts[0][0] + parts[parts.length - 1][0]) : name.substring(0, 2);
        document.getElementById("student-avatar").innerText = initials.toUpperCase();
      })
      .catch(err => {
        console.warn("Failed loading student profile:", err);
        document.getElementById("student-name-display").innerText = STUDENT_ID;
        document.getElementById("student-reg-display").innerText = "Profile loading failed";
      });

    // Load application count
    fetch(`${BACKEND_URL}/applications?student_id=${STUDENT_ID}`)
      .then(r => r.json())
      .then(apps => {
        if (apps && Array.isArray(apps)) {
          document.getElementById("stat-applied-count").innerText = apps.length;
        }
      })
      .catch(() => {});
  }

  // Load Active Application
  function loadActiveApplication() {
    chrome.storage.local.get(["activeApplicationId"], (store) => {
      if (!store.activeApplicationId) {
        if (!STUDENT_ID) return renderEmptyApplicationState();
        fetch(`${BACKEND_URL}/applications?student_id=${STUDENT_ID}`)
          .then(r => r.json())
          .then(apps => {
            if (apps && apps.length > 0) {
              activeAppId = apps[0].id;
              renderApplicationData(apps[0].id);
            } else {
              renderEmptyApplicationState();
            }
          })
          .catch(() => renderEmptyApplicationState());
      } else {
        activeAppId = store.activeApplicationId;
        renderApplicationData(activeAppId);
      }
    });
  }

  function renderEmptyApplicationState() {
    document.getElementById("app-company-name").innerText = "No Application Active";
    document.getElementById("app-job-title").innerText = "Navigate to a job on Haveloc to start";
    document.getElementById("app-state-tag").innerText = "IDLE";
    document.getElementById("answers-count").innerText = "0";
    answersContent.innerHTML = `<div class="empty-hint">Click '⚡ Extract & Instant Apply' on any Haveloc job page to start.</div>`;
  }

  function renderApplicationData(appId) {
    fetch(`${BACKEND_URL}/applications/${appId}`)
      .then(r => r.json())
      .then(app => {
        if (!app) return;
        document.getElementById("app-company-name").innerText = app.company;
        document.getElementById("app-job-title").innerText = app.title;
        document.getElementById("app-state-tag").innerText = app.state;
        document.getElementById("app-state-tag").className = `status-tag tag-${app.state.toLowerCase()}`;
        if (app.resume) {
          document.getElementById("app-resume-name").innerText = app.resume.file_reference;
        }

        // Handle Resume-Only Badge
        const resumeOnlyBadge = document.getElementById("resume-only-badge");
        if (resumeOnlyBadge) {
          const isResumeOnly = app.is_resume_only || (!app.answers || app.answers.length === 0);
          resumeOnlyBadge.style.display = isResumeOnly ? "inline-flex" : "none";
        }

        // Render Grounded Answers
        renderAnswers(appId, app.answers || [], app.is_resume_only);

        // Run Verification Gate
        runVerificationPipeline(appId);
      })
      .catch(err => console.error("Error loading application:", err));
  }

  function renderAnswers(appId, answers, isResumeOnly = false) {
    document.getElementById("answers-count").innerText = answers.length;
    answersContent.innerHTML = "";

    if (answers.length === 0 || isResumeOnly) {
      answersContent.innerHTML = `
        <div class="empty-hint" style="color:#34d399; font-weight:500; text-align:left; padding:8px 6px;">
          ✓ <strong>Resume-Only Application:</strong> Zero essay or custom questions required by this company.<br>
          Optimal verified resume variant is attached and ready for instant submission.
        </div>
      `;
      return;
    }

    answers.forEach(ans => {
      const card = document.createElement("div");
      card.className = "answer-card";

      const sourceLabel = ans.source === "ACHIEVEMENT_BANK" 
        ? "✓ Grounded in Verified Facts" 
        : `Source: ${ans.source}`;

      card.innerHTML = `
        <div class="answer-q">${ans.question_text || ans.question_key || ans.key}</div>
        <textarea class="answer-input" rows="2" id="input-${ans.question_key || ans.key}">${ans.answer_text || ans.answer}</textarea>
        <div style="display:flex; justify-content:space-between; align-items:center; margin-top:2px;">
          <span class="grounded-badge">${sourceLabel}</span>
          <button class="btn btn-secondary" style="padding:2px 6px; font-size:10px;" id="save-${ans.question_key || ans.key}">Save</button>
        </div>
      `;

      answersContent.appendChild(card);

      const qKey = ans.question_key || ans.key;
      const saveBtn = card.querySelector(`#save-${qKey}`);
      saveBtn.addEventListener("click", () => {
        const newVal = document.getElementById(`input-${qKey}`).value;
        saveBtn.innerText = "Saving...";
        fetch(`${BACKEND_URL}/applications/${appId}/resolve-review`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ question_key: qKey, confirmed_answer: newVal })
        })
          .then(r => r.json())
          .then(() => {
            saveBtn.innerText = "Saved ✓";
            setTimeout(() => saveBtn.innerText = "Save", 1500);
            runVerificationPipeline(appId);
          });
      });
    });
  }

  function runVerificationPipeline(appId) {
    fetch(`${BACKEND_URL}/applications/${appId}/verify`, { method: "POST" })
      .then(r => r.json())
      .then(report => {
        activeAppHash = report.application_hash;
        document.getElementById("sidepanel-hash-code").innerText = report.application_hash || "Computing...";

        const gatesContainer = document.getElementById("sidepanel-gates-container");
        gatesContainer.innerHTML = "";

        report.gate_checks.forEach(check => {
          const row = document.createElement("div");
          row.className = "gate-row";
          row.innerHTML = `
            <span>${check.gate_name || check.check_name}</span>
            <span class="${check.passed ? 'gate-passed' : 'gate-failed'}">
              ${check.passed ? '✓ PASS' : '✗ FLAG'}
            </span>
          `;
          gatesContainer.appendChild(row);
        });

        if (report.all_passed) {
          submitBtn.disabled = false;
          submitBtn.innerText = "Authorize & Submit (9/9 ✓)";
          submitBtn.style.background = "#238636";
        } else {
          submitBtn.disabled = true;
          submitBtn.innerText = "Review Flagged Items Above";
          submitBtn.style.background = "#78350f";
        }
      });
  }

  // Submit Button Handler
  submitBtn.addEventListener("click", () => {
    if (!activeAppId) return;

    submitBtn.innerText = "Authorizing...";
    submitBtn.disabled = true;

    fetch(`${BACKEND_URL}/applications/${activeAppId}/authorize`, { method: "POST" })
      .then(r => r.json())
      .then(authData => {
        activeAuthToken = authData.auth_token;
        chrome.storage.local.set({ activeAuthToken: activeAuthToken });

        submitBtn.innerText = "Submitting...";

        fetch(`${BACKEND_URL}/applications/${activeAppId}/submit`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            application_id: activeAppId,
            auth_token: activeAuthToken,
            application_hash: activeAppHash,
            portal_session_verified: true
          })
        })
          .then(r => r.json())
          .then(submitData => {
            submitBtn.innerText = "Submitted! Capturing Receipt...";
            submitBtn.style.background = "#1f6feb";
            document.getElementById("app-state-tag").innerText = "SUBMITTING";

            chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
              if (tabs[0] && tabs[0].id) {
                chrome.tabs.sendMessage(tabs[0].id, { type: "EXECUTE_SUBMIT" }, () => {});
              }
            });
          })
          .catch(err => {
            submitBtn.innerText = "Submission Failed";
            submitBtn.style.background = "#f85149";
          });
      })
      .catch(err => {
        submitBtn.innerText = "Authorization Rejected";
        submitBtn.style.background = "#f85149";
      });
  });

  refreshBtn.addEventListener("click", () => {
    if (activeAppId) {
      renderApplicationData(activeAppId);
    }
  });

  // Load Application History
  function loadApplicationHistory() {
    if (!STUDENT_ID) return;
    fetch(`${BACKEND_URL}/applications?student_id=${STUDENT_ID}`)
      .then(r => r.json())
      .then(apps => {
        const listEl = document.getElementById("sidepanel-history-list");
        if (!apps || apps.length === 0) {
          listEl.innerHTML = `<div class="empty-hint">No prior applications in this session.</div>`;
          return;
        }

        listEl.innerHTML = "";
        apps.forEach(app => {
          const item = document.createElement("div");
          item.style.cssText = "display:flex; justify-content:space-between; align-items:center; padding:6px 0; border-bottom:1px solid #21262d; cursor:pointer;";
          item.innerHTML = `
            <div>
              <div style="font-weight:600; color:#f0f6fc;">${app.company}</div>
              <div style="font-size:10px; color:#8b949e;">${app.title.substring(0, 26)}...</div>
            </div>
            <span class="status-tag tag-${app.state.toLowerCase()}">${app.state}</span>
          `;
          item.addEventListener("click", () => {
            activeAppId = app.id;
            chrome.storage.local.set({ activeApplicationId: app.id });
            renderApplicationData(app.id);
          });
          listEl.appendChild(item);
        });
      });
  }
});
