import { describe, expect, it } from 'vitest';
import { FLAG_GROUPS, checklistText, emptyInput, groupByPhase, toCount, type GateResult } from './GateData';

const result: GateResult = {
	input: emptyInput(),
	phases: [
		{ n: 1, label: 'Board approvals', summary: '' },
		{ n: 4, label: 'State and utility gates', summary: '' },
		{ n: 7, label: 'Building permit', summary: '' }
	],
	gates: [
		{
			id: 'pb-site-plan',
			order: 1,
			phase: 1,
			phase_label: 'Board approvals',
			authority: 'Planning Board',
			title: 'Site plan review permit',
			citation: '§ 275-6.4C',
			url: 'https://ecode360.com/38457736',
			verified: true,
			scope: 'city',
			reasons: ['New building footprint of 4,500 sq ft, 4,000 or more (§ 275-6.4C(2)).']
		},
		{
			id: 'building-permit',
			order: 2,
			phase: 7,
			phase_label: 'Building permit',
			authority: 'Code Enforcement Officer',
			title: 'Building permit',
			citation: '§ 127-2A',
			url: 'https://ecode360.com/38454333',
			verified: false,
			scope: 'city',
			reasons: ['Construction.']
		}
	],
	exempt: [],
	district_notes: [],
	assumptions: [],
	unverified: 1,
	checked: '2026-10-03'
};

describe('groupByPhase', () => {
	it('drops empty phases and keeps order', () => {
		expect(groupByPhase(result).map((p) => [p.phase.n, p.gates.map((g) => g.id)])).toEqual([
			[1, ['pb-site-plan']],
			[7, ['building-permit']]
		]);
	});
});

describe('checklistText', () => {
	it('lists gates with reasons, flags and the stamp', () => {
		const t = checklistText(result, { project: 'New building', use: 'Commercial' });
		expect(t).toContain('New building, Commercial');
		expect(t).toContain('1) Site plan review permit (Planning Board). § 275-6.4C');
		expect(t).toContain('- New building footprint of 4,500 sq ft');
		expect(t).toContain('2) Building permit (Code Enforcement Officer). § 127-2A [unverified]');
		expect(t.trim().endsWith('Research aid, not a determination of the Code Enforcement Officer.')).toBe(true);
		expect(t).not.toMatch(/\u2014/);
	});
});

describe('toCount', () => {
	it('reads square feet leniently', () => {
		expect(toCount('4,500')).toBe(4500);
		expect(toCount(' 12 ')).toBe(12);
		expect(toCount('')).toBe(0);
		expect(toCount('-3')).toBe(0);
		expect(toCount('abc')).toBe(0);
		expect(toCount(7.9)).toBe(7);
	});
});

describe('form vocabulary', () => {
	it('covers every boolean input once', () => {
		const keys = FLAG_GROUPS.flatMap((g) => g.flags.map((f) => f.key));
		expect(new Set(keys).size).toBe(keys.length);
		const bools = Object.entries(emptyInput())
			.filter(([, v]) => typeof v === 'boolean')
			.map(([k]) => k)
			.filter((k) => k !== 'visible_from_street');
		expect(keys.sort()).toEqual(bools.sort());
	});
});
