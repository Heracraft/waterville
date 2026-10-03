<script lang="ts">
	// Research desk (report items B1 to B4): cite-it answers in staff mode,
	// citation lookup into the source panel, chapter and source-type filters,
	// copy citation, copy answer with citations, save an answer to a case.
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

	function chooseCase() {
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
			<p class="page-lede">Cite-it answers: section numbers first, the controlling text quoted, the enforcement chain traced from the sources.</p>
		</div>
	</div>
	<section class="sheet desk-sheet" aria-label="Research tools">
		<div class="desk-grid">
			<DeskLookup bind:this={deskLookup} {edition} onopen={openLookup} />
			<div class="desk-case" bind:this={pickerEl}>
				<CasePicker bind:value={caseId} label="Working on case" none="No case" />
				<p class="desk-case-help">Answers you save go to this case. Questions asked here are logged against it.</p>
			</div>
		</div>
		<DeskFilters {facets} error={facetsError} bind:types bind:chapters />
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
	.desk.fresh :global(main > .desk-head),
	.desk.fresh :global(main > .desk-sheet) {
		order: -2;
	}
	.desk.fresh :global(form#ask) {
		order: -1;
		margin: 0 0 32px;
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
		margin-bottom: 32px;
		border-top: 3px solid var(--accent);
	}
	.desk-grid {
		display: grid;
		grid-template-columns: minmax(0, 2fr) minmax(0, 1fr);
		gap: 20px 32px;
		padding-bottom: 18px;
		border-bottom: 1px solid var(--rule);
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
	@media (max-width: 860px) {
		.desk-grid {
			grid-template-columns: minmax(0, 1fr);
		}
	}
	@media (max-width: 640px) {
		.desk-head {
			flex-wrap: wrap;
		}
	}
</style>
