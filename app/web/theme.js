"use strict";

// Light/dark toggle in the header. With no saved choice the page follows the
// system setting; a click saves the opposite of whatever is showing.
(() => {
  const root = document.documentElement;
  const btn = document.getElementById("theme-toggle");
  const label = btn.querySelector(".label");
  const system = window.matchMedia("(prefers-color-scheme: dark)");

  const current = () => root.dataset.theme || (system.matches ? "dark" : "light");

  function sync() {
    const now = current();
    root.dataset.themeNow = now;
    label.textContent = now === "dark" ? "Dark" : "Light";
    btn.setAttribute("aria-pressed", String(now === "dark"));
    btn.setAttribute("aria-label", `Dark mode is ${now === "dark" ? "on" : "off"}. Switch to ${now === "dark" ? "light" : "dark"} mode`);
  }

  btn.addEventListener("click", () => {
    const next = current() === "dark" ? "light" : "dark";
    root.dataset.theme = next;
    try { localStorage.setItem("theme", next); } catch {}
    sync();
  });
  system.addEventListener("change", sync);
  sync();
})();
