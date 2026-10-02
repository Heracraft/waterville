"use strict";

// Keep the newest message in view while an answer streams in. Scrolling up
// stops the follow; scrolling back to the bottom or asking a new question
// starts it again.
(() => {
  const thread = document.getElementById("thread");
  const NEAR = 80; // px from the bottom that still counts as "at the bottom"
  let follow = true;
  let userInputAt = 0;

  const atBottom = () =>
    window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - NEAR;

  const toBottom = () => window.scrollTo({ top: document.documentElement.scrollHeight, behavior: "auto" });

  // Only scrolls the user causes change the follow state, not our own.
  const markInput = () => (userInputAt = performance.now());
  for (const ev of ["wheel", "touchmove", "pointerdown"]) window.addEventListener(ev, markInput, { passive: true });
  window.addEventListener("keydown", (e) => {
    if (["ArrowUp", "ArrowDown", "PageUp", "PageDown", "Home", "End", " "].includes(e.key) && e.target === document.body) markInput();
    // Opening a source from the keyboard can scroll its chip into view.
    if ((e.key === "Enter" || e.key === " ") && e.target.closest?.(".cite, .sources a")) markInput();
  });
  window.addEventListener("scroll", () => {
    if (performance.now() - userInputAt < 400) follow = atBottom();
  }, { passive: true });

  let queued = false;
  new MutationObserver((records) => {
    for (const r of records) {
      for (const n of r.addedNodes) if (n.classList?.contains("user")) follow = true;
    }
    // The source panel locks the page behind it on narrow screens.
    if (!follow || queued || document.body.classList.contains("panel-open")) return;
    queued = true;
    requestAnimationFrame(() => {
      queued = false;
      if (follow) toBottom();
    });
  }).observe(thread, { childList: true, subtree: true, characterData: true });
})();
