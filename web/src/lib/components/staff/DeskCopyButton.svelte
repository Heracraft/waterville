<script lang="ts">
	// A button that copies text (and HTML) to the clipboard and says so for a moment.
	import { copyToClipboard } from './DeskCite';

	let {
		label,
		copy,
		variant = 'secondary',
		testid
	}: {
		label: string;
		/** Called on click: plain text, or text plus HTML for rich paste. */
		copy: () => string | { text: string; html?: string };
		variant?: 'primary' | 'secondary';
		testid?: string;
	} = $props();

	let status = $state<'idle' | 'done' | 'failed'>('idle');
	let timer: ReturnType<typeof setTimeout> | undefined;

	async function run() {
		const v = copy();
		const { text, html } = typeof v === 'string' ? { text: v, html: undefined } : v;
		status = (await copyToClipboard(text, html)) ? 'done' : 'failed';
		clearTimeout(timer);
		timer = setTimeout(() => (status = 'idle'), 2200);
	}

	$effect(() => () => clearTimeout(timer));
</script>

<button
	type="button"
	class="btn small desk-copy"
	class:secondary={variant === 'secondary'}
	class:is-done={status === 'done'}
	data-testid={testid}
	onclick={run}
>
	{status === 'done' ? 'Copied' : status === 'failed' ? 'Copy failed' : label}
</button>
<span class="sr-only" role="status">{status === 'done' ? `${label}: copied to the clipboard` : status === 'failed' ? 'Could not copy' : ''}</span>

<style>
	.desk-copy {
		min-width: 8.5em;
	}
	.desk-copy.is-done {
		border-color: var(--accent);
		color: var(--accent);
	}
	.desk-copy.is-done:not(.secondary) {
		color: var(--accent-text);
	}
</style>
