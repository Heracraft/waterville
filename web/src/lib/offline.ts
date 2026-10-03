// B11: the last source texts a reader opened, kept in Cache Storage on this
// device so /offline can show them with no connection. The service worker
// (src/service-worker.ts) caches the app shell and GET lookups; this module
// keeps the texts that arrive inside chat answers, which a worker cannot cache
// (they come in a POST stream).
//
// Staff notes (source_type staff_note) are never kept: the device may be a
// shared public computer. Nothing from a case is ever passed here.

import type { Source } from './api';

export const SOURCES_CACHE = 'wv-sources-v1';
export const KEEP = 40;
const PREFIX = '/__offline/source/';

export type SavedSource = Omit<Source, 'n'> & { key: string; saved_at: string };

function available(): boolean {
	try {
		return typeof caches !== 'undefined' && typeof window !== 'undefined' && window.isSecureContext;
	} catch {
		return false;
	}
}

/** Stable key per section: the citation, else the URL, else the title. */
export function sourceKey(s: Pick<Source, 'citation' | 'url' | 'title' | 'page_start'>): string {
	const id = s.citation || s.url || s.title || '';
	const page = s.page_start ? `#p${s.page_start}` : '';
	return id ? PREFIX + encodeURIComponent(id + page) : '';
}

export function keepable(s: Source | null | undefined): s is Source {
	return !!s && !!s.text && s.source_type !== 'staff_note' && !!sourceKey(s);
}

/** Save a source the reader opened. Fire and forget; failures are ignored. */
export async function rememberSource(s: Source | null | undefined): Promise<void> {
	if (!keepable(s) || !available()) return;
	try {
		const key = sourceKey(s);
		const { n: _n, ...rest } = s;
		const saved: SavedSource = { ...rest, key, saved_at: new Date().toISOString() };
		const cache = await caches.open(SOURCES_CACHE);
		await cache.put(key, new Response(JSON.stringify(saved), { headers: { 'Content-Type': 'application/json' } }));
		await trim(cache);
	} catch {
		/* storage full or blocked: offline copies are a convenience */
	}
}

async function trim(cache: Cache) {
	const all = await readAll(cache);
	for (const old of all.slice(KEEP)) await cache.delete(old.key);
}

async function readAll(cache: Cache): Promise<SavedSource[]> {
	const out: SavedSource[] = [];
	for (const req of await cache.keys()) {
		try {
			const res = await cache.match(req);
			if (res) out.push((await res.json()) as SavedSource);
		} catch {
			/* skip a broken entry */
		}
	}
	return out.sort((a, b) => b.saved_at.localeCompare(a.saved_at));
}

/** Saved sources, newest first. Empty when Cache Storage is unavailable. */
export async function savedSources(): Promise<SavedSource[]> {
	if (!available()) return [];
	try {
		return await readAll(await caches.open(SOURCES_CACHE));
	} catch {
		return [];
	}
}

export async function forgetSource(key: string): Promise<void> {
	if (!available()) return;
	try {
		await (await caches.open(SOURCES_CACHE)).delete(key);
	} catch {
		/* ignore */
	}
}

export async function forgetAll(): Promise<void> {
	if (!available()) return;
	try {
		await caches.delete(SOURCES_CACHE);
	} catch {
		/* ignore */
	}
}
