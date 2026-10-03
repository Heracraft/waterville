import { describe, expect, it } from 'vitest';
import {
	agenda,
	caseItemFor,
	fmtTime,
	groupTriggers,
	longDay,
	shortDay,
	statusOf,
	weekdayIndex,
	yearsOf,
	type Clock,
	type ComputeResult
} from './DeadlineData';

const clock = (over: Partial<Clock> = {}): Clock => ({
	id: 'zba-80b-45',
	triggers: ['zba-decision'],
	label: 'Appeal to Superior Court (Rule 80B)',
	actor: 'Any aggrieved party',
	kind: 'deadline',
	amount: 45,
	unit: 'days',
	direction: 'after',
	citation: 'Waterville City Code § 275-6.2F',
	url: 'https://ecode360.com/38457665',
	quote: 'within 45 days of the decision.',
	verified: true,
	applies: 'waterville',
	also: [],
	offset: '45 days after',
	convention: { id: 'rule6a', label: 'Court rule 6(a)', summary: '', citation: '', caution: '' },
	date: '2026-11-17',
	time: null,
	weekday: 'Tuesday',
	raw_date: null,
	closed: null,
	plan_by: null,
	alt: null,
	steps: [],
	...over
});

const result = (results: Clock[]): ComputeResult => ({
	trigger: { id: 'zba-decision', group: 'Zoning Board of Appeals', label: 'ZBA decision' },
	date: '2026-10-03',
	time: null,
	weekday: 'Saturday',
	event_closed: 'Saturday',
	results,
	unverified: 0
});

describe('dates', () => {
	it('names weekdays without a time zone shift', () => {
		expect(weekdayIndex('2026-10-05')).toBe(0);
		expect(shortDay('2026-10-09')).toBe('Fri');
		expect(longDay('2028-02-29')).toBe('Tuesday, February 29, 2028');
	});
	it('formats times', () => {
		expect(fmtTime('00:00')).toBe('12:00 am');
		expect(fmtTime('12:05')).toBe('12:05 pm');
		expect(fmtTime('14:30')).toBe('2:30 pm');
		expect(fmtTime(null)).toBe('');
	});
});

describe('statusOf', () => {
	it('separates verified, check and unverified', () => {
		expect(statusOf({ verified: true, applies: 'waterville' })).toBe('verified');
		expect(statusOf({ verified: true, applies: 'check' })).toBe('check');
		expect(statusOf({ verified: false, applies: 'waterville' })).toBe('unverified');
	});
});

describe('groupTriggers', () => {
	it('keeps table order within groups', () => {
		const g = groupTriggers([
			{ id: 'a', group: 'X', label: 'A' },
			{ id: 'b', group: 'Y', label: 'B' },
			{ id: 'c', group: 'X', label: 'C' }
		]);
		expect(g.map((x) => [x.group, x.items.map((i) => i.id)])).toEqual([
			['X', ['a', 'c']],
			['Y', ['b']]
		]);
	});
});

describe('agenda', () => {
	it('groups by month with the event day and holidays', () => {
		const r = result([
			clock({ id: 'a', date: '2026-10-10' }),
			clock({ id: 'b', date: '2026-11-17' }),
			clock({ id: 'c', date: '2026-11-17' }),
			clock({ id: 'd', date: '2027-01-01' })
		]);
		const months = agenda(r, [{ date: '2027-01-01', name: "New Year's Day", weekday: 'Friday' }]);
		expect(months.map((m) => m.label)).toEqual(['October 2026', 'November 2026', 'January 2027']);
		expect(months[0].days[0]).toMatchObject({ date: '2026-10-03', event: true, weekday: 'Sat' });
		expect(months[1].days[0].clocks.map((c) => c.id)).toEqual(['b', 'c']);
		expect(months[2].days[0].holiday).toBe("New Year's Day");
		expect(yearsOf(r)).toEqual([2026, 2027]);
	});
});

describe('caseItemFor', () => {
	it('builds the notebook deadline item', () => {
		const item = caseItemFor(clock({ plan_by: '2026-11-16', verified: false, caution: 'Check it.' }), result([]));
		expect(item).toMatchObject({
			kind: 'deadline',
			label: 'Appeal to Superior Court (Rule 80B)',
			date: '2026-11-17',
			citation: 'Waterville City Code § 275-6.2F',
			trigger: 'ZBA decision, Saturday, October 3, 2026'
		});
		if (item.kind !== 'deadline') throw new Error('kind');
		expect(item.note).toContain('45 days after (Court rule 6(a)).');
		expect(item.note).toContain('Monday, November 16, 2026');
		expect(item.note).toContain('Unverified, check before relying.');
		expect(item.note).toContain('Check it.');
	});
	it('clips long fields to the server limits', () => {
		const item = caseItemFor(clock({ label: 'x'.repeat(400), citation: 'y'.repeat(400) }), result([]));
		if (item.kind !== 'deadline') throw new Error('kind');
		expect(item.label.length).toBe(300);
		expect(item.citation?.length).toBe(300);
	});
});
