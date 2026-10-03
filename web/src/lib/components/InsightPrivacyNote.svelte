<script lang="ts">
	// Footer for the public page: the question log privacy note (A7a) and the
	// link to sections saved on this device for offline reading (B11).
	import { chrome } from '$lib/chrome.svelte';

	let { offlineLink = true }: { offlineLink?: boolean } = $props();
</script>

<footer class="privacy-note" inert={chrome.modal}>
	<div class="wrap">
		<p>
			Questions are logged without personal details to improve the service. Names, street addresses, map and lot
			numbers, phone numbers and email addresses are removed before a question is saved.
			{#if offlineLink}<a href="/offline">Sections saved on this device</a>{/if}
		</p>
	</div>
</footer>

<style>
	.privacy-note {
		border-top: 1px solid var(--border);
		font: 0.8rem/1.5 var(--sans);
		color: var(--muted);
	}
	.privacy-note .wrap {
		padding-block: 14px 18px;
	}
	p {
		margin: 0;
		max-width: 60em;
	}
	a {
		white-space: nowrap;
		margin-left: 4px;
	}
	@media print {
		.privacy-note {
			display: none;
		}
	}
</style>
