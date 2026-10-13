/* Light/dark theme. Loaded in <head> so the saved choice applies before first paint.
   With no saved choice the OS preference wins (see the prefers-color-scheme block in style.css). */
"use strict";

(() => {
  const KEY = "eams-theme";
  const root = document.documentElement;
  const systemDark = window.matchMedia("(prefers-color-scheme: dark)");

  try {
    const saved = localStorage.getItem(KEY);
    if (saved === "light" || saved === "dark") root.dataset.theme = saved;
  } catch { /* storage blocked: fall back to OS preference */ }

  // Delegated, so toggles rendered later (sidebar, topbar) work without extra wiring.
  document.addEventListener("click", (e) => {
    if (!e.target.closest("[data-theme-toggle]")) return;
    const current = root.dataset.theme || (systemDark.matches ? "dark" : "light");
    const next = current === "dark" ? "light" : "dark";
    root.dataset.theme = next;
    try { localStorage.setItem(KEY, next); } catch { /* not persisted */ }
  });
})();
