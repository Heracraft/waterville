<script lang="ts">
	// A2: shown under an answer when the question reports a hazard (route to
	// Code Enforcement or Fire) or asks about something the office does not
	// handle (point elsewhere, but still route hazards).
	import { telHref, type Triage } from './PublicData';

	let { triage, external = false }: { triage: Triage; external?: boolean } = $props();
	const t = $derived(triage);
</script>

<section class="pt" class:urgent={t.kind === 'urgent'} aria-label={t.title} role={t.kind === 'urgent' ? 'note' : undefined}>
	<h3 class="pt-title">{t.title}</h3>
	{#each t.lines as line, i (i)}<p>{line}</p>{/each}
	<p class="pt-actions">
		<a class="pt-call" href={telHref(t.office_phone)}>Call Code Enforcement, <span class="nowrap">{t.office_phone}</span></a>
		{#each t.links as l (l.href)}
			<a href={l.href} target={external ? '_blank' : undefined} rel={external ? 'noopener' : undefined}>{l.label}</a>
		{/each}
	</p>
</section>

<style>
	.pt {
		margin-top: 22px;
		padding: 14px 16px;
		border: 1px solid var(--rule);
		border-left: 4px solid var(--rule);
		background: var(--bg);
		font: 400 0.95rem/1.5 var(--sans);
	}
	.pt.urgent {
		border-left-color: var(--accent);
	}
	.pt-title {
		margin: 0 0 8px;
		font: 600 1rem/1.35 var(--sans);
		color: var(--text);
	}
	.pt.urgent .pt-title {
		color: var(--accent);
	}
	.pt p {
		margin: 0 0 8px;
	}
	.pt-actions {
		display: flex;
		flex-wrap: wrap;
		gap: 8px 16px;
		align-items: center;
		margin: 12px 0 0 !important;
		font-weight: 600;
	}
	.pt-call {
		display: inline-block;
		padding: 6px 12px;
		background: var(--accent);
		color: var(--accent-text);
		text-decoration: none;
	}
	.nowrap {
		white-space: nowrap;
	}
	/* Below the sources list on narrow layouts: clear its negative bottom margin. */
	@media (max-width: 1099.98px) {
		:global(.msg.bot > .sources) ~ .pt {
			margin-top: 40px;
		}
	}
	.pt-call:hover {
		filter: brightness(1.08);
	}
</style>
