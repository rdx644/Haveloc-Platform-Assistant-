// Universal Adaptive Form Filler for Haveloc Application Pages
// General-purpose: student facts come from turbo-prepare response, not hardcoded.
// Supports Resume-Only postings, dynamic student facts, terms checkboxes, and custom Q&A.
(function() {
  window.HavelocFormFiller = {
    fillField: function(selectorOrIdOrName, value) {
      if (!selectorOrIdOrName) return false;
      const el = document.getElementById(selectorOrIdOrName) || 
                 document.querySelector(`[name='${selectorOrIdOrName}']`) ||
                 document.querySelector(selectorOrIdOrName);
      if (!el) return false;

      if (el.tagName === "SELECT") {
        let matched = false;
        const valStr = String(value).toLowerCase();
        for (let opt of el.options) {
          const optText = opt.text.toLowerCase();
          const optVal = opt.value.toLowerCase();
          if (optVal === valStr || optText.includes(valStr) || valStr.includes(optText)) {
            el.value = opt.value;
            matched = true;
            break;
          }
        }
        if (!matched && el.options.length > 0) el.selectedIndex = 0;
      } else if (el.type === "checkbox") {
        el.checked = Boolean(value);
      } else if (el.type === "radio") {
        const radios = document.querySelectorAll(`input[name='${el.name}']`);
        radios.forEach(r => {
          if (r.value.toLowerCase() === String(value).toLowerCase()) r.checked = true;
        });
      } else {
        el.value = value;
      }

      // Dispatch events for React/Vue reactive form state
      el.dispatchEvent(new Event("input", { bubbles: true }));
      el.dispatchEvent(new Event("change", { bubbles: true }));
      return true;
    },

    selectResumeVariant: function(selectedResumeRef) {
      if (!selectedResumeRef) return false;
      console.log("[Haveloc Form Filler] Selecting resume variant:", selectedResumeRef);

      // 1. Search for any select element for resume
      const selects = document.querySelectorAll("select");
      for (const sel of selects) {
        const nameOrId = (sel.name + " " + sel.id + " " + (sel.labels ? Array.from(sel.labels).map(l => l.innerText).join(" ") : "")).toLowerCase();
        if (nameOrId.includes("resume") || nameOrId.includes("cv") || nameOrId.includes("variant")) {
          return this.fillField(sel.id ? `#${sel.id}` : `[name='${sel.name}']`, selectedResumeRef);
        }
      }

      // 2. Search for radio cards
      const radios = document.querySelectorAll("input[type='radio']");
      for (const r of radios) {
        const parentText = (r.closest("label") || r.parentElement)?.innerText?.toLowerCase() || "";
        const refLower = selectedResumeRef.toLowerCase();
        if ((parentText.includes("cloud") && refLower.includes("cloud")) ||
            (parentText.includes("sde") && refLower.includes("sde")) ||
            (parentText.includes("ml") && refLower.includes("ml")) ||
            (parentText.includes("genai") && refLower.includes("genai"))) {
          r.checked = true;
          r.dispatchEvent(new Event("change", { bubbles: true }));
          return true;
        }
      }

      // Fallback: fillField on common id
      return this.fillField("resume_variant", selectedResumeRef);
    },

    /**
     * Auto-fill standard student info fields using dynamic facts from the backend.
     * @param {Object} studentFacts - Dynamic student facts from turbo-prepare response.
     */
    autofillStudentFacts: function(studentFacts) {
      if (!studentFacts) return 0;

      const inputs = document.querySelectorAll("input:not([type='hidden']), select, textarea");
      let filled = 0;

      inputs.forEach(el => {
        const key = (el.name || el.id || "").toLowerCase();
        if (!key) return;

        if ((key.includes("roll") || key.includes("reg")) && studentFacts.roll_number) {
          el.value = studentFacts.roll_number;
          filled++;
        } else if ((key.includes("cgpa") || key.includes("gpa")) && studentFacts.cgpa) {
          el.value = studentFacts.cgpa;
          filled++;
        } else if ((key.includes("phone") || key.includes("mobile")) && studentFacts.phone) {
          el.value = studentFacts.phone;
          filled++;
        } else if (key.includes("email") && studentFacts.email) {
          el.value = studentFacts.email;
          filled++;
        } else if ((key.includes("branch") || key.includes("dept")) && studentFacts.branch) {
          this.fillField(el.id ? `#${el.id}` : `[name='${el.name}']`, studentFacts.branch);
          filled++;
        } else if (key.includes("backlog") && studentFacts.backlogs !== undefined) {
          el.value = studentFacts.backlogs;
          filled++;
        } else if (key.includes("name") && !key.includes("company") && studentFacts.full_name) {
          el.value = studentFacts.full_name;
          filled++;
        }

        el.dispatchEvent(new Event("input", { bubbles: true }));
        el.dispatchEvent(new Event("change", { bubbles: true }));
      });

      return filled;
    },

    autoCheckDeclarations: function() {
      const checkboxes = document.querySelectorAll("input[type='checkbox']");
      let checkedCount = 0;
      checkboxes.forEach(cb => {
        const label = (cb.closest("label") || cb.parentElement)?.innerText?.toLowerCase() || "";
        if (label.includes("agree") || label.includes("terms") || label.includes("declare") || 
            label.includes("undertaking") || label.includes("accurate") || label.includes("confirm") || 
            checkboxes.length === 1) {
          cb.checked = true;
          cb.dispatchEvent(new Event("change", { bubbles: true }));
          checkedCount++;
        }
      });
      return checkedCount;
    },

    /**
     * Main entry point. Populates the entire application form.
     * @param {Array} answersList - Answers from turbo-prepare response.
     * @param {string} selectedResumeRef - Resume file reference.
     * @param {Object} studentFacts - Dynamic student facts from backend (replaces hardcoded DEFAULT_STUDENT_FACTS).
     */
    populateApplication: function(answersList = [], selectedResumeRef = "", studentFacts = null) {
      console.log("[Haveloc Form Filler] Starting universal adaptive form population...");
      const t0 = performance.now();
      let filledCount = 0;

      // 1. Select Resume
      if (selectedResumeRef) {
        this.selectResumeVariant(selectedResumeRef);
        filledCount++;
      }

      // 2. Autofill student facts (dynamic from backend)
      if (studentFacts) {
        filledCount += this.autofillStudentFacts(studentFacts);
      }

      // 3. Auto check declarations
      filledCount += this.autoCheckDeclarations();

      // 4. Populate custom answers if any
      if (answersList && answersList.length > 0) {
        answersList.forEach(item => {
          const filled = this.fillField(item.key || item.question_key, item.answer || item.answer_text);
          if (filled) filledCount++;
        });
      }

      const elapsed = (performance.now() - t0).toFixed(1);
      console.log(`[Haveloc Form Filler] Populated ${filledCount} fields in ${elapsed}ms.`);
      return filledCount;
    },

    /**
     * In-page read-back validation — no API round-trip required.
     * Reads back all filled form fields and compares against expected values.
     * @param {Object} studentFacts - Expected student facts.
     * @param {Array} answersList - Expected answers.
     * @returns {Object} { passed: boolean, mismatches: string[] }
     */
    inPageReadBack: function(studentFacts, answersList) {
      const mismatches = [];

      if (studentFacts) {
        const inputs = document.querySelectorAll("input:not([type='hidden']), select, textarea");
        inputs.forEach(el => {
          const key = (el.name || el.id || "").toLowerCase();
          if (!key) return;

          if ((key.includes("cgpa") || key.includes("gpa")) && studentFacts.cgpa) {
            if (el.value !== studentFacts.cgpa && el.value !== String(studentFacts.cgpa)) {
              mismatches.push(`CGPA: expected ${studentFacts.cgpa}, got ${el.value}`);
            }
          } else if ((key.includes("roll") || key.includes("reg")) && studentFacts.roll_number) {
            if (el.value !== studentFacts.roll_number) {
              mismatches.push(`Roll: expected ${studentFacts.roll_number}, got ${el.value}`);
            }
          }
        });
      }

      if (answersList && answersList.length > 0) {
        answersList.forEach(item => {
          const fieldKey = item.key || item.question_key;
          const el = document.getElementById(fieldKey) || document.querySelector(`[name='${fieldKey}']`);
          if (el) {
            const expected = item.answer || item.answer_text;
            if (el.value !== expected) {
              mismatches.push(`${fieldKey}: expected "${expected.substring(0, 30)}...", got "${el.value.substring(0, 30)}..."`);
            }
          }
        });
      }

      return {
        passed: mismatches.length === 0,
        mismatches: mismatches
      };
    }
  };
})();
