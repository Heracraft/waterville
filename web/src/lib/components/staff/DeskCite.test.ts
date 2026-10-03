import { describe, expect, it } from 'vitest';
import { answerForCopy, citedNumbers, fmtEdition, fullCitation, lookupSource, type DeskSource, type LookupResult } from './DeskCite';

const CODE: DeskSource = {
	n: 1,
	citation: '§ 205-7',
	title: '§ 205-7. Enforcement.',
	url: 'https://ecode360.com/38529530',
	source_type: 'code',
	legislation_through: '08-05-2026'
};
const STATUTE: DeskSource = {
	n: 2,
	citation: '30-A M.R.S. § 4452',
	title: '30-A M.R.S. § 4452. Enforcement of land use laws and ordinances',
	url: 'https://legislature.maine.gov/statutes/30-A/title30-Asec4452.html',
	source_type: 'state_statute'
};
const MANUAL: DeskSource = {
	n: 3,
	citation: 'Court Rule 80K Manual (2017)',
	title: 'Court Rule 80K Manual (2017)',
	url: 'https://www.maine.gov/x/80k-manual-2017.pdf',
	open_url: 'https://www.maine.gov/x/80k-manual-2017.pdf#page=12',
	source_type: 'state_guidance',
	page_start: 12,
	page_end: 13
};

describe('fmtEdition', () => {
	it('reads eCode360 and ISO dates', () => {
		expect(fmtEdition('08-05-2026')).toBe('August 5, 2026');
		expect(fmtEdition('2026-08-05')).toBe('August 5, 2026');
		expect(fmtEdition('12/31/2025')).toBe('December 31, 2025');
	});
	it('passes anything else through', () => {
		expect(fmtEdition('')).toBe('');
		expect(fmtEdition(null)).toBe('');
		expect(fmtEdition('13-40-2026')).toBe('13-40-2026');
		expect(fmtEdition('soon')).toBe('soon');
	});
});

describe('fullCitation', () => {
	it('formats a City Code section with its edition and URL', () => {
		expect(fullCitation(CODE)).toBe(
			'Waterville City Code § 205-7 (eCode360, legislation through August 5, 2026), https://ecode360.com/38529530'
		);
	});
	it('adds a subsection and falls back to the code edition', () => {
		const s = { ...CODE, legislation_through: null };
		expect(fullCitation(s, { edition: '08-05-2026', subsection: 'A', url: false })).toBe(
			'Waterville City Code § 205-7A (eCode360, legislation through August 5, 2026)'
		);
		expect(fullCitation(s, { url: false })).toBe('Waterville City Code § 205-7 (eCode360)');
	});
	it('names the Charter, new laws and chapters', () => {
		expect(fullCitation({ n: 1, citation: 'Charter Art. IV, § 9', source_type: 'code', legislation_through: '08-05-2026' }, { url: false })).toBe(
			'Waterville City Charter Art. IV, § 9 (eCode360, legislation through August 5, 2026)'
		);
		expect(fullCitation({ n: 1, citation: 'Ord. No. 167-2026', source_type: 'new_law' }, { url: false, edition: '08-05-2026' })).toBe(
			'Waterville Ord. No. 167-2026 (New Law, not yet codified; eCode360, legislation through August 5, 2026)'
		);
		expect(fullCitation({ n: 1, citation: 'Chapter 205. Property Maintenance', source_type: 'code' }, { url: false })).toBe(
			'Waterville City Code Chapter 205. Property Maintenance (eCode360)'
		);
	});
	it('formats state sources without the eCode360 note', () => {
		expect(fullCitation(STATUTE, { subsection: '(3)' })).toBe(
			'30-A M.R.S. § 4452(3), https://legislature.maine.gov/statutes/30-A/title30-Asec4452.html'
		);
		expect(fullCitation(MANUAL)).toBe(
			'Court Rule 80K Manual (2017), pages 12-13 (state guidance, advisory), https://www.maine.gov/x/80k-manual-2017.pdf#page=12'
		);
		expect(fullCitation({ n: 1, title: '2021 IRC', source_type: 'model_code_ref' }, { url: false })).toBe('2021 IRC (reference only)');
	});
	it('drops unsafe URLs', () => {
		expect(fullCitation({ ...CODE, url: 'javascript:alert(1)' })).not.toContain('javascript');
	});
});

describe('answerForCopy', () => {
	const answer =
		'**§ 205-7; 30-A M.R.S. § 4452(3)**\n\nThe owner gets written notice first [1].\n\n> The Code Enforcement Officer shall notify the owner [1]\n\n**Enforcement chain**\n1. City section [1]\n2. Penalty tier [2.B]\n\n- Note [9]';

	it('keeps [n] markers and lists cited sources in order', () => {
		const { text } = answerForCopy(answer, [STATUTE, CODE, MANUAL], { question: 'Who gets notice?' });
		expect(text.startsWith('Question: Who gets notice?\n\n§ 205-7; 30-A M.R.S. § 4452(3)\n\nThe owner gets written notice first [1].')).toBe(true);
		expect(text).toContain('\n    The Code Enforcement Officer shall notify the owner [1]\n');
		expect(text).toContain('\n1. City section [1]\n2. Penalty tier [2.B]\n');
		expect(text).toContain(
			'\n\nSources\n[1] Waterville City Code § 205-7 (eCode360, legislation through August 5, 2026), https://ecode360.com/38529530\n' +
				'[2] 30-A M.R.S. § 4452, https://legislature.maine.gov/statutes/30-A/title30-Asec4452.html\n\n'
		);
		expect(text).not.toContain('[3]');
		expect(text).not.toContain('**');
		expect(text.endsWith('Research aid, not a determination of the Code Enforcement Officer.')).toBe(true);
	});

	it('builds HTML with quotes, lists and escaped text', () => {
		const { html } = answerForCopy(answer + '\n<script>x</script>', [CODE, STATUTE]);
		expect(html).toContain('<p><strong>§ 205-7; 30-A M.R.S. § 4452(3)</strong></p>');
		expect(html).toContain('<blockquote>\n<p>The Code Enforcement Officer shall notify the owner [1]</p>\n</blockquote>');
		expect(html).toContain('<ol>\n<li>City section [1]</li>\n<li>Penalty tier [2.B]</li>\n</ol>');
		expect(html).toContain('&lt;script&gt;');
		expect(html).toContain('<a href="https://ecode360.com/38529530">https://ecode360.com/38529530</a>');
		expect(html.endsWith('<p><em>Research aid, not a determination of the Code Enforcement Officer.</em></p>')).toBe(true);
	});

	it('omits the sources list when nothing is cited', () => {
		const { text } = answerForCopy('**Not in the sources.**', [CODE]);
		expect(text).toBe('Not in the sources.\n\nResearch aid, not a determination of the Code Enforcement Officer.');
	});

	it('finds cited numbers', () => {
		expect(citedNumbers('a [2] b [1] c [2.A] d [10]')).toEqual([1, 2, 10]);
	});
});

describe('lookupSource', () => {
	it('turns a lookup result into a panel source', () => {
		const r = {
			query: '205-7A',
			kind: 'section',
			requested: '§ 205-7',
			citation: '§ 205-7',
			subsection: 'A',
			parent: false,
			title: '§ 205-7. Enforcement.',
			breadcrumb: 'Chapter 205. Property Maintenance > § 205-7. Enforcement.',
			url: 'https://ecode360.com/38529530',
			open_url: 'https://ecode360.com/38529530',
			source_type: 'code',
			label: null,
			chapter_number: '205',
			chapter_title: 'Property Maintenance',
			legislation_through: '08-05-2026',
			page_start: null,
			page_end: null,
			chunk_count: 1,
			chunks: [],
			text: 'A. text'
		} satisfies LookupResult;
		const s = lookupSource(r);
		expect(s).toMatchObject({ n: 0, citation: '§ 205-7', text: 'A. text', legislation_through: '08-05-2026' });
	});
});
