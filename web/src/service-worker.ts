/// <reference types="@sveltejs/kit" />
/// <reference no-default-lib="true"/>
/// <reference lib="esnext" />
/// <reference lib="webworker" />

// B11: offline re-reading. SvelteKit registers this worker on every page.
//
//   App shell     the built JS/CSS, static files and the index page, cached at
//                 install; pages fall back to the cached shell when offline.
//   Public data   GET /api/lookup, /api/facets and the public rule tables
//                 (checklists, fees, permit router, deadline rules and calendar):
//                 network first, the last good copy when offline.
//   Everything else under /api goes straight to the network: chat (a POST
//   stream), and every /api/staff/* response, which can hold case data and is
//   never cached. Source texts opened in answers are kept by $lib/offline in
//   the "wv-sources-v1" cache, which this worker leaves alone.

import { build, files, version } from '$service-worker';

const sw = self as unknown as ServiceWorkerGlobalScope;

const SHELL = `wv-shell-${version}`;
const DATA = 'wv-data-v1';
const SOURCES = 'wv-sources-v1';
const DATA_KEEP = 80;
const INDEX = '/';

const ASSETS = new Set([...build, ...files]);

/** Public GET endpoints whose last answer is worth keeping for offline use. */
const CACHEABLE_API = [
	/^\/api\/lookup$/,
	/^\/api\/facets$/,
	/^\/api\/checklists(?:\/[^/]+)?$/,
	/^\/api\/fees$/,
	/^\/api\/permit-router$/,
	/^\/api\/deadlines$/,
	/^\/api\/deadlines\/calendar$/
];

sw.addEventListener('install', (event) => {
	event.waitUntil(
		(async () => {
			const cache = await caches.open(SHELL);
			// One missing file must not block the install, so add them one by one.
			await Promise.all(
				[...ASSETS, INDEX].map((url) => cache.add(new Request(url, { cache: 'reload' })).catch(() => undefined))
			);
			await sw.skipWaiting();
		})()
	);
});

sw.addEventListener('activate', (event) => {
	event.waitUntil(
		(async () => {
			for (const key of await caches.keys()) {
				if (key.startsWith('wv-shell-') && key !== SHELL) await caches.delete(key);
				// Anything unknown that is ours, from an older layout.
				if (key.startsWith('wv-') && ![SHELL, DATA, SOURCES].includes(key) && !key.startsWith('wv-shell-'))
					await caches.delete(key);
			}
			await sw.clients.claim();
		})()
	);
});

sw.addEventListener('fetch', (event) => {
	const req = event.request;
	if (req.method !== 'GET') return;
	const url = new URL(req.url);
	if (url.origin !== sw.location.origin) return;
	const path = url.pathname;

	if (path.startsWith('/api/')) {
		if (path.startsWith('/api/staff')) return; // case data: never cached
		if (CACHEABLE_API.some((rx) => rx.test(path))) event.respondWith(networkFirstData(req));
		return;
	}
	if (path === '/healthz' || path === '/_app/version.json' || path === '/service-worker.js') return;

	if (ASSETS.has(path)) {
		event.respondWith(cacheFirst(req, path));
		return;
	}
	if (req.mode === 'navigate') {
		event.respondWith(navigate(req));
	}
});

async function cacheFirst(req: Request, path: string): Promise<Response> {
	const cache = await caches.open(SHELL);
	const hit = await cache.match(path);
	if (hit) return hit;
	const res = await fetch(req);
	if (res.ok && res.type === 'basic') cache.put(path, res.clone()).catch(() => undefined);
	return res;
}

async function navigate(req: Request): Promise<Response> {
	try {
		const res = await fetch(req);
		// Keep the shell fresh: every client route serves the same index page.
		if (res.ok && res.headers.get('content-type')?.includes('text/html') && new URL(req.url).pathname === INDEX) {
			const cache = await caches.open(SHELL);
			cache.put(INDEX, res.clone()).catch(() => undefined);
		}
		return res;
	} catch {
		const shell = await (await caches.open(SHELL)).match(INDEX);
		return shell ?? offlineText();
	}
}

async function networkFirstData(req: Request): Promise<Response> {
	const cache = await caches.open(DATA);
	try {
		const res = await fetch(req);
		if (res.ok && (await keepable(res.clone()))) {
			await cache.put(req, res.clone());
			trim(cache);
		}
		return res;
	} catch {
		const hit = await cache.match(req);
		if (hit) {
			const headers = new Headers(hit.headers);
			headers.set('X-Offline-Copy', '1');
			return new Response(hit.body, { status: hit.status, statusText: hit.statusText, headers });
		}
		return new Response(JSON.stringify({ detail: 'You are offline, and this was not saved on this device.' }), {
			status: 503,
			headers: { 'Content-Type': 'application/json' }
		});
	}
}

/** A lookup a staff session made can return a staff note; those stay off the device. */
async function keepable(res: Response): Promise<boolean> {
	if (res.headers.has('set-cookie')) return false;
	if (!res.headers.get('content-type')?.includes('application/json')) return false;
	try {
		const body = await res.json();
		return !JSON.stringify(body).includes('"staff_note"');
	} catch {
		return false;
	}
}

async function trim(cache: Cache) {
	const keys = await cache.keys();
	for (const k of keys.slice(0, Math.max(0, keys.length - DATA_KEEP))) await cache.delete(k);
}

function offlineText(): Response {
	return new Response(
		'<!doctype html><meta charset="utf-8"><title>Offline</title><p style="font:16px system-ui;padding:24px">You are offline. Reconnect to load this page.</p>',
		{ status: 503, headers: { 'Content-Type': 'text/html; charset=utf-8' } }
	);
}
