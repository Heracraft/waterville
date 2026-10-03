<script lang="ts">
	// A1: the permit checklist for a topic. Shown under a matching public
	// answer and on /permits. Every card ends with the confirm line.
	import type { Checklist } from './PublicData';

	let {
		checklist,
		open = false,
		external = false,
		showGuide = true,
		headingLevel = 3
	}: {
		checklist: Checklist;
		/** Open the "What to bring" list. */
		open?: boolean;
		/** Open site links in a new tab (the embed lives in an iframe). */
		external?: boolean;
		/** Link to /permits for this project. */
		showGuide?: boolean;
		headingLevel?: 2 | 3;
	} = $props();

	const c = $derived(checklist);
	const target = $derived(external ? '_blank' : undefined);
	const rel = $derived(external ? 'noopener' : undefined);
	const fireClass = $derived(c.fire_review.status === 'yes' ? 'is-yes' : c.fire_review.status === 'no' ? 'is-no' : 'is-maybe');
</script>

<section class="pc" aria-label="Permit checklist: {c.title}">
	<div class="pc-head">
		<span class="pc-kicker">Permit checklist</span>
		<svelte:element this={`h${headingLevel}`} class="pc-title">{c.title}</svelte:element>
		{#if c.summary}<p class="pc-summary">{c.summary}</p>{/if}
	</div>

	<div class="pc-grid">
		<div class="pc-block">
			<h4>Controlling sections</h4>
			<ul class="pc-sections">
				{#each c.sections as s (s.citation)}
					<li>
						<a href={s.url} target="_blank" rel="noopener">Waterville City Code {s.citation}</a>
						<span>{s.says}</span>
					</li>
				{/each}
			</ul>
		</div>

		<div class="pc-block">
			<h4>Forms</h4>
			{#if c.forms.length}
				<ul class="pc-forms">
					{#each c.forms as f (f.id)}
						<li><a href={f.url} target="_blank" rel="noopener">{f.title}</a> <span class="pc-who">{f.who}</span></li>
					{/each}
				</ul>
			{:else}
				<p class="pc-muted">No form for this is posted online. Ask the office which application to file.</p>
			{/if}
			<p class="pc-muted">
				All city applications: <a href={c.applications_page} target="_blank" rel="noopener">Building Permit Applications</a>
			</p>
			<p class="pc-fire {fireClass}"><strong>Fire Department review.</strong> {c.fire_review.label}</p>
		</div>
	</div>

	<details class="pc-bring" {open}>
		<summary>What to bring ({c.bring.length})</summary>
		<ul>
			{#each c.bring as item, i (i)}<li>{item}</li>{/each}
		</ul>
		{#if c.survey_note}<p class="pc-muted">{c.survey_note}</p>{/if}
		{#if c.inspections}<p class="pc-muted">{c.inspections}</p>{/if}
	</details>

	{#if c.notes.length}
		<ul class="pc-notes">
			{#each c.notes as n, i (i)}<li>{n}</li>{/each}
		</ul>
	{/if}

	<p class="pc-confirm">{c.confirm_line}</p>
	<p class="pc-links">
		{#if showGuide}<a href={c.permit_guide} {target} {rel}>Open the permit guide</a>{/if}
		<a href="/fees" {target} {rel}>Estimate fees</a>
	</p>
</section>

<style>
	.pc {
		margin-top: 22px;
		padding-top: 16px;
		border-top: 1px solid var(--rule);
		font: 400 0.92rem/1.5 var(--sans);
	}
	@media (max-width: 1099.98px) {
		:global(.msg.bot > .sources) ~ .pc {
			margin-top: 40px;
		}
	}
	.pc-head {
		margin-bottom: 12px;
	}
	.pc-kicker {
		display: block;
		color: var(--accent);
		font: 600 0.8rem var(--sans);
		letter-spacing: 0.01em;
	}
	.pc-title {
		margin: 2px 0 0;
		font: 300 1.35rem/1.25 var(--serif);
		color: var(--text);
	}
	.pc-summary {
		margin: 4px 0 0;
		color: var(--muted);
	}
	.pc-grid {
		display: grid;
		gap: 0;
		border-top: 1px solid var(--border);
	}
	@media (min-width: 760px) {
		.pc-grid {
			grid-template-columns: 3fr 2fr;
		}
		.pc-grid > .pc-block + .pc-block {
			border-left: 1px solid var(--border);
			padding-left: 18px;
		}
		.pc-grid > .pc-block:first-child {
			padding-right: 18px;
		}
	}
	.pc-block {
		padding: 10px 0 12px;
		min-width: 0;
	}
	h4 {
		margin: 0 0 6px;
		font: 600 0.8rem var(--sans);
		letter-spacing: 0.01em;
		color: var(--text);
		text-transform: none;
	}
	ul {
		margin: 0;
		padding: 0;
		list-style: none;
	}
	.pc-sections li {
		padding: 6px 0;
		border-bottom: 1px solid var(--border);
	}
	.pc-sections li:last-child {
		border-bottom: 0;
	}
	.pc-sections a,
	.pc-forms a {
		font-weight: 600;
		overflow-wrap: anywhere;
	}
	.pc-sections span {
		display: block;
		margin-top: 2px;
		font: 400 0.95rem/1.5 var(--serif);
		color: var(--text);
	}
	.pc-forms li {
		padding: 3px 0;
	}
	.pc-who {
		display: block;
		color: var(--muted);
		font-size: 0.82rem;
	}
	.pc-muted {
		margin: 8px 0 0;
		color: var(--muted);
		font-size: 0.85rem;
	}
	.pc-fire {
		margin: 10px 0 0;
		padding: 8px 10px;
		background: var(--bg);
		border-left: 3px solid var(--rule);
		font-size: 0.86rem;
	}
	.pc-fire.is-yes {
		border-left-color: var(--accent);
	}
	.pc-bring {
		border-top: 1px solid var(--border);
		padding-top: 8px;
	}
	.pc-bring summary {
		cursor: pointer;
		color: var(--accent);
		font-weight: 600;
		font-size: 0.85rem;
		padding: 2px 0 6px;
	}
	.pc-bring ul {
		counter-reset: bring;
	}
	.pc-bring li {
		counter-increment: bring;
		position: relative;
		padding: 5px 0 5px 28px;
		border-bottom: 1px solid var(--border);
	}
	.pc-bring li::before {
		content: counter(bring) '.';
		position: absolute;
		left: 0;
		color: var(--accent);
		font-family: var(--serif);
	}
	.pc-notes {
		margin-top: 12px;
	}
	.pc-notes li {
		padding: 4px 0 4px 12px;
		border-left: 2px solid var(--accent-soft);
		margin-bottom: 6px;
		color: var(--text);
	}
	.pc-confirm {
		margin: 14px 0 0;
		padding: 10px 12px;
		border: 1px solid var(--accent);
		color: var(--text);
		font-weight: 600;
	}
	.pc-links {
		display: flex;
		flex-wrap: wrap;
		gap: 6px 18px;
		margin: 10px 0 0;
		font-weight: 600;
	}
	.pc-links a::after {
		content: ' \2192';
	}
</style>
