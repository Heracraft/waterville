<script lang="ts">
	// Filter chips for the research desk (B4): source types and City Code
	// chapters, from GET /api/facets. Bind `types` and `chapters`; the desk
	// sends them as chat filters.
	import type { Facets } from './DeskCite';

	// Chapters an inspector reaches for most; the rest sit under "All chapters".
	const PINNED = ['205', '275', '127', '215', '173', '145', '244', '210'];

	let {
		facets,
		types = $bindable([]),
		chapters = $bindable([]),
		error = ''
	}: { facets: Facets | null; types?: string[]; chapters?: string[]; error?: string } = $props();

	const uid = $props.id();
	const allChapters = $derived(facets?.chapters ?? []);
	const shownChapters = $derived(
		allChapters.filter((c) => PINNED.includes(c.value) || chapters.includes(c.value))
	);
	const titleOf = (v: string) => allChapters.find((c) => c.value === v)?.title || '';
	const nameOf = (v: string) => facets?.source_types.find((t) => t.value === v)?.name || v;
	const active = $derived(types.length + chapters.length > 0);
	const chapterLabel = (v: string) => (v === 'C' ? 'Charter' : `Ch. ${v}`);

	function toggle(list: string[], v: string): string[] {
		return list.includes(v) ? list.filter((x) => x !== v) : [...list, v];
	}

	const summary = $derived(
		[
			chapters.length ? chapters.map(chapterLabel).join(', ') : '',
			types.length ? types.map(nameOf).join(', ') : ''
		]
			.filter(Boolean)
			.join('; ')
	);
</script>

<div class="desk-filters" role="group" aria-labelledby="{uid}-h">
	<h3 id="{uid}-h" class="desk-h">Narrow the search</h3>
	{#if error}
		<p class="error-text desk-small">Could not load the filters: {error}</p>
	{:else if !facets}
		<p class="muted desk-small">Loading filters</p>
	{:else}
		<div class="desk-row">
			<span class="desk-row-label" id="{uid}-types">Sources</span>
			<ul class="chips" aria-labelledby="{uid}-types">
				{#each facets.source_types as t (t.value)}
					<li>
						<button
							type="button"
							class="chip"
							aria-pressed={types.includes(t.value)}
							title={t.label || t.name}
							onclick={() => (types = toggle(types, t.value))}>{t.name}</button
						>
					</li>
				{/each}
			</ul>
		</div>
		<div class="desk-row">
			<span class="desk-row-label" id="{uid}-ch">Chapters</span>
			<ul class="chips" aria-labelledby="{uid}-ch">
				{#each shownChapters as c (c.value)}
					<li>
						<button
							type="button"
							class="chip"
							aria-pressed={chapters.includes(c.value)}
							title={c.title}
							onclick={() => (chapters = toggle(chapters, c.value))}
							>{chapterLabel(c.value)}<span class="chip-title">{c.title}</span></button
						>
					</li>
				{/each}
			</ul>
		</div>
		{#if allChapters.length > shownChapters.length}
			<details class="desk-more">
				<summary>All chapters ({allChapters.length})</summary>
				<div class="desk-more-grid">
					{#each allChapters as c (c.value)}
						<label class="check">
							<input
								type="checkbox"
								checked={chapters.includes(c.value)}
								onchange={() => (chapters = toggle(chapters, c.value))}
							/>
							<span><strong>{chapterLabel(c.value)}</strong> {c.title}</span>
						</label>
					{/each}
				</div>
			</details>
		{/if}
		<p class="desk-scope desk-small" aria-live="polite">
			{#if active}
				Searching only {summary}.
				<button type="button" class="linkish" onclick={() => ((types = []), (chapters = []))}>Clear filters</button>
			{:else}
				Searching every source. Chapter filters narrow the City Code; state sources stay in unless you pick source types.
			{/if}
		</p>
		{#if chapters.some((c) => !titleOf(c))}
			<p class="muted desk-small">Some chosen chapters are not in the index.</p>
		{/if}
	{/if}
</div>

<style>
	.desk-filters {
		display: grid;
		gap: 10px;
	}
	.desk-h {
		margin: 0;
		font: 600 0.85rem var(--sans);
		color: var(--accent);
		letter-spacing: 0.01em;
	}
	.desk-small {
		margin: 0;
		font-size: 0.85rem;
	}
	.desk-row {
		display: grid;
		grid-template-columns: 6.5em minmax(0, 1fr);
		align-items: baseline;
		gap: 8px;
	}
	.desk-row-label {
		font: 600 0.8rem var(--sans);
		color: var(--muted);
		text-transform: uppercase;
		letter-spacing: 0.06em;
	}
	.chips {
		display: flex;
		flex-wrap: wrap;
		gap: 6px;
		margin: 0;
		padding: 0;
		list-style: none;
	}
	.chip {
		display: inline-flex;
		align-items: baseline;
		gap: 6px;
		cursor: pointer;
		border: 1px solid var(--rule);
		border-radius: 0;
		background: var(--surface);
		color: var(--text);
		font: 500 0.84rem/1.3 var(--sans);
		padding: 5px 10px;
		transition: background-color 0.15s, color 0.15s;
	}
	.chip:hover {
		background: var(--surface-hover);
	}
	.chip[aria-pressed='true'] {
		background: var(--accent);
		border-color: var(--accent);
		color: var(--accent-text);
	}
	.chip-title {
		font-size: 0.76rem;
		opacity: 0.8;
		max-width: 17em;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.desk-more summary {
		cursor: pointer;
		font: 600 0.85rem var(--sans);
		color: var(--accent);
	}
	.desk-more-grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(15em, 1fr));
		gap: 4px 18px;
		margin-top: 10px;
		padding: 12px;
		max-height: 260px;
		overflow-y: auto;
		border: 1px solid var(--border);
		background: var(--bg);
		font-size: 0.88rem;
	}
	.desk-scope {
		color: var(--muted);
		border-top: 1px solid var(--border);
		padding-top: 8px;
	}
	.linkish {
		border: 0;
		background: none;
		padding: 0;
		color: var(--accent);
		font-family: var(--sans);
		font-size: inherit;
		font-weight: 600;
		text-decoration: underline;
		text-underline-offset: 3px;
		cursor: pointer;
	}
	@media (max-width: 640px) {
		.desk-row {
			grid-template-columns: 1fr;
			gap: 4px;
		}
		.chip-title {
			display: none;
		}
	}
</style>
