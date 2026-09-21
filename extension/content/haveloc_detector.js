// Haveloc Portal Detector & UI Injected Overlay
(function() {
  window.HavelocDetector = {
    getPageType: function() {
      const path = window.location.pathname;
      if (document.getElementById("submission-confirmation-card") || path.includes("/confirmation")) {
        return "CONFIRMATION";
      }
      if (document.getElementById("placement-application-form") || path.includes("/apply")) {
        return "APPLICATION_FORM";
      }
      if (document.getElementById("haveloc-portal-container") || path.includes("/jobs")) {
        return "JOB_BOARD";
      }
      return "UNKNOWN";
    },

    extractJobId: function() {
      const hiddenInput = document.getElementById("job_id");
      if (hiddenInput && hiddenInput.value) return hiddenInput.value;
      const match = window.location.pathname.match(/\/jobs\/([^\/]+)/);
      return match ? match[1] : null;
    },

    injectOverlayBadge: function() {
      if (document.getElementById("haveloc-agent-badge")) return;

      const badge = document.createElement("div");
      badge.id = "haveloc-agent-badge";
      badge.style.cssText = `
        position: fixed;
        bottom: 20px;
        right: 20px;
        z-index: 999999;
        background: #111827;
        border: 1px solid #3b82f6;
        border-radius: 10px;
        padding: 12px 18px;
        box-shadow: 0 8px 30px rgba(0,0,0,0.6);
        color: #f3f4f6;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        font-size: 13px;
        display: flex;
        flex-direction: column;
        gap: 6px;
        max-width: 320px;
      `;

      badge.innerHTML = `
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <span style="font-weight:600; color:#60a5fa;">⚡ Haveloc Assistant</span>
          <span id="haveloc-badge-status" style="font-size:11px; background:#1e3a8a; color:#93c5fd; padding:2px 6px; border-radius:4px;">IDLE</span>
        </div>
        <div id="haveloc-badge-msg" style="font-size:12px; color:#9ca3af;">Portal session connected.</div>
        <div id="haveloc-badge-actions" style="display:flex; gap:6px; margin-top:4px;"></div>
      `;

      document.body.appendChild(badge);
    },

    updateBadge: function(status, message, actionsHtml = "") {
      const statusEl = document.getElementById("haveloc-badge-status");
      const msgEl = document.getElementById("haveloc-badge-msg");
      const actionsEl = document.getElementById("haveloc-badge-actions");
      if (statusEl) statusEl.innerText = status;
      if (msgEl) msgEl.innerText = message;
      if (actionsEl && actionsHtml) actionsEl.innerHTML = actionsHtml;
    }
  };

  // Initialize overlay on load
  window.addEventListener("DOMContentLoaded", () => {
    window.HavelocDetector.injectOverlayBadge();
    const pageType = window.HavelocDetector.getPageType();
    console.log("[Haveloc Detector] Detected Page Type:", pageType);
  });
})();
