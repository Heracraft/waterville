<script lang="ts">
	// Research desk (report items B1 to B4): cite-it answers in staff mode,
	// citation lookup into the source panel, chapter and source-type filters,
	// copy citation, copy answer with citations, save an answer to a case.
	import { tick } from 'svelte';
	import { page } from '$app/state';
	import { chrome } from '$lib/chrome.svelte';
	import { api } from '$lib/api';
	import type { Source } from '$lib/api';
	import Chat from '$lib/components/Chat.svelte';
	import { ChatSession } from '$lib/chat.svelte';
	import CasePicker from '$lib/components/staff/CasePicker.svelte';
	import { cases, caseHeading, type Case } from '$lib/components/staff/CaseData';
	import DeskAnswerTools from '$lib/components/staff/DeskAnswerTools.svelte';
	import DeskCopyButton from '$lib/components/staff/DeskCopyButton.svelte';
	import DeskFilters from '$lib/components/staff/DeskFilters.svelte';
	import DeskLookup from '$lib/components/staff/DeskLookup.svelte';
	import { fullCitation, lookupSource, type DeskSource, type Facets, type LookupResult } from '$lib/components/staff/DeskCite';

	const FILTERS_KEY = 'wv-desk-filters';
	const PANELS_KEY = 'wv-desk-panels';
	type Panel = 'lookup' | 'filters' | 'case';
	const EXAMPLES = [
		'What notice must the owner get before a property maintenance penalty applies?',
		'What is the penalty range for starting work without a building permit?',
		'Can the Code Enforcement Officer approve a fence over 6 feet, and under which section?',
		'Who hears an appeal of a Code Enforcement Officer decision, and how many days are allowed?'
	];
	// Whole-section lookups make sense for these; manuals and model codes are cited by page.
	const LOOKUP_TYPES = new Set(['code', 'new_law', 'state_statute', 'state_rule']);

	const saved = loadFilters();
	let types = $state<string[]>(saved.types);
	let chapters = $state<string[]>(saved.chapters);
	let caseId = $state(page.url.searchParams.get('case') || '');
	let caseList = $state<Case[]>([]);
	let facets = $state<Facets | null>(null);
	let facetsError = $state('');
	let lookupResult = $state<LookupResult | null>(null);
	let chat = $state<ReturnType<typeof Chat>>();
	let deskLookup = $state<ReturnType<typeof DeskLookup>>();
	let pickerEl = $state<HTMLElement>();
	// Lookup, filters and case stay closed until the inspector opens them, so
	// the ask bar is the first thing on the page.
	let panels = $state<Record<Panel, boolean>>(loadPanels());
	const filterCount = $derived(types.length + chapters.length);

	const session = new ChatSession({
		mode: 'staff',
		filters: () => ({ chapters: [...chapters], source_types: [...types] }),
		caseId: () => caseId || undefined
	});

	const edition = $derived(facets?.legislation_through ?? null);
	const caseName = $derived.by(() => {
		const c = caseList.find((x) => x.id === caseId);
		const name = c ? caseHeading(c) : caseId;
		return name.length > 28 ? name.slice(0, 27).trimEnd() + '...' : name;
	});

	function loadPanels(): Record<Panel, boolean> {
		try {
			const v = JSON.parse(localStorage.getItem(PANELS_KEY) || '{}');
			return { lookup: v.lookup === true, filters: v.filters === true, case: v.case === true };
		} catch {
			return { lookup: false, filters: false, case: false };
		}
	}

	function togglePanel(p: Panel) {
		panels[p] = !panels[p];
		try {
			localStorage.setItem(PANELS_KEY, JSON.stringify(panels));
		} catch {
			/* storage blocked: panels reset next visit */
		}
	}

	function loadFilters(): { types: string[]; chapters: string[] } {
		try {
			const v = JSON.parse(localStorage.getItem(FILTERS_KEY) || '{}');
			const list = (x: unknown) => (Array.isArray(x) ? x.filter((y) => typeof y === 'string').slice(0, 50) : []);
			return { types: list(v.types), chapters: list(v.chapters) };
		} catch {
			return { types: [], chapters: [] };
		}
	}

	$effect(() => {
		const v = JSON.stringify({ types, chapters });
		try {
			localStorage.setItem(FILTERS_KEY, v);
		} catch {
			/* storage blocked: filters last for this visit */
		}
	});

	// Facets for the chips; drop saved filters the index no longer has.
	$effect(() => {
		api
			.get<Facets>('/api/facets')
			.then((f) => {
				facets = f;
				const t = new Set(f.source_types.map((x) => x.value));
				const c = new Set(f.chapters.map((x) => x.value));
				types = types.filter((x) => t.has(x));
				chapters = chapters.filter((x) => c.has(x));
			})
			.catch((e) => (facetsError = e instanceof Error ? e.message : String(e)));
	});

	// Case names for the save button.
	$effect(() => {
		if (!caseId || caseList.some((c) => c.id === caseId)) return;
		cases
			.list({ status: 'all' })
			.then((r) => (caseList = r.cases))
			.catch(() => {});
	});

	// New chat sits in the header, where the public page has it.
	$effect(() => {
		chrome.newChat = session.started ? () => session.clear() : null;
		return () => (chrome.newChat = null);
	});

	function openLookup(r: LookupResult, trigger: HTMLElement) {
		lookupResult = r;
		const kicker = r.kind === 'chapter' ? 'Chapter lookup' : r.chunk_count > 1 ? `Lookup, ${r.chunk_count} parts` : 'Lookup';
		chat?.showSource(lookupSource(r), trigger, kicker);
	}

	async function chooseCase() {
		if (!panels.case) togglePanel('case');
		await tick();
		pickerEl?.scrollIntoView({ block: 'center' });
		pickerEl?.querySelector('select')?.focus();
	}

	function panelCitation(s: Source) {
		const lr = s.n === 0 ? lookupResult : null;
		const sub = lr && lr.kind !== 'chapter' && !lr.parent ? lr.subsection : '';
		return fullCitation(s as DeskSource, { edition, subsection: sub });
	}
</script>

<svelte:head>
	<title>Research desk | Staff | Waterville Codes RAG</title>
</svelte:head>

{#snippet tools()}
	<div class="page-head desk-head">
		<div>
			<h2 class="page-title">Research desk</h2>
			<p class="page-lede">Answers name and cite each section. Open a citation to read its text.</p>
		</div>
	</div>
	<div class="desk-bar" role="toolbar" aria-label="Research tools">
		<button type="button" class="desk-toggle" aria-expanded={panels.lookup} aria-controls="desk-lookup" onclick={() => togglePanel('lookup')}>
			Citation lookup
		</button>
		<button type="button" class="desk-toggle" class:on={filterCount > 0} aria-expanded={panels.filters} aria-controls="desk-filters" onclick={() => togglePanel('filters')}>
			{filterCount ? `Filters: ${filterCount} on` : 'Filters'}
		</button>
		<button type="button" class="desk-toggle" class:on={!!caseId} aria-expanded={panels.case} aria-controls="desk-case" onclick={() => togglePanel('case')}>
			{caseId ? `Case: ${caseName}` : 'Case: none'}
		</button>
	</div>
	<!-- Hidden rather than removed, so the lookup keeps its recent list and the
	     case picker its list while closed. -->
	<section id="desk-lookup" class="sheet desk-sheet" aria-label="Citation lookup" hidden={!panels.lookup}>
		<DeskLookup bind:this={deskLookup} {edition} onopen={openLookup} />
	</section>
	<section id="desk-filters" class="sheet desk-sheet" aria-label="Filters" hidden={!panels.filters}>
		<DeskFilters {facets} error={facetsError} bind:types bind:chapters />
	</section>
	<section id="desk-case" class="sheet desk-sheet" aria-label="Case" hidden={!panels.case}>
		<div class="desk-case" bind:this={pickerEl}>
			<CasePicker bind:value={caseId} label="Working on case" none="No case" />
			<p class="desk-case-help">Answers you save go to this case. Questions asked here are logged against it.</p>
		</div>
	</section>
{/snippet}

{#snippet intro(ask: (q: string) => void)}
	<p class="hint">Try one of these</p>
	<div class="examples">
		{#each EXAMPLES as q (q)}
			<button type="button" onclick={() => ask(q)}>{q}</button>
		{/each}
	</div>
{/snippet}

{#snippet answerTools(msg: import('$lib/chat.svelte').BotMessage)}
	{#if msg.meta?.mode === 'staff'}
		<DeskAnswerTools {msg} {edition} {caseId} {caseName} onchoosecase={chooseCase} />
	{/if}
{/snippet}

{#snippet panelTools(s: Source)}
	<div class="desk-panel-actions">
		<DeskCopyButton label="Copy citation" testid="panel-copy-citation" copy={() => panelCitation(s)} />
		{#if s.n > 0 && s.citation && LOOKUP_TYPES.has(s.source_type || '')}
			<button
				type="button"
				class="btn small secondary"
				onclick={(e) => deskLookup?.lookup(s.citation || '', e.currentTarget)}>Read the whole section</button
			>
		{/if}
	</div>
{/snippet}

<div class="desk" class:fresh={!session.started}>
	<Chat
		bind:this={chat}
		{session}
		placeholder="Ask about a section or case"
		before={tools}
		{intro}
		extra={answerTools}
		panelActions={panelTools}
	/>
</div>

<style>
	.desk {
		display: contents;
	}
	/* Before the first question the ask bar sits right under the tools, above the
	   starter questions, so it never covers them. Afterwards the usual order
	   (thread, then the ask bar) returns. */
	/* Before the first question: heading, ask bar, then the tool toggles and
	   any open panel, then the starter questions. Afterwards the usual order
	   (thread, then the ask bar) returns. */
	.desk.fresh :global(main > .desk-head) {
		order: -3;
	}
	.desk.fresh :global(form#ask) {
		order: -2;
		margin: 0 0 14px;
	}
	.desk.fresh :global(main > .desk-bar),
	.desk.fresh :global(main > .desk-sheet) {
		order: -1;
	}
	.desk-bar {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
		margin: 0 0 16px;
	}
	.desk-toggle {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		max-width: 100%;
		padding: 6px 12px;
		border: 1px solid var(--rule);
		background: transparent;
		color: var(--text);
		font: 500 0.85rem/1.3 var(--sans);
		cursor: pointer;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.desk-toggle::after {
		content: '';
		width: 6px;
		height: 6px;
		border-right: 1.5px solid currentColor;
		border-bottom: 1.5px solid currentColor;
		transform: translateY(-2px) rotate(45deg);
		flex: none;
	}
	.desk-toggle[aria-expanded='true']::after {
		transform: translateY(1px) rotate(-135deg);
	}
	.desk-toggle:hover {
		background: var(--surface-hover);
	}
	.desk-toggle[aria-expanded='true'] {
		background: var(--surface);
		border-color: var(--accent);
	}
	.desk-toggle.on {
		color: var(--accent);
		border-color: var(--accent);
		font-weight: 600;
	}
	.desk-sheet[hidden] {
		display: none;
	}
	.desk-head {
		display: flex;
		align-items: flex-end;
		justify-content: space-between;
		gap: 16px;
	}
	.desk-sheet {
		display: grid;
		gap: 20px;
		margin-bottom: 16px;
		border-top: 3px solid var(--accent);
	}
	.desk-case :global(.field) {
		margin-bottom: 6px;
	}
	.desk-case :global(.field > span) {
		color: var(--accent);
	}
	.desk-case-help {
		margin: 0;
		font-size: 0.82rem;
		color: var(--muted);
	}
	.desk-panel-actions {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
		margin-top: 10px;
	}
	@media (max-width: 640px) {
		.desk-head {
			flex-wrap: wrap;
		}
	}
</style>
