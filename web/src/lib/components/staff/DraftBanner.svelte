<script lang="ts">
	// The status line on every printed draft. Paper only: staff know a draft is a draft.
	import { BANNER } from './DraftData';

	let { text = BANNER }: { text?: string } = $props();
</script>

<p class="draft-banner" role="note">
	<span class="tag">Draft</span>
	<span>{text}</span>
</p>

<style>
	.draft-banner {
		display: flex;
		align-items: baseline;
		gap: 12px;
		margin: 0 0 16px;
		padding: 10px 14px;
		border: 1px solid var(--rule);
		border-left: 4px solid var(--accent);
		background: var(--surface);
		color: var(--text);
		font: 500 0.9rem/1.45 var(--sans);
	}
	.tag {
		flex: none;
		border: 1px solid var(--accent);
		color: var(--accent);
		padding: 0 7px;
		font: 700 0.72rem/1.7 var(--sans);
		letter-spacing: 0.08em;
		text-transform: uppercase;
	}
	@media screen {
		.draft-banner {
			display: none;
		}
	}
	@media print {
		.draft-banner {
			border-color: #000;
			border-left-color: #000;
			background: #fff;
			color: #000;
		}
		.tag {
			border-color: #000;
			color: #000;
		}
	}
</style>
