import { describe, expect, it } from 'vitest';
import {
	cleanValues,
	flagCounts,
	groupTemplates,
	isRequired,
	money,
	noteBlocks,
	sections,
	type DraftField
} from './DraftData';

const f = (name: string, over: Partial<DraftField> = {}): DraftField => ({
	name,
	label: name,
	kind: 'text',
	required: false,
	section: 'Details',
	...over
});

describe('DraftData helpers', () => {
	it('groups templates by group in order', () => {
		const g = groupTemplates([
			{ id: 'c', group: 'Court', order: 80 },
			{ id: 'a', group: 'Enforcement', order: 10 },
			{ id: 'b', group: 'Enforcement', order: 20 }
		]);
		expect(g.map((x) => x.group)).toEqual(['Enforcement', 'Court']);
		expect(g[0].items.map((x) => x.id)).toEqual(['a', 'b']);
	});

	it('keeps sections in first-appearance order', () => {
		const s = sections([f('a', { section: 'Recipient' }), f('b', { section: 'Violation' }), f('c', { section: 'Recipient' })]);
		expect(s.map((x) => [x.section, x.fields.map((y) => y.name)])).toEqual([
			['Recipient', ['a', 'c']],
			['Violation', ['b']]
		]);
	});

	it('applies required_when', () => {
		const m = f('mortgagee', { required_when: { violation_type: ['property_maintenance'] } });
		expect(isRequired(m, { violation_type: 'zoning_specific' })).toBe(false);
		expect(isRequired(m, { violation_type: 'property_maintenance' })).toBe(true);
		expect(isRequired(f('x', { required: true }), {})).toBe(true);
	});

	it('splits notes into paragraphs and lists', () => {
		const b = noteBlocks('First line\ncontinues.\n\n- one\n- two\n\nLast.');
		expect(b).toEqual([
			{ type: 'p', lines: ['First line continues.'] },
			{ type: 'ul', lines: ['one', 'two'] },
			{ type: 'p', lines: ['Last.'] }
		]);
	});

	it('counts flags and formats money', () => {
		expect(flagCounts('[VERIFY: a] x [MISSING: b] [FILL: c] [VERIFY]')).toEqual({ verify: 2, open: 2 });
		expect(money(305000)).toBe('$305,000');
		expect(money(12.5)).toBe('$12.50');
		expect(money(null)).toBe('');
	});

	it('drops null values', () => {
		expect(cleanValues({ a: 'x', b: null, c: undefined })).toEqual({ a: 'x' });
	});
});
