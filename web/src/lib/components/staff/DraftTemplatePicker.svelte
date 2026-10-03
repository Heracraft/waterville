<script lang="ts">
	// Template choice for a new draft, grouped (Enforcement, Zoning notices,
	// Decisions, Court). Each entry links to /staff/drafts/new?template=...
	// keeping the chosen case.
	import { groupTemplates, type TemplateSummary } from './DraftData';

	let { templates, caseId = '', current = '' }: { templates: TemplateSummary[]; caseId?: string; current?: string } = $props();

	const groups = $derived(groupTemplates(templates));
	const href = (id: string) =>
		`/staff/drafts/new?template=${encodeURIComponent(id)}${caseId ? `&case=${encodeURIComponent(caseId)}` : ''}`;
</script>

<div class="picker">
	{#each groups as g (g.group)}
		<section aria-label={g.group}>
			<h3>{g.group}</h3>
			<ul>
				{#each g.items as t (t.id)}
					<li>
						<a href={href(t.id)} aria-current={t.id === current ? 'true' : undefined}>
							<span class="t">{t.title}</span>
							<span class="d">{t.description}</span>
						</a>
					</li>
				{/each}
			</ul>
		</section>
	{/each}
</div>

<style>
	.picker {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
		gap: 20px;
	}
	h3 {
		margin: 0 0 8px;
		font: 600 0.78rem var(--sans);
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: var(--accent);
	}
	ul {
		margin: 0;
		padding: 0;
		list-style: none;
		border: 1px solid var(--rule);
		background: var(--surface);
	}
	li + li {
		border-top: 1px solid var(--border);
	}
	a {
		display: grid;
		gap: 3px;
		padding: 12px 14px;
		color: var(--text);
		text-decoration: none;
		border-left: 3px solid transparent;
		transition: background-color 0.15s;
	}
	a:hover {
		background: var(--surface-hover);
		border-left-color: var(--accent);
	}
	a:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: -2px;
	}
	a[aria-current='true'] {
		border-left-color: var(--accent);
		background: var(--surface-hover);
	}
	.t {
		font: 600 0.95rem/1.35 var(--sans);
	}
	.d {
		font-size: 0.85rem;
		line-height: 1.45;
		color: var(--muted);
	}
</style>
