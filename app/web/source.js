"use strict";

// Pure helpers for the source panel: a safe Markdown renderer for chunk text and
// a deterministic matcher that finds the passage an answer sentence came from.
// Loaded as a classic script before app.js; also require()-able from node tests.

const CITE_RE = /\[(\d{1,2})(?:[.,:;\s][^\]\n]{0,40})?\]/g;

function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

function safeUrl(u) {
  return typeof u === "string" && /^https?:\/\/[^\s"'<>]+$/i.test(u) ? u : "";
}

// ---------------------------------------------------------------- Markdown

const BR = "\u0000";

function inlineMd(t) {
  return escapeHtml(String(t).replace(/<br\s*\/?>/gi, BR))
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/(^|[^*\w])\*([^*\n]+)\*(?![*\w])/g, "$1<em>$2</em>")
    .replace(/(^|[^\w])_([^_\n]+)_(?!\w)/g, "$1<em>$2</em>")
    .replace(/\u0000/g, "<br>");
}

function plainText(t) {
  return String(t)
    .replace(/<br\s*\/?>/gi, " ")
    .replace(/\*\*|__/g, "")
    .replace(/(^|[^\w])[*_]([^*_\n]+)[*_](?!\w)/g, "$1$2")
    .replace(/\s+/g, " ")
    .trim();
}

function splitRow(line) {
  return line.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map((c) => c.trim());
}

const isSepRow = (cells) => cells.length > 0 && cells.every((c) => /^:?-{2,}:?$/.test(c));

// Blocks are what the matcher scores and the renderer marks: headings,
// paragraphs, list items and table rows.
function parseBlocks(text) {
  const blocks = [];
  let para = null;
  let table = 0;
  let inTable = false;
  for (const raw of String(text || "").split("\n")) {
    const line = raw.replace(/\s+$/, "");
    if (/^\s*\|/.test(line)) {
      para = null;
      if (!inTable) table++;
      inTable = true;
      const cells = splitRow(line);
      if (isSepRow(cells)) {
        for (const b of blocks) if (b.type === "tr" && b.table === table) b.head = true;
        continue;
      }
      blocks.push({ type: "tr", table, cells, head: false, text: cells.map(plainText).filter(Boolean).join(" | ") });
      continue;
    }
    inTable = false;
    if (!line.trim()) {
      para = null;
      continue;
    }
    const h = line.match(/^\s*(#{1,6})\s+(.*)$/);
    const li = line.match(/^(\s*)[-*•]\s+(.*)$/);
    if (h) {
      para = null;
      blocks.push({ type: "h", level: h[1].length, md: h[2], text: plainText(h[2]) });
    } else if (li) {
      para = null;
      blocks.push({ type: "li", depth: Math.floor(li[1].replace(/\t/g, "  ").length / 2), md: li[2], text: plainText(li[2]) });
    } else if (para) {
      para.md += " " + line.trim();
      para.text = plainText(para.md);
    } else {
      para = { type: "p", md: line.trim(), text: plainText(line) };
      blocks.push(para);
    }
  }
  return blocks;
}

function renderTable(rows, attrs) {
  const width = Math.max(...rows.map(({ b }) => b.cells.length));
  const row = ({ b, i }) => {
    const tag = b.head ? "th" : "td";
    const cells = Array.from({ length: width }, (_, k) => `<${tag}>${inlineMd(b.cells[k] || "")}</${tag}>`).join("");
    return `<tr${attrs(i)}>${cells}</tr>`;
  };
  const head = rows.filter((r) => r.b.head);
  const body = rows.filter((r) => !r.b.head);
  return (
    `<div class="tbl"><table>` +
    (head.length ? `<thead>${head.map(row).join("")}</thead>` : "") +
    `<tbody>${body.map(row).join("")}</tbody></table></div>`
  );
}

// hl: Set of block indexes to highlight.
function renderBlocks(blocks, hl = new Set()) {
  const attrs = (i) => ` data-b="${i}"${hl.has(i) ? ' class="hl"' : ""}`;
  const out = [];
  const depths = [];
  const closeLists = (to = -1) => {
    while (depths.length && depths[depths.length - 1] > to) {
      out.push("</li></ul>");
      depths.pop();
    }
  };
  for (let i = 0; i < blocks.length; i++) {
    const b = blocks[i];
    if (b.type === "li") {
      closeLists(b.depth);
      if (depths.length && depths[depths.length - 1] === b.depth) out.push("</li>");
      else {
        out.push("<ul>");
        depths.push(b.depth);
      }
      out.push(`<li><div${attrs(i)}>${inlineMd(b.md)}</div>`);
      continue;
    }
    closeLists();
    if (b.type === "tr") {
      const rows = [];
      while (i < blocks.length && blocks[i].type === "tr" && blocks[i].table === b.table) rows.push({ b: blocks[i], i: i++ });
      i--;
      out.push(renderTable(rows, attrs));
    } else if (b.type === "h") {
      const tag = `h${Math.min(6, b.level + 2)}`;
      out.push(`<${tag}${attrs(i)}>${inlineMd(b.md)}</${tag}>`);
    } else {
      out.push(`<p${attrs(i)}>${inlineMd(b.md)}</p>`);
    }
  }
  closeLists();
  return out.join("");
}

// ---------------------------------------------------------------- answer sentences

const NO_SPLIT_BEFORE = /(?:^|[\s(])(?:[A-Za-z]|no|nos|ord|ch|sec|secs|art|st|vs|etc|e\.g|i\.e|m\.r\.s|cmr|approx)\.$/i;

function sentenceSpans(line) {
  const spans = [];
  let start = 0;
  for (const m of line.matchAll(/[.!?](?:\[[^\]\n]{1,40}\])*(?=\s+["'(*]*[A-Z])/g)) {
    const end = m.index + m[0].length;
    if (NO_SPLIT_BEFORE.test(line.slice(Math.max(0, m.index - 11), m.index + 1))) continue;
    spans.push([start, end]);
    start = end;
  }
  spans.push([start, line.length]);
  return spans;
}

function cleanSentence(s) {
  return plainText(s.replace(CITE_RE, " ").replace(/^\s*(?:[-*•]|\d+[.)])\s+/, "").replace(/^#+\s*/, "")).replace(/\s+([.,;:!?])/g, "$1");
}

// The sentence around a citation that starts at pos and ends at end in md.
function sentenceAround(md, pos, end) {
  const lineStart = md.lastIndexOf("\n", pos - 1) + 1;
  const nl = md.indexOf("\n", end);
  const line = md.slice(lineStart, nl < 0 ? md.length : nl);
  const rel = pos - lineStart;
  const spans = sentenceSpans(line);
  let k = spans.findIndex(([s, e]) => rel >= s && rel < e);
  if (k < 0) k = spans.length - 1;
  let [s, e] = spans[k];
  const before = cleanSentence(line.slice(s, rel));
  if (k > 0 && before.split(/\s+/).filter(Boolean).length < 2) s = spans[k - 1][0];
  return cleanSentence(line.slice(s, e));
}

function citations(md) {
  return [...String(md).matchAll(CITE_RE)].map((m) => ({ n: Number(m[1]), pos: m.index, end: m.index + m[0].length }));
}

// The sentence holding the occ-th citation chip in the answer.
function citedSentence(md, occ) {
  const c = citations(md)[occ];
  return c ? sentenceAround(md, c.pos, c.end) : "";
}

// Every distinct sentence that cites source n.
function sentencesFor(md, n) {
  const seen = new Set();
  for (const c of citations(md)) if (c.n === n) seen.add(sentenceAround(md, c.pos, c.end));
  return [...seen].filter(Boolean);
}

// ---------------------------------------------------------------- matcher

const STOP = new Set(
  ("a about above after again against all also am an and any are as at be because been before being below between both but by can " +
    "could did do does doing down during each either few for from further had has have having he her here hers him his how i if in " +
    "into is it its itself just may me might more most must my no nor not now of off on once only or other our out over own per same " +
    "shall she should so some such than that the their theirs them then there these they this those through to too under until up upon " +
    "us very was we were what when where which while who whom why will with within without would you your yours herein thereof " +
    "section sections subsection paragraph chapter code city waterville maine see also").split(" ")
);

const NUM_WORDS = {
  one: 1, two: 2, three: 3, four: 4, five: 5, six: 6, seven: 7, eight: 8, nine: 9, ten: 10, eleven: 11, twelve: 12,
  fifteen: 15, twenty: 20, thirty: 30, forty: 40, fifty: 50, sixty: 60, seventy: 70, hundred: 100,
};
const UNITS = {
  foot: "ft", feet: "ft", ft: "ft", inch: "in", inches: "in", mile: "mi", miles: "mi", day: "day", days: "day",
  year: "yr", years: "yr", month: "mo", months: "mo", hour: "hr", hours: "hr", minute: "min", minutes: "min",
  acre: "acre", acres: "acre", room: "room", rooms: "room", percent: "%", pounds: "lb", gallons: "gal",
};
const NUM = `\\d+(?:,\\d{3})*(?:\\.\\d+)?|${Object.keys(NUM_WORDS).join("|")}`;
const UNIT_RE = `(%|square feet|${Object.keys(UNITS).join("|")})(?![a-z])`;
const unitKey = (n, u) => {
  u = u.toLowerCase();
  return `${NUM_WORDS[n.toLowerCase()] ?? n.replace(/,/g, "")} ${u === "%" ? "%" : u === "square feet" ? "sqft" : UNITS[u]}`;
};
const FIGURE_RES = [
  [new RegExp(`\\((\\d+(?:,\\d{3})*(?:\\.\\d+)?)\\)\\s?(?:-\\s?)?${UNIT_RE}`, "gi"), (m) => unitKey(m[1], m[2])],
  [/\$\s?\d+(?:,\d{3})*(?:\.\d{1,2})?/g, (m) => "$" + m[0].replace(/[$\s,]/g, "").replace(/\.0+$/, "")],
  [new RegExp(`\\b(${NUM})\\s?(?:-\\s?)?${UNIT_RE}`, "gi"), (m) => unitKey(m[1], m[2])],
  [/\b[A-Z]{0,4}\d+[A-Z]?(?:-[A-Z0-9]+)+(?:\.\d+)*(?:\([A-Za-z0-9]+\))*/g, (m) => m[0].toLowerCase()],
  [/\b[A-Z]{1,4}\d+(?:\.\d+)+\b/g, (m) => m[0].toLowerCase()],
  [/\b\d{2,}(?:,\d{3})*(?:\.\d+)?\b/g, (m) => m[0].replace(/,/g, "")],
];

// Figure spans in text: money, numbers with units, section and date forms, multi-digit numbers.
function figureSpans(text) {
  const spans = [];
  const taken = (s, e) => spans.some((x) => s < x.end && e > x.start);
  for (const [re, key] of FIGURE_RES) {
    for (const m of String(text).matchAll(re)) {
      const start = m.index;
      const end = start + m[0].length;
      if (!taken(start, end)) spans.push({ start, end, key: key(m) });
    }
  }
  return spans.sort((a, b) => a.start - b.start);
}

const stem = (w) => (w.length > 4 && w.endsWith("ies") ? w.slice(0, -3) + "y" : w.length > 3 && /[^s]s$/.test(w) ? w.slice(0, -1) : w);

function tokens(text) {
  return (String(text).toLowerCase().replace(/[‘’]/g, "'").match(/[a-z0-9]+(?:'[a-z]+)?/g) || []).map((w) => stem(w.replace(/'s$/, "")));
}

function features(text) {
  const plain = String(text).replace(/^\s*(?:\(?[A-Za-z0-9]{1,3}[.)]\s+)+/, "");
  const all = tokens(plain);
  const grams = new Set();
  for (let i = 0; i + 4 <= all.length; i++) grams.add(all.slice(i, i + 4).join(" "));
  return {
    words: new Set(all.filter((w) => w.length > 2 && !/^\d/.test(w) && !STOP.has(w))),
    figs: new Set(figureSpans(plain).map((f) => f.key)),
    grams,
  };
}

const shared = (a, b) => [...a].filter((x) => b.has(x));

function scoreFeatures(f, sent) {
  const words = shared(f.words, sent.words).length;
  const figs = shared(f.figs, sent.figs);
  const grams = Math.min(5, shared(f.grams, sent.grams).length);
  return { score: words + 3 * figs.length + 2 * grams, figs };
}

const scoreBlock = (block, sent) => scoreFeatures(features(typeof block === "string" ? block : block.text), sent);

const MIN_SCORE = 4;
const CLOSE = 0.85;
const MAX_HL = 4;
const GROUP_GAIN = 1.5;
const MAX_ITEMS = 12;

// Table rows also carry the words of their table's header rows and of earlier
// rows without figures, since bare row labels like "4" mean nothing alone.
function blockFeatures(blocks) {
  return blocks.map((b, i) => {
    const f = features(b.text);
    if (b.type !== "tr" || b.head) return f;
    for (const x of blocks.slice(0, i)) {
      if (x.type === "tr" && x.table === b.table && (x.head || !figureSpans(x.text).length)) {
        for (const w of features(x.text).words) f.words.add(w);
      }
    }
    return f;
  });
}

const ENUM = /^\s*\(?[A-Za-z0-9]{1,3}[.)]\s/;
const itemKind = (b) => (b.type === "li" ? "li" : (b.text.match(ENUM) || [""])[0].replace(/\d+/g, "1").replace(/[a-z]/g, "a").replace(/[A-Z]/g, "A").trim());

// A lead-in ending in ":" and the run of same-style items after it.
function listGroups(blocks) {
  const out = [];
  blocks.forEach((b, i) => {
    const kind = blocks[i + 1] && itemKind(blocks[i + 1]);
    if (!kind || !/:\s*$/.test(b.text)) return;
    const items = [];
    for (let j = i + 1; j < blocks.length && items.length < MAX_ITEMS && itemKind(blocks[j]) === kind; j++) items.push(j);
    out.push({ i, items });
  });
  return out;
}

function unionFeatures(fs) {
  const u = { words: new Set(), figs: new Set(), grams: new Set() };
  for (const f of fs) for (const key of Object.keys(u)) for (const v of f[key]) u[key].add(v);
  return u;
}

// A sentence that sums up a whole list: the lead-in plus the items it touches,
// when together they beat the best single block by a clear margin.
function bestGroup(groups, fs, scores, sent, best) {
  let pick = null;
  for (const g of groups) {
    const score = scoreFeatures(unionFeatures([g.i, ...g.items].map((k) => fs[k])), sent).score;
    const hits = g.items.filter((k) => scores[k].score > 0);
    if (score >= MIN_SCORE && score > best * GROUP_GAIN && hits.length >= 2 && (!pick || score > pick.score)) pick = { score, blocks: [g.i, ...hits] };
  }
  return pick;
}

// Picks the blocks that best support each sentence. Returns the highlighted
// block indexes (in document order) and the figure keys shared with each.
function matchPassages(blocks, sentences) {
  const fs = blockFeatures(blocks);
  const groups = listGroups(blocks);
  const hl = new Map();
  const add = (x) => hl.set(x.i, new Set([...(hl.get(x.i) || []), ...x.figs]));
  for (const s of sentences) {
    const sent = features(s);
    if (!sent.words.size && !sent.figs.size) continue;
    const scores = fs.map((f, i) => ({ i, ...scoreFeatures(f, sent) }));
    const scored = scores.filter((x) => x.score >= MIN_SCORE);
    const best = scored.length ? Math.max(...scored.map((x) => x.score)) : 0;
    const group = bestGroup(groups, fs, scores, sent, best);
    if (group) {
      group.blocks.forEach((k) => add(scores[k]));
      continue;
    }
    scored
      .filter((x) => x.score >= best * CLOSE)
      .sort((a, b) => b.score - a.score || a.i - b.i)
      .slice(0, MAX_HL)
      .forEach(add);
  }
  return [...hl.keys()].sort((a, b) => a - b).map((i) => ({ i, figs: hl.get(i) }));
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    escapeHtml, safeUrl, inlineMd, plainText, parseBlocks, renderBlocks, sentenceSpans, citedSentence,
    sentencesFor, citations, figureSpans, tokens, features, scoreBlock, matchPassages, CITE_RE,
  };
}
