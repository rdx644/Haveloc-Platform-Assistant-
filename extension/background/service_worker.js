// Background Service Worker for Haveloc Placement Assistant
// General-purpose: reads student ID dynamically from chrome.storage.local
const BACKEND_URL = "https://api.haveloc-agent.com";

// Helper: get student ID from storage (returns a Promise)
function getStudentId() {
  return new Promise((resolve) => {
    chrome.storage.local.get(["studentId"], (data) => {
      resolve(data.studentId || null);
    });
  });
}

// Initialize default settings in chrome storage
chrome.runtime.onInstalled.addListener(() => {
  chrome.storage.local.get(["studentId"], (existing) => {
    // Set defaults but preserve existing student ID if already configured
    const defaults = {
      backendUrl: BACKEND_URL,
      autonomyMode: "CONFIRM",
      safeMode: true,
      activeApplications: []
    };

    chrome.storage.local.set(defaults);

    // Setup defaults without forcing a setup page
    if (existing.studentId) {
      console.log("[Haveloc Extension] Initialized with Student ID:", existing.studentId);
    } else {
      console.log("[Haveloc Extension] Initialized without Student ID. Awaiting Just-In-Time extraction from Haveloc.");
    }
  });

  if (chrome.sidePanel && chrome.sidePanel.setPanelBehavior) {
    chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true }).catch((err) => {
      console.warn("Could not set side panel behavior:", err);
    });
  }
});

// Listener for messages from content scripts, sidepanel, and popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.type === "OPEN_SIDE_PANEL") {
    if (chrome.sidePanel && chrome.sidePanel.open) {
      if (sender.tab && sender.tab.id) {
        chrome.sidePanel.open({ tabId: sender.tab.id })
          .then(() => sendResponse({ success: true }))
          .catch(err => sendResponse({ success: false, error: err.message }));
        return true;
      }
    }
    sendResponse({ success: false, note: "sidePanel API not available directly" });
    return true;
  }

  if (request.type === "CHECK_BACKEND_HEALTH") {
    fetch(`${BACKEND_URL}/health`)
      .then(res => res.json())
      .then(data => sendResponse({ success: true, data }))
      .catch(err => sendResponse({ success: false, error: err.message }));
    return true;
  }

  if (request.type === "GET_STUDENT_ID") {
    getStudentId().then(id => sendResponse({ studentId: id }));
    return true;
  }

  if (request.type === "GET_STUDENT_PROFILE") {
    getStudentId().then(studentId => {
      const sid = request.studentId || studentId;
      if (!sid) {
        sendResponse({ success: false, error: "No student configured. Open setup wizard." });
        return;
      }
      fetch(`${BACKEND_URL}/profile?student_id=${sid}`)
        .then(res => res.json())
        .then(data => sendResponse({ success: true, data }))
        .catch(err => sendResponse({ success: false, error: err.message }));
    });
    return true;
  }

  if (request.type === "TURBO_PREPARE_APPLICATION") {
    chrome.storage.local.get(["autonomyMode", "studentId"], (store) => {
      const studentId = request.payload?.student_id || store.studentId;
      if (!studentId) {
        sendResponse({ status: 400, data: { detail: "No student configured. Open setup wizard." } });
        return;
      }
      const mode = request.autonomyMode || store.autonomyMode || "CONFIRM";
      const payload = Object.assign({}, request.payload, {
        student_id: studentId,
        autonomy_mode: mode
      });
      fetch(`${BACKEND_URL}/applications/turbo-prepare`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      })
        .then(res => res.json().then(data => ({ status: res.status, data })))
        .then(result => sendResponse(result))
        .catch(err => sendResponse({ status: 500, error: err.message }));
    });
    return true;
  }

  if (request.type === "LIVE_PREPARE_APPLICATION") {
    chrome.storage.local.get(["autonomyMode", "studentId"], (store) => {
      const studentId = request.payload?.student_id || store.studentId;
      if (!studentId) {
        sendResponse({ status: 400, data: { detail: "No student configured." } });
        return;
      }
      const mode = request.autonomyMode || store.autonomyMode || "CONFIRM";
      const payload = Object.assign({}, request.payload, {
        student_id: studentId,
        autonomy_mode: mode
      });
      fetch(`${BACKEND_URL}/applications/live-prepare`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      })
        .then(res => res.json().then(data => ({ status: res.status, data })))
        .then(result => sendResponse(result))
        .catch(err => sendResponse({ status: 500, error: err.message }));
    });
    return true;
  }

  if (request.type === "INITIATE_APPLICATION") {
    chrome.storage.local.get(["autonomyMode", "studentId"], (store) => {
      const studentId = request.studentId || store.studentId;
      const mode = request.autonomyMode || store.autonomyMode || "CONFIRM";
      fetch(`${BACKEND_URL}/applications/initiate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          student_id: studentId,
          job_id: request.jobId,
          autonomy_mode: mode
        })
      })
        .then(res => res.json().then(data => ({ status: res.status, data })))
        .then(result => sendResponse(result))
        .catch(err => sendResponse({ status: 500, error: err.message }));
    });
    return true;
  }

  if (request.type === "READ_BACK_VERIFY") {
    fetch(`${BACKEND_URL}/applications/${request.applicationId}/read-back-verify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        application_id: request.applicationId,
        filled_fields: request.filledFields || {}
      })
    })
      .then(res => res.json())
      .then(data => sendResponse({ success: true, data }))
      .catch(err => sendResponse({ success: false, error: err.message }));
    return true;
  }

  if (request.type === "RESOLVE_REVIEW") {
    fetch(`${BACKEND_URL}/applications/${request.applicationId}/resolve-review`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question_key: request.questionKey,
        confirmed_answer: request.confirmedAnswer
      })
    })
      .then(res => res.json())
      .then(data => sendResponse({ success: true, data }))
      .catch(err => sendResponse({ success: false, error: err.message }));
    return true;
  }

  if (request.type === "VERIFY_APPLICATION") {
    fetch(`${BACKEND_URL}/applications/${request.applicationId}/verify`, { method: "POST" })
      .then(res => res.json())
      .then(data => sendResponse({ success: true, data }))
      .catch(err => sendResponse({ success: false, error: err.message }));
    return true;
  }

  if (request.type === "AUTHORIZE_APPLICATION") {
    fetch(`${BACKEND_URL}/applications/${request.applicationId}/authorize`, { method: "POST" })
      .then(res => res.json())
      .then(data => sendResponse({ success: true, data }))
      .catch(err => sendResponse({ success: false, error: err.message }));
    return true;
  }

  if (request.type === "SUBMIT_APPLICATION") {
    fetch(`${BACKEND_URL}/applications/${request.applicationId}/submit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        application_id: request.applicationId,
        auth_token: request.authToken,
        application_hash: request.applicationHash,
        portal_session_verified: true
      })
    })
      .then(res => res.json().then(data => ({ status: res.status, data })))
      .then(result => sendResponse(result))
      .catch(err => sendResponse({ status: 500, error: err.message }));
    return true;
  }

  if (request.type === "CONFIRM_SUBMISSION") {
    fetch(`${BACKEND_URL}/applications/${request.applicationId}/confirm`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        application_id: request.applicationId,
        auth_token: request.authToken,
        portal_application_id: request.portalApplicationId,
        status_code: request.statusCode || 200,
        confirmation_evidence: request.evidence || {}
      })
    })
      .then(res => res.json())
      .then(data => sendResponse({ success: true, data }))
      .catch(err => sendResponse({ success: false, error: err.message }));
    return true;
  }
});
