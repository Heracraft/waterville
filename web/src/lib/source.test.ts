import { describe, expect, it } from 'vitest';
import * as src from './source';
import golden from './source.golden.json';

const SAMPLE = `Sec. 22-41. Fences.

(a) No fence in a residential zone shall exceed six (6) feet in height.
(b) Fences in the front yard shall not exceed four (4) feet.

| Use | Fee |
| --- | --- |
| Short-term rental license | $150.00 |
| Renewal | $75 |

The following are prohibited:
- barbed wire below 6 feet
- electric fences
  - except agricultural
## Penalties
A violation is subject to a fine of $100 per day under 30-A M.R.S. 4452.`;

const ANSWER = `A fence in a residential zone can be up to 6 feet tall [1]. In the front yard the limit is 4 feet [1.b]. A short-term rental license costs $150 [2]. Renewals cost $75 [2, Table].
- Barbed wire below 6 feet is prohibited [1].
- See Sec. 22-41 for details [3].`;

describe('source helpers', () => {
	it('parses blocks of each kind', () => {
		const blocks = src.parseBlocks(SAMPLE);
		expect(blocks.map((b) => b.type)).toEqual(['p', 'p', 'tr', 'tr', 'tr', 'p', 'li', 'li', 'li', 'h', 'p']);
		expect(blocks[2]).toMatchObject({ type: 'tr', head: true });
	});

	it('finds the sentence around a citation, including [n.sub] forms', () => {
		expect(src.citations(ANSWER).map((c) => c.n)).toEqual([1, 1, 2, 2, 1, 3]);
		expect(src.citedSentence(ANSWER, 1)).toBe('In the front yard the limit is 4 feet.');
		expect(src.sentencesFor(ANSWER, 2)).toEqual(['A short-term rental license costs $150.', 'Renewals cost $75.']);
	});

	it('highlights the matching passage', () => {
		const blocks = src.parseBlocks(SAMPLE);
		const found = src.matchPassages(blocks, [src.citedSentence(ANSWER, 1)]);
		expect(found.map((f) => f.i)).toContain(1);
		expect(src.renderBlocks(blocks, new Set([1]))).toContain('<p data-b="1" class="hl">');
	});

	it('only allows http(s) urls', () => {
		expect(src.safeUrl('javascript:alert(1)')).toBe('');
		expect(src.safeUrl('https://example.com/a.pdf#page=2')).toBe('https://example.com/a.pdf#page=2');
	});

	it('escapes HTML in chunk text', () => {
		expect(src.renderBlocks(src.parseBlocks('<script>x</script> **bold**'))).toBe(
			'<p data-b="0">&lt;script&gt;x&lt;/script&gt; <strong>bold</strong></p>'
		);
	});
});

// The original app/web/source.js is gone; its outputs for SAMPLE and ANSWER are
// frozen in source.golden.json, so the port stays line-for-line compatible.
describe('parity with the original app/web/source.js', () => {
	it('renders and matches exactly like the old code', () => {
		const blocks = src.parseBlocks(SAMPLE);
		expect(blocks).toEqual(golden.blocks);
		for (let occ = 0; occ < 6; occ++) {
			const want = golden.occ[occ];
			const s = src.citedSentence(ANSWER, occ);
			expect(s).toBe(want.sentence);
			const a = src.matchPassages(blocks, [s]);
			expect(a.map((x) => [x.i, [...x.figs].sort()])).toEqual(want.matches);
			const hl = new Set(a.map((x) => x.i));
			expect(src.renderBlocks(blocks, hl)).toBe(want.html);
		}
		for (const n of [1, 2, 3])
			expect(src.sentencesFor(ANSWER, n)).toEqual(golden.sentencesFor[String(n) as '1' | '2' | '3']);
		expect(src.figureSpans(SAMPLE)).toEqual(golden.figureSpans);
		expect(src.inlineMd('a <br> *b* _c_ **d**')).toBe(golden.inlineMd);
	});
});
