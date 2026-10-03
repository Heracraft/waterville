// Research desk helpers: full citations for copying (B2), the citation lookup
// result as a panel source (B3), and the clipboard.

import type { Source } from '$lib/api';
import { CITE_RE, escapeHtml, pages, safeUrl } from '$lib/source';

/** A source as the staff chat and the lookup send it (staff sources carry the edition date). */
export type DeskSource = Source & { legislation_through?: string | null };

export type LookupChunk = {
	id: string;
	chunk_index: number | null;
	page_start: number | null;
	page_end: number | null;
	text: string;
};

/** GET /api/lookup?cite= */
export type LookupResult = {
	query: string;
	kind: 'section' | 'charter' | 'chapter' | 'ordinance' | 'statute' | 'rule';
	requested: string;
	citation: string;
	subsection: string;
	parent: boolean;
	title: string | null;
	breadcrumb: string | null;
	url: string | null;
	open_url: string | null;
	source_type: string | null;
	label: string | null;
	chapter_number: string | null;
	chapter_title: string | null;
	legislation_through: string | null;
	page_start: number | null;
	page_end: number | null;
	chunk_count: number;
	chunks: LookupChunk[];
	text: string;
	sections?: { citation: string; title: string | null }[];
};

export type Facet = { value: string; count: number | null };
/** GET /api/facets */
export type Facets = {
	chapters: (Facet & { title: string })[];
	source_types: (Facet & { name: string; label: string | null })[];
	legislation_through: string | null;
};

export const STAMP = 'Research aid, not a determination of the Code Enforcement Officer.';

const MONTHS = [
	'January',
	'February',
	'March',
	'April',
	'May',
	'June',
	'July',
	'August',
	'September',
	'October',
	'November',
	'December'
];

/** eCode360's "08-05-2026" (or an ISO "2026-08-05") as "August 5, 2026". Other text comes back as is. */
export function fmtEdition(raw: string | null | undefined): string {
	const s = (raw || '').trim();
	let m = s.match(/^(\d{1,2})[-/](\d{1,2})[-/](\d{4})$/);
	let y: number, mo: number, d: number;
	if (m) [mo, d, y] = [Number(m[1]), Number(m[2]), Number(m[3])];
	else if ((m = s.match(/^(\d{4})-(\d{2})-(\d{2})/))) [y, mo, d] = [Number(m[1]), Number(m[2]), Number(m[3])];
	else return s;
	if (mo < 1 || mo > 12 || d < 1 || d > 31) return s;
	return `${MONTHS[mo - 1]} ${d}, ${y}`;
}

/** "§ 205-7" plus subsection "A" is "§ 205-7A"; a statute's "(3)" attaches the same way. */
function withSub(cite: string, sub?: string): string {
	return sub ? `${cite}${sub}` : cite;
}

const CITY_TYPES = new Set(['code', 'attachment']);

/**
 * The citation a CEO pastes into a notice or memo, with the URL:
 *   Waterville City Code § 205-7 (eCode360, legislation through August 5, 2026), https://ecode360.com/38529530
 * `edition` is the code's date from /api/facets when the source has none of its own.
 */
export function fullCitation(
	s: DeskSource,
	opts: { edition?: string | null; subsection?: string; url?: boolean } = {}
): string {
	const cite = withSub((s.citation || s.title || 'Source').trim(), opts.subsection);
	const pg = pages(s);
	const where = pg ? `, ${pg}` : '';
	const date = fmtEdition(s.legislation_through || opts.edition);
	const ecode = date ? `eCode360, legislation through ${date}` : 'eCode360';
	const type = s.source_type || '';
	let text: string;
	if (CITY_TYPES.has(type) || !type) {
		text = cite.startsWith('Charter ')
			? `Waterville City Charter ${cite.slice('Charter '.length)}${where} (${ecode})`
			: `Waterville City Code ${cite}${where} (${ecode})`;
	} else if (type === 'new_law') {
		text = `Waterville ${cite}${where} (New Law, not yet codified; ${ecode})`;
	} else if (type === 'city_form') {
		text = `City of Waterville form: ${s.title || cite}${where}`;
	} else if (type === 'state_statute' || type === 'state_rule') {
		text = `${cite}${where}`;
	} else if (type === 'state_guidance') {
		text = `${s.title || cite}${where} (state guidance, advisory)`;
	} else if (type === 'model_code_ref') {
		text = `${s.title || cite} (reference only)`;
	} else if (type === 'staff_note') {
		text = `Staff note: ${s.title || cite}`;
	} else {
		text = `${cite}${where}`;
	}
	const url = opts.url === false ? '' : safeUrl(s.open_url) || safeUrl(s.url);
	return url ? `${text}, ${url}` : text;
}

/** The lookup result as a source the panel can show. n is 0: no answer cites it. */
export function lookupSource(r: LookupResult): DeskSource {
	return {
		n: 0,
		citation: r.citation,
		title: r.title,
		breadcrumb: r.breadcrumb,
		url: r.url,
		open_url: r.open_url,
		source_type: r.source_type,
		page_start: r.page_start,
		page_end: r.page_end,
		label: r.label,
		text: r.text,
		legislation_through: r.legislation_through
	};
}

// ---------------------------------------------------------------- copy answer

type Line = { kind: 'p' | 'quote' | 'ul' | 'ol'; text: string };

function lines(md: string): Line[] {
	const out: Line[] = [];
	for (const raw of md.split('\n')) {
		const line = raw.trimEnd();
		if (!line.trim()) {
			out.push({ kind: 'p', text: '' });
			continue;
		}
		let m: RegExpMatchArray | null;
		if ((m = line.match(/^\s*>\s?(.*)$/))) out.push({ kind: 'quote', text: m[1] });
		else if ((m = line.match(/^\s*[-*•]\s+(.*)$/))) out.push({ kind: 'ul', text: m[1] });
		else if ((m = line.match(/^\s*(\d+[.)])\s+(.*)$/))) out.push({ kind: 'ol', text: `${m[1]} ${m[2]}` });
		else out.push({ kind: 'p', text: line.replace(/^#+\s*/, '') });
	}
	return out;
}

const stripEmphasis = (t: string) => t.replace(/\*\*(.+?)\*\*/g, '$1').replace(/(^|[^*])\*([^*\n]+)\*/g, '$1$2');

function inlineHtml(t: string): string {
	return escapeHtml(t)
		.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
		.replace(/(^|[^*])\*([^*\n]+)\*/g, '$1<em>$2</em>');
}

/** Source numbers the answer cites, ascending. */
export function citedNumbers(answer: string): number[] {
	const ns = new Set<number>();
	for (const m of answer.matchAll(CITE_RE)) ns.add(Number(m[1]));
	return [...ns].sort((a, b) => a - b);
}

/**
 * An answer ready to paste: the text with its [n] markers, then each cited
 * source as a full citation with its URL, then the research-aid stamp.
 * Returns plain text and HTML (for pasting into Word with quotes and links).
 */
export function answerForCopy(
	answer: string,
	sources: DeskSource[],
	opts: { edition?: string | null; question?: string; stamp?: string } = {}
): { text: string; html: string } {
	const byN = new Map(sources.map((s) => [s.n, s]));
	const cited = citedNumbers(answer).filter((n) => byN.has(n));
	const stamp = opts.stamp || STAMP;

	const textParts: string[] = [];
	const html: string[] = [];
	if (opts.question) {
		textParts.push(`Question: ${opts.question}`, '');
		html.push(`<p><strong>Question:</strong> ${escapeHtml(opts.question)}</p>`);
	}
	let open: 'quote' | 'ul' | 'ol' | null = null;
	const close = () => {
		if (open === 'quote') html.push('</blockquote>');
		else if (open) html.push(`</${open}>`);
		open = null;
	};
	for (const l of lines(answer.trim())) {
		if (!l.text) {
			close();
			textParts.push('');
			continue;
		}
		const plain = stripEmphasis(l.text);
		if (l.kind === 'quote') {
			textParts.push(`    ${plain}`);
			if (open !== 'quote') {
				close();
				html.push('<blockquote>');
				open = 'quote';
			}
			html.push(`<p>${inlineHtml(l.text)}</p>`);
		} else if (l.kind === 'ul' || l.kind === 'ol') {
			textParts.push(l.kind === 'ul' ? `- ${plain}` : plain);
			if (open !== l.kind) {
				close();
				html.push(`<${l.kind}>`);
				open = l.kind;
			}
			html.push(`<li>${inlineHtml(l.kind === 'ol' ? l.text.replace(/^\d+[.)]\s+/, '') : l.text)}</li>`);
		} else {
			close();
			textParts.push(plain);
			html.push(`<p>${inlineHtml(l.text)}</p>`);
		}
	}
	close();
	let text = textParts.join('\n').replace(/\n{3,}/g, '\n\n').trim();

	if (cited.length) {
		const refs = cited.map((n) => {
			const s = byN.get(n)!;
			return { n, cite: fullCitation(s, { edition: opts.edition, url: false }), url: safeUrl(s.open_url) || safeUrl(s.url) };
		});
		text += '\n\nSources\n' + refs.map((r) => `[${r.n}] ${r.cite}${r.url ? `, ${r.url}` : ''}`).join('\n');
		html.push('<p><strong>Sources</strong></p>');
		for (const r of refs) {
			const link = r.url ? `, <a href="${escapeHtml(r.url)}">${escapeHtml(r.url)}</a>` : '';
			html.push(`<p>[${r.n}] ${escapeHtml(r.cite)}${link}</p>`);
		}
	}
	text += `\n\n${stamp}`;
	html.push(`<p><em>${escapeHtml(stamp)}</em></p>`);
	return { text, html: html.join('\n') };
}

// ---------------------------------------------------------------- clipboard

/** Copies text (and HTML when the browser allows it). Resolves false when nothing worked. */
export async function copyToClipboard(text: string, html?: string): Promise<boolean> {
	try {
		if (html && typeof ClipboardItem !== 'undefined' && navigator.clipboard?.write) {
			await navigator.clipboard.write([
				new ClipboardItem({
					'text/plain': new Blob([text], { type: 'text/plain' }),
					'text/html': new Blob([html], { type: 'text/html' })
				})
			]);
			return true;
		}
	} catch {
		/* fall through to plain text */
	}
	try {
		if (navigator.clipboard?.writeText) {
			await navigator.clipboard.writeText(text);
			return true;
		}
	} catch {
		/* fall through to the textarea */
	}
	try {
		const ta = document.createElement('textarea');
		ta.value = text;
		ta.setAttribute('readonly', '');
		ta.style.position = 'fixed';
		ta.style.opacity = '0';
		document.body.appendChild(ta);
		ta.select();
		const ok = document.execCommand('copy');
		ta.remove();
		return ok;
	} catch {
		return false;
	}
}
