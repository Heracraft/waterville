// Pure helpers for the source panel: a safe Markdown renderer for chunk text and
// a deterministic matcher that finds the passage an answer sentence came from.
// Ported line for line from app/web/source.js.

export const CITE_RE = /\[(\d{1,2})(?:[.,:;\s][^\]\n]{0,40})?\]/g;

export function escapeHtml(s: unknown): string {
	return String(s ?? '').replace(
		/[&<>"']/g,
		(c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c] as string
	);
}

export function safeUrl(u: unknown): string {
	return typeof u === 'string' && /^https?:\/\/[^\s"'<>]+$/i.test(u) ? u : '';
}

// ---------------------------------------------------------------- Markdown

const BR = '\u0000';

export function inlineMd(t: string): string {
	return escapeHtml(String(t).replace(/<br\s*\/?>/gi, BR))
		.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
		.replace(/(^|[^*\w])\*([^*\n]+)\*(?![*\w])/g, '$1<em>$2</em>')
		.replace(/(^|[^\w])_([^_\n]+)_(?!\w)/g, '$1<em>$2</em>')
		.replace(/\u0000/g, '<br>');
}

export function plainText(t: string): string {
	return String(t)
		.replace(/<br\s*\/?>/gi, ' ')
		.replace(/\*\*|__/g, '')
		.replace(/(^|[^\w])[*_]([^*_\n]+)[*_](?!\w)/g, '$1$2')
		.replace(/\s+/g, ' ')
		.trim();
}

function splitRow(line: string): string[] {
	return line
		.trim()
		.replace(/^\|/, '')
		.replace(/\|$/, '')
		.split('|')
		.map((c) => c.trim());
}

const isSepRow = (cells: string[]) => cells.length > 0 && cells.every((c) => /^:?-{2,}:?$/.test(c));

export type Block =
	| { type: 'tr'; table: number; cells: string[]; head: boolean; text: string }
	| { type: 'h'; level: number; md: string; text: string }
	| { type: 'li'; depth: number; md: string; text: string }
	| { type: 'p'; md: string; text: string };

// Blocks are what the matcher scores and the renderer marks: headings,
// paragraphs, list items and table rows.
export function parseBlocks(text: string): Block[] {
	const blocks: Block[] = [];
	let para: Extract<Block, { type: 'p' }> | null = null;
	let table = 0;
	let inTable = false;
	for (const raw of String(text || '').split('\n')) {
		const line = raw.replace(/\s+$/, '');
		if (/^\s*\|/.test(line)) {
			para = null;
			if (!inTable) table++;
			inTable = true;
			const cells = splitRow(line);
			if (isSepRow(cells)) {
				for (const b of blocks) if (b.type === 'tr' && b.table === table) b.head = true;
				continue;
			}
			blocks.push({ type: 'tr', table, cells, head: false, text: cells.map(plainText).filter(Boolean).join(' | ') });
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
			blocks.push({ type: 'h', level: h[1].length, md: h[2], text: plainText(h[2]) });
		} else if (li) {
			para = null;
			blocks.push({
				type: 'li',
				depth: Math.floor(li[1].replace(/\t/g, '  ').length / 2),
				md: li[2],
				text: plainText(li[2])
			});
		} else if (para) {
			para.md += ' ' + line.trim();
			para.text = plainText(para.md);
		} else {
			para = { type: 'p', md: line.trim(), text: plainText(line) };
			blocks.push(para);
		}
	}
	return blocks;
}

type Row = { b: Extract<Block, { type: 'tr' }>; i: number };

function renderTable(rows: Row[], attrs: (i: number) => string): string {
	const width = Math.max(...rows.map(({ b }) => b.cells.length));
	const row = ({ b, i }: Row) => {
		const tag = b.head ? 'th' : 'td';
		const cells = Array.from({ length: width }, (_, k) => `<${tag}>${inlineMd(b.cells[k] || '')}</${tag}>`).join('');
		return `<tr${attrs(i)}>${cells}</tr>`;
	};
	const head = rows.filter((r) => r.b.head);
	const body = rows.filter((r) => !r.b.head);
	return (
		`<div class="tbl"><table>` +
		(head.length ? `<thead>${head.map(row).join('')}</thead>` : '') +
		`<tbody>${body.map(row).join('')}</tbody></table></div>`
	);
}

// hl: Set of block indexes to highlight.
export function renderBlocks(blocks: Block[], hl: Set<number> = new Set()): string {
	const attrs = (i: number) => ` data-b="${i}"${hl.has(i) ? ' class="hl"' : ''}`;
	const out: string[] = [];
	const depths: number[] = [];
	const closeLists = (to = -1) => {
		while (depths.length && depths[depths.length - 1] > to) {
			out.push('</li></ul>');
			depths.pop();
		}
	};
	for (let i = 0; i < blocks.length; i++) {
		const b = blocks[i];
		if (b.type === 'li') {
			closeLists(b.depth);
			if (depths.length && depths[depths.length - 1] === b.depth) out.push('</li>');
			else {
				out.push('<ul>');
				depths.push(b.depth);
			}
			out.push(`<li><div${attrs(i)}>${inlineMd(b.md)}</div>`);
			continue;
		}
		closeLists();
		if (b.type === 'tr') {
			const rows: Row[] = [];
			while (i < blocks.length) {
				const x = blocks[i];
				if (x.type !== 'tr' || x.table !== b.table) break;
				rows.push({ b: x, i: i++ });
			}
			i--;
			out.push(renderTable(rows, attrs));
		} else if (b.type === 'h') {
			const tag = `h${Math.min(6, b.level + 2)}`;
			out.push(`<${tag}${attrs(i)}>${inlineMd(b.md)}</${tag}>`);
		} else {
			out.push(`<p${attrs(i)}>${inlineMd(b.md)}</p>`);
		}
	}
	closeLists();
	return out.join('');
}

// ---------------------------------------------------------------- answer sentences

const NO_SPLIT_BEFORE = /(?:^|[\s(])(?:[A-Za-z]|no|nos|ord|ch|sec|secs|art|st|vs|etc|e\.g|i\.e|m\.r\.s|cmr|approx)\.$/i;

export function sentenceSpans(line: string): [number, number][] {
	const spans: [number, number][] = [];
	let start = 0;
	for (const m of line.matchAll(/[.!?](?:\[[^\]\n]{1,40}\])*(?=\s+["'(*]*[A-Z])/g)) {
		const idx = m.index ?? 0;
		const end = idx + m[0].length;
		if (NO_SPLIT_BEFORE.test(line.slice(Math.max(0, idx - 11), idx + 1))) continue;
		spans.push([start, end]);
		start = end;
	}
	spans.push([start, line.length]);
	return spans;
}

function cleanSentence(s: string): string {
	return plainText(
		s
			.replace(CITE_RE, ' ')
			.replace(/^\s*(?:[-*•]|\d+[.)])\s+/, '')
			.replace(/^#+\s*/, '')
	).replace(/\s+([.,;:!?])/g, '$1');
}

// The sentence around a citation that starts at pos and ends at end in md.
function sentenceAround(md: string, pos: number, end: number): string {
	const lineStart = md.lastIndexOf('\n', pos - 1) + 1;
	const nl = md.indexOf('\n', end);
	const line = md.slice(lineStart, nl < 0 ? md.length : nl);
	const rel = pos - lineStart;
	const spans = sentenceSpans(line);
	let k = spans.findIndex(([s, e]) => rel >= s && rel < e);
	if (k < 0) k = spans.length - 1;
	let [s] = spans[k];
	const e = spans[k][1];
	const before = cleanSentence(line.slice(s, rel));
	if (k > 0 && before.split(/\s+/).filter(Boolean).length < 2) s = spans[k - 1][0];
	return cleanSentence(line.slice(s, e));
}

export type Citation = { n: number; pos: number; end: number };

export function citations(md: string): Citation[] {
	return [...String(md).matchAll(CITE_RE)].map((m) => ({
		n: Number(m[1]),
		pos: m.index ?? 0,
		end: (m.index ?? 0) + m[0].length
	}));
}

// The sentence holding the occ-th citation chip in the answer.
export function citedSentence(md: string, occ: number): string {
	const c = citations(md)[occ];
	return c ? sentenceAround(md, c.pos, c.end) : '';
}

// Every distinct sentence that cites source n.
export function sentencesFor(md: string, n: number): string[] {
	const seen = new Set<string>();
	for (const c of citations(md)) if (c.n === n) seen.add(sentenceAround(md, c.pos, c.end));
	return [...seen].filter(Boolean);
}

// ---------------------------------------------------------------- matcher

const STOP = new Set(
	(
		'a about above after again against all also am an and any are as at be because been before being below between both but by can ' +
		'could did do does doing down during each either few for from further had has have having he her here hers him his how i if in ' +
		'into is it its itself just may me might more most must my no nor not now of off on once only or other our out over own per same ' +
		'shall she should so some such than that the their theirs them then there these they this those through to too under until up upon ' +
		'us very was we were what when where which while who whom why will with within without would you your yours herein thereof ' +
		'section sections subsection paragraph chapter code city waterville maine see also'
	).split(' ')
);

const NUM_WORDS: Record<string, number> = {
	one: 1, two: 2, three: 3, four: 4, five: 5, six: 6, seven: 7, eight: 8, nine: 9, ten: 10, eleven: 11, twelve: 12,
	fifteen: 15, twenty: 20, thirty: 30, forty: 40, fifty: 50, sixty: 60, seventy: 70, hundred: 100
};
const UNITS: Record<string, string> = {
	foot: 'ft', feet: 'ft', ft: 'ft', inch: 'in', inches: 'in', mile: 'mi', miles: 'mi', day: 'day', days: 'day',
	year: 'yr', years: 'yr', month: 'mo', months: 'mo', hour: 'hr', hours: 'hr', minute: 'min', minutes: 'min',
	acre: 'acre', acres: 'acre', room: 'room', rooms: 'room', percent: '%', pounds: 'lb', gallons: 'gal'
};
const NUM = `\\d+(?:,\\d{3})*(?:\\.\\d+)?|${Object.keys(NUM_WORDS).join('|')}`;
const UNIT_RE = `(%|square feet|${Object.keys(UNITS).join('|')})(?![a-z])`;
const unitKey = (n: string, u: string) => {
	u = u.toLowerCase();
	return `${NUM_WORDS[n.toLowerCase()] ?? n.replace(/,/g, '')} ${u === '%' ? '%' : u === 'square feet' ? 'sqft' : UNITS[u]}`;
};
const FIGURE_RES: [RegExp, (m: RegExpMatchArray) => string][] = [
	[new RegExp(`\\((\\d+(?:,\\d{3})*(?:\\.\\d+)?)\\)\\s?(?:-\\s?)?${UNIT_RE}`, 'gi'), (m) => unitKey(m[1], m[2])],
	[/\$\s?\d+(?:,\d{3})*(?:\.\d{1,2})?/g, (m) => '$' + m[0].replace(/[$\s,]/g, '').replace(/\.0+$/, '')],
	[new RegExp(`\\b(${NUM})\\s?(?:-\\s?)?${UNIT_RE}`, 'gi'), (m) => unitKey(m[1], m[2])],
	[/\b[A-Z]{0,4}\d+[A-Z]?(?:-[A-Z0-9]+)+(?:\.\d+)*(?:\([A-Za-z0-9]+\))*/g, (m) => m[0].toLowerCase()],
	[/\b[A-Z]{1,4}\d+(?:\.\d+)+\b/g, (m) => m[0].toLowerCase()],
	[/\b\d{2,}(?:,\d{3})*(?:\.\d+)?\b/g, (m) => m[0].replace(/,/g, '')]
];

export type FigureSpan = { start: number; end: number; key: string };

// Figure spans in text: money, numbers with units, section and date forms, multi-digit numbers.
export function figureSpans(text: string): FigureSpan[] {
	const spans: FigureSpan[] = [];
	const taken = (s: number, e: number) => spans.some((x) => s < x.end && e > x.start);
	for (const [re, key] of FIGURE_RES) {
		for (const m of String(text).matchAll(re)) {
			const start = m.index ?? 0;
			const end = start + m[0].length;
			if (!taken(start, end)) spans.push({ start, end, key: key(m) });
		}
	}
	return spans.sort((a, b) => a.start - b.start);
}

const stem = (w: string) =>
	w.length > 4 && w.endsWith('ies') ? w.slice(0, -3) + 'y' : w.length > 3 && /[^s]s$/.test(w) ? w.slice(0, -1) : w;

export function tokens(text: string): string[] {
	return (
		String(text)
			.toLowerCase()
			.replace(/[‘’]/g, "'")
			.match(/[a-z0-9]+(?:'[a-z]+)?/g) || []
	).map((w) => stem(w.replace(/'s$/, '')));
}

export type Features = { words: Set<string>; figs: Set<string>; grams: Set<string> };

export function features(text: string): Features {
	const plain = String(text).replace(/^\s*(?:\(?[A-Za-z0-9]{1,3}[.)]\s+)+/, '');
	const all = tokens(plain);
	const grams = new Set<string>();
	for (let i = 0; i + 4 <= all.length; i++) grams.add(all.slice(i, i + 4).join(' '));
	return {
		words: new Set(all.filter((w) => w.length > 2 && !/^\d/.test(w) && !STOP.has(w))),
		figs: new Set(figureSpans(plain).map((f) => f.key)),
		grams
	};
}

const shared = <T>(a: Set<T>, b: Set<T>) => [...a].filter((x) => b.has(x));

function scoreFeatures(f: Features, sent: Features) {
	const words = shared(f.words, sent.words).length;
	const figs = shared(f.figs, sent.figs);
	const grams = Math.min(5, shared(f.grams, sent.grams).length);
	return { score: words + 3 * figs.length + 2 * grams, figs };
}

export const scoreBlock = (block: string | Block, sent: Features) =>
	scoreFeatures(features(typeof block === 'string' ? block : block.text), sent);

const MIN_SCORE = 4;
const CLOSE = 0.85;
const MAX_HL = 4;
const GROUP_GAIN = 1.5;
const MAX_ITEMS = 12;

// Table rows also carry the words of their table's header rows and of earlier
// rows without figures, since bare row labels like "4" mean nothing alone.
function blockFeatures(blocks: Block[]): Features[] {
	return blocks.map((b, i) => {
		const f = features(b.text);
		if (b.type !== 'tr' || b.head) return f;
		for (const x of blocks.slice(0, i)) {
			if (x.type === 'tr' && x.table === b.table && (x.head || !figureSpans(x.text).length)) {
				for (const w of features(x.text).words) f.words.add(w);
			}
		}
		return f;
	});
}

const ENUM = /^\s*\(?[A-Za-z0-9]{1,3}[.)]\s/;
const itemKind = (b: Block) =>
	b.type === 'li'
		? 'li'
		: (b.text.match(ENUM) || [''])[0]
				.replace(/\d+/g, '1')
				.replace(/[a-z]/g, 'a')
				.replace(/[A-Z]/g, 'A')
				.trim();

type Group = { i: number; items: number[] };

// A lead-in ending in ":" and the run of same-style items after it.
function listGroups(blocks: Block[]): Group[] {
	const out: Group[] = [];
	blocks.forEach((b, i) => {
		const kind = blocks[i + 1] && itemKind(blocks[i + 1]);
		if (!kind || !/:\s*$/.test(b.text)) return;
		const items: number[] = [];
		for (let j = i + 1; j < blocks.length && items.length < MAX_ITEMS && itemKind(blocks[j]) === kind; j++) items.push(j);
		out.push({ i, items });
	});
	return out;
}

function unionFeatures(fs: Features[]): Features {
	const u: Features = { words: new Set(), figs: new Set(), grams: new Set() };
	for (const f of fs) for (const key of ['words', 'figs', 'grams'] as const) for (const v of f[key]) u[key].add(v);
	return u;
}

type Scored = { i: number; score: number; figs: string[] };

// A sentence that sums up a whole list: the lead-in plus the items it touches,
// when together they beat the best single block by a clear margin.
function bestGroup(groups: Group[], fs: Features[], scores: Scored[], sent: Features, best: number) {
	let pick: { score: number; blocks: number[] } | null = null;
	for (const g of groups) {
		const score = scoreFeatures(unionFeatures([g.i, ...g.items].map((k) => fs[k])), sent).score;
		const hits = g.items.filter((k) => scores[k].score > 0);
		if (score >= MIN_SCORE && score > best * GROUP_GAIN && hits.length >= 2 && (!pick || score > pick.score))
			pick = { score, blocks: [g.i, ...hits] };
	}
	return pick;
}

export type Match = { i: number; figs: Set<string> };

// Picks the blocks that best support each sentence. Returns the highlighted
// block indexes (in document order) and the figure keys shared with each.
export function matchPassages(blocks: Block[], sentences: string[]): Match[] {
	const fs = blockFeatures(blocks);
	const groups = listGroups(blocks);
	const hl = new Map<number, Set<string>>();
	const add = (x: Scored) => hl.set(x.i, new Set([...(hl.get(x.i) || []), ...x.figs]));
	for (const s of sentences) {
		const sent = features(s);
		if (!sent.words.size && !sent.figs.size) continue;
		const scores: Scored[] = fs.map((f, i) => ({ i, ...scoreFeatures(f, sent) }));
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
	return [...hl.keys()].sort((a, b) => a - b).map((i) => ({ i, figs: hl.get(i) as Set<string> }));
}

// Wraps the given figures in <mark> inside el's text nodes.
export function markFigures(el: Element | null, figs: Set<string>): void {
	if (!el || !figs.size) return;
	const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
	const nodes: Text[] = [];
	while (walker.nextNode()) nodes.push(walker.currentNode as Text);
	for (const node of nodes) {
		const spans = figureSpans(node.data).filter((f) => figs.has(f.key));
		for (const f of spans.reverse()) {
			const hit = node.splitText(f.start);
			hit.splitText(f.end - f.start);
			const mark = document.createElement('mark');
			hit.replaceWith(mark);
			mark.appendChild(hit);
		}
	}
}

export function pages(s: { page_start?: number | null; page_end?: number | null }): string {
	if (!s.page_start) return '';
	return s.page_end && s.page_end !== s.page_start ? `pages ${s.page_start}-${s.page_end}` : `page ${s.page_start}`;
}
