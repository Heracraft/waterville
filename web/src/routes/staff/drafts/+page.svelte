<script lang="ts">
	// Office drafts: every saved letter, notice and Rule 80K packet, newest
	// change first, plus the template list to start a new one.
	import { page } from '$app/state';
	import CasePicker from '$lib/components/staff/CasePicker.svelte';
	import DraftBanner from '$lib/components/staff/DraftBanner.svelte';
	import DraftTemplatePicker from '$lib/components/staff/DraftTemplatePicker.svelte';
	import { drafts, fmtWhen, type DraftSummary, type TemplateSummary } from '$lib/components/staff/DraftData';

	let caseId = $state(page.url.searchParams.get('case') ?? '');
	let q = $state('');
	let list = $state<DraftSummary[] | null>(null);
	let templates = $state<TemplateSummary[]>([]);
	let error = $state('');

	$effect(() => {
		drafts
			.templates()
			.then((r) => (templates = r.templates))
			.catch((e) => (error = e instanceof Error ? e.message : String(e)));
	});

	let timer: ReturnType<typeof setTimeout> | undefined;
	$effect(() => {
		const params = { case_id: caseId, q: q.trim() };
		clearTimeout(timer);
		timer = setTimeout(() => {
			drafts
				.list(params)
				.then((r) => {
					list = r.drafts;
					error = '';
				})
				.catch((e) => (error = e instanceof Error ? e.message : String(e)));
		}, 200);
	});
</script>

<svelte:head>
	<title>Drafts | Staff | Waterville Codes RAG</title>
</svelte:head>

<main class="wrap staff-main drafts-page">
	<div class="page-head">
		<span class="eyebrow">Letters, notices and court packets</span>
		<h2 class="page-title">Drafts</h2>
		<p class="page-lede">
			Notices of violation, stop-work orders, abutter and hearing notices, decision letters and Rule 80K packets, drafted from
			Waterville templates. Nothing is sent from here. The Code Enforcement Officer reviews, signs and sends.
		</p>
	</div>

	<DraftBanner />

	<section class="start" aria-labelledby="start-h">
		<h3 id="start-h" class="sec-h">Start a draft{caseId ? ` for case ${caseId}` : ''}</h3>
		{#if templates.length}
			<DraftTemplatePicker {templates} {caseId} />
		{:else if !error}
			<div class="loading" role="status"><span class="loading-label">Loading templates</span><span class="loading-bar" aria-hidden="true"></span></div>
		{/if}
	</section>

	<section class="saved" aria-labelledby="saved-h">
		<div class="saved-head">
			<h3 id="saved-h" class="sec-h">Saved drafts</h3>
			<div class="filters">
				<label class="field" for="draft-q">
					<span>Search</span>
					<input id="draft-q" type="search" bind:value={q} placeholder="Title, template or case" />
				</label>
				<CasePicker bind:value={caseId} label="Case" none="All cases" includeClosed />
			</div>
		</div>

		{#if error}<p class="notice error-text" role="alert">Could not load drafts: {error}</p>{/if}

		{#if list === null}
			{#if !error}<div class="loading" role="status"><span class="loading-label">Loading drafts</span><span class="loading-bar" aria-hidden="true"></span></div>{/if}
		{:else if list.length === 0}
			<div class="sheet"><p class="muted">{q || caseId ? 'No drafts match.' : 'No drafts yet. Pick a template above to start one.'}</p></div>
		{:else}
			<div class="table-scroll">
				<table class="ledger">
					<thead>
						<tr><th>Draft</th><th>Template</th><th>Case</th><th>Review</th><th>Last change</th></tr>
					</thead>
					<tbody>
						{#each list as d (d.id)}
							<tr>
								<td><a href="/staff/drafts/{encodeURIComponent(d.id)}">{d.title}</a></td>
								<td>{d.template_title}</td>
								<td>{#if d.case_id}<a href="/staff/cases/{encodeURIComponent(d.case_id)}">{d.case_id}</a>{:else}<span class="muted">None</span>{/if}</td>
								<td class="flags">
									{#if d.status === 'reviewed'}<span class="tag-pill">Citations checked</span>{/if}
									{#if d.missing_count}<span class="flag bad">{d.missing_count} missing</span>{/if}
									{#if d.verify_count}<span class="flag">{d.verify_count} to verify</span>{/if}
									{#if !d.missing_count && !d.verify_count && d.status !== 'reviewed'}<span class="muted">Ready for review</span>{/if}
								</td>
								<td class="when">{fmtWhen(d.updated_at)}<br /><span class="muted">{d.updated_by}</span></td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
	</section>
</main>

<style>
	.sec-h {
		margin: 0 0 12px;
		font: 600 1rem var(--sans);
	}
	.start {
		margin: 8px 0 36px;
	}
	.saved-head {
		display: flex;
		flex-wrap: wrap;
		justify-content: space-between;
		align-items: end;
		gap: 0 20px;
	}
	.filters {
		display: flex;
		flex-wrap: wrap;
		gap: 0 14px;
	}
	.filters .field {
		min-width: 220px;
	}
	.flags {
		display: flex;
		flex-wrap: wrap;
		gap: 6px;
	}
	.flag {
		font: 600 0.78rem/1.6 var(--sans);
		padding: 0 7px;
		border: 1px solid var(--border);
	}
	.flag.bad {
		border-color: var(--error);
		color: var(--error);
	}
	.when {
		white-space: nowrap;
		font-size: 0.85rem;
	}
	td a {
		color: var(--text);
		text-decoration-color: var(--accent);
		text-underline-offset: 2px;
	}
	@media (max-width: 640px) {
		.filters,
		.filters .field {
			width: 100%;
			min-width: 0;
		}
		.filters :global(.case-picker) {
			width: 100%;
		}
	}
</style>
