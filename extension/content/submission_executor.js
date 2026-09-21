// Submission Executor & Confirmation Agent — TURBO MODE
// 3-step pipeline: 1) Extract + Turbo Prepare (1 API call)  2) Fill + In-Page Read-Back  3) Submit
// General-purpose: no hardcoded student IDs. Reads from chrome.storage.
(function() {
  let currentAppId = null;
  let currentAuthToken = null;
  let currentAppHash = null;

  function init() {
    window.HavelocCaptchaGuard.monitor(
      () => {
        window.HavelocDetector.updateBadge(
          "PAUSED",
          "⚠ Human verification required. Automation paused.",
          `<button style="background:#eab308; color:#000; border:none; padding:4px 8px; border-radius:4px; font-size:11px; cursor:pointer;" onclick="document.getElementById('captcha-container').scrollIntoView();">Solve Challenge</button>`
        );
      },
      () => {
        window.HavelocDetector.updateBadge("READY", "Verification challenge passed. Safe to proceed.");
      }
    );

    const pageType = window.HavelocDetector.getPageType();

    // 1. Application Form Page Flow
    if (pageType === "APPLICATION_FORM") {
      const jobId = window.HavelocDetector.extractJobId();
      window.HavelocDetector.updateBadge(
        "FORM DETECTED",
        `Job: ${jobId}`,
        `<button id="agent-prepare-btn" style="background:#2563eb; color:#fff; border:none; padding:5px 10px; border-radius:4px; font-size:11px; font-weight:600; cursor:pointer;">⚡ Turbo Apply</button>`
      );

      const prepareBtn = document.getElementById("agent-prepare-btn");
      if (prepareBtn) {
        prepareBtn.addEventListener("click", () => handleTurboPipeline(jobId));
      }
    }

    // 2. Confirmation Page Flow
    if (pageType === "CONFIRMATION") {
      const receiptEl = document.getElementById("portal-application-receipt-id");
      const portalReceiptId = receiptEl ? receiptEl.innerText.trim() : "HVL-SRM-UNKNOWN";
      
      chrome.storage.local.get(["activeApplicationId", "activeAuthToken"], (data) => {
        if (data.activeApplicationId) {
          chrome.runtime.sendMessage({
            type: "CONFIRM_SUBMISSION",
            applicationId: data.activeApplicationId,
            authToken: data.activeAuthToken,
            portalApplicationId: portalReceiptId,
            evidence: {
              url: window.location.href,
              receipt: portalReceiptId,
              timestamp: new Date().toISOString()
            }
          }, (resp) => {
            console.log("[Haveloc Executor] Submission confirmed with backend:", resp);
            window.HavelocDetector.updateBadge(
              "COMPLETED ✓",
              `Portal Receipt: ${portalReceiptId}`,
              `<span style="color:#10b981; font-weight:600;">Status: Officially Accepted</span>`
            );
          });
        }
      });
    }
  }

  /**
   * TURBO PIPELINE — 3 steps instead of 5:
   * Step 1: Extract DOM + Single turbo-prepare API call (returns everything)
   * Step 2: Fill DOM + In-page read-back validation (zero API calls)
   * Step 3: Submit (if authorized)
   */
  async function handleTurboPipeline(jobId) {
    const t0 = performance.now();
    window.HavelocDetector.updateBadge("⚡ TURBO", "Extracting live job & form from Haveloc DOM...");

    // Step 1: Extract and send to turbo-prepare
    let extractPayload;
    if (window.HavelocLiveExtractor && window.HavelocLiveExtractor.extractFullLiveApplicationPayloadAsync) {
      extractPayload = await window.HavelocLiveExtractor.extractFullLiveApplicationPayloadAsync();
    } else {
      extractPayload = { haveloc_job_id: jobId, title: "Placement Opportunity", company: "Haveloc Partner", is_resume_only: false };
    }

    chrome.runtime.sendMessage({
      type: "TURBO_PREPARE_APPLICATION",
      payload: extractPayload
    }, (initResp) => {
      if (!initResp || (initResp.status && initResp.status >= 400)) {
        const errorMsg = initResp?.data?.detail || initResp?.error || "Turbo prepare failed";
        window.HavelocDetector.updateBadge("ERROR", errorMsg);
        return;
      }

      const appData = initResp.data || initResp;
      currentAppId = appData.application_id;
      chrome.storage.local.set({ activeApplicationId: currentAppId });

      // Check if student is not configured
      if (!appData.student_facts) {
        window.HavelocDetector.updateBadge("SETUP NEEDED", "No student profile found. Open extension options to configure.");
        return;
      }

      // Check if ineligible
      if (appData.state === "INELIGIBLE") {
        window.HavelocDetector.updateBadge(
          "INELIGIBLE ✗",
          `Not eligible: ${(appData.reasons || []).join("; ")}`,
          `<span style="color:#f85149; font-size:11px;">Check requirements and CGPA eligibility.</span>`
        );
        return;
      }

      const resumeRef = appData.selected_resume ? appData.selected_resume.file_reference : "";
      const autonomyMode = appData.autonomy_mode || "CONFIRM";
      const studentFacts = appData.student_facts;

      // Step 2: Fill DOM with everything from the single response
      window.HavelocFormFiller.populateApplication(
        appData.answers || [],
        resumeRef,
        studentFacts
      );

      if (appData.is_resume_only) {
        window.HavelocDetector.updateBadge(
          "RESUME SELECTED ✓",
          `Attached: ${resumeRef} (No Q&A required)`
        );
      }

      // In-page read-back validation (no API call!)
      const rbResult = window.HavelocFormFiller.inPageReadBack(studentFacts, appData.answers || []);
      if (!rbResult.passed) {
        window.HavelocDetector.updateBadge(
          "FIELD MISMATCH ⚠",
          `Discrepancy: ${rbResult.mismatches[0] || "DOM fields mismatch"}`,
          `<button id="agent-sidepanel-fix-btn" style="background:#ef4444; color:#fff; border:none; padding:4px 8px; border-radius:4px; font-size:11px; cursor:pointer;">Review & Fix</button>`
        );
        const fixBtn = document.getElementById("agent-sidepanel-fix-btn");
        if (fixBtn) fixBtn.addEventListener("click", () => chrome.runtime.sendMessage({ type: "OPEN_SIDE_PANEL" }));
        return;
      }

      // Check verification result from turbo-prepare response
      const verReport = appData.verification_report;
      currentAppHash = appData.application_hash;
      currentAuthToken = appData.auth_token;

      if (!verReport || !verReport.all_passed) {
        const failMsg = (verReport?.failure_messages && verReport.failure_messages[0]) || "Verification gate flagged";
        window.HavelocDetector.updateBadge(
          "REVIEW NEEDED",
          `Gate check: ${failMsg}`,
          `<span style="color:#38bdf8; font-size:11px;">Open side panel to review.</span>`
        );
        return;
      }

      const pipelineMs = (performance.now() - t0).toFixed(0);
      chrome.storage.local.set({ activeAuthToken: currentAuthToken });

      // Step 3: Submit or confirm
      if (autonomyMode === "AUTONOMOUS" && currentAuthToken) {
        window.HavelocDetector.updateBadge("AUTONOMOUS SUBMIT", `9/9 verified in ${pipelineMs}ms. Submitting...`);
        executeBrowserSubmit();
      } else {
        window.HavelocDetector.updateBadge(
          `AUTHORIZED (9/9) ✓`,
          `Pipeline: ${pipelineMs}ms | Hash: ${currentAppHash.substring(0, 10)}... [${autonomyMode}]`,
          `<button id="agent-execute-submit-btn" style="background:#10b981; color:#fff; border:none; padding:5px 10px; border-radius:4px; font-size:11px; font-weight:600; cursor:pointer;">Confirm & Submit</button>`
        );

        const submitBtn = document.getElementById("agent-execute-submit-btn");
        if (submitBtn) {
          submitBtn.addEventListener("click", () => executeBrowserSubmit());
        }
      }
    });
  }

  function executeBrowserSubmit() {
    if (window.HavelocCaptchaGuard.detectCaptcha()) {
      alert("Please complete the human verification challenge before submitting.");
      return;
    }

    window.HavelocDetector.updateBadge("SUBMITTING", "Submitting via authenticated browser session...");

    chrome.runtime.sendMessage({
      type: "SUBMIT_APPLICATION",
      applicationId: currentAppId,
      authToken: currentAuthToken,
      applicationHash: currentAppHash
    }, (resp) => {
      if (resp && resp.status === 200) {
        // Trigger native form submission
        const form = document.getElementById("placement-application-form") || document.querySelector("form");
        if (form) form.submit();
      } else {
        window.HavelocDetector.updateBadge("SUBMISSION FAILED", resp?.data?.detail || "Authorization rejected");
      }
    });
  }

  // Runtime message listener from background worker or sidepanel
  chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.type === "EXTRACT_AND_PREPARE") {
      const jobId = request.jobId || (window.HavelocDetector && window.HavelocDetector.extractJobId()) || "HVL-LIVE";
      handleTurboPipeline(jobId);
      sendResponse({ status: "STARTED", jobId: jobId });
    } else if (request.type === "EXECUTE_SUBMIT") {
      executeBrowserSubmit();
      sendResponse({ status: "SUBMITTING" });
    }
    return true;
  });

  window.addEventListener("DOMContentLoaded", init);
})();
