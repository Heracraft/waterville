"use strict";

const thread = document.getElementById("thread");
const form = document.getElementById("ask");
const input = document.getElementById("q");
const send = document.getElementById("send");
const intro = document.getElementById("intro");
const history = []; // {role, content}

const msgData = new WeakMap(); // bot message element -> {sources, answer}

const chipHref = (s) => safeUrl(s.open_url) || safeUrl(s.url);

// Minimal Markdown: paragraphs, bullet/numbered lists, bold, italics, [n] citations.
function render(md, sources) {
  const byN = new Map(sources.map((s) => [s.n, s]));
  let occ = 0;
  const chip = (m, n) => {
    const k = occ++;
    const s = byN.get(Number(n));
    if (!s) return escapeHtml(m);
    const label = escapeHtml(s.citation || s.title || "");
    const href = chipHref(s);
    const link = href ? `href="${escapeHtml(href)}" target="_blank" rel="noopener"` : 'role="button" tabindex="0"';
    return `<a class="cite" ${link} data-n="${s.n}" data-occ="${k}" aria-controls="panel" title="${label}" aria-label="Source ${s.n}: ${label}">${n}</a>`;
  };
  // Chips are cut from the raw line so occ counts the same matches as citations(md).
  const inline = (t) => {
    const chips = [];
    const marked = t.replace(/[\u0001\u0002]/g, "").replace(CITE_RE, (m, n) => `\u0001${chips.push(chip(m, n)) - 1}\u0002`);
    return escapeHtml(marked)
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/(^|[^*])\*([^*\n]+)\*/g, "$1<em>$2</em>")
      .replace(/\u0001(\d+)\u0002/g, (_, k) => chips[k]);
  };
  const out = [];
  let list = null;
  for (const raw of md.split("\n")) {
    const line = raw.trimEnd();
    const bullet = line.match(/^\s*[-*•]\s+(.*)$/);
    const num = line.match(/^\s*\d+[.)]\s+(.*)$/);
    if (bullet || num) {
      const tag = bullet ? "ul" : "ol";
      if (list !== tag) {
        if (list) out.push(`</${list}>`);
        out.push(`<${tag}>`);
        list = tag;
      }
      out.push(`<li>${inline((bullet || num)[1])}</li>`);
      continue;
    }
    if (list) {
      out.push(`</${list}>`);
      list = null;
    }
    if (line.trim()) out.push(`<p>${inline(line.replace(/^#+\s*/, ""))}</p>`);
  }
  if (list) out.push(`</${list}>`);
  return out.join("");
}

function pages(s) {
  if (!s.page_start) return "";
  return s.page_end && s.page_end !== s.page_start ? `pages ${s.page_start}-${s.page_end}` : `page ${s.page_start}`;
}

function renderSources(el, sources, answer) {
  if (!sources.length) return;
  const cited = new Set(citations(answer).map((c) => c.n));
  // Show what the answer cites; if it cites nothing, the top few results.
  const shown = cited.size ? sources.filter((s) => cited.has(s.n)) : sources.slice(0, 3);
  const items = shown
    .map((s) => {
      const page = pages(s) ? ` (${pages(s)})` : "";
      const label = escapeHtml((s.title || s.citation) + page);
      const crumb = (s.breadcrumb || "").split(" > ").slice(0, -1).join(" > ");
      const href = chipHref(s);
      const link = href ? `href="${escapeHtml(href)}" target="_blank" rel="noopener"` : 'role="button" tabindex="0"';
      return `<li><span class="n">${s.n}.</span><a class="src" ${link} data-n="${s.n}" aria-controls="panel">${label}</a><span class="crumb">${escapeHtml(crumb)}</span></li>`;
    })
    .join("");
  const det = document.createElement("details");
  det.className = "sources";
  det.open = true;
  det.innerHTML = `<summary>${cited.size ? "Sources" : "Related sections"} (${shown.length})</summary><ol>${items}</ol>`;
  el.appendChild(det);
}

// ---------------------------------------------------------------- source panel

const panel = document.getElementById("panel");
const backdrop = document.getElementById("panel-backdrop");
const panelTitle = document.getElementById("panel-title");
const panelMeta = document.getElementById("panel-meta");
const panelClaim = document.getElementById("panel-claim");
const panelNote = document.getElementById("panel-note");
const panelBody = document.getElementById("panel-body");
const panelScroll = document.getElementById("panel-scroll");
const panelOpen = document.getElementById("panel-open");
const wide = window.matchMedia("(min-width: 960px)");
const calm = window.matchMedia("(prefers-reduced-motion: reduce)");
const TYPE_NAMES = { code: "City Code", attachment: "City Code attachment" };
let active = null; // {msg, n, occ, trigger}

function setMode() {
  const modal = !panel.hidden && !wide.matches;
  if (wide.matches) {
    panel.setAttribute("role", "complementary");
    panel.setAttribute("aria-label", "Source text");
    panel.removeAttribute("aria-labelledby");
    panel.removeAttribute("aria-modal");
  } else {
    panel.setAttribute("role", "dialog");
    panel.setAttribute("aria-modal", "true");
    panel.setAttribute("aria-labelledby", "panel-title");
    panel.removeAttribute("aria-label");
  }
  for (const el of document.querySelectorAll("body > header, body > main")) el.inert = modal;
  backdrop.hidden = !modal;
  document.body.classList.toggle("panel-open", !panel.hidden);
  if (modal && !panel.contains(document.activeElement)) panelTitle.focus({ preventScroll: true });
}

function markFigures(el, figs) {
  if (!figs.size) return;
  const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
  const nodes = [];
  while (walker.nextNode()) nodes.push(walker.currentNode);
  for (const node of nodes) {
    const spans = figureSpans(node.data).filter((f) => figs.has(f.key));
    for (const f of spans.reverse()) {
      const hit = node.splitText(f.start);
      hit.splitText(f.end - f.start);
      const mark = document.createElement("mark");
      hit.replaceWith(mark);
      mark.appendChild(hit);
    }
  }
}

function fillPanel(s, sentences) {
  const isRef = s.source_type === "model_code_ref";
  const where = pages(s);
  panelTitle.innerHTML = `<span class="panel-n">Source ${s.n}</span> ${escapeHtml(s.citation || s.title || "")}`;
  panelMeta.innerHTML =
    `<span class="tag">${escapeHtml(s.label || TYPE_NAMES[s.source_type] || "Source")}</span>` +
    (where ? `<span class="pg">${escapeHtml(where[0].toUpperCase() + where.slice(1))}</span>` : "") +
    (s.breadcrumb ? `<span class="crumb">${escapeHtml(s.breadcrumb)}</span>` : "");
  panelClaim.hidden = !sentences.length;
  panelClaim.innerHTML = sentences.length
    ? `<span class="claim-label">The answer says</span>${sentences.map((t) => `<q>${escapeHtml(t)}</q>`).join("")}`
    : "";

  const blocks = parseBlocks(s.text || "");
  const found = sentences.length ? matchPassages(blocks, sentences) : [];
  panelBody.innerHTML = renderBlocks(blocks, new Set(found.map((f) => f.i)));
  for (const f of found) markFigures(panelBody.querySelector(`[data-b="${f.i}"]`), f.figs);

  const note = isRef
    ? "The full text of this code is not available here. The link below opens the publisher's viewer."
    : sentences.length && !found.length
      ? "Could not pinpoint the exact passage. The full source text is below."
      : "";
  panelNote.textContent = note;
  panelNote.hidden = !note;

  const href = safeUrl(s.open_url) || safeUrl(s.url);
  panelOpen.hidden = !href;
  if (href) panelOpen.href = href;
  const pdf = /\.pdf(?:$|[#?])/i.test(href);
  panelOpen.textContent = pdf && s.page_start ? `Open original PDF at page ${s.page_start}` : "Open original";
  return found.length > 0;
}

function scrollToHighlight() {
  const hit = panelBody.querySelector(".hl");
  if (!hit) return void (panelScroll.scrollTop = 0);
  const top = hit.getBoundingClientRect().top - panelScroll.getBoundingClientRect().top + panelScroll.scrollTop;
  panelScroll.scrollTo({ top: Math.max(0, top - 72), behavior: calm.matches ? "auto" : "smooth" });
}

function syncActive() {
  for (const el of thread.querySelectorAll(".is-active")) {
    el.classList.remove("is-active");
    el.removeAttribute("aria-current");
  }
  if (!active || panel.hidden) return;
  const sel = active.occ == null ? `.sources a[data-n="${active.n}"]` : `.cite[data-occ="${active.occ}"]`;
  const el = active.msg.querySelector(sel);
  if (el) {
    el.classList.add("is-active");
    el.setAttribute("aria-current", "true");
  }
}

function openSource(msg, n, occ, trigger) {
  const data = msgData.get(msg);
  const s = data && data.sources.find((x) => x.n === n);
  if (!s) return false;
  const sentences = occ == null ? sentencesFor(data.answer, n) : [citedSentence(data.answer, occ)].filter(Boolean);
  active = { msg, n, occ, trigger };
  fillPanel(s, sentences);
  panel.hidden = false;
  setMode();
  syncActive();
  panelTitle.focus({ preventScroll: true });
  requestAnimationFrame(scrollToHighlight);
  if (wide.matches && trigger.getBoundingClientRect().bottom > form.getBoundingClientRect().top) {
    trigger.scrollIntoView({ block: "center", behavior: calm.matches ? "auto" : "smooth" });
  }
  return true;
}

function closePanel() {
  if (panel.hidden) return;
  panel.hidden = true;
  setMode();
  const a = active;
  active = null;
  syncActive();
  if (!a) return;
  const sel = a.occ == null ? `.sources a[data-n="${a.n}"]` : `.cite[data-occ="${a.occ}"]`;
  const back = a.trigger.isConnected ? a.trigger : a.msg.querySelector(sel);
  if (back) back.focus();
}

function activate(e) {
  const el = e.target.closest(".cite, .sources a[data-n]");
  if (!el || !thread.contains(el)) return;
  if (e.type === "click" && (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey)) return;
  if (e.type === "keydown" && (el.hasAttribute("href") || (e.key !== "Enter" && e.key !== " "))) return;
  const msg = el.closest(".msg");
  const occ = el.classList.contains("cite") ? Number(el.dataset.occ) : null;
  if (openSource(msg, Number(el.dataset.n), occ, el)) e.preventDefault();
}

thread.addEventListener("click", activate);
thread.addEventListener("keydown", activate);
panel.querySelector(".panel-close").addEventListener("click", closePanel);
backdrop.addEventListener("click", closePanel);
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && !panel.hidden) {
    e.preventDefault();
    closePanel();
  }
});
wide.addEventListener("change", setMode);

// ---------------------------------------------------------------- chat

function addMessage(role, html) {
  const li = document.createElement("li");
  li.className = `msg ${role}`;
  li.innerHTML = html;
  thread.appendChild(li);
  li.scrollIntoView({ block: "end", behavior: "smooth" });
  return li;
}

function showAnswer(bot) {
  const { answer, sources } = msgData.get(bot);
  const focused = bot.contains(document.activeElement) && document.activeElement.dataset.occ;
  bot.innerHTML = render(answer, sources);
  syncActive();
  if (focused) bot.querySelector(`.cite[data-occ="${focused}"]`)?.focus();
}

async function ask(question) {
  intro.hidden = true;
  send.disabled = true;
  addMessage("user", escapeHtml(question));
  history.push({ role: "user", content: question });
  const bot = addMessage("bot", '<p class="typing">Searching the code</p>');
  const data = { sources: [], answer: "" };
  msgData.set(bot, data);
  let failed = null;

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages: history.slice(-6) }),
    });
    if (!res.ok) {
      let detail = "Something went wrong. Please try again.";
      try {
        detail = (await res.json()).detail || detail;
      } catch {}
      throw new Error(typeof detail === "string" ? detail : "Please check your question and try again.");
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      let idx;
      while ((idx = buf.indexOf("\n\n")) >= 0) {
        const raw = buf.slice(0, idx);
        buf = buf.slice(idx + 2);
        const ev = (raw.match(/^event: (.*)$/m) || [])[1];
        const payload = JSON.parse((raw.match(/^data: (.*)$/m) || [, "null"])[1]);
        if (ev === "sources") data.sources = payload;
        else if (ev === "delta") {
          data.answer += payload.text;
          showAnswer(bot);
        } else if (ev === "error") failed = payload.message;
      }
    }
  } catch (e) {
    failed = e.message;
  }

  const { sources, answer } = data;
  if (failed && !answer) {
    bot.innerHTML = `<p class="error">${escapeHtml(failed)}</p>`;
    history.pop();
  } else {
    showAnswer(bot);
    if (failed) bot.insertAdjacentHTML("beforeend", `<p class="error">${escapeHtml(failed)}</p>`);
    renderSources(bot, sources, answer);
    syncActive();
    history.push({ role: "assistant", content: answer });
  }
  send.disabled = false;
  input.focus();
}

form.addEventListener("submit", (e) => {
  e.preventDefault();
  const q = input.value.trim();
  if (!q || send.disabled) return;
  input.value = "";
  input.style.height = "";
  ask(q);
});

input.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    form.requestSubmit();
  }
});

input.addEventListener("input", () => {
  input.style.height = "auto";
  input.style.height = input.scrollHeight + "px";
});

for (const b of document.querySelectorAll(".examples button")) {
  b.addEventListener("click", () => ask(b.textContent));
}
