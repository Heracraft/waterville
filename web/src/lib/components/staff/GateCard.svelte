<script lang="ts">
	// One approval in the ordered gate list: why it applies, who grants it,
	// what it blocks, and the controlling text with its citation.
	import type { Gate } from './GateData';

	let { gate }: { gate: Gate } = $props();
	const uid = $props.id();
</script>

<article class="gate" class:unverified={!gate.verified} aria-labelledby="{uid}-t">
	<div class="num" aria-hidden="true">{gate.order}</div>
	<div class="body">
		<p class="top">
			<span class="auth">{gate.authority}</span>
			{#if gate.verified}
				<span class="st st-ok">Verified against primary text</span>
			{:else if gate.scope === 'city'}
				<span class="st st-no">Unverified</span>
			{:else}
				<span class="st st-no">Unverified for Waterville</span>
			{/if}
		</p>
		<h4 id="{uid}-t"><span class="sr-only">Step {gate.order}: </span>{gate.title}</h4>
		<ul class="reasons">
			{#each gate.reasons as r, i (i)}<li>{r}</li>{/each}
		</ul>
		{#if gate.blocks}<p class="blocks">{gate.blocks}</p>{/if}
		{#if gate.quote}
			<blockquote>
				<p>{gate.quote}</p>
				<footer><a href={gate.url} target="_blank" rel="noopener noreferrer">{gate.citation}</a></footer>
			</blockquote>
		{:else}
			<p class="cit"><a href={gate.url} target="_blank" rel="noopener noreferrer">{gate.citation}</a></p>
		{/if}
		{#if gate.note}<p class="note">{gate.note}</p>{/if}
	</div>
</article>

<style>
	.gate {
		display: grid;
		grid-template-columns: 52px minmax(0, 1fr);
		background: var(--surface);
		border: 1px solid var(--rule);
	}
	.gate.unverified {
		border-style: dashed;
	}
	.num {
		display: flex;
		justify-content: center;
		padding-top: 14px;
		border-right: 1px solid var(--border);
		background: var(--bg);
		font: 300 1.5rem/1 var(--serif);
		color: var(--accent);
	}
	.body {
		padding: 12px 16px 14px;
		min-width: 0;
	}
	.top {
		display: flex;
		flex-wrap: wrap;
		justify-content: space-between;
		gap: 4px 12px;
		margin: 0;
	}
	.auth {
		font: 600 0.74rem var(--sans);
		text-transform: uppercase;
		letter-spacing: 0.06em;
		color: var(--muted);
	}
	.st {
		padding: 0 8px;
		font: 600 0.72rem/1.7 var(--sans);
		border: 1px solid currentColor;
	}
	.st-ok {
		color: var(--muted);
	}
	.st-no {
		color: var(--accent-text);
		background: var(--accent);
		border-color: var(--accent);
	}
	h4 {
		margin: 4px 0 6px;
		font: 600 1.02rem/1.35 var(--sans);
	}
	.reasons {
		margin: 0 0 8px;
		padding-left: 1.2em;
		font: 0.9rem/1.5 var(--sans);
	}
	.blocks {
		margin: 0 0 8px;
		padding: 6px 10px;
		border-left: 3px solid var(--accent);
		background: var(--bg);
		font: 0.86rem/1.45 var(--sans);
	}
	blockquote {
		margin: 8px 0 6px;
		padding: 2px 0 2px 14px;
		border-left: 1px solid var(--rule);
		font: 400 0.95rem/1.55 var(--serif);
	}
	blockquote p {
		margin: 0 0 4px;
	}
	blockquote footer,
	.cit {
		font: 600 0.82rem var(--sans);
	}
	a {
		color: var(--text);
		text-decoration-color: var(--accent);
	}
	.cit {
		margin: 0 0 6px;
	}
	.note {
		margin: 0;
		font-size: 0.86rem;
		color: var(--muted);
	}
	@media (max-width: 640px) {
		.gate {
			grid-template-columns: 38px minmax(0, 1fr);
		}
		.num {
			font-size: 1.2rem;
		}
		.body {
			padding: 10px 12px 12px;
		}
	}
	@media print {
		.gate {
			break-inside: avoid;
		}
	}
</style>
