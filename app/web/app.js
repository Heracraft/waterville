"use strict";

const thread = document.getElementById("thread");
const form = document.getElementById("ask");
const input = document.getElementById("q");
const send = document.getElementById("send");
const intro = document.getElementById("intro");
const history = []; // {role, content}

function escapeHtml(s) {
  return s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

// Minimal Markdown: paragraphs, bullet/numbered lists, bold, italics, [n] citations.
function render(md, sources) {
  const byN = new Map(sources.map((s) => [s.n, s]));
  const inline = (t) =>
    escapeHtml(t)
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/(^|[^*])\*([^*\n]+)\*/g, "$1<em>$2</em>")
      .replace(/\[(\d{1,2})(?:[.,:;\s][^\]\n]{0,40})?\]/g, (m, n) => {
        const s = byN.get(Number(n));
        if (!s) return m;
        const label = escapeHtml(s.citation || s.title || "");
        return `<a class="cite" href="${escapeHtml(s.url)}" target="_blank" rel="noopener" title="${label}">${n}</a>`;
      });
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

function renderSources(el, sources, answer) {
  if (!sources.length) return;
  const cited = new Set([...answer.matchAll(/\[(\d{1,2})(?:[.,:;\s][^\]\n]{0,40})?\]/g)].map((m) => Number(m[1])));
  // Show what the answer cites; if it cites nothing, the top few results.
  const shown = cited.size ? sources.filter((s) => cited.has(s.n)) : sources.slice(0, 3);
  const items = shown
    .map((s) => {
      const page = s.page_start ? ` (page ${s.page_start})` : "";
      const label = escapeHtml((s.title || s.citation) + page);
      const crumb = (s.breadcrumb || "").split(" > ").slice(0, -1).join(" > ");
      return `<li><span class="n">${s.n}.</span><a href="${escapeHtml(s.url)}" target="_blank" rel="noopener">${label}</a><span class="crumb">${escapeHtml(crumb)}</span></li>`;
    })
    .join("");
  const det = document.createElement("details");
  det.className = "sources";
  det.open = true;
  det.innerHTML = `<summary>${cited.size ? "Sources" : "Related sections"} (${shown.length})</summary><ol>${items}</ol>`;
  el.appendChild(det);
}

function addMessage(role, html) {
  const li = document.createElement("li");
  li.className = `msg ${role}`;
  li.innerHTML = html;
  thread.appendChild(li);
  li.scrollIntoView({ block: "end", behavior: "smooth" });
  return li;
}

async function ask(question) {
  intro.hidden = true;
  send.disabled = true;
  addMessage("user", escapeHtml(question));
  history.push({ role: "user", content: question });
  const bot = addMessage("bot", '<p class="typing">Searching the code</p>');
  let sources = [];
  let answer = "";
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
        const data = JSON.parse((raw.match(/^data: (.*)$/m) || [, "null"])[1]);
        if (ev === "sources") sources = data;
        else if (ev === "delta") {
          answer += data.text;
          bot.innerHTML = render(answer, sources);
        } else if (ev === "error") failed = data.message;
      }
    }
  } catch (e) {
    failed = e.message;
  }

  if (failed && !answer) {
    bot.innerHTML = `<p class="error">${escapeHtml(failed)}</p>`;
    history.pop();
  } else {
    bot.innerHTML = render(answer, sources);
    if (failed) bot.insertAdjacentHTML("beforeend", `<p class="error">${escapeHtml(failed)}</p>`);
    renderSources(bot, sources, answer);
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
