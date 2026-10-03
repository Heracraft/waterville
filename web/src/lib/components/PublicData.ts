// Types and API helpers for the public tools: checklists (A1), triage (A2),
// the permit router (A3) and the fee estimator (A4). The complaint sheet (A5)
// has no API: everything stays in the browser.

import { api } from '$lib/api';
import type { BotMessage } from '$lib/chat.svelte';

export type Form = { id: string; title: string; url: string; who: string };

export type Section = { citation: string; url: string; says: string };

export type FireStatus = 'yes' | 'likely' | 'maybe' | 'no';

export type Checklist = {
	id: string;
	title: string;
	summary: string;
	sections: Section[];
	forms: Form[];
	bring: string[];
	building_permit: boolean;
	survey_note: string | null;
	inspections: string | null;
	notes: string[];
	fire_review: { status: FireStatus; label: string; form: Form };
	permit_guide: string;
	confirm_line: string;
	office_phone: string;
	applications_page: string;
	checked: string;
};

export type Triage = {
	id: string;
	kind: 'urgent' | 'elsewhere';
	title: string;
	lines: string[];
	links: { label: string; href: string }[];
	office_phone: string;
};

export type RouterProject = { id: string; label: string; checklist: string | null; defaults: Record<string, boolean> };
export type RouterQuestion = { id: string; label: string; help: string; fire: boolean };
export type RouterOptions = {
	projects: RouterProject[];
	questions: RouterQuestion[];
	confirm_line: string;
	office_phone: string;
	applications_page: string;
};

export type RouterResult = {
	project: { id: string; label: string };
	answers: Record<string, boolean>;
	permits: (Form & { why: string })[];
	also: { title: string; who: string; why: string; citation: string; url: string }[];
	ask_office: string | null;
	fire_review: { status: 'required' | 'ask' | 'not_indicated'; text: string; reasons: string[]; form: Form };
	checklist: Checklist | null;
	confirm_line: string;
	office_phone: string;
	applications_page: string;
};

export type FeeItem = { id: string; group: string; label: string; cents: number };
export type FeeSchedule = {
	building: { published: boolean; note: string; quote: string; citation: string; url: string };
	after_the_fact: string;
	life_safety: { title: string; rate: string; source: string; source_url: string; formula: string; excludes: string };
	electrical: {
		title: string;
		source: string;
		source_url: string;
		scope: string;
		minimum_note: string;
		minimum: { id: string; label: string; cents: number }[];
		items: FeeItem[];
	};
	fixed: { label: string; cents: number; citation: string; url: string }[];
	office_phone: string;
	checked: string;
};

export type FeeRequest = {
	electrical?: { occupancy?: string | null; items: Record<string, number> };
	life_safety?: { construction_cost: number };
};

export type FeeEstimate = {
	estimate: true;
	life_safety?: { construction_cost_cents: number; rate: string; estimate_cents: number };
	electrical?: {
		lines: { id: string; label: string; qty: number; unit_cents: number; cents: number }[];
		subtotal_cents: number;
		minimum: { id: string; label: string; cents: number } | null;
		estimate_cents: number;
		basis: 'minimum' | 'line_items';
	};
};

export const publicApi = {
	checklist: (id: string) => api.get<Checklist>(`/api/checklists/${encodeURIComponent(id)}`),
	routerOptions: () => api.get<RouterOptions>('/api/permit-router'),
	route: (project: string, answers: Record<string, boolean>) =>
		api.post<RouterResult>('/api/permit-router', { project, answers }),
	fees: () => api.get<FeeSchedule>('/api/fees'),
	estimate: (body: FeeRequest) => api.post<FeeEstimate>('/api/fees/estimate', body)
};

/** The checklist and triage cards the server sent with an answer, if any. */
export function answerCards(msg: BotMessage): { checklist: Checklist | null; triage: Triage | null } {
	const x = msg.extras || {};
	return {
		checklist: isChecklist(x.checklist) ? x.checklist : null,
		triage: isTriage(x.triage) ? x.triage : null
	};
}

function isChecklist(v: unknown): v is Checklist {
	return !!v && typeof v === 'object' && Array.isArray((v as Checklist).sections) && Array.isArray((v as Checklist).bring);
}

function isTriage(v: unknown): v is Triage {
	return !!v && typeof v === 'object' && Array.isArray((v as Triage).lines) && typeof (v as Triage).title === 'string';
}

/** "$1,234.50" from cents. */
export function money(cents: number): string {
	const sign = cents < 0 ? '-' : '';
	const abs = Math.abs(Math.round(cents));
	const dollars = Math.floor(abs / 100).toLocaleString('en-US');
	return `${sign}$${dollars}.${String(abs % 100).padStart(2, '0')}`;
}

/** Parses a typed dollar amount ("$12,500", "12500.5"); null when empty or not a number. */
export function parseDollars(text: string): number | null {
	const t = text.replace(/[$,\s]/g, '');
	if (!t) return null;
	if (!/^\d+(\.\d{0,2})?$/.test(t)) return null;
	return Number(t);
}

/** Phone number as a tel: link target. */
export function telHref(phone: string): string {
	return 'tel:+1' + phone.replace(/\D/g, '');
}

// ------------------------------------------------------------------ complaint sheet (A5)

export const CONCERNS = [
	{ id: 'no_heat', label: 'No heat', urgent: true },
	{ id: 'sewage', label: 'Sewage or plumbing failure', urgent: true },
	{ id: 'structural', label: 'Structural damage, sagging or collapse', urgent: true },
	{ id: 'fire', label: 'Fire hazard, blocked exit or missing smoke alarms', urgent: true },
	{ id: 'wiring', label: 'Unsafe electrical wiring', urgent: true },
	{ id: 'water', label: 'No running water', urgent: true },
	{ id: 'exterior', label: 'Building exterior in disrepair (roof, siding, windows, porches)', urgent: false },
	{ id: 'yard', label: 'Trash, junk or debris in the yard; grass over 10 inches', urgent: false },
	{ id: 'vehicles', label: 'Two or more unregistered or uninspected vehicles', urgent: false },
	{ id: 'vacant', label: 'Vacant or abandoned building not secured', urgent: false },
	{ id: 'vermin', label: 'Rodents or insects', urgent: false },
	{ id: 'no_permit', label: 'Construction without a permit', urgent: false },
	{ id: 'use', label: 'A use that may not be allowed in the zone (business, units, signs)', urgent: false },
	{ id: 'other', label: 'Other', urgent: false }
] as const;

export type ConcernId = (typeof CONCERNS)[number]['id'];

export type Complaint = {
	name: string;
	phone: string;
	email: string;
	mailing: string;
	relation: string;
	address: string;
	unit: string;
	mapLot: string;
	owner: string;
	concerns: ConcernId[];
	description: string;
	firstSeen: string;
	lastSeen: string;
	ongoing: string;
	ownerContacted: string;
	photos: string;
	others: string;
};

export function emptyComplaint(): Complaint {
	return {
		name: '',
		phone: '',
		email: '',
		mailing: '',
		relation: '',
		address: '',
		unit: '',
		mapLot: '',
		owner: '',
		concerns: [],
		description: '',
		firstSeen: '',
		lastSeen: '',
		ongoing: '',
		ownerContacted: '',
		photos: '',
		others: ''
	};
}

export const RELATIONS = ['Tenant at the property', 'Neighbor', 'Owner', 'Other'];

/** True when any selected concern is a life safety matter that should not wait for an appointment. */
export function isUrgent(c: Pick<Complaint, 'concerns'>): boolean {
	return c.concerns.some((id) => CONCERNS.find((x) => x.id === id)?.urgent);
}

/** The sheet's missing essentials, in the order the office needs them. */
export function missing(c: Complaint): string[] {
	const out: string[] = [];
	if (!c.address.trim()) out.push('the address of the property');
	if (!c.concerns.length) out.push('the type of concern');
	if (!c.description.trim()) out.push('a description of what you saw');
	return out;
}

/** "October 3, 2026" from "2026-10-03"; the input text when it is not a date. */
export function longDate(iso: string): string {
	const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
	if (!m) return iso;
	const d = new Date(Date.UTC(+m[1], +m[2] - 1, +m[3]));
	return d.toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric', timeZone: 'UTC' });
}
