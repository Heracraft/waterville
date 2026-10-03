// Fetch wrappers and the SSE reader for POST /api/chat.
// Every request is same-origin; staff writes carry X-Requested-With: wv (CSRF rule in the spec).

export type Source = {
	n: number;
	citation?: string | null;
	title?: string | null;
	breadcrumb?: string | null;
	url?: string | null;
	open_url?: string | null;
	source_type?: string | null;
	page_start?: number | null;
	page_end?: number | null;
	label?: string | null;
	text?: string | null;
};

export type ChatMode = 'public' | 'staff';

export type ChatTurn = { role: 'user' | 'assistant'; content: string };

export type ChatFilters = { chapters?: string[]; source_types?: string[] };

export type ChatRequest = {
	messages: ChatTurn[];
	mode?: ChatMode;
	filters?: ChatFilters;
	case_id?: string;
};

export type ChatMeta = { mode: ChatMode; answer_id: string; [key: string]: unknown };

export type ChatEvent =
	| { event: 'meta'; data: ChatMeta }
	| { event: 'sources'; data: Source[] }
	| { event: 'delta'; data: { text: string } }
	| { event: 'error'; data: { message: string } }
	| { event: 'done'; data: Record<string, unknown> }
	| { event: string; data: unknown };

export class ApiError extends Error {
	status: number;
	detail: unknown;
	constructor(status: number, message: string, detail?: unknown) {
		super(message);
		this.name = 'ApiError';
		this.status = status;
		this.detail = detail;
	}
}

const GENERIC = 'Something went wrong. Please try again.';

// FastAPI errors arrive as {detail: string} or {detail: [{msg, loc}]} for validation.
async function errorFrom(res: Response): Promise<ApiError> {
	let detail: unknown = null;
	let message = GENERIC;
	try {
		detail = (await res.json()).detail;
	} catch {
		/* not JSON */
	}
	if (typeof detail === 'string' && detail) message = detail;
	else if (detail) message = 'Please check your question and try again.';
	return new ApiError(res.status, message, detail);
}

type Body = unknown;

// Set by the staff layout: called when a staff request comes back 401
// (session expired), so the page can send the browser to the login page.
let unauthorized: (() => void) | null = null;
export function onUnauthorized(fn: (() => void) | null) {
	unauthorized = fn;
}

export async function request<T = unknown>(
	method: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE',
	path: string,
	body?: Body,
	init: RequestInit = {}
): Promise<T> {
	const headers = new Headers(init.headers);
	headers.set('Accept', 'application/json');
	if (method !== 'GET') headers.set('X-Requested-With', 'wv');
	if (body !== undefined && !(body instanceof FormData)) headers.set('Content-Type', 'application/json');
	const res = await fetch(path, {
		...init,
		method,
		headers,
		credentials: 'same-origin',
		body: body === undefined ? undefined : body instanceof FormData ? body : JSON.stringify(body)
	});
	if (!res.ok) {
		if (res.status === 401 && path.startsWith('/api/staff/') && !/^\/api\/staff\/(me|login)(\b|$)/.test(path)) unauthorized?.();
		throw await errorFrom(res);
	}
	if (res.status === 204) return undefined as T;
	const type = res.headers.get('Content-Type') || '';
	return (type.includes('json') ? await res.json() : await res.text()) as T;
}

export const api = {
	get: <T = unknown>(path: string, init?: RequestInit) => request<T>('GET', path, undefined, init),
	post: <T = unknown>(path: string, body?: Body, init?: RequestInit) => request<T>('POST', path, body ?? {}, init),
	put: <T = unknown>(path: string, body?: Body, init?: RequestInit) => request<T>('PUT', path, body ?? {}, init),
	patch: <T = unknown>(path: string, body?: Body, init?: RequestInit) => request<T>('PATCH', path, body ?? {}, init),
	del: <T = unknown>(path: string, init?: RequestInit) => request<T>('DELETE', path, undefined, init)
};

// Splits a text/event-stream body into {event, data} records. data is JSON.
export async function* readSSE(body: ReadableStream<Uint8Array>): AsyncGenerator<ChatEvent> {
	const reader = body.getReader();
	const decoder = new TextDecoder();
	let buf = '';
	const parse = (raw: string): ChatEvent | null => {
		let event = 'message';
		const data: string[] = [];
		for (const line of raw.split(/\r?\n/)) {
			if (line.startsWith('event:')) event = line.slice(6).trim();
			else if (line.startsWith('data:')) data.push(line.slice(line[5] === ' ' ? 6 : 5));
		}
		if (!data.length) return null;
		return { event, data: JSON.parse(data.join('\n')) } as ChatEvent;
	};
	try {
		for (;;) {
			const { value, done } = await reader.read();
			if (done) break;
			buf += decoder.decode(value, { stream: true }).replace(/\r\n/g, '\n');
			let idx;
			while ((idx = buf.indexOf('\n\n')) >= 0) {
				const raw = buf.slice(0, idx);
				buf = buf.slice(idx + 2);
				const ev = parse(raw);
				if (ev) yield ev;
			}
		}
		buf += decoder.decode();
		if (buf.trim()) {
			const ev = parse(buf);
			if (ev) yield ev;
		}
	} finally {
		reader.releaseLock();
	}
}

// POST /api/chat and yield its events. Throws ApiError on a non-2xx reply.
export async function* streamChat(req: ChatRequest, signal?: AbortSignal): AsyncGenerator<ChatEvent> {
	const headers: Record<string, string> = { 'Content-Type': 'application/json' };
	if (req.mode === 'staff') headers['X-Requested-With'] = 'wv';
	const res = await fetch('/api/chat', {
		method: 'POST',
		headers,
		credentials: 'same-origin',
		body: JSON.stringify(req),
		signal
	});
	if (!res.ok) throw await errorFrom(res);
	if (!res.body) throw new ApiError(res.status, GENERIC);
	yield* readSSE(res.body);
}

// Staff session. Returns null when not logged in (401).
export type StaffUser = {
	username: string;
	expires?: number | string;
	/** APP_ENV: production, preview or local. */
	env?: string;
	/** Research-aid stamp text shown under staff answers. */
	stamp?: string;
	[key: string]: unknown;
};

export async function staffMe(): Promise<StaffUser | null> {
	try {
		return await api.get<StaffUser>('/api/staff/me');
	} catch (e) {
		if (e instanceof ApiError && e.status === 401) return null;
		throw e;
	}
}
