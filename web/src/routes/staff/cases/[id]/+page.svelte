<script lang="ts">
	// One case notebook: details, timeline (saved answers, notes, deadlines,
	// drafts), edit, delete, Markdown export and a print view.
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { ApiError } from '$lib/api';
	import CaseBadge from '$lib/components/staff/CaseBadge.svelte';
	import CaseComposer from '$lib/components/staff/CaseComposer.svelte';
	import CaseConfirm from '$lib/components/staff/CaseConfirm.svelte';
	import CaseForm from '$lib/components/staff/CaseForm.svelte';
	import CaseItemView from '$lib/components/staff/CaseItem.svelte';
	import {
		KIND_LABELS,
		cases,
		caseHeading,
		deadlines,
		dueLabel,
		daysUntil,
		fmtDay,
		fmtWhen,
		tagLabel,
		type CaseFields,
		type CaseItem,
		type CaseWithItems
	} from '$lib/components/staff/CaseData';

	const id = $derived(page.params.id ?? '');

	let data = $state<CaseWithItems | null>(null);
	let missing = $state(false);
	let error = $state('');
	let editing = $state(false);
	let newestFirst = $state(true);
	let kind = $state<'all' | CaseItem['kind']>('all');
	let pendingItem = $state<CaseItem | null>(null);
	let confirmCase = $state<CaseConfirm>();
	let confirmItem = $state<CaseConfirm>();
	let flash = $state('');

	async function load(caseId: string) {
		error = '';
		missing = false;
		try {
			data = await cases.get(caseId);
		} catch (e) {
			data = null;
			if (e instanceof ApiError && e.status === 404) missing = true;
			else error = e instanceof Error ? e.message : String(e);
		}
	}

	$effect(() => {
		const caseId = id;
		editing = false;
		load(caseId);
	});

	const items = $derived(data?.items ?? []);
	const shown = $derived.by(() => {
		const list = kind === 'all' ? items : items.filter((i) => i.kind === kind);
		return newestFirst ? [...list].reverse() : list;
	});
	const clocks = $derived(deadlines(items));
	const upcoming = $derived(clocks.filter((d) => daysUntil(d.date) >= 0));
	const drafts = $derived(items.filter((i) => i.kind === 'draft'));
	const counts = $derived(
		items.reduce<Record<string, number>>((acc, i) => ((acc[i.kind] = (acc[i.kind] ?? 0) + 1), acc), {})
	);

	async function save(fields: CaseFields) {
		if (!data) return;
		const updated = await cases.update(data.id, fields);
		data = { ...data, ...updated };
		editing = false;
		say('Case saved.');
	}

	function added(item: CaseItem) {
		if (!data) return;
		data = { ...data, items: [...data.items, item], updated_at: new Date().toISOString() };
		say(`${KIND_LABELS[item.kind]} added.`);
	}

	function askDeleteItem(item: CaseItem) {
		pendingItem = item;
		confirmItem?.open();
	}

	async function deleteItem() {
		if (!data || !pendingItem) return;
		const gone = pendingItem;
		await cases.removeItem(data.id, gone.id);
		data = { ...data, items: data.items.filter((i) => i.id !== gone.id) };
		pendingItem = null;
		say(`${KIND_LABELS[gone.kind]} deleted.`);
	}

	async function deleteCase() {
		if (!data) return;
		await cases.remove(data.id);
		await goto('/staff/cases', { replaceState: true });
	}

	let flashTimer: ReturnType<typeof setTimeout> | undefined;
	function say(msg: string) {
		flash = msg;
		clearTimeout(flashTimer);
		flashTimer = setTimeout(() => (flash = ''), 4000);
	}

	const FILTERS: { value: 'all' | CaseItem['kind']; label: string }[] = [
		{ value: 'all', label: 'Everything' },
		{ value: 'answer', label: 'Answers' },
		{ value: 'note', label: 'Notes' },
		{ value: 'deadline', label: 'Deadlines' },
		{ value: 'draft', label: 'Drafts' }
	];
</script>

<svelte:head>
	<title>{data ? `${caseHeading(data)} | Case ${data.id}` : 'Case'} | Staff | Waterville Codes RAG</title>
</svelte:head>

<main class="wrap staff-main case-page">
	<p class="back no-print"><a href="/staff/cases">All cases</a></p>

	{#if missing}
		<div class="sheet accent">
			<h2 class="page-title">No such case</h2>
			<p class="muted">Case {id} does not exist. Someone may have deleted it.</p>
			<a class="btn secondary" href="/staff/cases">Back to cases</a>
		</div>
	{:else if error}
		<p class="notice error-text" role="alert">Could not load the case: {error}</p>
		<button type="button" class="btn secondary" onclick={() => load(id)}>Try again</button>
	{:else if !data}
		<div class="loading" role="status"><span class="loading-label">Loading the case</span><span class="loading-bar" aria-hidden="true"></span></div>
	{:else}
		{#if editing}
			<CaseForm
				heading="Edit case {data.id}"
				initial={{
					address: data.address,
					map_lot: data.map_lot,
					owner: data.owner,
					title: data.title,
					summary: data.summary,
					tags: data.tags,
					status: data.status
				}}
				submitLabel="Save changes"
				onsubmit={save}
				oncancel={() => (editing = false)}
			/>
		{:else}
			<header class="case-head">
				<div class="title-row">
					<div>
						<span class="eyebrow">Case {data.id}</span>
						<h2 class="page-title">{caseHeading(data)}</h2>
					</div>
					<CaseBadge status={data.status} />
				</div>
				{#if data.tags.length}
					<div class="tags">{#each data.tags as t (t)}<span class="tag-pill">{tagLabel(t)}</span>{/each}</div>
				{/if}
				<dl class="facts">
					<div><dt>Address</dt><dd>{data.address}</dd></div>
					<div><dt>Map/lot</dt><dd>{data.map_lot || 'Not recorded'}</dd></div>
					<div><dt>Owner</dt><dd>{data.owner || 'Not recorded'}</dd></div>
					<div><dt>Opened</dt><dd>{fmtWhen(data.created_at)}, {data.created_by}</dd></div>
					<div><dt>Last change</dt><dd>{fmtWhen(data.updated_at)}, {data.updated_by}</dd></div>
				</dl>
				{#if data.summary}<p class="summary">{data.summary}</p>{/if}
				<div class="btn-row actions no-print">
					<button type="button" class="btn secondary small" onclick={() => (editing = true)}>Edit</button>
					<a class="btn secondary small" href={cases.exportUrl(data.id)} download="case-{data.id}.md">Export Markdown</a>
					<button type="button" class="btn secondary small" onclick={() => window.print()}>Print</button>
					<button type="button" class="btn secondary small danger-outline" onclick={() => confirmCase?.open()}>Delete case</button>
				</div>
			</header>
		{/if}

		{#if flash}<p class="flash no-print" role="status">{flash}</p>{/if}

		<div class="layout">
			<section class="timeline-col" aria-labelledby="tl-h">
				<CaseComposer caseId={data.id} onadded={added} />

				<div class="tl-bar">
					<h3 id="tl-h">Timeline <span class="muted">({items.length})</span></h3>
					<div class="tl-tools no-print">
						<label class="sr-only" for="kind-filter">Show</label>
						<select id="kind-filter" class="input compact" bind:value={kind}>
							{#each FILTERS as f (f.value)}
								<option value={f.value}>{f.label}{f.value !== 'all' && counts[f.value] ? ` (${counts[f.value]})` : ''}</option>
							{/each}
						</select>
						<button type="button" class="btn secondary small" onclick={() => (newestFirst = !newestFirst)} aria-pressed={!newestFirst}>
							{newestFirst ? 'Newest first' : 'Oldest first'}
						</button>
					</div>
				</div>

				{#if items.length === 0}
					<div class="sheet empty">
						<p>Nothing saved here yet.</p>
						<p class="muted">
							Ask a question on the <a href="/staff?case={encodeURIComponent(data.id)}">research desk</a> and save the answer to this case,
							add a clock from the <a href="/staff/deadlines?case={encodeURIComponent(data.id)}">deadline calculator</a>, or write a note above.
						</p>
					</div>
				{:else if shown.length === 0}
					<p class="muted">No {FILTERS.find((f) => f.value === kind)?.label.toLowerCase()} on this case.</p>
				{:else}
					<ol class="timeline">
						{#each shown as item (item.id)}
							<CaseItemView {item} ondelete={askDeleteItem} />
						{/each}
					</ol>
				{/if}
			</section>

			<aside class="side" aria-label="Case summary">
				<section class="side-box">
					<h3>Deadlines</h3>
					{#if clocks.length === 0}
						<p class="muted small-text">None yet.</p>
					{:else}
						<ul class="clock-list">
							{#each clocks as d (d.id)}
								{@const n = daysUntil(d.date)}
								<li class:past={n < 0} class:soon={n >= 0 && n <= 7}>
									<a href="#item-{d.id}" onclick={() => ((kind = 'all'), true)}>
										<span class="d">{fmtDay(d.date)}</span>
										<span class="l">{d.label}</span>
										<span class="due">{dueLabel(d.date)}{d.citation ? `, ${d.citation}` : ''}</span>
									</a>
								</li>
							{/each}
						</ul>
						{#if upcoming.length === 0}<p class="muted small-text">Every deadline here has passed.</p>{/if}
					{/if}
					<a class="side-link no-print" href="/staff/deadlines?case={encodeURIComponent(data.id)}">Open the deadline calculator</a>
				</section>
				<section class="side-box">
					<h3>Drafts</h3>
					{#if drafts.length === 0}
						<p class="muted small-text">No drafts linked.</p>
					{:else}
						<ul class="draft-list">
							{#each drafts as d (d.id)}
								{#if d.kind === 'draft'}
									<li><a href="/staff/drafts/{encodeURIComponent(d.draft_id)}">{d.title || d.template || 'Draft'}</a></li>
								{/if}
							{/each}
						</ul>
					{/if}
					<a class="side-link no-print" href="/staff/drafts/new?case={encodeURIComponent(data.id)}">Start a draft for this case</a>
				</section>
				<section class="side-box no-print">
					<h3>Research</h3>
					<a class="side-link" href="/staff?case={encodeURIComponent(data.id)}">Ask on the research desk for this case</a>
					<a class="side-link" href="/staff/gates?case={encodeURIComponent(data.id)}">Check the project gates for this case</a>
				</section>
			</aside>
		</div>

		<p class="print-foot">Printed from the Waterville staff desk.</p>

		<CaseConfirm bind:this={confirmCase} title="Delete case {data.id}?" confirmLabel="Delete case" onconfirm={deleteCase}>
			<p>This deletes <strong>{caseHeading(data)}</strong> and its {items.length} timeline {items.length === 1 ? 'item' : 'items'} for every staff user.</p>
			<p>Export it as Markdown first if you need a record.</p>
		</CaseConfirm>
		<CaseConfirm bind:this={confirmItem} title="Delete this {pendingItem ? KIND_LABELS[pendingItem.kind].toLowerCase() : 'item'}?" onconfirm={deleteItem}>
			<p>It leaves the case timeline for everyone. This cannot be undone.</p>
		</CaseConfirm>
	{/if}
</main>

<style>
	.back {
		margin: 0 0 14px;
		font: 500 0.88rem var(--sans);
	}
	.back a {
		color: var(--muted);
		text-decoration-color: var(--accent);
	}
	.back a::before {
		content: '\2190';
		margin-right: 6px;
		color: var(--accent);
	}
	.case-head {
		margin: 0 0 24px;
		padding-bottom: 18px;
		border-bottom: 1px solid var(--rule);
	}
	.title-row {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		gap: 16px;
	}
	.title-row .page-title {
		overflow-wrap: anywhere;
	}
	.tags {
		display: flex;
		flex-wrap: wrap;
		gap: 6px;
		margin: 12px 0 0;
	}
	.facts {
		display: grid;
		grid-template-columns: repeat(5, minmax(0, 1fr));
		margin: 18px 0 0;
		border: 1px solid var(--rule);
		background: var(--surface);
	}
	.facts div {
		padding: 10px 14px;
		border-right: 1px solid var(--border);
		min-width: 0;
	}
	.facts div:last-child {
		border-right: 0;
	}
	.facts dt {
		font: 600 0.72rem var(--sans);
		text-transform: uppercase;
		letter-spacing: 0.06em;
		color: var(--muted);
		margin-bottom: 2px;
	}
	.facts dd {
		margin: 0;
		font: 0.92rem/1.4 var(--sans);
		overflow-wrap: anywhere;
	}
	.summary {
		margin: 16px 0 0;
		max-width: 46em;
		font: 400 1.05rem/1.6 var(--serif);
		white-space: pre-wrap;
	}
	.actions {
		margin-top: 18px;
	}
	.danger-outline {
		color: var(--error);
		border-color: var(--error);
	}
	.flash {
		margin: -8px 0 18px;
		padding: 8px 14px;
		border-left: 3px solid var(--accent);
		background: var(--surface);
		font: 600 0.88rem var(--sans);
	}
	.layout {
		display: grid;
		grid-template-columns: minmax(0, 1fr) 280px;
		gap: 32px;
		align-items: start;
	}
	.tl-bar {
		display: flex;
		flex-wrap: wrap;
		justify-content: space-between;
		align-items: center;
		gap: 10px;
		margin: 0 0 16px;
		padding-bottom: 10px;
		border-bottom: 1px solid var(--rule);
	}
	.tl-bar h3 {
		margin: 0;
		font: 300 1.4rem/1.2 var(--serif);
	}
	.tl-bar h3 .muted {
		font-size: 1rem;
	}
	.tl-tools {
		display: flex;
		gap: 8px;
		align-items: center;
	}
	.input.compact {
		width: auto;
		padding: 5px 10px;
		font-size: 0.85rem;
	}
	.timeline {
		list-style: none;
		margin: 0;
		padding: 0;
	}
	.empty p {
		margin: 0 0 6px;
	}
	.empty a {
		color: var(--text);
		text-decoration-color: var(--accent);
	}
	.side {
		display: grid;
		gap: 16px;
		position: sticky;
		top: 16px;
	}
	.side-box {
		background: var(--surface);
		border: 1px solid var(--rule);
		padding: 14px 16px;
	}
	.side-box h3 {
		margin: 0 0 10px;
		font: 600 0.78rem var(--sans);
		text-transform: uppercase;
		letter-spacing: 0.06em;
		color: var(--accent);
	}
	.small-text {
		margin: 0 0 10px;
		font-size: 0.88rem;
	}
	.clock-list,
	.draft-list {
		list-style: none;
		margin: 0 0 10px;
		padding: 0;
		border-top: 1px solid var(--border);
	}
	.clock-list li,
	.draft-list li {
		border-bottom: 1px solid var(--border);
	}
	.clock-list a {
		display: grid;
		gap: 1px;
		padding: 8px 0;
		color: var(--text);
		text-decoration: none;
		font: 0.88rem/1.4 var(--sans);
	}
	.clock-list a:hover .l {
		text-decoration: underline;
		text-decoration-color: var(--accent);
	}
	.clock-list .d {
		font: 400 1rem var(--serif);
	}
	.clock-list .due {
		color: var(--muted);
		font-size: 0.8rem;
	}
	.clock-list .soon .due {
		color: var(--accent);
		font-weight: 600;
	}
	.clock-list .past {
		opacity: 0.7;
	}
	.clock-list .past .due {
		color: var(--error);
	}
	.draft-list a {
		display: block;
		padding: 8px 0;
		color: var(--text);
		font: 600 0.9rem var(--sans);
		text-decoration-color: var(--accent);
	}
	.side-link {
		display: block;
		width: fit-content;
		margin-top: 6px;
		color: var(--accent);
		font: 600 0.85rem var(--sans);
		text-underline-offset: 2px;
	}
	.sr-only {
		position: absolute;
		width: 1px;
		height: 1px;
		overflow: hidden;
		clip-path: inset(50%);
		white-space: nowrap;
	}
	.print-foot {
		display: none;
	}
	@media (max-width: 960px) {
		.facts {
			grid-template-columns: repeat(3, minmax(0, 1fr));
		}
		.facts div {
			border-bottom: 1px solid var(--border);
		}
		.layout {
			grid-template-columns: 1fr;
		}
		.side {
			position: static;
			order: -1;
			grid-template-columns: 1fr 1fr;
		}
		.side-box:last-child {
			grid-column: 1 / -1;
		}
	}
	@media (max-width: 640px) {
		.facts {
			grid-template-columns: 1fr 1fr;
		}
		.facts div:first-child {
			grid-column: 1 / -1;
		}
		.side {
			grid-template-columns: 1fr;
		}
	}
	@media print {
		/* Paper is light whatever the screen theme; beats the dark-theme selectors. */
		:global(:root:root:root) {
			--bg: #fff;
			--surface: #fff;
			--surface-hover: #fff;
			--text: #000;
			--muted: #333;
			--rule: #000;
			--border: #999;
			--accent: #ba351a;
			--accent-text: #fff;
			--accent-soft: #f4e4dc;
			--error: #9b1c1c;
		}
		.layout {
			display: block;
		}
		.side {
			position: static;
			display: block;
			margin-top: 24px;
		}
		.side-box {
			margin-bottom: 12px;
			break-inside: avoid;
		}
		.facts {
			grid-template-columns: repeat(3, 1fr);
		}
		.print-foot {
			display: block;
			margin-top: 24px;
			font-size: 0.8rem;
		}
	}
</style>
