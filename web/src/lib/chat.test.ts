import { describe, expect, it } from 'vitest';
import { failureText, NETWORK_ERROR } from './chat.svelte';

describe('failureText', () => {
	it('turns a fetch TypeError into plain copy', () => {
		expect(failureText(new TypeError('Failed to fetch'))).toBe(NETWORK_ERROR);
	});
	it('keeps server messages', () => {
		expect(failureText(new Error('Please keep questions under 1000 characters.'))).toBe(
			'Please keep questions under 1000 characters.'
		);
	});
});
