<script lang="ts">
	// The research-aid stamp under staff answers. The UI renders it, never the
	// model. The wording comes from the server (GET /api/staff/me -> stamp).
	import { staff } from '$lib/staff.svelte';

	const FALLBACK = 'Research aid, not a determination of the Code Enforcement Officer.';

	let { text, label }: { text?: string; label?: string } = $props();

	const shown = $derived(text || (typeof staff.user?.stamp === 'string' && staff.user.stamp) || FALLBACK);
</script>

<div class="stamp" role="note">
	{#if label}<span class="stamp-label">{label}</span>{/if}
	<span class="stamp-text">{shown}</span>
</div>

<style>
	.stamp {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: 4px 12px;
		margin: 18px 0 0;
		padding: 8px 14px;
		border: 1px solid var(--accent);
		border-left-width: 3px;
		background: var(--bg);
		color: var(--accent);
		font: 600 0.82rem/1.45 var(--sans);
		letter-spacing: 0.01em;
	}
	.stamp-label {
		text-transform: uppercase;
		letter-spacing: 0.06em;
		font-size: 0.72rem;
	}
	.stamp-text {
		flex: 1 1 16em;
	}
</style>
