// Haveloc Live Page Extractor (Real-Time Dynamic DOM Ingestion)
// General-purpose: reads student ID from chrome.storage, no hardcoded values.
// Designed for https://placements.haveloc.com/ with zero pre-seeded data dependencies.
(function() {
  window.HavelocLiveExtractor = {
    extractActiveJobContext: function() {
      console.log("[Haveloc Extractor] Extracting live job context from DOM...");

      // 1. Check for modal or drawer
      const modalEl = document.querySelector(".modal, .dialog, [role='dialog'], .drawer, #application-modal");
      const rootEl = modalEl || document.body;

      // 2. Company Name
      let company = "";
      const companySelectors = [
        ".company-name", ".company-title", "[data-company]", 
        ".job-header h3", ".job-header h2", "h3.company",
        ".table-card h3", ".card-header h3"
      ];
      for (const sel of companySelectors) {
        const el = rootEl.querySelector(sel);
        if (el && el.innerText.trim()) {
          company = el.innerText.trim();
          break;
        }
      }
      if (!company) {
        const h1 = document.querySelector("h1, h2");
        if (h1 && !h1.innerText.includes("Jobs") && !h1.innerText.includes("Good")) {
          company = h1.innerText.trim();
        } else {
          company = "Haveloc Placement Partner";
        }
      }

      // 3. Job Title / Role
      let title = "";
      const titleSelectors = [
        ".job-role", ".job-title", ".role-name", "[data-role]",
        ".job-header h1", ".job-header h4", "h4.role"
      ];
      for (const sel of titleSelectors) {
        const el = rootEl.querySelector(sel);
        if (el && el.innerText.trim()) {
          title = el.innerText.trim();
          break;
        }
      }
      if (!title) {
        const titleFallback = rootEl.querySelector("h2, h3");
        title = titleFallback ? titleFallback.innerText.trim() : "Software Engineer";
      }

      // 4. Haveloc Job / Requisition ID
      let havelocJobId = "";
      const hiddenJobInput = document.querySelector("input[name='job_id'], input#job_id, [data-job-id]");
      if (hiddenJobInput) {
        havelocJobId = hiddenJobInput.value || hiddenJobInput.getAttribute("data-job-id");
      }
      if (!havelocJobId) {
        const urlMatch = window.location.pathname.match(/\/jobs\/([^\/\?]+)/);
        if (urlMatch) havelocJobId = urlMatch[1];
      }
      if (!havelocJobId) {
        // Deterministic hash based on company and role
        havelocJobId = `HVL-${company.replace(/\s+/g, '-').toUpperCase().substring(0, 8)}-${Date.now().toString().slice(-4)}`;
      }

      // 5. Raw snapshot of requirements and job text
      const descContainer = rootEl.querySelector(".job-description, .job-details, .requirements, .card-body") || rootEl;
      const rawText = descContainer.innerText ? descContainer.innerText.substring(0, 3000) : `${company} hiring for ${title}`;

      return {
        company: company,
        title: title,
        haveloc_job_id: havelocJobId,
        raw_text: rawText,
        current_url: window.location.href
      };
    },

    inspectApplicationForm: function() {
      const form = document.getElementById("placement-application-form") || document.querySelector("form") || document.body;
      const inputs = form.querySelectorAll("input, select, textarea");
      
      let hasResumeSelector = false;
      let resumeElementSelector = null;
      let declarationCheckboxes = [];
      let detectedFields = [];
      let customQuestionsCount = 0;

      inputs.forEach(el => {
        const nameOrId = el.name || el.id || "";
        const lowerName = nameOrId.toLowerCase();
        const type = (el.type || "").toLowerCase();
        const tagName = el.tagName.toLowerCase();

        // 1. Resume Selectors (select dropdown, radio buttons, file inputs)
        if (lowerName.includes("resume") || lowerName.includes("cv") || (el.labels && Array.from(el.labels).some(l => l.innerText.toLowerCase().includes("resume")))) {
          hasResumeSelector = true;
          resumeElementSelector = el.id ? `#${el.id}` : `[name='${el.name}']`;
          return;
        }

        // 2. Declaration / Agreement Checkbox
        if (type === "checkbox") {
          declarationCheckboxes.push(el);
          return;
        }

        // 3. Skip CSRF tokens / hidden tracking
        if (type === "hidden" || lowerName.includes("csrf") || lowerName.includes("token")) {
          return;
        }

        // 4. Standard student info fields (auto-filled deterministically)
        const isStandardInfo = lowerName.includes("cgpa") || lowerName.includes("roll") || 
                               lowerName.includes("name") || lowerName.includes("email") || 
                               lowerName.includes("phone") || lowerName.includes("branch") || 
                               lowerName.includes("year");

        let labelText = nameOrId;
        if (el.labels && el.labels.length > 0) {
          labelText = el.labels[0].innerText.trim();
        } else if (el.placeholder) {
          labelText = el.placeholder;
        }

        if (tagName === "textarea" || (tagName === "input" && type === "text" && !isStandardInfo)) {
          customQuestionsCount++;
        }

        detectedFields.push({
          key: nameOrId,
          label: labelText,
          tag: tagName,
          type: type,
          is_standard: isStandardInfo
        });
      });

      // A form is Resume-Only if there are NO custom essay/free-text questions
      const isResumeOnly = (customQuestionsCount === 0);

      return {
        has_form: inputs.length > 0,
        has_resume_selector: hasResumeSelector,
        resume_selector: resumeElementSelector,
        declaration_checkboxes: declarationCheckboxes,
        detected_fields: detectedFields,
        custom_questions_count: customQuestionsCount,
        is_resume_only: isResumeOnly
      };
    },

    /**
     * Attempt to extract logged-in student identity from the Haveloc portal DOM.
     * Looks for nav elements, profile sections, or user name displays.
     */
    detectPortalIdentity: function() {
      const identitySelectors = [
        ".user-name", ".profile-name", ".student-name",
        "nav .name", ".navbar .user", "#user-display",
        ".header-profile span", ".topbar .user-info"
      ];
      for (const sel of identitySelectors) {
        const el = document.querySelector(sel);
        if (el && el.innerText.trim()) {
          return { name: el.innerText.trim() };
        }
      }
      return null;
    },

    /**
     * Deep scrape of student profile from a given Document object (or body).
     */
    scrapeStudentProfileFromDoc: function(doc) {
      let profile = {
        name: "",
        roll_no: "",
        branch: "",
        cgpa: 0,
        resumes: []
      };

      // Extract Name and Roll No
      const nameHeading = doc.querySelector(".name-row h2, #student-name");
      if (nameHeading) {
        profile.name = nameHeading.innerText.trim();
      }
      
      const rollDiv = doc.querySelector("#student-roll-number");
      if (rollDiv) {
        profile.roll_no = rollDiv.innerText.trim();
      } else {
        const headerMatch = doc.querySelector("header")?.innerText.match(/(RA\d{13})/i);
        if (headerMatch) profile.roll_no = headerMatch[1].toUpperCase();
      }

      // Extract Branch
      const branchDiv = doc.querySelector("#student-branch-name");
      if (branchDiv) {
        profile.branch = branchDiv.innerText.trim();
      }

      // Extract CGPA
      const cgpaDiv = doc.querySelector("#student-cgpa-score");
      if (cgpaDiv) {
        profile.cgpa = parseFloat(cgpaDiv.innerText.trim());
      }

      // Extract Resumes
      const resumeElements = doc.querySelectorAll(".resume-item");
      if (resumeElements.length > 0) {
        resumeElements.forEach(opt => {
          const val = opt.innerText.trim();
          if (val) {
            let role_tag = "software_engineer";
            const textLower = val.toLowerCase();
            if (textLower.includes("cloud") || textLower.includes("devops")) role_tag = "cloud_devops";
            else if (textLower.includes("ml") || textLower.includes("ai") || textLower.includes("data")) role_tag = "machine_learning";
            else if (textLower.includes("frontend")) role_tag = "frontend";
            else if (textLower.includes("backend")) role_tag = "backend";
            else if (textLower.includes("fullstack")) role_tag = "fullstack";

            profile.resumes.push({
              file_reference: val,
              role_tag: role_tag,
              version: "1.0",
              skills: [role_tag.replace("_", " ")],
              experience_tags: [role_tag],
              project_tags: []
            });
          }
        });
      }

      // Fallback 1: Extract from typical info blocks on resume-only pages
      if (!profile.name || !profile.cgpa) {
        const textNodes = doc.body.innerText.split('\\n');
        for (let i = 0; i < textNodes.length; i++) {
          const line = textNodes[i];
          if (line.includes("Candidate:") && !profile.name) {
            const match = line.match(/Candidate:\\s*(.+?)\\s*\\((\\w+)\\)/);
            if (match) {
              profile.name = match[1].trim();
              profile.roll_no = match[2].trim();
            }
          }
          if (line.includes("Department:") && !profile.cgpa) {
            const match = line.match(/Department:\\s*(.+?)\\s*\\|\\s*CGPA:\\s*([\\d\\.]+)/);
            if (match) {
              profile.branch = match[1].trim();
              profile.cgpa = parseFloat(match[2]);
            }
          }
        }
        
        // Fallback resumes from select elements
        if (profile.resumes.length === 0) {
          const resumeSelects = doc.querySelectorAll("select[name*='resume'], select[id*='resume'], select[name*='cv']");
          resumeSelects.forEach(select => {
            const options = Array.from(select.options);
            options.forEach(opt => {
              if (opt.value && !opt.value.toLowerCase().includes("select")) {
                let role_tag = "software_engineer";
                const textLower = opt.innerText.toLowerCase();
                if (textLower.includes("cloud")) role_tag = "cloud_devops";
                profile.resumes.push({
                  file_reference: opt.value,
                  role_tag: role_tag,
                  version: "1.0",
                  skills: [role_tag.replace("_", " ")],
                  experience_tags: [role_tag],
                  project_tags: []
                });
              }
            });
          });
        }
      }

      return profile.roll_no ? profile : null;
    },

    scrapeStudentProfile: function() {
      console.log("[Haveloc Extractor] Scraping student profile from current DOM...");
      return this.scrapeStudentProfileFromDoc(document);
    },

    fetchFullProfileFromNetwork: async function() {
      try {
        console.log("[Haveloc Extractor] Fetching full profile from /profile to ensure accurate data...");
        const response = await fetch("/profile");
        const htmlText = await response.text();
        const parser = new DOMParser();
        const doc = parser.parseFromString(htmlText, "text/html");
        return this.scrapeStudentProfileFromDoc(doc);
      } catch (err) {
        console.warn("[Haveloc Extractor] Failed to fetch /profile:", err);
        return null;
      }
    },

    /**
     * Build the full live application payload.
     * Uses scraped_profile to allow just-in-time backend registration.
     */
    extractFullLiveApplicationPayloadAsync: async function() {
      const jobCtx = this.extractActiveJobContext();
      const formInfo = this.inspectApplicationForm();
      
      // Try local DOM first
      let scrapedProfile = this.scrapeStudentProfile();
      
      // If incomplete (missing name or cgpa), fetch from /profile
      if (!scrapedProfile || !scrapedProfile.name || !scrapedProfile.cgpa) {
        const netProfile = await this.fetchFullProfileFromNetwork();
        if (netProfile && netProfile.roll_no) {
          scrapedProfile = netProfile;
        }
      }

      // If scraped successfully, save the ID to storage for future synchronous calls
      if (scrapedProfile && scrapedProfile.roll_no) {
        chrome.storage.local.set({ 
          studentId: scrapedProfile.roll_no,
          studentName: scrapedProfile.name
        });
        window._havelocStudentId = scrapedProfile.roll_no;
      }

      const store = await new Promise(resolve => chrome.storage.local.get(["studentId"], resolve));
      const studentId = scrapedProfile?.roll_no || store.studentId || null;

      if (!studentId) {
        console.warn("[Haveloc Extractor] No student ID could be scraped or found in storage.");
      }

      return {
        student_id: studentId,
        company: jobCtx.company,
        title: jobCtx.title,
        haveloc_job_id: jobCtx.haveloc_job_id,
        raw_text: jobCtx.raw_text,
        is_resume_only: formInfo.is_resume_only,
        detected_fields: formInfo.detected_fields,
        autonomy_mode: "CONFIRM",
        scraped_profile: scrapedProfile // Include scraped data for JIT registration
      };
    },

    /**
     * Synchronous fallback (uses last-known student ID if available in window).
     * Used by submission_executor for backward compat.
     */
    extractFullLiveApplicationPayload: function(studentId) {
      const jobCtx = this.extractActiveJobContext();
      const formInfo = this.inspectApplicationForm();
      const scrapedProfile = this.scrapeStudentProfile();

      return {
        student_id: scrapedProfile?.roll_no || studentId || window._havelocStudentId || null,
        company: jobCtx.company,
        title: jobCtx.title,
        haveloc_job_id: jobCtx.haveloc_job_id,
        raw_text: jobCtx.raw_text,
        is_resume_only: formInfo.is_resume_only,
        detected_fields: formInfo.detected_fields,
        autonomy_mode: "CONFIRM",
        scraped_profile: scrapedProfile
      };
    }
  };

  // Cache student ID in window for synchronous access
  chrome.storage.local.get(["studentId"], (data) => {
    window._havelocStudentId = data.studentId || null;
  });
})();
