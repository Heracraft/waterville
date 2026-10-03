import { describe, expect, it } from 'vitest';
import { bucket, digestText, normalizeChanges, pct, reportCsv, shortDay, type Insights, type Report } from './InsightData';
import { keepable, sourceKey } from '$lib/offline';

function days(n: number, start = '2026-01-01') {
	const t0 = Date.parse(start + 'T00:00:00Z');
	return Array.from({ length: n }, (_, i) => ({
		date: new Date(t0 + i * 86400000).toISOString().slice(0, 10),
		count: 3,
		unanswered: 1,
		failed: i % 2
	}));
}

describe('bucket', () => {
	it('keeps days up to 90', () => {
		const b = bucket(days(30));
		expect(b).toHaveLength(30);
		expect(b[0]).toMatchObject({ label: 'Jan 1', count: 3, unanswered: 1, failed: 0, answered: 2 });
		expect(b[1].answered).toBe(1);
	});
	it('groups weeks from Monday past 90 days', () => {
		const b = bucket(days(120));
		// 2026-01-01 is a Thursday: the first week holds 4 days.
		expect(b[0].start).toBe('2025-12-29');
		expect(b[0].count).toBe(12);
		expect(b[1].count).toBe(21);
		expect(b[0].label).toBe('Week of Dec 29');
		expect(b.reduce((s, x) => s + x.count, 0)).toBe(360);
	});
});

describe('formatting', () => {
	it('pct and shortDay', () => {
		expect(pct(null)).toBe('n/a');
		expect(pct(0.256)).toBe('26%');
		expect(shortDay('2026-10-03')).toBe('Oct 3');
		expect(shortDay('2026-10-03T12:00:00Z', true)).toBe('Oct 3, 2026');
		expect(shortDay('nope')).toBe('nope');
	});
});

describe('normalizeChanges', () => {
	it('reads lists, wrappers and field variants, newest first', () => {
		expect(normalizeChanges(null)).toEqual([]);
		expect(normalizeChanges({ detail: 'x' })).toEqual([]);
		const out = normalizeChanges({
			changes: [
				{ citation: '§ 205-7', change: 'changed', ts: '2026-09-01' },
				{ _rk: '§ 275-4.12', title: 'Fences', status: 'added', _pk: '2026-10-01', open_url: 'https://x' },
				{ nothing: true }
			]
		});
		expect(out.map((c) => c.citation)).toEqual(['§ 275-4.12', '§ 205-7']);
		expect(out[0]).toMatchObject({ kind: 'added', url: 'https://x', detected_at: '2026-10-01', title: 'Fences' });
		expect(normalizeChanges([{ citation: 'a' }])).toHaveLength(1);
	});
});

const insights: Insights = {
	range: { start: '2026-09-04', end: '2026-10-03', days: 30 },
	logging: { enabled: true },
	totals: { questions: 10, answered: 6, unanswered: 3, failed: 1, unanswered_rate: 0.3333, avg_answer_chars: 500 },
	volume: [],
	topics: [{ id: 'fences', label: 'Fences and walls', count: 4, unanswered: 1, examples: ['fence?'] }],
	top_sections: [{ citation: '§ 275-4.12', count: 4 }],
	unanswered_examples: [{ date: '2026-10-01', question: 'Who is the mayor?', times: 2 }],
	feedback: { yes: 3, no: 1, total: 4, helpful_rate: 0.75, not_helpful: [] }
};

describe('digestText', () => {
	it('summarizes without em dashes', () => {
		const text = digestText(insights, [{ citation: '§ 205-7', kind: 'changed' }]);
		expect(text).toContain('Sep 4, 2026 to Oct 3, 2026');
		expect(text).toContain('Not answered: 3 (33%)');
		expect(text).toContain('- Fences and walls: 4 (1 not answered)');
		expect(text).toContain('- § 275-4.12: 4');
		expect(text).toContain('- Who is the mayor? (asked 2 times)');
		expect(text).toContain('3 helpful, 1 not helpful (75% helpful)');
		expect(text).toContain('- § 205-7 (changed)');
		expect(text).not.toMatch(/\u2014/);
	});
});

describe('reportCsv', () => {
	it('quotes cells and lists summary and cases', () => {
		const r = {
			id: 'lpi',
			title: 'LPI annual report',
			start: '2026-01-01',
			end: '2026-12-31',
			note: 'Permit records rule.',
			summary: [{ label: 'Permits issued', count: null, basis: 'Not kept, sorry', confirm: 'Permit records' }],
			cases: [
				{
					id: '2026-aaaaaa',
					address: '1 Elm St, Apt "2"',
					map_lot: '9-9',
					title: 't',
					tags: ['plumbing'],
					status: 'open',
					opened: '2026-01-02',
					last_activity: '2026-02-01',
					notes: 1,
					deadlines: 0,
					actions: ['NOV 1 (2026-01-05)', 'Final NOV (2026-02-01)']
				}
			]
		} as unknown as Report;
		const csv = reportCsv(r).split('\r\n');
		expect(csv[0]).toBe('LPI annual report,2026-01-01 to 2026-12-31');
		expect(csv).toContain('Permits issued,,"Not kept, sorry",Permit records');
		expect(csv[csv.length - 1]).toBe(
			'2026-aaaaaa,"1 Elm St, Apt ""2""",9-9,t,plumbing,open,2026-01-02,2026-02-01,1,0,NOV 1 (2026-01-05); Final NOV (2026-02-01)'
		);
	});
});

describe('offline keys', () => {
	it('keeps code text and skips staff notes', () => {
		expect(sourceKey({ citation: '§ 205-7', page_start: null })).toBe('/__offline/source/' + encodeURIComponent('§ 205-7'));
		expect(sourceKey({ citation: null, url: null, title: null })).toBe('');
		expect(keepable({ n: 1, citation: '§ 205-7', text: 'x', source_type: 'code' })).toBe(true);
		expect(keepable({ n: 1, citation: 'note', text: 'x', source_type: 'staff_note' })).toBe(false);
		expect(keepable({ n: 1, citation: '§ 205-7', text: '' })).toBe(false);
		expect(keepable(null)).toBe(false);
	});
});
