<script lang="ts">
	// Case status as a small ruled label: open is rust, monitoring ink, closed muted.
	import { statusLabel } from './CaseData';

	let { status }: { status: string } = $props();
</script>

<span class="badge s-{status}">{statusLabel(status)}</span>

<style>
	.badge {
		display: inline-block;
		padding: 0 8px;
		border: 1px solid currentColor;
		font: 600 0.74rem/1.7 var(--sans);
		letter-spacing: 0.06em;
		text-transform: uppercase;
		white-space: nowrap;
	}
	.s-open {
		color: var(--accent);
	}
	.s-monitoring {
		color: var(--text);
		background: var(--accent-soft);
		border-color: var(--rule);
	}
	.s-closed {
		color: var(--muted);
		border-style: dashed;
	}
</style>
