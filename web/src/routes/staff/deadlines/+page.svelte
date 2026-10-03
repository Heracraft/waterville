<script lang="ts">
	// Deadline calculator (B7): pick a trigger event and its date, see every
	// clock it starts with the controlling text, as cards or as a calendar list,
	// and add clocks to a case. ?case=ID preselects the case; ?trigger= and
	// ?date= (and &time=) reopen a calculation.
	import { page } from '$app/state';
	import { replaceState } from '$app/navigation';
	import { untrack } from 'svelte';
	import Stamp from '$lib/components/Stamp.svelte';
	import CasePicker from '$lib/components/staff/CasePicker.svelte';
	import { cases } from '$lib/components/staff/CaseData';
	import DeadlineClock from '$lib/components/staff/DeadlineClock.svelte';
	import DeadlineAgenda from '$lib/components/staff/DeadlineAgenda.svelte';
	import DeadlineRuleTable from '$lib/components/staff/DeadlineRuleTable.svelte';
	import {
		caseItemFor,
		deadlinesApi,
		groupTriggers,
		longDay,
		fmtTime,
		todayYmd,
		yearsOf,
		type Clock,
		type ComputeResult,
		type Holiday,
		type RuleTable
	} from '$lib/components/staff/DeadlineData';

	const params = untrack(() => page.url.searchParams);
	let caseId = $state(params.get('case') || '');
	let trigger = $state(params.get('trigger') || '');
	let day = $state(params.get('date') || todayYmd());
	let at = $state(params.get('time') || '');
	let view = $state<'cards' | 'calendar'>('cards');

	let table = $state<RuleTable | null>(null);
	let tableError = $state('');
	let result = $state<ComputeResult | null>(null);
	let holidays = $state<Holiday[]>([]);
	let busy = $state(false);
	let error = $state('');
	let saves = $state<Record<string, 'idle' | 'saving' | 'saved' | 'error'>>({});
	let saveAllMsg = $state('');

	const groups = $derived(table ? groupTriggers(table.triggers) : []);
	const chosen = $derived(table?.triggers.find((t) => t.id === trigger));
	const unsaved = $derived(result ? result.results.filter((c) => saves[c.id] !== 'saved') : []);

	$effect(() => {
		deadlinesApi
			.table()
			.then((t) => {
				table = t;
				if (untrack(() => trigger) && untrack(() => params.get('date'))) calculate();
			})
			.catch((e) => (tableError = e instanceof Error ? e.message : String(e)));
	});

	async function calculate(ev?: SubmitEvent) {
		ev?.preventDefault();
		if (!trigger || !day) return;
		busy = true;
		error = '';
		saves = {};
		saveAllMsg = '';
		try {
			const r = await deadlinesApi.compute(trigger, day, chosen?.needs_time ? at : '');
			result = r;
			syncUrl();
			const hs: Holiday[] = [];
			for (const y of yearsOf(r)) {
				try {
					hs.push(...(await deadlinesApi.calendar(y)).holidays);
				} catch {
					/* the agenda still works without holiday names */
				}
			}
			holidays = hs;
		} catch (e) {
			result = null;
			error = e instanceof Error ? e.message : String(e);
		} finally {
			busy = false;
		}
	}

	function syncUrl() {
		const u = new URL(page.url);
		u.searchParams.set('trigger', trigger);
		u.searchParams.set('date', day);
		if (chosen?.needs_time && at) u.searchParams.set('time', at);
		else u.searchParams.delete('time');
		if (caseId) u.searchParams.set('case', caseId);
		else u.searchParams.delete('case');
		try {
			replaceState(u, {});
		} catch {
			/* before the router is ready */
		}
	}

	async function save(c: Clock) {
		if (!caseId || !result) return;
		saves[c.id] = 'saving';
		try {
			await cases.addItem(caseId, caseItemFor(c, result));
			saves[c.id] = 'saved';
		} catch {
			saves[c.id] = 'error';
		}
	}

	async function saveAll() {
		if (!caseId || !result) return;
		const todo = unsaved;
		for (const c of todo) await save(c);
		const failed = todo.filter((c) => saves[c.id] === 'error').length;
		saveAllMsg = failed ? `${todo.length - failed} added, ${failed} failed.` : `${todo.length} clocks added to case ${caseId}.`;
	}

	// A new case choice clears the "added" marks, which belong to the old case.
	let lastCase = untrack(() => caseId);
	$effect(() => {
		if (caseId !== lastCase) {
			lastCase = caseId;
			saves = {};
			saveAllMsg = '';
			if (result) syncUrl();
		}
	});
</script>

<svelte:head>
	<title>Deadlines | Staff | Waterville Codes RAG</title>
</svelte:head>

<main class="wrap staff-main">
	<div class="page-head">
		<h2 class="page-title">Deadlines</h2>
		<p class="page-lede">
			Pick the event and its date to see every legal clock it starts, with the controlling text and its citation.
		</p>
	</div>

	<div class="layout">
		<aside class="side">
			<form class="sheet accent" onsubmit={calculate} aria-label="Deadline calculator">
				{#if tableError}
					<p class="error-text" role="alert">Could not load the rule table: {tableError}</p>
				{/if}
				<label class="field" for="dl-trigger">
					<span>Event</span>
					<select id="dl-trigger" bind:value={trigger} required disabled={!table}>
						<option value="" disabled>{table ? 'Choose the event' : 'Loading'}</option>
						{#each groups as g (g.group)}
							<optgroup label={g.group}>
								{#each g.items as t (t.id)}<option value={t.id}>{t.label}</option>{/each}
							</optgroup>
						{/each}
					</select>
					{#if chosen?.help}<span class="help">{chosen.help}</span>{/if}
				</label>
				<div class="row">
					<label class="field" for="dl-date">
						<span>Date of the event</span>
						<input
							id="dl-date"
							type="date"
							bind:value={day}
							required
							min={table?.range.min}
							max={table?.range.max}
						/>
					</label>
					{#if chosen?.needs_time}
						<label class="field" for="dl-time">
							<span>Time</span>
							<input id="dl-time" type="time" bind:value={at} />
						</label>
					{/if}
				</div>
				{#if chosen?.needs_time && !at}
					<p class="help fine">No time: hour clocks count from 12:00 am, the earliest reading.</p>
				{/if}
				<CasePicker bind:value={caseId} label="Case to save clocks to" none="No case" />
				<button type="submit" class="btn" disabled={busy || !trigger || !day}>
					{busy ? 'Calculating' : 'Calculate'}
				</button>
			</form>

			<div class="sheet facts">
				<h3>How days are counted</h3>
				<ul>
					<li>The day of the event is never counted.</li>
					<li>City Hall is open Monday to Thursday. "Working days" counts those days, less City holidays (§ 56-5.1).</li>
					<li>Court periods follow M.R. Civ. P. 6(a): a last day on a weekend or Maine legal holiday runs to the next court day.</li>
					<li>City periods do not move. When the last day falls on a closed day, plan on the last open day before it.</li>
				</ul>
			</div>
		</aside>

		<section class="results" aria-live="polite" aria-busy={busy}>
			{#if error}
				<p class="notice error-text" role="alert">{error}</p>
			{/if}
			{#if result}
				<div class="sum">
					<div>
						<p class="eyebrow">{result.trigger.group}</p>
						<h3>{result.trigger.label}</h3>
						<p class="muted">
							{longDay(result.date)}{result.time ? `, ${fmtTime(result.time)}` : ''}{result.event_closed
								? ` (City Hall closed: ${result.event_closed})`
								: ''}. {result.results.length}
							{result.results.length === 1 ? 'clock' : 'clocks'}{result.unverified
								? `, ${result.unverified} unverified`
								: ''}.
						</p>
					</div>
					<div class="tools no-print">
						<div class="seg" role="group" aria-label="View">
							<button type="button" aria-pressed={view === 'cards'} onclick={() => (view = 'cards')}>Clocks</button>
							<button type="button" aria-pressed={view === 'calendar'} onclick={() => (view = 'calendar')}>Calendar</button>
						</div>
						<button
							type="button"
							class="btn secondary small"
							disabled={!caseId || unsaved.length === 0}
							onclick={saveAll}
							title={caseId ? '' : 'Choose a case first'}>Add all to case</button
						>
						<button type="button" class="btn secondary small" onclick={() => window.print()}>Print</button>
					</div>
				</div>
				{#if !caseId}
					<p class="muted fine no-print">Choose a case in the form to add clocks to it.</p>
				{/if}
				{#if saveAllMsg}
					<p class="flash" role="status">
						{saveAllMsg}
						{#if caseId}<a href="/staff/cases/{caseId}">Open the case</a>{/if}
					</p>
				{/if}

				{#if view === 'cards'}
					<ol class="clocks">
						{#each result.results as c (c.id)}
							<li>
								<DeadlineClock clock={c} canSave={!!caseId} saveState={saves[c.id] ?? 'idle'} onsave={save} />
							</li>
						{/each}
					</ol>
				{:else}
					<DeadlineAgenda {result} {holidays} />
				{/if}
				<Stamp />
			{:else if !busy}
				<div class="empty sheet">
					<p>Choose an event and its date, then Calculate.</p>
					<p class="muted">
						Each clock shows its citation and the controlling text. Clocks marked "Unverified, check before relying"
						could not be confirmed from primary text.
					</p>
				</div>
			{/if}
		</section>
	</div>

	{#if table}
		<details class="all-rules">
			<summary>Rule table: all {table.rules.length} clocks and how they count</summary>
			<div class="conventions">
				{#each Object.entries(table.conventions) as [id, c] (id)}
					<div class="conv">
						<h4>{c.label}</h4>
						<p>{c.summary}</p>
						{#if c.citation}<p class="muted">{c.citation}</p>{/if}
					</div>
				{/each}
			</div>
			<p class="muted fine">
				{table.calendars.city.note}
			</p>
			<DeadlineRuleTable {table} />
		</details>
	{/if}
</main>

<style>
	.layout {
		display: grid;
		grid-template-columns: 360px minmax(0, 1fr);
		gap: 32px;
		align-items: start;
	}
	.side {
		display: grid;
		gap: 16px;
	}
	.row {
		display: grid;
		grid-template-columns: minmax(0, 1fr) auto;
		gap: 12px;
	}
	.row .field:only-child {
		grid-column: 1 / -1;
	}
	.fine {
		font-size: 0.82rem;
	}
	.help.fine {
		margin: -8px 0 14px;
		color: var(--muted);
	}
	.facts h3 {
		font: 600 0.78rem var(--sans);
		text-transform: uppercase;
		letter-spacing: 0.06em;
		color: var(--accent);
	}
	.facts ul {
		margin: 0;
		padding-left: 1.1em;
		font-size: 0.88rem;
		line-height: 1.5;
	}
	.facts li + li {
		margin-top: 6px;
	}
	.sum {
		display: flex;
		flex-wrap: wrap;
		justify-content: space-between;
		align-items: flex-end;
		gap: 12px 20px;
		padding-bottom: 12px;
		margin-bottom: 16px;
		border-bottom: 1px solid var(--rule);
	}
	.sum h3 {
		margin: 0;
		font: 300 1.5rem/1.25 var(--serif);
	}
	.sum p {
		margin: 4px 0 0;
	}
	.sum .eyebrow {
		margin: 0;
	}
	.tools {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
		align-items: center;
	}
	.seg {
		display: inline-flex;
		border: 1px solid var(--rule);
	}
	.seg button {
		cursor: pointer;
		border: 0;
		background: var(--surface);
		color: var(--text);
		font: 600 0.8rem var(--sans);
		padding: 5px 12px;
	}
	.seg button + button {
		border-left: 1px solid var(--rule);
	}
	.seg button[aria-pressed='true'] {
		background: var(--text);
		color: var(--bg);
	}
	.seg button:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: -2px;
	}
	.flash {
		margin: 0 0 14px;
		padding: 8px 14px;
		border-left: 3px solid var(--accent);
		background: var(--surface);
		font: 600 0.88rem var(--sans);
	}
	.flash a {
		margin-left: 8px;
		color: var(--text);
		text-decoration-color: var(--accent);
	}
	.clocks {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		gap: 14px;
	}
	.empty p {
		margin: 0 0 6px;
	}
	.all-rules {
		margin-top: 36px;
		border-top: 1px solid var(--rule);
		padding-top: 14px;
	}
	.all-rules > summary {
		cursor: pointer;
		font: 300 1.3rem/1.3 var(--serif);
	}
	.all-rules > summary:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
	}
	.conventions {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
		gap: 0;
		margin: 16px 0;
		border: 1px solid var(--rule);
		background: var(--surface);
	}
	.conv {
		padding: 12px 14px;
		border-right: 1px solid var(--border);
		border-bottom: 1px solid var(--border);
		font-size: 0.86rem;
	}
	.conv h4 {
		margin: 0 0 4px;
		font: 600 0.88rem var(--sans);
	}
	.conv p {
		margin: 0 0 4px;
	}
	@media (max-width: 1099px) {
		.layout {
			grid-template-columns: minmax(0, 1fr);
		}
	}
	@media print {
		.side,
		.all-rules {
			display: none;
		}
		.layout {
			display: block;
		}
	}
</style>
