import { describe, expect, it } from 'vitest';
import type { BotMessage } from '$lib/chat.svelte';
import {
	CONCERNS,
	answerCards,
	emptyComplaint,
	isUrgent,
	longDate,
	missing,
	money,
	parseDollars,
	telHref
} from './PublicData';

function bot(extras?: Record<string, unknown>): BotMessage {
	return {
		id: 1,
		role: 'bot',
		question: 'q',
		answer: 'a',
		sources: [],
		meta: null,
		status: 'done',
		error: null,
		loadingLabel: '',
		extras
	};
}

describe('money', () => {
	it('formats cents as dollars', () => {
		expect(money(0)).toBe('$0.00');
		expect(money(50)).toBe('$0.50');
		expect(money(15000)).toBe('$150.00');
		expect(money(123456789)).toBe('$1,234,567.89');
	});
});

describe('parseDollars', () => {
	it('reads typed amounts', () => {
		expect(parseDollars('')).toBeNull();
		expect(parseDollars('$25,000')).toBe(25000);
		expect(parseDollars('1234.5')).toBe(1234.5);
		expect(parseDollars('12.345')).toBeNull();
		expect(parseDollars('abc')).toBeNull();
		expect(parseDollars('-5')).toBeNull();
	});
});

describe('answerCards', () => {
	it('reads the checklist and triage events', () => {
		expect(answerCards(bot())).toEqual({ checklist: null, triage: null });
		const checklist = { id: 'deck', sections: [], bring: [] };
		expect(answerCards(bot({ checklist })).checklist).toBe(checklist);
		const triage = { id: 'life_safety', title: 'Report', lines: ['x'] };
		expect(answerCards(bot({ triage })).triage).toBe(triage);
	});

	it('ignores malformed events', () => {
		expect(answerCards(bot({ checklist: 'nope', triage: { title: 1 } }))).toEqual({ checklist: null, triage: null });
	});
});

describe('complaint sheet', () => {
	it('lists what is missing', () => {
		const c = emptyComplaint();
		expect(missing(c)).toEqual(['the address of the property', 'the type of concern', 'a description of what you saw']);
		c.address = '1 Main St';
		c.concerns = ['yard'];
		c.description = 'Junk in the yard';
		expect(missing(c)).toEqual([]);
	});

	it('flags life safety concerns', () => {
		expect(isUrgent({ concerns: ['yard', 'vehicles'] })).toBe(false);
		expect(isUrgent({ concerns: ['yard', 'no_heat'] })).toBe(true);
		for (const id of ['no_heat', 'sewage', 'structural', 'fire', 'wiring'] as const) {
			expect(CONCERNS.find((x) => x.id === id)?.urgent).toBe(true);
		}
	});

	it('formats dates', () => {
		expect(longDate('2026-10-03')).toBe('October 3, 2026');
		expect(longDate('')).toBe('');
	});

	it('writes no em dashes', () => {
		for (const k of CONCERNS) expect(k.label).not.toMatch(/—/);
	});
});

describe('telHref', () => {
	it('builds a tel link', () => {
		expect(telHref('207-680-4208')).toBe('tel:+12076804208');
	});
});
