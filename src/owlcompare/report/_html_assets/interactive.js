/*
 * owlcompare HTML report — interactive enhancements (Component 17).
 *
 * Pure vanilla ES2022, no framework, no build step. Every behaviour here is
 * *enhancement*: the report is fully readable with this script disabled
 * (docs/design/FIRST_PAINT.md). Handlers are attached programmatically — the
 * document carries no inline on* attributes.
 *
 * Behaviours: (1) section collapse/expand, (2) theme cycle auto->light->dark,
 * (3) JSON download, (4) copy link. Nothing else — no analytics, no network.
 */
(function () {
  "use strict";

  var THEMES = ["auto", "light", "dark"];
  var STORAGE_KEY = "owlcompare-theme";
  var root = document.documentElement;

  /* --- Theme toggle ---------------------------------------------------- */

  // localStorage is wrapped: under file:// sandboxing or a strict privacy
  // policy it can throw, in which case the toggle still works for the session
  // (it just does not persist). See spec § localStorage blocked.
  function readStoredTheme() {
    try {
      var value = window.localStorage.getItem(STORAGE_KEY);
      return THEMES.indexOf(value) >= 0 ? value : null;
    } catch (e) {
      return null;
    }
  }

  function storeTheme(theme) {
    try {
      window.localStorage.setItem(STORAGE_KEY, theme);
    } catch (e) {
      /* persistence unavailable; current-session override still applies */
    }
  }

  function applyTheme(theme) {
    // 'auto' means: defer to prefers-color-scheme, so remove the override.
    if (theme === "auto") {
      root.removeAttribute("data-theme");
    } else {
      root.setAttribute("data-theme", theme);
    }
  }

  function initTheme() {
    var stored = readStoredTheme();
    if (stored) {
      applyTheme(stored);
    }
  }

  function currentTheme() {
    var explicit = root.getAttribute("data-theme");
    return THEMES.indexOf(explicit) >= 0 ? explicit : "auto";
  }

  function cycleTheme() {
    var next = THEMES[(THEMES.indexOf(currentTheme()) + 1) % THEMES.length];
    applyTheme(next);
    storeTheme(next);
  }

  /* --- Section collapse/expand ----------------------------------------- */

  function toggleSection(section) {
    var collapsed = section.getAttribute("data-collapsed") === "true";
    section.setAttribute("data-collapsed", collapsed ? "false" : "true");
    var toggle = section.querySelector(".section-toggle");
    if (toggle) {
      toggle.setAttribute("aria-expanded", collapsed ? "true" : "false");
    }
  }

  function initSections() {
    var headers = document.querySelectorAll(".change-section .section-header");
    headers.forEach(function (header) {
      var section = header.closest(".change-section");
      header.addEventListener("click", function () {
        toggleSection(section);
      });
    });
    // Esc collapses the section currently containing focus (ACCESSIBILITY.md).
    document.addEventListener("keydown", function (event) {
      if (event.key !== "Escape") {
        return;
      }
      var active = document.activeElement;
      var section = active && active.closest ? active.closest(".change-section") : null;
      if (section && section.getAttribute("data-collapsed") !== "true") {
        toggleSection(section);
      }
    });
  }

  /* --- JSON download --------------------------------------------------- */

  function downloadJson() {
    var payload = document.getElementById("diff-json");
    if (!payload) {
      return;
    }
    var blob = new Blob([payload.textContent], { type: "application/json" });
    var url = URL.createObjectURL(blob);
    var link = document.createElement("a");
    link.href = url;
    link.download = "owlcompare-diff.json";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    // Release the object URL on the next tick, after the click is processed.
    setTimeout(function () {
      URL.revokeObjectURL(url);
    }, 0);
  }

  /* --- Copy link ------------------------------------------------------- */

  function flashMessage(button, text) {
    var note = document.createElement("span");
    note.className = "toolbar-msg";
    note.textContent = text;
    button.parentNode.insertBefore(note, button.nextSibling);
    setTimeout(function () {
      if (note.parentNode) {
        note.parentNode.removeChild(note);
      }
    }, 2000);
  }

  function copyLink(button) {
    // navigator.clipboard is unavailable on some older browsers and under
    // file:// restrictions; tell the user rather than failing silently.
    if (!navigator.clipboard || !navigator.clipboard.writeText) {
      flashMessage(button, "Not supported in this context");
      return;
    }
    navigator.clipboard.writeText(window.location.href).then(
      function () {
        flashMessage(button, "Copied");
      },
      function () {
        flashMessage(button, "Not supported in this context");
      }
    );
  }

  /* --- Wiring ---------------------------------------------------------- */

  function initActions() {
    document.querySelectorAll("[data-action]").forEach(function (el) {
      el.addEventListener("click", function (event) {
        var action = el.getAttribute("data-action");
        if (action === "theme-toggle") {
          cycleTheme();
        } else if (action === "download-json" || action === "view-json") {
          event.preventDefault();
          downloadJson();
        } else if (action === "copy-link") {
          event.preventDefault();
          copyLink(el);
        }
      });
    });
  }

  initTheme();
  initSections();
  initActions();
})();
