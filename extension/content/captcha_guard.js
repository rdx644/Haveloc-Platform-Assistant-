// CAPTCHA Guard for Haveloc Extension
// Adheres strictly to Principle 2.2: Halts automation upon detecting CAPTCHA/challenges.

(function() {
  window.HavelocCaptchaGuard = {
    isPaused: false,

    detectCaptcha: function() {
      // Look for common CAPTCHA elements, Google reCAPTCHA, hCaptcha, Cloudflare turnstile, or mock portal challenge
      const selectors = [
        "#captcha-container",
        ".g-recaptcha",
        ".h-captcha",
        "#cf-turnstile",
        "iframe[src*='captcha']",
        "iframe[src*='recaptcha']",
        "iframe[src*='turnstile']"
      ];

      for (const sel of selectors) {
        const el = document.querySelector(sel);
        if (el && el.offsetParent !== null && window.getComputedStyle(el).display !== "none") {
          return true;
        }
      }
      return false;
    },

    monitor: function(onCaptchaDetected, onCaptchaResolved) {
      const check = () => {
        const hasCaptcha = this.detectCaptcha();
        if (hasCaptcha && !this.isPaused) {
          this.isPaused = true;
          console.warn("[Haveloc Guard] ⚠ CAPTCHA Detected! Halting automated execution.");
          if (onCaptchaDetected) onCaptchaDetected();
        } else if (!hasCaptcha && this.isPaused) {
          this.isPaused = false;
          console.log("[Haveloc Guard] ✓ CAPTCHA challenge resolved by student. Automation safe to resume.");
          if (onCaptchaResolved) onCaptchaResolved();
        }
      };

      // Periodic check and DOM observer
      setInterval(check, 1000);
      const observer = new MutationObserver(check);
      observer.observe(document.body, { childList: true, subtree: true, attributes: true });
    }
  };
})();
