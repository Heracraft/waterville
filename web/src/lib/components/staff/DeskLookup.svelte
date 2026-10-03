<script lang="ts">
	// Citation lookup (B3): type "205-7", "§ 275-4.27K(3)" or "30-A § 4452" and
	// read the whole section in the source panel. GET /api/lookup?cite=
	import { api, ApiError } from '$lib/api';
	import DeskCopyButton from './DeskCopyButton.svelte';
	import { fullCitation, lookupSource, type LookupResult } from './DeskCite';

	const RECENT_KEY = 'wv-desk-recent';
	const KIND_LABELS: Record<LookupResult['kind'], string> = {
		section: 'City Code section',
		charter: 'City Charter',
		chapter: 'City Code chapter',
		ordinance: 'New law',
		statute: 'Maine statute',
		rule: 'Maine rule'
	};

	let {
		edition = null,
		onopen
	}: {
		/** The code's "legislation through" date, for citations without their own. */
		edition?: string | null;
		/** Show the result in the source panel; focus returns to `trigger` on close. */
		onopen: (result: LookupResult, trigger: HTMLElement) => void;
	} = $props();

	const uid = $props.id();
	let cite = $state('');
	let busy = $state(false);
	let error = $state('');
	let result = $state<LookupResult | null>(null);
	let recent = $state<string[]>(loadRecent());
	let inputEl = $state<HTMLInputElement>();
	let readEl = $state<HTMLButtonElement>();

	function loadRecent(): string[] {
		try {
			const v = JSON.parse(localStorage.getItem(RECENT_KEY) || '[]');
			return Array.isArray(v) ? v.filter((x) => typeof x === 'string').slice(0, 6) : [];
		} catch {
			return [];
		}
	}

	function remember(c: string) {
		recent = [c, ...recent.filter((x) => x !== c)].slice(0, 6);
		try {
			localStorage.setItem(RECENT_KEY, JSON.stringify(recent));
		} catch {
			/* private window: recent lookups last for this visit only */
		}
	}

	export async function lookup(query: string, trigger?: HTMLElement) {
		const q = query.trim();
		if (!q || busy) return;
		cite = q;
		busy = true;
		error = '';
		try {
			const r = await api.get<LookupResult>(`/api/lookup?cite=${encodeURIComponent(q)}`);
			result = r;
			remember(r.kind === 'chapter' ? r.requested : r.citation);
			onopen(r, trigger ?? readEl ?? inputEl!);
		} catch (e) {
			result = null;
			error = e instanceof ApiError || e instanceof Error ? e.message : String(e);
		} finally {
			busy = false;
		}
	}

	function submit(e: SubmitEvent) {
		e.preventDefault();
		lookup(cite, (e.submitter as HTMLElement) || undefined);
	}

	const shownCite = $derived(
		result ? (result.kind === 'chapter' ? result.citation : result.citation + (result.subsection || '')) : ''
	);
	const sectionTitle = $derived(
		result?.title && result.title !== result.citation ? result.title.replace(/^.*?\.\s+/, '') : ''
	);
</script>

<div class="desk-lookup">
	<form class="desk-lookup-form" onsubmit={submit} autocomplete="off">
		<label class="desk-lookup-label" for="{uid}-cite">Look up a citation</label>
		<div class="desk-lookup-bar">
			<input
				id="{uid}-cite"
				class="input"
				type="text"
				maxlength="80"
				placeholder="205-7, § 275-4.27K(3), Charter Art. IV, § 9, 30-A § 4452"
				aria-describedby="{uid}-help"
				bind:value={cite}
				bind:this={inputEl}
			/>
			<button type="submit" class="btn" disabled={busy || !cite.trim()}>{busy ? 'Opening' : 'Open'}</button>
		</div>
		<p id="{uid}-help" class="desk-help">
			City Code sections, Charter sections, chapters, new laws, Maine statutes and rules. A subsection opens its whole section.
		</p>
	</form>

	{#if error}
		<p class="desk-error" role="alert">{error}</p>
	{/if}

	{#if result}
		<div class="desk-result" aria-live="polite">
			<span class="desk-kicker">{KIND_LABELS[result.kind]}{result.label ? `, ${result.label}` : ''}</span>
			<p class="desk-result-cite"><strong>{shownCite}</strong>{#if sectionTitle}{' '}<span class="desk-result-title">{sectionTitle}</span>{/if}</p>
			{#if result.parent}
				<p class="desk-note">The index has no {result.requested}. Showing the section that contains it, {result.citation}.</p>
			{:else if result.subsection && result.kind !== 'chapter'}
				<p class="desk-note">Subsection {result.subsection} is inside the text of {result.citation}.</p>
			{/if}
			<div class="btn-row">
				<button type="button" class="btn small" bind:this={readEl} onclick={() => result && onopen(result, readEl!)}>
					Read {result.chunk_count > 1 ? `all ${result.chunk_count} parts` : 'the text'}
				</button>
				<DeskCopyButton
					label="Copy citation"
					testid="lookup-copy-citation"
					copy={() =>
						fullCitation(lookupSource(result!), {
							edition,
							subsection: result!.kind === 'chapter' || result!.parent ? '' : result!.subsection
						})}
				/>
			</div>
			{#if result.sections?.length}
				<details class="desk-toc" open={result.sections.length <= 30}>
					<summary>Sections in this chapter ({result.sections.length})</summary>
					<ol>
						{#each result.sections as s (s.citation)}
							<li>
								<button type="button" class="desk-toc-link" onclick={(e) => lookup(s.citation, e.currentTarget)}>{s.citation}</button>
								<span class="muted">{(s.title || '').replace(/^.*?\.\s+/, '')}</span>
							</li>
						{/each}
					</ol>
				</details>
			{/if}
		</div>
	{/if}

	{#if recent.length}
		<div class="desk-recent">
			<span class="desk-recent-label">Recent</span>
			<ul>
				{#each recent as r (r)}
					<li><button type="button" class="desk-toc-link" onclick={(e) => lookup(r, e.currentTarget)}>{r}</button></li>
				{/each}
			</ul>
		</div>
	{/if}
</div>

<style>
	.desk-lookup {
		display: grid;
		gap: 12px;
		min-width: 0;
	}
	.desk-lookup-form {
		display: grid;
		gap: 6px;
	}
	.desk-lookup-label {
		font: 600 0.85rem var(--sans);
		color: var(--accent);
		letter-spacing: 0.01em;
	}
	.desk-lookup-bar {
		display: flex;
		min-width: 0;
	}
	.desk-lookup-bar .input {
		flex: 1;
		min-width: 0;
		border-right: 0;
		font-family: var(--serif);
		font-size: 1.05rem;
	}
	.desk-lookup-bar .btn {
		flex: none;
		min-width: 5.5em;
	}
	.desk-help {
		margin: 0;
		font-size: 0.82rem;
		color: var(--muted);
	}
	.desk-error {
		margin: 0;
		padding: 8px 12px;
		border-left: 3px solid var(--error);
		background: var(--bg);
		color: var(--error);
		font-size: 0.9rem;
	}
	.desk-result {
		display: grid;
		gap: 8px;
		padding: 12px 14px;
		background: var(--bg);
		border: 1px solid var(--border);
		border-left: 3px solid var(--accent);
	}
	.desk-kicker {
		font: 600 0.74rem var(--sans);
		color: var(--muted);
		text-transform: uppercase;
		letter-spacing: 0.06em;
	}
	.desk-result-cite {
		margin: 0;
		font: 400 1.1rem/1.35 var(--serif);
	}
	.desk-result-cite strong {
		font-weight: 600;
	}
	.desk-result-title {
		margin-left: 0.15em;
	}
	.desk-note {
		margin: 0;
		font-size: 0.86rem;
		color: var(--muted);
	}
	.desk-toc summary {
		cursor: pointer;
		font: 600 0.85rem var(--sans);
		color: var(--accent);
	}
	.desk-toc ol {
		margin: 8px 0 0;
		padding: 0;
		list-style: none;
		max-height: 280px;
		overflow-y: auto;
		border-top: 1px solid var(--border);
		font-size: 0.88rem;
	}
	.desk-toc li {
		padding: 5px 0;
		border-bottom: 1px solid var(--border);
	}
	.desk-toc-link {
		border: 0;
		background: none;
		padding: 0;
		margin-right: 6px;
		color: var(--accent);
		font: 600 0.88rem var(--sans);
		text-decoration: underline;
		text-decoration-color: var(--border);
		text-underline-offset: 3px;
		cursor: pointer;
	}
	.desk-toc-link:hover {
		text-decoration-color: var(--accent);
	}
	.desk-recent {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: 4px 10px;
		font-size: 0.85rem;
	}
	.desk-recent-label {
		font: 600 0.74rem var(--sans);
		color: var(--muted);
		text-transform: uppercase;
		letter-spacing: 0.06em;
	}
	.desk-recent ul {
		display: contents;
		list-style: none;
	}
	.desk-recent li {
		display: inline;
	}
</style>
