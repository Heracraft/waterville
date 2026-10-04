<script lang="ts">
	// Project gate checklist (B8): enter the project's facts, get the approvals
	// it needs in the order they must clear, each with its citation and text.
	import { page } from '$app/state';
	import { untrack } from 'svelte';
	import Stamp from '$lib/components/Stamp.svelte';
	import CasePicker from '$lib/components/staff/CasePicker.svelte';
	import { cases } from '$lib/components/staff/CaseData';
	import GateCard from '$lib/components/staff/GateCard.svelte';
	import GateForm from '$lib/components/staff/GateForm.svelte';
	import {
		checklistText,
		emptyInput,
		gatesApi,
		groupByPhase,
		loadSaved,
		saveInput,
		type GateInput,
		type GateOptions,
		type GateResult
	} from '$lib/components/staff/GateData';

	let input = $state<GateInput>(loadSaved() ?? emptyInput());
	let options = $state<GateOptions | null>(null);
	let result = $state<GateResult | null>(null);
	let busy = $state(false);
	let error = $state('');
	let caseId = $state(untrack(() => page.url.searchParams.get('case')) || '');
	let flash = $state('');

	const phases = $derived(result ? groupByPhase(result) : []);
	const label = (list: { value: string; label: string }[] | undefined, v: string) =>
		list?.find((o) => o.value === v)?.label ?? v;
	const labels = $derived({
		project: label(options?.project_types, input.project_type),
		use: label(options?.uses, input.use),
		district: input.district === 'unknown' ? '' : label(options?.districts, input.district)
	});

	$effect(() => {
		gatesApi
			.options()
			.then((o) => (options = o))
			.catch((e) => (error = e instanceof Error ? e.message : String(e)));
	});

	async function check() {
		busy = true;
		error = '';
		flash = '';
		try {
			result = await gatesApi.check($state.snapshot(input));
			saveInput($state.snapshot(input));
		} catch (e) {
			error = e instanceof Error ? e.message : String(e);
		} finally {
			busy = false;
		}
	}

	function reset() {
		input = emptyInput();
		result = null;
		flash = '';
	}

	async function copy() {
		if (!result) return;
		try {
			await navigator.clipboard.writeText(checklistText(result, labels));
			flash = 'Checklist copied.';
		} catch {
			flash = 'Could not copy; your browser blocked the clipboard.';
		}
	}

	async function saveToCase() {
		if (!result || !caseId) return;
		try {
			await cases.addItem(caseId, { kind: 'note', text: checklistText(result, labels).slice(0, 20000) });
			flash = `Checklist saved to case ${caseId}.`;
		} catch (e) {
			flash = `Could not save: ${e instanceof Error ? e.message : String(e)}`;
		}
	}
</script>

<svelte:head>
	<title>Project gates | Staff | Waterville Codes RAG</title>
</svelte:head>

<main class="wrap staff-main">
	<div class="page-head">
		<h2 class="page-title">Project gates</h2>
		<p class="page-lede">
			Enter what you know about a project to see every approval it needs, in the order they must clear, with the
			controlling section for each.
		</p>
	</div>

	<div class="layout">
		<aside class="side">
			<GateForm bind:input {options} {busy} onsubmit={check} onreset={reset} />
		</aside>

		<section class="results" aria-live="polite" aria-busy={busy}>
			{#if error}<p class="notice error-text" role="alert">{error}</p>{/if}
			{#if result}
				<div class="sum">
					<div>
						<h3>{result.gates.length} {result.gates.length === 1 ? 'approval' : 'approvals'}</h3>
						<p class="muted">
							{[labels.project, labels.use, labels.district].filter(Boolean).join(', ')}.{result.unverified
								? ` ${result.unverified} unverified for Waterville.`
								: ''}
						</p>
					</div>
					<div class="tools no-print">
						<button type="button" class="btn secondary small" onclick={copy}>Copy as text</button>
						<button type="button" class="btn secondary small" onclick={() => window.print()}>Print</button>
					</div>
				</div>
				<div class="save no-print">
					<CasePicker bind:value={caseId} label="Save the checklist to a case" none="No case" />
					<button type="button" class="btn secondary small" disabled={!caseId} onclick={saveToCase}>Save as a case note</button>
				</div>
				{#if flash}
					<p class="flash" role="status">
						{flash}{#if flash.startsWith('Checklist saved') && caseId}{' '}<a href="/staff/cases/{caseId}">Open the case</a>{/if}
					</p>
				{/if}

				{#each result.district_notes as n (n.district)}
					<p class="notice">
						{n.text}{#if n.citation}
							({#if n.url}<a href={n.url} target="_blank" rel="noopener noreferrer">{n.citation}</a>{:else}{n.citation}{/if}){/if}
					</p>
				{/each}

				{#each phases as p (p.phase.n)}
					<section class="phase" aria-labelledby="ph-{p.phase.n}">
						<header>
							<h3 id="ph-{p.phase.n}"><span class="pn">{p.phase.n}</span> {p.phase.label}</h3>
							<p class="muted">{p.phase.summary}</p>
						</header>
						<ol class="gates">
							{#each p.gates as g (g.id)}<li><GateCard gate={g} /></li>{/each}
						</ol>
					</section>
				{/each}

				{#if result.exempt.length}
					<section class="phase">
						<header><h3>Not required</h3></header>
						<ul class="exempt">
							{#each result.exempt as e (e.id)}
								<li><strong>{e.title}.</strong> {e.exempt_reason}</li>
							{/each}
						</ul>
					</section>
				{/if}

				<section class="assume">
					<h3>What this rests on</h3>
					<ul>
						{#each result.assumptions as a, i (i)}<li>{a}</li>{/each}
						<li>Rules and quotes checked against primary text on {result.checked}.</li>
					</ul>
				</section>
				<Stamp />
			{:else if !busy}
				<div class="empty sheet">
					<p>Fill in the project facts and choose Check gates.</p>
				</div>
			{/if}
		</section>
	</div>
</main>

<style>
	.layout {
		display: grid;
		grid-template-columns: 360px minmax(0, 1fr);
		gap: 32px;
		align-items: start;
	}
	.sum {
		display: flex;
		flex-wrap: wrap;
		justify-content: space-between;
		align-items: flex-end;
		gap: 12px 20px;
		padding-bottom: 12px;
		margin-bottom: 14px;
		border-bottom: 1px solid var(--rule);
	}
	.sum h3 {
		margin: 0;
		font: 300 1.6rem/1.2 var(--serif);
	}
	.sum p {
		margin: 4px 0 0;
	}
	.tools {
		display: flex;
		gap: 8px;
	}
	.save {
		display: flex;
		flex-wrap: wrap;
		align-items: flex-end;
		gap: 10px 12px;
		margin-bottom: 14px;
	}
	.save :global(.case-picker) {
		margin: 0;
		flex: 1 1 260px;
	}
	.save .btn {
		margin-bottom: 1px;
	}
	.flash {
		margin: 0 0 14px;
		padding: 8px 14px;
		border-left: 3px solid var(--accent);
		background: var(--surface);
		font: 600 0.88rem var(--sans);
	}
	.flash a,
	.notice a {
		margin-left: 8px;
		color: var(--text);
		text-decoration-color: var(--accent);
	}
	.phase {
		margin: 0 0 24px;
	}
	.phase header {
		margin-bottom: 10px;
	}
	.phase h3 {
		margin: 0;
		font: 300 1.3rem/1.25 var(--serif);
	}
	.phase header p {
		margin: 2px 0 0;
		font-size: 0.88rem;
	}
	.pn {
		display: inline-block;
		min-width: 1.6em;
		color: var(--accent);
	}
	.gates {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		gap: 10px;
	}
	.exempt {
		margin: 0;
		padding: 12px 16px 12px 32px;
		background: var(--surface);
		border: 1px solid var(--rule);
		font-size: 0.9rem;
	}
	.assume {
		padding-top: 12px;
		border-top: 1px solid var(--rule);
	}
	.assume h3 {
		margin: 0 0 6px;
		font: 600 0.78rem var(--sans);
		text-transform: uppercase;
		letter-spacing: 0.06em;
		color: var(--accent);
	}
	.assume ul {
		margin: 0;
		padding-left: 1.2em;
		font-size: 0.88rem;
		color: var(--muted);
	}
	.empty p {
		margin: 0 0 6px;
	}
	@media (max-width: 1099px) {
		.layout {
			grid-template-columns: minmax(0, 1fr);
		}
	}
	@media print {
		.side {
			display: none;
		}
		.layout {
			display: block;
		}
	}
</style>
