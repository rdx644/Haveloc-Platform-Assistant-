// Haveloc Portal Content Adapter
// Integrates directly with Haveloc DOM (Jobs board, Student Profile, Application Form)
(function() {
  window.HavelocAdapter = {
    detectPortalContext: function() {
      const path = window.location.pathname;
      const isHaveloc = window.location.hostname.includes("haveloc") || 
                        window.location.hostname.includes("hirepro") ||
                        window.location.port === "8080";

      if (!isHaveloc) return null;

      if (document.querySelector(".data-table") || document.querySelector("table") || path.includes("/jobs")) {
        return "JOBS_TABLE";
      }
      if (document.querySelector(".profile-header") || path.includes("/profile")) {
        return "PROFILE";
      }
      if (document.getElementById("placement-application-form") || path.includes("/apply")) {
        return "APPLICATION_FORM";
      }
      return "DASHBOARD";
    },

    enhanceJobsTable: function() {
      const rows = document.querySelectorAll("table tbody tr");
      if (!rows || rows.length === 0) return;

      rows.forEach(row => {
        if (row.querySelector(".agent-quick-apply-btn")) return;

        const statusCell = row.querySelector(".job-status-pill, .status-pill, td:nth-child(6)");
        const isAppOpen = statusCell && (
          statusCell.textContent.toLowerCase().includes("open") ||
          statusCell.querySelector(".status-dot-blue") !== null
        );

        if (isAppOpen) {
          const actionCell = row.querySelector("td:last-child");
          if (actionCell) {
            const btn = document.createElement("button");
            btn.className = "agent-quick-apply-btn";
            btn.innerHTML = "⚡ Agent Apply";
            btn.style.cssText = `
              background: linear-gradient(135deg, #10b981 0%, #059669 100%);
              color: #ffffff;
              border: none;
              padding: 4px 10px;
              border-radius: 6px;
              font-size: 11px;
              font-weight: 600;
              cursor: pointer;
              margin-left: 8px;
              box-shadow: 0 2px 8px rgba(16, 185, 129, 0.3);
              transition: all 0.2s ease;
            `;
            btn.addEventListener("mouseenter", () => btn.style.transform = "scale(1.05)");
            btn.addEventListener("mouseleave", () => btn.style.transform = "scale(1.0)");
            btn.addEventListener("click", (e) => {
              e.preventDefault();
              e.stopPropagation();
              const titleEl = row.querySelector("td:first-child");
              const companyName = titleEl ? titleEl.innerText.split("\n")[0].trim() : "Unknown";
              console.log("[Haveloc Adapter] Quick apply triggered for:", companyName);
              chrome.runtime.sendMessage({
                type: "OPEN_SIDE_PANEL",
                companyName: companyName
              });
            });
            actionCell.appendChild(btn);
          }
        }
      });
    },

    injectTopNavAssistantPill: function() {
      if (document.getElementById("haveloc-agent-nav-pill")) return;
      const nav = document.querySelector(".header-nav, nav, header");
      if (!nav) return;

      const pill = document.createElement("div");
      pill.id = "haveloc-agent-nav-pill";
      pill.style.cssText = `
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background: rgba(16, 185, 129, 0.15);
        border: 1px solid rgba(16, 185, 129, 0.4);
        color: #34d399;
        font-size: 12px;
        font-weight: 600;
        padding: 4px 12px;
        border-radius: 9999px;
        margin-left: 16px;
        cursor: pointer;
      `;
      pill.innerHTML = `<span>⚡</span> <span>Agent Active · Mode: CONFIRM</span>`;
      pill.addEventListener("click", () => {
        chrome.runtime.sendMessage({ type: "OPEN_SIDE_PANEL" });
      });
      nav.appendChild(pill);
    }
  };

  window.addEventListener("DOMContentLoaded", () => {
    setTimeout(() => {
      window.HavelocAdapter.injectTopNavAssistantPill();
      if (window.HavelocAdapter.detectPortalContext() === "JOBS_TABLE") {
        window.HavelocAdapter.enhanceJobsTable();
      }
    }, 800);
  });
})();
