// Case notebooks: types, vocabularies and API calls for /api/staff/cases.
// The server is app/routers/notebooks.py; keep TAGS and STATUSES in step with it.

import { api } from '$lib/api';
import type { Source } from '$lib/api';

export const TAGS = [
	{ value: 'building', label: 'Building' },
	{ value: 'zoning', label: 'Zoning' },
	{ value: 'property-maintenance', label: 'Property maintenance' },
	{ value: 'shoreland', label: 'Shoreland' },
	{ value: 'floodplain', label: 'Floodplain' },
	{ value: 'rental', label: 'Rental' },
	{ value: 'complaint', label: 'Complaint' },
	{ value: 'dangerous-building', label: 'Dangerous building' },
	{ value: 'plumbing', label: 'Plumbing' },
	{ value: 'subsurface', label: 'Subsurface' },
	{ value: 'other', label: 'Other' }
] as const;

export type CaseTag = (typeof TAGS)[number]['value'];

export const STATUSES = [
	{ value: 'open', label: 'Open' },
	{ value: 'monitoring', label: 'Monitoring' },
	{ value: 'closed', label: 'Closed' }
] as const;

export type CaseStatus = (typeof STATUSES)[number]['value'];

export const tagLabel = (t: string) => TAGS.find((x) => x.value === t)?.label ?? t;
export const statusLabel = (s: string) => STATUSES.find((x) => x.value === s)?.label ?? s;

export type CaseFields = {
	address: string;
	map_lot: string;
	owner: string;
	title: string;
	summary: string;
	tags: CaseTag[];
	status: CaseStatus;
};

export type Case = CaseFields & {
	id: string;
	created_by: string;
	created_at: string;
	updated_by: string;
	updated_at: string;
	item_count?: number;
	kinds?: Record<string, number>;
	next_deadline?: { date: string; label: string } | null;
};

type ItemBase = { id: string; case_id: string; created_by: string; created_at: string; updated_at: string };

export type NoteItem = ItemBase & { kind: 'note'; text: string };
export type AnswerItem = ItemBase & {
	kind: 'answer';
	answer_id: string | null;
	question: string;
	answer: string;
	sources: Source[];
	cited: number[];
	asked_at: string | null;
	note: string;
	stamp: string;
};
export type DeadlineItem = ItemBase & {
	kind: 'deadline';
	label: string;
	date: string;
	citation: string;
	note: string;
	trigger: string;
};
export type DraftItem = ItemBase & { kind: 'draft'; draft_id: string; title: string; template: string };
export type CaseItem = NoteItem | AnswerItem | DeadlineItem | DraftItem;

export type CaseWithItems = Case & { items: CaseItem[] };

/** POST bodies for /api/staff/cases/{id}/items. Other pages (research desk,
 * deadline calculator, drafts) use these to save into a case. */
export type NewItem =
	| { kind: 'note'; text: string }
	| { kind: 'answer'; answer_id?: string; question?: string; answer?: string; sources?: Source[]; note?: string }
	| { kind: 'deadline'; label: string; date: string; citation?: string; note?: string; trigger?: string }
	| { kind: 'draft'; draft_id: string; title?: string; template?: string };

export const emptyCase = (): CaseFields => ({
	address: '',
	map_lot: '',
	owner: '',
	title: '',
	summary: '',
	tags: [],
	status: 'open'
});

const base = '/api/staff/cases';
const enc = encodeURIComponent;

export const cases = {
	list: (params: { q?: string; status?: string; tag?: string } = {}) => {
		const qs = new URLSearchParams();
		for (const [k, v] of Object.entries(params)) if (v) qs.set(k, v);
		const s = qs.toString();
		return api.get<{ cases: Case[]; total: number }>(s ? `${base}?${s}` : base);
	},
	create: (fields: CaseFields) => api.post<Case>(base, fields),
	get: (id: string) => api.get<CaseWithItems>(`${base}/${enc(id)}`),
	update: (id: string, fields: Partial<CaseFields>) => api.patch<Case>(`${base}/${enc(id)}`, fields),
	remove: (id: string) => api.del<{ ok: boolean; items_deleted: number }>(`${base}/${enc(id)}`),
	items: (id: string) => api.get<{ items: CaseItem[] }>(`${base}/${enc(id)}/items`),
	addItem: (id: string, item: NewItem) => api.post<CaseItem>(`${base}/${enc(id)}/items`, item),
	removeItem: (id: string, itemId: string) => api.del<{ ok: boolean }>(`${base}/${enc(id)}/items/${enc(itemId)}`),
	exportUrl: (id: string) => `${base}/${enc(id)}/export.md`
};

// ---------------------------------------------------------------- formatting

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

/** "2026-11-02" -> "Nov 2, 2026" without a time zone shift. */
export function fmtDay(ymd: string): string {
	const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(ymd || '');
	if (!m) return ymd || '';
	return `${MONTHS[Number(m[2]) - 1]} ${Number(m[3])}, ${m[1]}`;
}

/** ISO timestamp -> "Oct 3, 2026, 14:05" in the viewer's zone. */
export function fmtWhen(iso: string): string {
	const d = new Date(iso);
	if (Number.isNaN(d.getTime())) return iso || '';
	const hh = String(d.getHours()).padStart(2, '0');
	const mm = String(d.getMinutes()).padStart(2, '0');
	return `${MONTHS[d.getMonth()]} ${d.getDate()}, ${d.getFullYear()}, ${hh}:${mm}`;
}

export function todayYmd(now: Date = new Date()): string {
	const p = (n: number) => String(n).padStart(2, '0');
	return `${now.getFullYear()}-${p(now.getMonth() + 1)}-${p(now.getDate())}`;
}

/** Whole days from today to ymd (negative when past). */
export function daysUntil(ymd: string, now: Date = new Date()): number {
	const [y, m, d] = ymd.split('-').map(Number);
	const a = Date.UTC(y, m - 1, d);
	const b = Date.UTC(now.getFullYear(), now.getMonth(), now.getDate());
	return Math.round((a - b) / 86_400_000);
}

export function dueLabel(ymd: string, now: Date = new Date()): string {
	const n = daysUntil(ymd, now);
	if (n === 0) return 'Due today';
	if (n === 1) return 'Due tomorrow';
	if (n > 1) return `In ${n} days`;
	if (n === -1) return '1 day past';
	return `${-n} days past`;
}

/** The deadlines of a case, soonest first. */
export function deadlines(items: CaseItem[]): DeadlineItem[] {
	return items
		.filter((i): i is DeadlineItem => i.kind === 'deadline')
		.sort((a, b) => a.date.localeCompare(b.date) || a.created_at.localeCompare(b.created_at));
}

export const caseHeading = (c: Pick<Case, 'title' | 'address' | 'id'>) => c.title || c.address || c.id;

export const KIND_LABELS: Record<CaseItem['kind'], string> = {
	note: 'Note',
	answer: 'Saved answer',
	deadline: 'Deadline',
	draft: 'Draft'
};
