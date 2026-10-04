// Project gate checklist (B8): types, API calls and helpers.
// The server is app/gates.py (rules in app/data/gates.toml), served by
// POST /api/staff/gates and GET /api/staff/gates/options.

import { api } from '$lib/api';

export type GateInput = {
	project_type: 'new_building' | 'addition' | 'alteration' | 'change_of_use' | 'demolition' | 'site_work';
	use: 'one_two_family' | 'multifamily' | 'commercial' | 'industrial' | 'institutional' | 'mixed';
	district: string;
	units: number;
	footprint: number;
	impervious: number;
	construction_cost: number;
	historic: 'none' | 'contributing' | 'noncontributing' | 'landmark';
	visible_from_street: boolean;
	shoreland: boolean;
	flood_zone: boolean;
	subdivision: boolean;
	use_requires_site_plan: boolean;
	needs_variance: boolean;
	private_road: boolean;
	plumbing: boolean;
	subsurface: boolean;
	electrical: boolean;
	demolition: boolean;
	renovation_over_75: boolean;
	life_safety_change: boolean;
	solar: boolean;
	sprinkler_alarm: boolean;
	sewer_water: boolean;
	street_work: boolean;
	new_driveway: boolean;
	state_road: boolean;
	near_protected_resource: boolean;
};

export type BoolField = { [K in keyof GateInput]: GateInput[K] extends boolean ? K : never }[keyof GateInput];

export type Option = { value: string; label: string };
export type Phase = { n: number; label: string; summary: string };

export type GateOptions = {
	project_types: Option[];
	uses: Option[];
	historic: Option[];
	districts: Option[];
	phases: Phase[];
};

export type Gate = {
	id: string;
	order: number;
	phase: number;
	phase_label: string;
	authority: string;
	title: string;
	citation: string;
	url: string;
	source?: string;
	quote?: string;
	verified: boolean;
	scope: 'city' | 'state' | 'utility';
	blocks?: string;
	note?: string;
	reasons: string[];
};

export type ExemptGate = Omit<Gate, 'order' | 'phase_label'> & { exempt_reason: string };

export type GateResult = {
	input: GateInput;
	phases: Phase[];
	gates: Gate[];
	exempt: ExemptGate[];
	district_notes: { district: string; text: string; citation?: string; url?: string }[];
	assumptions: string[];
	unverified: number;
	checked: string;
};

export const gatesApi = {
	options: () => api.get<GateOptions>('/api/staff/gates/options'),
	check: (input: GateInput) => api.post<GateResult>('/api/staff/gates', input)
};

export const emptyInput = (): GateInput => ({
	project_type: 'new_building',
	use: 'one_two_family',
	district: 'unknown',
	units: 1,
	footprint: 0,
	impervious: 0,
	construction_cost: 0,
	historic: 'none',
	visible_from_street: true,
	shoreland: false,
	flood_zone: false,
	subdivision: false,
	use_requires_site_plan: false,
	needs_variance: false,
	private_road: false,
	plumbing: false,
	subsurface: false,
	electrical: false,
	demolition: false,
	renovation_over_75: false,
	life_safety_change: false,
	solar: false,
	sprinkler_alarm: false,
	sewer_water: false,
	street_work: false,
	new_driveway: false,
	state_road: false,
	near_protected_resource: false
});

/** Checkbox groups for the form, in the order a CEO walks a project. */
export const FLAG_GROUPS: { title: string; flags: { key: BoolField; label: string; help?: string }[] }[] = [
	{
		title: 'Location',
		flags: [
			{ key: 'shoreland', label: 'In the shoreland zone', help: 'Within 250 ft of the Kennebec or Messalonskee, 75 ft of a stream (§ 275-4.27B)' },
			{ key: 'flood_zone', label: 'In a special flood hazard area' },
			{ key: 'near_protected_resource', label: 'In or next to a protected natural resource', help: 'River, stream, wetland or significant habitat' },
			{ key: 'state_road', label: 'Driveway or entrance on a state road' }
		]
	},
	{
		title: 'Planning and zoning',
		flags: [
			{ key: 'subdivision', label: 'Creates or sits in a subdivision' },
			{ key: 'use_requires_site_plan', label: 'Use that Chapter 275 sends to site plan review' },
			{ key: 'needs_variance', label: 'Needs a variance' },
			{ key: 'private_road', label: 'Served by a private road' }
		]
	},
	{
		title: 'Scope of work',
		flags: [
			{ key: 'plumbing', label: 'Plumbing' },
			{ key: 'subsurface', label: 'Septic system (subsurface disposal)' },
			{ key: 'electrical', label: 'Electrical' },
			{ key: 'sprinkler_alarm', label: 'Sprinkler or fire alarm' },
			{ key: 'solar', label: 'Solar' },
			{ key: 'demolition', label: 'Demolition, in whole or part' },
			{ key: 'renovation_over_75', label: 'Renovates more than 75% of the occupied space' },
			{ key: 'life_safety_change', label: 'Alters life safety components (exits, alarms)' }
		]
	},
	{
		title: 'Streets and utilities',
		flags: [
			{ key: 'sewer_water', label: 'New or changed sewer or water connection' },
			{ key: 'street_work', label: 'Digging in a City street' },
			{ key: 'new_driveway', label: 'New or changed driveway on a City street' }
		]
	}
];

export function groupByPhase(result: GateResult): { phase: Phase; gates: Gate[] }[] {
	return result.phases
		.map((phase) => ({ phase, gates: result.gates.filter((g) => g.phase === phase.n) }))
		.filter((p) => p.gates.length > 0);
}

/** Plain-text checklist for a case note or the clipboard. */
export function checklistText(result: GateResult, labels: { project?: string; use?: string; district?: string } = {}): string {
	const lines: string[] = ['Project gates'];
	const head = [labels.project, labels.use, labels.district].filter(Boolean).join(', ');
	if (head) lines.push(head);
	lines.push('');
	for (const { phase, gates } of groupByPhase(result)) {
		lines.push(`${phase.n}. ${phase.label}`);
		for (const g of gates) {
			const flag = g.verified ? '' : ' [unverified]';
			lines.push(`  ${g.order}) ${g.title} (${g.authority}). ${g.citation}${flag}`);
			for (const r of g.reasons) lines.push(`     - ${r}`);
		}
	}
	if (result.exempt.length) {
		lines.push('', 'Not required');
		for (const e of result.exempt) lines.push(`  ${e.title}: ${e.exempt_reason}`);
	}
	lines.push('', 'Research aid, not a determination of the Code Enforcement Officer.');
	return lines.join('\n');
}

const STORE_KEY = 'wv.gates.input';

export function loadSaved(): GateInput | null {
	try {
		const raw = localStorage.getItem(STORE_KEY);
		if (!raw) return null;
		return { ...emptyInput(), ...(JSON.parse(raw) as Partial<GateInput>) };
	} catch {
		return null;
	}
}

export function saveInput(input: GateInput) {
	try {
		localStorage.setItem(STORE_KEY, JSON.stringify(input));
	} catch {
		/* private window or blocked storage */
	}
}

/** Numbers from text inputs: blank or junk is 0, never negative. */
export function toCount(v: unknown): number {
	const n = Math.floor(Number(String(v ?? '').replace(/[,\s]/g, '')));
	return Number.isFinite(n) && n > 0 ? n : 0;
}
