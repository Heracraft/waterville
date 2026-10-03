// Letter and notice drafts: types, API calls and small helpers for
// /api/staff/drafts. The server is app/routers/drafts.py; templates live in
// app/data/templates/. Nothing here sends a letter: staff export or print it
// and the Code Enforcement Officer signs.

import { api } from '$lib/api';

export type FieldKind = 'text' | 'textarea' | 'date' | 'select' | 'number';

export type DraftField = {
	name: string;
	label: string;
	kind: FieldKind;
	required: boolean;
	required_when?: Record<string, string[]>;
	default?: string;
	options?: { value: string; label: string }[];
	from_case?: string;
	help?: string;
	section: string;
	rows?: number;
	ai?: boolean;
	ai_prompt?: string;
};

export type TemplateSummary = {
	id: string;
	title: string;
	group: string;
	order: number;
	description: string;
	letterhead: boolean;
	ai_fields: string[];
	tools: string[];
	fields: DraftField[];
};

export type TemplateFull = TemplateSummary & {
	notes: string;
	body: string;
	defaults: Record<string, string>;
	banner: string;
};

export type Missing = { name: string; label: string };
export type Check = { ok: boolean; message: string; days: number };

export type RenderResult = {
	body: string;
	html: string;
	missing: Missing[];
	checks: Check[];
	derived: Record<string, string>;
};

export type DraftStatus = 'draft' | 'reviewed';

export type Draft = RenderResult & {
	id: string;
	template: string;
	template_title?: string;
	title: string;
	case_id: string;
	values: Record<string, string>;
	edited: boolean;
	status: DraftStatus;
	reviewed_by?: string | null;
	created_by: string;
	created_at: string;
	updated_by: string;
	updated_at: string;
	exported_at?: string;
	exported_by?: string;
	letterhead?: boolean;
	banner: string;
};

export type DraftSummary = Pick<
	Draft,
	'id' | 'template' | 'title' | 'case_id' | 'status' | 'edited' | 'created_by' | 'created_at' | 'updated_by' | 'updated_at' | 'exported_at'
> & { template_title: string; missing_count: number; verify_count: number };

export type PenaltyTier = { value: string; label: string; min: number; max: number; cite: string; verify: string };

export type PenaltyResult = {
	tier: string;
	label: string;
	cite: string;
	verify: string;
	min_per_day: number;
	max_per_day: number;
	days: number | null;
	min_total: number | null;
	max_total: number | null;
	requested_per_day: number | null;
	requested_total: number | null;
	warnings: string[];
	note: string;
};

/** The banner every draft carries. The server sends the same text with each draft. */
export const BANNER =
	'The Code Enforcement Officer reviews and signs. Check every citation against the primary source.';

const base = '/api/staff/drafts';
const enc = encodeURIComponent;

export const drafts = {
	templates: () => api.get<{ templates: TemplateSummary[]; banner: string }>(`${base}/templates`),
	template: (id: string, caseId = '') =>
		api.get<TemplateFull>(`${base}/templates/${enc(id)}${caseId ? `?case_id=${enc(caseId)}` : ''}`),
	render: (body: { template: string; values: Record<string, string>; body?: string }) =>
		api.post<RenderResult>(`${base}/render`, body),
	list: (params: { case_id?: string; q?: string } = {}) => {
		const qs = new URLSearchParams();
		for (const [k, v] of Object.entries(params)) if (v) qs.set(k, v);
		const s = qs.toString();
		return api.get<{ drafts: DraftSummary[] }>(s ? `${base}?${s}` : base);
	},
	create: (body: { template: string; values: Record<string, string>; case_id?: string; title?: string; body?: string }) =>
		api.post<Draft>(base, body),
	get: (id: string) => api.get<Draft>(`${base}/${enc(id)}`),
	update: (
		id: string,
		patch: Partial<{ values: Record<string, string>; body: string; edited: boolean; title: string; case_id: string; status: DraftStatus }>
	) => api.put<Draft>(`${base}/${enc(id)}`, patch),
	remove: (id: string) => api.del<{ ok: boolean }>(`${base}/${enc(id)}`),
	facts: (body: { template: string; case_id?: string; field?: string; values: Record<string, string>; instructions?: string }) =>
		api.post<{ text: string; field: string }>(`${base}/facts`, body),
	penaltyTiers: () => api.get<{ tiers: PenaltyTier[]; note: string }>(`${base}/penalty-tiers`),
	penalty: (body: { tier: string; start?: string; end?: string; per_day?: string }) =>
		api.post<PenaltyResult>(`${base}/penalty`, body),
	exportUrl: (id: string) => `${base}/${enc(id)}/export.docx`
};

// ---------------------------------------------------------------- helpers

/** Templates grouped for the picker, in the server's order. */
export function groupTemplates<T extends { group: string; order: number }>(list: T[]): { group: string; items: T[] }[] {
	const out: { group: string; items: T[] }[] = [];
	for (const t of [...list].sort((a, b) => a.order - b.order)) {
		let g = out.find((x) => x.group === t.group);
		if (!g) out.push((g = { group: t.group, items: [] }));
		g.items.push(t);
	}
	return out;
}

/** Fields in form sections, keeping the order in which sections first appear. */
export function sections(fields: DraftField[]): { section: string; fields: DraftField[] }[] {
	const out: { section: string; fields: DraftField[] }[] = [];
	for (const f of fields) {
		let s = out.find((x) => x.section === f.section);
		if (!s) out.push((s = { section: f.section, fields: [] }));
		s.fields.push(f);
	}
	return out;
}

/** Required now, given the other values (required_when). Mirrors drafts._is_required. */
export function isRequired(f: DraftField, values: Record<string, string>): boolean {
	if (f.required) return true;
	return Object.entries(f.required_when ?? {}).some(([k, allowed]) => allowed.includes(values[k] ?? ''));
}

/** Values to send: strings only, nothing undefined. */
export function cleanValues(values: Record<string, string | undefined | null>): Record<string, string> {
	const out: Record<string, string> = {};
	for (const [k, v] of Object.entries(values)) if (v != null) out[k] = String(v);
	return out;
}

/** Template notes as paragraphs and bullet lists, for rendering as text (no HTML). */
export function noteBlocks(notes: string): { type: 'p' | 'ul'; lines: string[] }[] {
	const out: { type: 'p' | 'ul'; lines: string[] }[] = [];
	for (const chunk of notes.split(/\n\s*\n/)) {
		const lines = chunk
			.split('\n')
			.map((l) => l.trim())
			.filter(Boolean);
		if (!lines.length) continue;
		const bullets = lines.filter((l) => l.startsWith('- '));
		const prose = lines.filter((l) => !l.startsWith('- '));
		if (prose.length) out.push({ type: 'p', lines: [prose.join(' ')] });
		if (bullets.length) out.push({ type: 'ul', lines: bullets.map((l) => l.slice(2)) });
	}
	return out;
}

export function money(n: number | null | undefined): string {
	if (n == null) return '';
	return n.toLocaleString('en-US', {
		style: 'currency',
		currency: 'USD',
		minimumFractionDigits: Number.isInteger(n) ? 0 : 2,
		maximumFractionDigits: 2
	});
}

/** Count of review flags in a body: [VERIFY ...] and [MISSING: ...]/[FILL: ...]/[FACT NEEDED: ...]. */
export function flagCounts(body: string): { verify: number; open: number } {
	return {
		verify: (body.match(/\[VERIFY\b/g) ?? []).length,
		open: (body.match(/\[(?:MISSING|FILL|FACT NEEDED)\b/g) ?? []).length
	};
}

export function fmtWhen(iso: string | undefined | null): string {
	if (!iso) return '';
	const d = new Date(iso);
	if (Number.isNaN(d.getTime())) return iso;
	return d.toLocaleString('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit' });
}
