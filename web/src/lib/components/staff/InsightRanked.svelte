<script lang="ts" generics="T">
	// A ranked list with a thin bar per row (one series, so no legend): top
	// topics and most cited sections. `detail` renders under a row when opened.
	import type { Snippet } from 'svelte';

	let {
		rows,
		label,
		count,
		note,
		detail,
		empty = 'Nothing yet.',
		caption
	}: {
		rows: T[];
		label: (r: T) => string;
		count: (r: T) => number;
		note?: (r: T) => string;
		detail?: Snippet<[T]>;
		empty?: string;
		caption: string;
	} = $props();

	const max = $derived(Math.max(1, ...rows.map(count)));
</script>

{#if rows.length === 0}
	<p class="muted">{empty}</p>
{:else}
	<ol class="ranked" aria-label={caption}>
		{#each rows as r, i (i)}
			<li>
				{#if detail}
					<details>
						<summary>
							<span class="name">{label(r)}</span>
							<span class="num">{count(r)}</span>
							<span class="bar" style:width="{(count(r) / max) * 100}%" aria-hidden="true"></span>
							{#if note?.(r)}<span class="note">{note(r)}</span>{/if}
						</summary>
						<div class="more">{@render detail(r)}</div>
					</details>
				{:else}
					<div class="row">
						<span class="name">{label(r)}</span>
						<span class="num">{count(r)}</span>
						<span class="bar" style:width="{(count(r) / max) * 100}%" aria-hidden="true"></span>
						{#if note?.(r)}<span class="note">{note(r)}</span>{/if}
					</div>
				{/if}
			</li>
		{/each}
	</ol>
{/if}

<style>
	.ranked {
		list-style: none;
		margin: 0;
		padding: 0;
		border-top: 1px solid var(--border);
	}
	li {
		border-bottom: 1px solid var(--border);
	}
	summary,
	.row {
		display: grid;
		grid-template-columns: 1fr auto;
		gap: 4px 12px;
		padding: 8px 0 9px;
		font: 0.92rem/1.4 var(--sans);
	}
	summary {
		cursor: pointer;
		list-style: none;
	}
	summary::-webkit-details-marker {
		display: none;
	}
	summary .name::before {
		content: '+';
		display: inline-block;
		width: 1em;
		color: var(--accent);
		font-weight: 600;
	}
	details[open] summary .name::before {
		content: '\2212';
	}
	summary:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
	}
	.name {
		min-width: 0;
		overflow-wrap: anywhere;
	}
	.num {
		font-weight: 600;
		font-variant-numeric: tabular-nums;
	}
	.bar {
		grid-column: 1 / -1;
		height: 4px;
		min-width: 2px;
		background: var(--accent);
	}
	.note {
		grid-column: 1 / -1;
		color: var(--muted);
		font-size: 0.8rem;
	}
	.more {
		padding: 0 0 12px 1em;
		font-size: 0.9rem;
	}
</style>
