// Haveloc DOM Read-Back Validator (Phase 12)
(function() {
  window.HavelocReadBackValidator = {
    readCurrentDomValues: function() {
      const fieldMap = {};
      const form = document.getElementById("placement-application-form") || document.querySelector("form");
      if (!form) return fieldMap;

      const elements = form.querySelectorAll("input, select, textarea");
      elements.forEach(el => {
        const key = el.name || el.id;
        if (!key) return;

        if (el.type === "checkbox") {
          fieldMap[key] = el.checked;
        } else if (el.type === "radio") {
          if (el.checked) fieldMap[el.name] = el.value;
        } else if (el.tagName === "SELECT") {
          fieldMap[key] = el.options[el.selectedIndex] ? el.options[el.selectedIndex].value : el.value;
        } else {
          fieldMap[key] = el.value;
        }
      });

      console.log("[Haveloc Read-Back Validator] Captured DOM inputs:", fieldMap);
      return fieldMap;
    },

    verifyDomAgainstPlan: function(applicationId, callback) {
      const observedDom = this.readCurrentDomValues();
      chrome.runtime.sendMessage({
        type: "READ_BACK_VERIFY",
        applicationId: applicationId,
        filledFields: observedDom
      }, (resp) => {
        if (!resp || !resp.success) {
          console.error("[Haveloc Read-Back Validator] Verification request failed:", resp?.error);
          callback({ passed: false, error: resp?.error || "Failed to reach agent backend" });
          return;
        }
        callback(resp.data);
      });
    }
  };
})();
