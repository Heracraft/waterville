import { describe, expect, it } from 'vitest';
import { parseAnswer, shownSources, type Inline, type AnswerBlock } from './answer';
import type { Source } from './api';

const SOURCES: Source[] = [
	{ n: 1, citation: 'Sec. 22-41', title: 'Fences', url: 'https://library.municode.com/x' },
	{ n: 2, citation: 'Sec. 9-3', title: 'Licenses', url: null },
	{ n: 3, citation: 'Ch. 4', title: 'Other' }
];

// Renders the tree back to the HTML the old app.js render() produced (minus chip attributes).
function html(blocks: AnswerBlock[]): string {
	const inl = (ns: Inline[]): string =>
		ns
			.map((n) =>
				n.t === 'text'
					? n.s
					: n.t === 'strong'
						? `<strong>${inl(n.c)}</strong>`
						: n.t === 'em'
							? `<em>${inl(n.c)}</em>`
							: `{${n.n}#${n.occ}:${n.label}}`
			)
			.join('');
	return blocks
		.map((b) =>
			b.t === 'p'
				? `<p>${inl(b.c)}</p>`
				: b.t === 'quote'
					? `<blockquote>${b.lines.map((l) => `<p>${inl(l)}</p>`).join('')}</blockquote>`
					: `<${b.t}>${b.items.map((i) => `<li>${inl(i)}</li>`).join('')}</${b.t}>`
		)
		.join('');
}

describe('parseAnswer blockquotes (staff answers)', () => {
	it('groups "> " lines into one quote until a blank line', () => {
		const md = '**§ 205-7**\n\n> First line [1]\n> second line\n>\n> after an empty quote line\n\n> Another quote [2]\n- item';
		expect(html(parseAnswer(md, SOURCES))).toBe(
			'<p><strong>§ 205-7</strong></p>' +
				'<blockquote><p>First line {1#0:1}</p><p>second line</p><p>after an empty quote line</p></blockquote>' +
				'<blockquote><p>Another quote {2#1:2}</p></blockquote><ul><li>item</li></ul>'
		);
	});

	it('leaves a ">" inside a line alone', () => {
		expect(html(parseAnswer('a > b', SOURCES))).toBe('<p>a > b</p>');
	});
});

describe('parseAnswer', () => {
	it('parses paragraphs, lists, bold, italics and citations', () => {
		const md = '## Fences\nA fence may be **6 feet** tall [1] or *less* [1.b].\n- one [2]\n- two [9]\n1. first\n2. second [3, Table 2]';
		expect(html(parseAnswer(md, SOURCES))).toBe(
			'<p>Fences</p><p>A fence may be <strong>6 feet</strong> tall {1#0:1} or <em>less</em> {1#1:1}.</p>' +
				'<ul><li>one {2#2:2}</li><li>two [9]</li></ul><ol><li>first</li><li>second {3#4:3}</li></ol>'
		);
	});

	it('keeps bold that spans a citation', () => {
		expect(html(parseAnswer('**up to 6 feet [1]** in back', SOURCES))).toBe('<p><strong>up to 6 feet {1#0:1}</strong> in back</p>');
	});

	it('treats markup as text', () => {
		expect(html(parseAnswer('<img src=x onerror=alert(1)>', SOURCES))).toBe('<p><img src=x onerror=alert(1)></p>');
		const [p] = parseAnswer('<b>x</b>', SOURCES);
		expect(p).toEqual({ t: 'p', c: [{ t: 'text', s: '<b>x</b>' }] });
	});
});

describe('shownSources', () => {
	it('lists cited sources, or the top three when nothing is cited', () => {
		expect(shownSources(SOURCES, 'x [2]')).toEqual({ cited: true, shown: [SOURCES[1]] });
		expect(shownSources(SOURCES, 'no cites').shown).toHaveLength(3);
	});
});
