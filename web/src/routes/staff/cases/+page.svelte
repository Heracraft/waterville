<script lang="ts">
	// Case list: search, status and type filters, and a form for a new case.
	import { goto, replaceState } from '$app/navigation';
	import { page } from '$app/state';
	import { untrack } from 'svelte';
	import CaseForm from '$lib/components/staff/CaseForm.svelte';
	import CaseBadge from '$lib/components/staff/CaseBadge.svelte';
	import {
		STATUSES,
		TAGS,
		cases,
		caseHeading,
		dueLabel,
		daysUntil,
		fmtDay,
		fmtWhen,
		tagLabel,
		type Case,
		type CaseFields
	} from '$lib/components/staff/CaseData';

	const params = untrack(() => page.url.searchParams);
	let q = $state(params.get('q') || '');
	let status = $state(params.get('status') || 'active');
	let tag = $state(params.get('tag') || '');
	let creating = $state(params.get('new') === '1');

	let list = $state<Case[]>([]);
	let total = $state(0);
	let loading = $state(true);
	let error = $state('');
	let seq = 0;

	const FILTERS = [
		{ value: 'active', label: 'Open and monitoring' },
		...STATUSES,
		{ value: 'all', label: 'All' }
	];

	async function load() {
		const mine = ++seq;
		error = '';
		try {
			// "active" is a page-side filter: open plus monitoring.
			const res = await cases.list({ q: q.trim(), status: status === 'active' ? '' : status, tag });
			if (mine !== seq) return;
			list = status === 'active' ? res.cases.filter((c) => c.status !== 'closed') : res.cases;
			total = res.total;
		} catch (e) {
			if (mine !== seq) return;
			error = e instanceof Error ? e.message : String(e);
		} finally {
			if (mine === seq) loading = false;
		}
	}

	// Reload on filter changes; typing waits a moment.
	let timer: ReturnType<typeof setTimeout> | undefined;
	$effect(() => {
		const key = [q, status, tag];
		void key;
		clearTimeout(timer);
		timer = setTimeout(
			() => {
				load();
				syncUrl();
			},
			untrack(() => loading) ? 0 : 180
		);
		return () => clearTimeout(timer);
	});

	function syncUrl() {
		const u = new URL(page.url);
		for (const [k, v] of [
			['q', q.trim()],
			['status', status === 'active' ? '' : status],
			['tag', tag]
		])
			if (v) u.searchParams.set(k, v);
			else u.searchParams.delete(k);
		u.searchParams.delete('new');
		if (u.search !== page.url.search) {
			try {
				replaceState(u, {});
			} catch {
				/* router not ready yet */
			}
		}
	}

	function clearFilters() {
		q = '';
		status = 'all';
		tag = '';
	}

	async function create(fields: CaseFields) {
		const c = await cases.create(fields);
		creating = false;
		await goto(`/staff/cases/${encodeURIComponent(c.id)}`);
	}

	const filtered = $derived(Boolean(q.trim() || tag || (status !== 'all' && status !== 'active')));
</script>

<svelte:head>
	<title>Cases | Staff | Waterville Codes RAG</title>
</svelte:head>

<main class="wrap staff-main cases-page">
	<div class="page-head head-row">
		<div>
			<h2 class="page-title">Cases</h2>
			<p class="page-lede">One notebook per property: saved answers with their sources, notes, deadlines and drafts.</p>
		</div>
		{#if !creating}
			<button type="button" class="btn" onclick={() => (creating = true)}>New case</button>
		{/if}
	</div>

	{#if creating}
		<CaseForm heading="New case" submitLabel="Create case" busyLabel="Creating" onsubmit={create} oncancel={() => (creating = false)} />
	{/if}

	<form class="filters" role="search" onsubmit={(e) => e.preventDefault()}>
		<label class="field search">
			<span>Search</span>
			<input type="search" name="q" bind:value={q} placeholder="Address, map/lot, owner or case number" autocomplete="off" />
		</label>
		<label class="field">
			<span>Status</span>
			<select name="status" bind:value={status}>
				{#each FILTERS as f (f.value)}<option value={f.value}>{f.label}</option>{/each}
			</select>
		</label>
		<label class="field">
			<span>Type</span>
			<select name="tag" bind:value={tag}>
				<option value="">Any type</option>
				{#each TAGS as t (t.value)}<option value={t.value}>{t.label}</option>{/each}
			</select>
		</label>
	</form>

	{#if error}
		<p class="notice error-text" role="alert">Could not load cases: {error}</p>
		<button type="button" class="btn secondary" onclick={load}>Try again</button>
	{:else if loading}
		<div class="loading" role="status"><span class="loading-label">Loading cases</span><span class="loading-bar" aria-hidden="true"></span></div>
	{:else if total === 0}
		<div class="sheet empty">
			<h3>No cases yet</h3>
			<p class="muted">Start one with <strong>New case</strong>. From the research desk you can then save answers into it.</p>
		</div>
	{:else}
		<p class="count" role="status">
			{list.length === 1 ? '1 case' : `${list.length} cases`}{list.length !== total ? ` of ${total}` : ''}
			{#if filtered}<button type="button" class="linkish" onclick={clearFilters}>Clear filters</button>{/if}
		</p>
		{#if list.length === 0}
			<div class="sheet empty">
				<h3>No case matches</h3>
				<p class="muted">Try fewer words, another status, or <button type="button" class="linkish" onclick={clearFilters}>clear the filters</button>.</p>
			</div>
		{:else}
			<ol class="case-list">
				<li class="row head-cells" aria-hidden="true">
					<span>Case</span><span>Type</span><span>Status</span><span>Next deadline</span><span>Last change</span>
				</li>
				{#each list as c (c.id)}
					<li class="row">
						<div class="main-cell">
							<a class="case-link" href="/staff/cases/{encodeURIComponent(c.id)}">{caseHeading(c)}</a>
							<span class="sub">
								{#if c.title}{c.address}<span class="sep">,</span>{/if}
								{#if c.map_lot}map/lot {c.map_lot}<span class="sep">,</span>{/if}
								{#if c.owner}{c.owner}<span class="sep">,</span>{/if}
								<span class="cid">{c.id}</span>
							</span>
						</div>
						<div class="tags-cell">
							{#each c.tags as t (t)}<span class="tag-pill">{tagLabel(t)}</span>{/each}
						</div>
						<div class="status-cell"><CaseBadge status={c.status} /></div>
						<div class="due-cell">
							{#if c.next_deadline}
								<span class:soon={daysUntil(c.next_deadline.date) <= 7}>{fmtDay(c.next_deadline.date)}</span>
								<span class="sub">{dueLabel(c.next_deadline.date)}: {c.next_deadline.label}</span>
							{:else}
								<span class="sub">None</span>
							{/if}
						</div>
						<div class="when-cell">
							<span>{fmtWhen(c.updated_at)}</span>
							<span class="sub">{c.updated_by}, {c.item_count ?? 0} {(c.item_count ?? 0) === 1 ? 'item' : 'items'}</span>
						</div>
					</li>
				{/each}
			</ol>
		{/if}
	{/if}
</main>

<style>
	.head-row {
		display: flex;
		flex-wrap: wrap;
		align-items: flex-end;
		justify-content: space-between;
		gap: 16px;
	}
	.filters {
		display: grid;
		grid-template-columns: minmax(0, 2fr) minmax(0, 1fr) minmax(0, 1fr);
		gap: 0 12px;
		padding: 14px 16px 0;
		margin-bottom: 18px;
		background: var(--bg);
		border: 1px solid var(--rule);
	}
	.filters .field {
		margin-bottom: 14px;
	}
	.count {
		display: flex;
		gap: 12px;
		align-items: baseline;
		margin: 0 0 10px;
		font: 600 0.85rem var(--sans);
		color: var(--muted);
	}
	.linkish {
		cursor: pointer;
		border: 0;
		padding: 0;
		background: none;
		color: var(--accent);
		font: inherit;
		text-decoration: underline;
		text-underline-offset: 2px;
	}
	.empty h3 {
		font: 300 1.35rem/1.25 var(--serif) !important;
	}
	.case-list {
		list-style: none;
		margin: 0;
		padding: 0;
		border: 1px solid var(--rule);
		background: var(--surface);
	}
	.row {
		display: grid;
		grid-template-columns: minmax(0, 2.4fr) minmax(0, 1.3fr) 8.5em minmax(0, 1.3fr) minmax(0, 1.2fr);
		gap: 12px;
		padding: 12px 16px;
		border-bottom: 1px solid var(--border);
		font: 0.9rem/1.45 var(--sans);
		align-items: start;
	}
	.row:last-child {
		border-bottom: 0;
	}
	.row:not(.head-cells):hover {
		background: var(--surface-hover);
	}
	.head-cells {
		background: var(--bg);
		border-bottom-color: var(--rule);
		font-weight: 600;
		padding-block: 8px;
	}
	.main-cell,
	.due-cell,
	.when-cell {
		display: grid;
		gap: 2px;
		min-width: 0;
	}
	.case-link {
		color: var(--text);
		font: 400 1.12rem/1.3 var(--serif);
		text-decoration-color: var(--accent);
		text-underline-offset: 3px;
		overflow-wrap: anywhere;
	}
	.sub {
		color: var(--muted);
		font-size: 0.82rem;
		overflow-wrap: anywhere;
	}
	.sep {
		margin-right: 4px;
	}
	.cid {
		font-variant-numeric: tabular-nums;
	}
	.tags-cell {
		display: flex;
		flex-wrap: wrap;
		gap: 4px;
	}
	.soon {
		color: var(--accent);
		font-weight: 600;
	}
	@media (max-width: 860px) {
		.head-cells {
			display: none;
		}
		.row {
			grid-template-columns: minmax(0, 1fr) auto;
			gap: 8px 12px;
		}
		.main-cell {
			grid-column: 1;
		}
		.status-cell {
			grid-column: 2;
			grid-row: 1;
		}
		.tags-cell,
		.due-cell,
		.when-cell {
			grid-column: 1 / -1;
		}
		.due-cell,
		.when-cell {
			display: flex;
			flex-wrap: wrap;
			gap: 0 8px;
			align-items: baseline;
		}
		.due-cell:has(.sub:only-child) {
			display: none;
		}
	}
	@media (max-width: 640px) {
		.filters {
			grid-template-columns: 1fr 1fr;
			padding: 12px 12px 0;
		}
		.filters .search {
			grid-column: 1 / -1;
		}
		.row {
			padding: 12px;
		}
	}
</style>
