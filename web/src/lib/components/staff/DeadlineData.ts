// Deadline calculator (B7): types, API calls and pure helpers.
// The server is app/routers/deadlines.py; the rules are app/data/deadlines.toml.

import { api } from '$lib/api';
import type { NewItem } from './CaseData';

export type Trigger = {
	id: string;
	group: string;
	label: string;
	help?: string;
	needs_time?: boolean;
};

export type Convention = {
	label: string;
	summary: string;
	citation?: string;
	url?: string;
	quote?: string;
	caution?: string;
};

export type Related = { citation: string; url: string; quote: string; source?: string };

export type Rule = {
	id: string;
	triggers: string[];
	label: string;
	actor: string;
	kind: 'deadline' | 'lapse' | 'earliest';
	amount: number;
	unit: 'days' | 'working_days' | 'hours' | 'months' | 'annual';
	direction: 'after' | 'before';
	convention: string;
	citation: string;
	url: string;
	source?: string;
	quote: string;
	verified: boolean;
	applies: 'waterville' | 'check';
	checked?: string;
	caution?: string;
	note?: string;
	also: Related[];
	offset: string;
};

export type Clock = Omit<Rule, 'convention'> & {
	convention: { id: string; label: string; summary: string; citation: string; caution: string };
	date: string;
	time: string | null;
	weekday: string;
	raw_date: string | null;
	closed: string | null;
	plan_by: string | null;
	alt: { date: string; basis: string } | null;
	steps: string[];
};

export type ComputeResult = {
	trigger: Trigger;
	date: string;
	time: string | null;
	weekday: string;
	event_closed: string | null;
	results: Clock[];
	unverified: number;
};

export type RuleTable = {
	checked: string;
	conventions: Record<string, Convention>;
	calendars: Record<string, { label: string; citation: string; url: string; quote: string; note: string }>;
	triggers: Trigger[];
	rules: Rule[];
	range: { min: string; max: string };
};

export type Holiday = { date: string; name: string; weekday: string };

export const deadlinesApi = {
	table: () => api.get<RuleTable>('/api/deadlines'),
	compute: (trigger: string, date: string, time?: string) => {
		const qs = new URLSearchParams({ trigger, date });
		if (time) qs.set('time', time);
		return api.get<ComputeResult>(`/api/deadlines/compute?${qs}`);
	},
	calendar: (year: number) => api.get<{ year: number; holidays: Holiday[] }>(`/api/deadlines/calendar?year=${year}`)
};

// ---------------------------------------------------------------- helpers

/** Triggers grouped in the order the table lists them. */
export function groupTriggers(triggers: Trigger[]): { group: string; items: Trigger[] }[] {
	const out: { group: string; items: Trigger[] }[] = [];
	for (const t of triggers) {
		let g = out.find((x) => x.group === t.group);
		if (!g) out.push((g = { group: t.group, items: [] }));
		g.items.push(t);
	}
	return out;
}

export type Status = 'verified' | 'check' | 'unverified';

export function statusOf(r: Pick<Rule, 'verified' | 'applies'>): Status {
	if (!r.verified) return 'unverified';
	return r.applies === 'check' ? 'check' : 'verified';
}

export const STATUS_TEXT: Record<Status, string> = {
	verified: 'Verified against primary text',
	check: 'Text verified; reach in Waterville unconfirmed',
	unverified: 'Unverified'
};

export const KIND_TEXT: Record<Rule['kind'], string> = {
	deadline: 'Act by',
	lapse: 'Lapses',
	earliest: 'Not before'
};

const MONTHS = [
	'January',
	'February',
	'March',
	'April',
	'May',
	'June',
	'July',
	'August',
	'September',
	'October',
	'November',
	'December'
];
const SHORT_DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

function parts(ymd: string): [number, number, number] {
	const [y, m, d] = ymd.split('-').map(Number);
	return [y, m, d];
}

/** Monday = 0, matching the server. */
export function weekdayIndex(ymd: string): number {
	const [y, m, d] = parts(ymd);
	return (new Date(Date.UTC(y, m - 1, d)).getUTCDay() + 6) % 7;
}

export function shortDay(ymd: string): string {
	return SHORT_DAYS[weekdayIndex(ymd)];
}

/** "2026-11-17" -> "Tuesday, November 17, 2026". */
export function longDay(ymd: string): string {
	const [y, m, d] = parts(ymd);
	const names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
	return `${names[weekdayIndex(ymd)]}, ${MONTHS[m - 1]} ${d}, ${y}`;
}

/** "14:30" -> "2:30 pm". */
export function fmtTime(hhmm: string | null | undefined): string {
	if (!hhmm) return '';
	const [h, m] = hhmm.split(':').map(Number);
	const suffix = h < 12 ? 'am' : 'pm';
	const h12 = h % 12 === 0 ? 12 : h % 12;
	return `${h12}:${String(m).padStart(2, '0')} ${suffix}`;
}

export type AgendaDay = { date: string; day: number; weekday: string; clocks: Clock[]; event: boolean; holiday: string };
export type AgendaMonth = { key: string; label: string; days: AgendaDay[] };

/** Clocks laid out by month and day, with the event date and any holidays on those days. */
export function agenda(result: Pick<ComputeResult, 'date' | 'results'>, holidays: Holiday[] = []): AgendaMonth[] {
	const byDate = new Map<string, AgendaDay>();
	const hol = new Map(holidays.map((h) => [h.date, h.name]));
	const ensure = (ymd: string) => {
		let d = byDate.get(ymd);
		if (!d) {
			d = { date: ymd, day: parts(ymd)[2], weekday: shortDay(ymd), clocks: [], event: false, holiday: hol.get(ymd) || '' };
			byDate.set(ymd, d);
		}
		return d;
	};
	ensure(result.date).event = true;
	for (const c of result.results) ensure(c.date).clocks.push(c);
	const days = [...byDate.values()].sort((a, b) => a.date.localeCompare(b.date));
	const months: AgendaMonth[] = [];
	for (const d of days) {
		const key = d.date.slice(0, 7);
		let m = months.at(-1);
		if (!m || m.key !== key) {
			const [y, mo] = parts(d.date);
			months.push((m = { key, label: `${MONTHS[mo - 1]} ${y}`, days: [] }));
		}
		m.days.push(d);
	}
	return months;
}

/** Years an agenda spans, for loading holiday names. */
export function yearsOf(result: Pick<ComputeResult, 'date' | 'results'>): number[] {
	const ys = new Set([result.date, ...result.results.map((r) => r.date)].map((d) => Number(d.slice(0, 4))));
	return [...ys].sort();
}

/** The notebook item for one clock (POST /api/staff/cases/{id}/items). */
export function caseItemFor(c: Clock, result: Pick<ComputeResult, 'trigger' | 'date' | 'time'>): NewItem {
	const when = `${longDay(result.date)}${result.time ? ` at ${fmtTime(result.time)}` : ''}`;
	const lines = [
		`${c.offset} (${c.convention.label}).`,
		c.time ? `Time: ${fmtTime(c.time)}.` : '',
		c.plan_by ? `City Hall is closed that day; last open day before it: ${longDay(c.plan_by)}.` : '',
		c.alt ? `Counting ${c.alt.basis} instead gives ${longDay(c.alt.date)}.` : '',
		statusOf(c) === 'verified' ? '' : `${STATUS_TEXT[statusOf(c)]}.`,
		c.caution ?? ''
	].filter(Boolean);
	return {
		kind: 'deadline',
		label: clip(c.label, 300),
		date: c.date,
		citation: clip(c.citation, 300),
		trigger: clip(`${result.trigger.label}, ${when}`, 300),
		note: clip(lines.join(' '), 4000)
	};
}

function clip(s: string, n: number): string {
	return s.length <= n ? s : s.slice(0, n - 1) + '…';
}

/** Today's date as YYYY-MM-DD in the viewer's zone. */
export function todayYmd(now: Date = new Date()): string {
	const p = (n: number) => String(n).padStart(2, '0');
	return `${now.getFullYear()}-${p(now.getMonth() + 1)}-${p(now.getDate())}`;
}
