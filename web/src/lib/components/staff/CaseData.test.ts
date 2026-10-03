import { describe, expect, it } from 'vitest';
import { daysUntil, deadlines, dueLabel, fmtDay, statusLabel, tagLabel, TAGS, type CaseItem } from './CaseData';

const now = new Date(2026, 9, 3, 15, 30); // Oct 3, 2026, local time

describe('case formatting', () => {
	it('formats days without a time zone shift', () => {
		expect(fmtDay('2026-11-02')).toBe('Nov 2, 2026');
		expect(fmtDay('2026-01-31')).toBe('Jan 31, 2026');
		expect(fmtDay('garbage')).toBe('garbage');
	});

	it('counts whole days to a date', () => {
		expect(daysUntil('2026-10-03', now)).toBe(0);
		expect(daysUntil('2026-10-04', now)).toBe(1);
		expect(daysUntil('2026-11-02', now)).toBe(30);
		expect(daysUntil('2026-10-01', now)).toBe(-2);
	});

	it('labels due dates', () => {
		expect(dueLabel('2026-10-03', now)).toBe('Due today');
		expect(dueLabel('2026-10-04', now)).toBe('Due tomorrow');
		expect(dueLabel('2026-10-13', now)).toBe('In 10 days');
		expect(dueLabel('2026-10-02', now)).toBe('1 day past');
		expect(dueLabel('2026-09-23', now)).toBe('10 days past');
	});

	it('sorts deadlines soonest first and skips other kinds', () => {
		const base = { case_id: 'c', created_by: 'a', updated_at: '' };
		const items: CaseItem[] = [
			{ ...base, id: '1', kind: 'deadline', label: 'B', date: '2026-12-01', citation: '', note: '', trigger: '', created_at: '1' },
			{ ...base, id: '2', kind: 'note', text: 'x', created_at: '2' },
			{ ...base, id: '3', kind: 'deadline', label: 'A', date: '2026-11-01', citation: '', note: '', trigger: '', created_at: '3' }
		];
		expect(deadlines(items).map((d) => d.label)).toEqual(['A', 'B']);
	});

	it('has the eleven type tags the server accepts', () => {
		expect(TAGS.map((t) => t.value)).toEqual([
			'building',
			'zoning',
			'property-maintenance',
			'shoreland',
			'floodplain',
			'rental',
			'complaint',
			'dangerous-building',
			'plumbing',
			'subsurface',
			'other'
		]);
		expect(tagLabel('dangerous-building')).toBe('Dangerous building');
		expect(statusLabel('monitoring')).toBe('Monitoring');
	});
});
