import { describe, expect, it } from 'vitest';
import { readSSE, type ChatEvent } from './api';

function stream(chunks: string[]): ReadableStream<Uint8Array> {
	const enc = new TextEncoder();
	return new ReadableStream({
		start(c) {
			for (const ch of chunks) c.enqueue(enc.encode(ch));
			c.close();
		}
	});
}

async function all(s: ReadableStream<Uint8Array>) {
	const out: ChatEvent[] = [];
	for await (const ev of readSSE(s)) out.push(ev);
	return out;
}

describe('readSSE', () => {
	it('reads meta, sources, delta, error and done across chunk boundaries', async () => {
		const body = [
			'event: meta\ndata: {"mode": "public", "answer_id": "a1"}\n\n',
			'event: sources\ndata: [{"n": 1}]\n\nevent: del',
			'ta\ndata: {"text": "Hel"}\n\nevent: delta\ndata: {"text": "lo"}\n',
			'\nevent: error\ndata: {"message": "x"}\n\nevent: done\ndata: {}\n\n'
		];
		expect(await all(stream(body))).toEqual([
			{ event: 'meta', data: { mode: 'public', answer_id: 'a1' } },
			{ event: 'sources', data: [{ n: 1 }] },
			{ event: 'delta', data: { text: 'Hel' } },
			{ event: 'delta', data: { text: 'lo' } },
			{ event: 'error', data: { message: 'x' } },
			{ event: 'done', data: {} }
		]);
	});

	it('handles CRLF line endings', async () => {
		expect(await all(stream(['event: delta\r\ndata: {"text": "a"}\r\n\r\n']))).toEqual([
			{ event: 'delta', data: { text: 'a' } }
		]);
	});
});
