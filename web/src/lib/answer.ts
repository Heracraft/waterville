// Minimal Markdown for answers: paragraphs, bullet and numbered lists, bold,
// italics and [n] / [n.sub] citations. Ported from render() in app/web/app.js,
// but it returns a tree that components render, so citation chips are
// components with their own handlers instead of HTML strings.

import { CITE_RE, citations, safeUrl } from './source';
import type { Source } from './api';

export type Inline =
	| { t: 'text'; s: string }
	| { t: 'strong'; c: Inline[] }
	| { t: 'em'; c: Inline[] }
	| { t: 'cite'; n: number; occ: number; label: string; source: Source };

export type AnswerBlock =
	| { t: 'p'; c: Inline[] }
	| { t: 'ul' | 'ol'; items: Inline[][] }
	/** "> " lines (staff answers quote the controlling text); one entry per line. */
	| { t: 'quote'; lines: Inline[][] };

export const chipHref = (s: Pick<Source, 'open_url' | 'url'>) => safeUrl(s.open_url) || safeUrl(s.url);

const OPEN_CHIP = '\u0001';
const CLOSE_CHIP = '\u0002';
const OPEN_STRONG = '\u0003';
const CLOSE_STRONG = '\u0004';
const OPEN_EM = '\u0005';
const CLOSE_EM = '\u0006';

export function parseAnswer(md: string, sources: Source[]): AnswerBlock[] {
	const byN = new Map(sources.map((s) => [s.n, s]));
	let occ = 0;

	// Chips are cut from the raw line so occ counts the same matches as citations(md).
	const inline = (t: string): Inline[] => {
		const chips: Inline[] = [];
		const marked = t
			.replace(/[\u0001-\u0006]/g, '')
			.replace(CITE_RE, (m: string, n: string) => {
				const k = occ++;
				const s = byN.get(Number(n));
				chips.push(s ? { t: 'cite', n: s.n, occ: k, label: n, source: s } : { t: 'text', s: m });
				return `${OPEN_CHIP}${chips.length - 1}${CLOSE_CHIP}`;
			})
			.replace(/\*\*(.+?)\*\*/g, `${OPEN_STRONG}$1${CLOSE_STRONG}`)
			.replace(/(^|[^*])\*([^*\n]+)\*/g, `$1${OPEN_EM}$2${CLOSE_EM}`);
		return toTree(marked, chips);
	};

	const out: AnswerBlock[] = [];
	let list: Extract<AnswerBlock, { t: 'ul' | 'ol' }> | null = null;
	let quote: Extract<AnswerBlock, { t: 'quote' }> | null = null;
	for (const raw of md.split('\n')) {
		const line = raw.trimEnd();
		const quoted = line.match(/^\s*>\s?(.*)$/);
		if (quoted) {
			list = null;
			if (!quote) {
				quote = { t: 'quote', lines: [] };
				out.push(quote);
			}
			if (quoted[1].trim()) quote.lines.push(inline(quoted[1]));
			continue;
		}
		quote = null;
		const bullet = line.match(/^\s*[-*•]\s+(.*)$/);
		const num = line.match(/^\s*\d+[.)]\s+(.*)$/);
		const item = bullet || num;
		if (item) {
			const tag = bullet ? 'ul' : 'ol';
			if (!list || list.t !== tag) {
				list = { t: tag, items: [] };
				out.push(list);
			}
			list.items.push(inline(item[1]));
			continue;
		}
		list = null;
		if (line.trim()) out.push({ t: 'p', c: inline(line.replace(/^#+\s*/, '')) });
	}
	return out;
}

function toTree(marked: string, chips: Inline[]): Inline[] {
	const root: Inline[] = [];
	const stack: { kind: 'strong' | 'em' | 'root'; c: Inline[] }[] = [{ kind: 'root', c: root }];
	let text = '';
	const top = () => stack[stack.length - 1];
	const flush = () => {
		if (text) top().c.push({ t: 'text', s: text });
		text = '';
	};
	const close = (kind: 'strong' | 'em') => {
		const at = stack.map((x) => x.kind).lastIndexOf(kind);
		if (at <= 0) return;
		flush();
		stack.length = at;
	};
	for (let i = 0; i < marked.length; i++) {
		const ch = marked[i];
		if (ch === OPEN_CHIP) {
			const end = marked.indexOf(CLOSE_CHIP, i);
			const chip = chips[Number(marked.slice(i + 1, end))];
			flush();
			if (chip) top().c.push(chip);
			i = end;
		} else if (ch === OPEN_STRONG || ch === OPEN_EM) {
			flush();
			const node: Inline = ch === OPEN_STRONG ? { t: 'strong', c: [] } : { t: 'em', c: [] };
			top().c.push(node);
			stack.push({ kind: node.t as 'strong' | 'em', c: (node as { c: Inline[] }).c });
		} else if (ch === CLOSE_STRONG) close('strong');
		else if (ch === CLOSE_EM) close('em');
		else text += ch;
	}
	flush();
	return root;
}

// Sources the answer cites; if it cites nothing, the top few results.
export function shownSources(sources: Source[], answer: string): { cited: boolean; shown: Source[] } {
	const cited = new Set(citations(answer).map((c) => c.n));
	return {
		cited: cited.size > 0,
		shown: cited.size ? sources.filter((s) => cited.has(s.n)) : sources.slice(0, 3)
	};
}
