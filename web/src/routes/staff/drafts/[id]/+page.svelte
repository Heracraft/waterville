<script lang="ts">
	// One draft. /staff/drafts/new?template=nov-1&case=2026-3f9a1c starts a new
	// draft (pick a template first when none is given); any other id opens a
	// saved draft. Saving a new draft with a case adds it to that case's
	// timeline (the server does it, app/routers/drafts.py).
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { ApiError } from '$lib/api';
	import DraftEditor from '$lib/components/staff/DraftEditor.svelte';
	import DraftTemplatePicker from '$lib/components/staff/DraftTemplatePicker.svelte';
	import { drafts, type Draft, type TemplateFull, type TemplateSummary } from '$lib/components/staff/DraftData';

	const id = $derived(page.params.id ?? '');
	const isNew = $derived(id === 'new');
	const tid = $derived(page.url.searchParams.get('template') ?? '');
	const caseParam = $derived(page.url.searchParams.get('case') ?? '');

	let template = $state<TemplateFull | null>(null);
	let draft = $state<Draft | null>(null);
	let all = $state<TemplateSummary[]>([]);
	let missing = $state('');
	let error = $state('');
	let loading = $state(true);

	async function load(draftId: string, templateId: string, caseId: string) {
		loading = true;
		error = '';
		missing = '';
		template = null;
		draft = null;
		try {
			if (draftId === 'new') {
				if (templateId) {
					template = await drafts.template(templateId, caseId);
				} else {
					all = (await drafts.templates()).templates;
				}
			} else {
				draft = await drafts.get(draftId);
				template = await drafts.template(draft.template);
			}
		} catch (e) {
			if (e instanceof ApiError && e.status === 404) {
				missing = draftId === 'new' ? (caseId && templateId ? 'case or template' : 'template') : 'draft';
			} else error = e instanceof Error ? e.message : String(e);
		} finally {
			loading = false;
		}
	}

	$effect(() => {
		load(id, tid, caseParam);
	});

	const heading = $derived(
		draft ? draft.title : template ? `New draft: ${template.title}` : isNew ? 'New draft' : 'Draft'
	);
</script>

<svelte:head>
	<title>{heading} | Staff | Waterville Codes RAG</title>
</svelte:head>

<main class="wrap staff-main draft-page">
	<p class="back no-print">
		{#if (draft?.case_id || caseParam)}
			<a href="/staff/cases/{encodeURIComponent(draft?.case_id || caseParam)}">Case {draft?.case_id || caseParam}</a>
			<span class="sep" aria-hidden="true">/</span>
		{/if}
		<a href="/staff/drafts{caseParam ? `?case=${encodeURIComponent(caseParam)}` : ''}">All drafts</a>
	</p>

	{#if loading}
		<div class="loading" role="status"><span class="loading-label">Loading the draft</span><span class="loading-bar" aria-hidden="true"></span></div>
	{:else if missing}
		<div class="sheet accent">
			<h2 class="page-title">No such {missing}</h2>
			<p class="muted">
				{missing === 'draft' ? `Draft ${id} does not exist. Someone may have deleted it.` : 'That link names a template or case that does not exist.'}
			</p>
			<a class="btn secondary" href="/staff/drafts">Back to drafts</a>
		</div>
	{:else if error}
		<p class="notice error-text" role="alert">Could not load: {error}</p>
		<button type="button" class="btn secondary" onclick={() => load(id, tid, caseParam)}>Try again</button>
	{:else if isNew && !template}
		<div class="page-head">
			<span class="eyebrow">New draft{caseParam ? ` for case ${caseParam}` : ''}</span>
			<h2 class="page-title">Pick a template</h2>
		</div>
		<DraftTemplatePicker templates={all} caseId={caseParam} />
	{:else if template}
		<div class="page-head no-print">
			<span class="eyebrow">{template.group}{draft ? `, draft ${draft.id}` : ''}</span>
			<h2 class="page-title">{heading}</h2>
			<p class="page-lede">{template.description}</p>
		</div>
		{#key draft?.id ?? `new-${template.id}-${caseParam}`}
			<DraftEditor
				{template}
				{draft}
				caseId={caseParam}
				oncreated={(d) => goto(`/staff/drafts/${encodeURIComponent(d.id)}`, { replaceState: true })}
				ondeleted={() => goto(draft?.case_id ? `/staff/cases/${encodeURIComponent(draft.case_id)}` : '/staff/drafts', { replaceState: true })}
			/>
		{/key}
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
	.back a:first-child::before {
		content: '\2190';
		margin-right: 6px;
		color: var(--accent);
	}
	.sep {
		margin: 0 8px;
		color: var(--muted);
	}
	@media print {
		.draft-page {
			padding: 0;
		}
	}
</style>
