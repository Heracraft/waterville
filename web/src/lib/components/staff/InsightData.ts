// Types and helpers for /staff/insights: the question digest (A7b), the
// reports from case notebooks (B13) and the code change alerts.

import { api, ApiError } from '$lib/api';

export type DayCount = { date: string; count: number; unanswered: number; failed: number };
export type Topic = { id: string; label: string; count: number; unanswered: number; examples: string[] };

export type Insights = {
	range: { start: string; end: string; days: number };
	logging: { enabled: boolean };
	totals: {
		questions: number;
		answered: number;
		unanswered: number;
		failed: number;
		unanswered_rate: number | null;
		avg_answer_chars: number | null;
	};
	volume: DayCount[];
	topics: Topic[];
	top_sections: { citation: string; count: number }[];
	unanswered_examples: { date: string; question: string; times: number }[];
	feedback: {
		yes: number;
		no: number;
		total: number;
		helpful_rate: number | null;
		not_helpful: { date: string; question: string; cited: string[]; times: number }[];
	};
};

export type SummaryRow = { label: string; count: number | null; basis: string; confirm: string };

export type ReportCase = {
	id: string;
	address: string;
	map_lot: string;
	title: string;
	tags: string[];
	status: 'open' | 'monitoring' | 'closed';
	opened: string;
	last_activity: string;
	opened_in_period: boolean;
	notes: number;
	research: number;
	deadlines: number;
	actions: string[];
	complaint: boolean;
	enforcement: boolean;
	court: boolean;
};

export type Report = {
	id: 'shoreland' | 'lpi';
	title: string;
	citation: string;
	quote: string;
	recipient: string;
	verify?: string;
	tags: string[];
	start: string;
	end: string;
	generated_at: string;
	note: string;
	summary: SummaryRow[];
	status: Record<'open' | 'monitoring' | 'closed', number>;
	opened_in_period: number;
	cases: ReportCase[];
};

/** One code change alert, read loosely: the corpus agent owns /api/staff/changes. */
export type Change = {
	citation: string;
	title?: string;
	kind?: string;
	url?: string;
	detected_at?: string;
	summary?: string;
};

export const RANGES = [
	{ days: 7, label: 'Last 7 days' },
	{ days: 30, label: 'Last 30 days' },
	{ days: 90, label: 'Last 90 days' },
	{ days: 365, label: 'Last 12 months' }
];

export const insightsApi = {
	get: (days: number) => api.get<Insights>(`/api/staff/insights?days=${days}`),
	shoreland: (start: string, end: string) =>
		api.get<Report>(`/api/staff/reports/shoreland?start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}`),
	lpi: (year: number) => api.get<Report>(`/api/staff/reports/lpi?year=${year}`)
};

/** Change alerts, or null when the endpoint is not there yet (404/501). */
export async function loadChanges(): Promise<Change[] | null> {
	try {
		return normalizeChanges(await api.get<unknown>('/api/staff/changes'));
	} catch (e) {
		if (e instanceof ApiError && (e.status === 404 || e.status === 501)) return null;
		throw e;
	}
}

function str(v: unknown): string | undefined {
	return typeof v === 'string' && v ? v : undefined;
}

/** Accepts a list or {changes: [...]}/{items: [...]}, with common field names. */
export function normalizeChanges(raw: unknown): Change[] {
	const list = Array.isArray(raw)
		? raw
		: raw && typeof raw === 'object'
			? ((raw as Record<string, unknown>).changes ?? (raw as Record<string, unknown>).items ?? [])
			: [];
	if (!Array.isArray(list)) return [];
	const out: Change[] = [];
	for (const r of list) {
		if (!r || typeof r !== 'object') continue;
		const o = r as Record<string, unknown>;
		const citation = str(o.citation) ?? str(o.id) ?? str(o._rk);
		if (!citation) continue;
		out.push({
			citation,
			title: str(o.title),
			kind: str(o.kind) ?? str(o.change) ?? str(o.status),
			url: str(o.url) ?? str(o.open_url),
			detected_at: str(o.detected_at) ?? str(o.ts) ?? str(o.created_at) ?? str(o.date) ?? str(o._pk),
			summary: str(o.summary) ?? str(o.note)
		});
	}
	return out.sort((a, b) => (b.detected_at ?? '').localeCompare(a.detected_at ?? ''));
}

export function pct(rate: number | null | undefined): string {
	return rate == null ? 'n/a' : `${Math.round(rate * 100)}%`;
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

/** "2026-10-03" to "Oct 3" (or "Oct 3, 2026" with year). */
export function shortDay(iso: string, year = false): string {
	const [y, m, d] = iso.slice(0, 10).split('-').map(Number);
	if (!y || !m || !d) return iso;
	return `${MONTHS[m - 1]} ${d}${year ? `, ${y}` : ''}`;
}

/** Bars for the volume chart: days, or weeks (Monday start) past 90 days. */
export function bucket(volume: DayCount[]): { label: string; start: string; end: string; answered: number; unanswered: number; failed: number; count: number }[] {
	const weekly = volume.length > 90;
	const out: ReturnType<typeof bucket> = [];
	for (const d of volume) {
		const date = new Date(d.date + 'T00:00:00Z');
		const key = weekly ? weekStart(date) : d.date;
		let b = out[out.length - 1];
		if (!b || b.start !== key) {
			b = { label: '', start: key, end: d.date, answered: 0, unanswered: 0, failed: 0, count: 0 };
			out.push(b);
		}
		b.end = d.date;
		b.count += d.count;
		b.unanswered += d.unanswered;
		b.failed += d.failed;
		b.answered += d.count - d.unanswered - d.failed;
	}
	for (const b of out) b.label = weekly ? `Week of ${shortDay(b.start)}` : shortDay(b.start);
	return out;
}

function weekStart(d: Date): string {
	const back = (d.getUTCDay() + 6) % 7;
	return new Date(d.getTime() - back * 86400000).toISOString().slice(0, 10);
}

/** A plain-text digest the CEO can paste into an email (A7b without a mail service). */
export function digestText(i: Insights, changes: Change[] | null): string {
	const t = i.totals;
	const lines = [
		`Public question digest, ${shortDay(i.range.start, true)} to ${shortDay(i.range.end, true)}`,
		'',
		`Questions: ${t.questions}. Answered from the sources: ${t.answered}. Not answered: ${t.unanswered} (${pct(t.unanswered_rate)}). Failed: ${t.failed}.`
	];
	if (i.feedback.total)
		lines.push(`Feedback: ${i.feedback.yes} helpful, ${i.feedback.no} not helpful (${pct(i.feedback.helpful_rate)} helpful).`);
	if (i.topics.length) {
		lines.push('', 'Top topics');
		for (const g of i.topics) lines.push(`- ${g.label}: ${g.count}${g.unanswered ? ` (${g.unanswered} not answered)` : ''}`);
	}
	if (i.top_sections.length) {
		lines.push('', 'Most cited sections');
		for (const s of i.top_sections) lines.push(`- ${s.citation}: ${s.count}`);
	}
	if (i.unanswered_examples.length) {
		lines.push('', 'Questions the sources did not answer');
		for (const q of i.unanswered_examples) lines.push(`- ${q.question}${q.times > 1 ? ` (asked ${q.times} times)` : ''}`);
	}
	if (changes?.length) {
		lines.push('', 'Code change alerts');
		for (const c of changes.slice(0, 15))
			lines.push(`- ${c.citation}${c.title ? ` ${c.title}` : ''}${c.kind ? ` (${c.kind})` : ''}`);
	}
	lines.push('', 'Questions are logged with names, addresses, phone numbers and emails removed.');
	return lines.join('\n');
}

function csvCell(v: unknown): string {
	const s = v == null ? '' : String(v);
	return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

/** The report's case table as CSV, for a spreadsheet. */
export function reportCsv(r: Report): string {
	const head = ['Case', 'Address', 'Map/lot', 'Title', 'Tags', 'Status', 'Opened', 'Last activity', 'Notes', 'Deadlines', 'Actions in period'];
	const rows = r.cases.map((c) => [
		c.id,
		c.address,
		c.map_lot,
		c.title,
		c.tags.join(' '),
		c.status,
		c.opened,
		c.last_activity,
		c.notes,
		c.deadlines,
		c.actions.join('; ')
	]);
	const summary = r.summary.map((s) => [s.label, s.count ?? '', s.basis, s.confirm]);
	return [
		[r.title, `${r.start} to ${r.end}`],
		[r.note],
		[],
		['Category', 'From case notebooks', 'Basis', 'Confirm in'],
		...summary,
		[],
		head,
		...rows
	]
		.map((row) => row.map(csvCell).join(','))
		.join('\r\n');
}

export function download(name: string, text: string, type = 'text/csv') {
	const url = URL.createObjectURL(new Blob([text], { type: `${type};charset=utf-8` }));
	const a = document.createElement('a');
	a.href = url;
	a.download = name;
	document.body.appendChild(a);
	a.click();
	a.remove();
	setTimeout(() => URL.revokeObjectURL(url), 1000);
}
