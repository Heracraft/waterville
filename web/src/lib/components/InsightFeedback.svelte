<script lang="ts">
	// "Was this helpful?" under a finished public answer. Sends only the answer id
	// and yes or no (POST /api/feedback); a second click changes the vote.
	import { api } from '$lib/api';
	import type { BotMessage } from '$lib/chat.svelte';

	let { msg }: { msg: BotMessage } = $props();

	const answerId = $derived(msg.meta?.answer_id ?? '');
	const show = $derived(
		msg.status === 'done' && !msg.error && !!msg.answer && msg.meta?.mode !== 'staff' && /^[a-f0-9]{32}$/.test(answerId)
	);

	let vote = $state<boolean | null>(null);
	let sending = $state(false);
	let problem = $state('');

	async function send(helpful: boolean) {
		if (sending || vote === helpful) return;
		sending = true;
		problem = '';
		try {
			await api.post('/api/feedback', { answer_id: answerId, helpful });
			vote = helpful;
		} catch (e) {
			problem = e instanceof Error ? e.message : 'Could not send. Please try again.';
		} finally {
			sending = false;
		}
	}
</script>

{#if show}
	<div class="helpful" role="group" aria-label="Was this answer helpful?">
		<span class="q" aria-hidden="true">Was this helpful?</span>
		<button type="button" aria-pressed={vote === true} disabled={sending} onclick={() => send(true)}>Yes</button>
		<button type="button" aria-pressed={vote === false} disabled={sending} onclick={() => send(false)}>No</button>
		<span class="thanks" role="status">
			{#if problem}<span class="err">{problem}</span>{:else if vote !== null}Thank you. This helps us improve the answers.{/if}
		</span>
	</div>
{/if}

<style>
	.helpful {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 6px 8px;
		margin-top: 14px;
		font: 500 0.82rem var(--sans);
		color: var(--muted);
	}
	.q {
		margin-right: 2px;
	}
	button {
		cursor: pointer;
		border: 1px solid var(--border);
		border-radius: 0;
		background: transparent;
		color: var(--text);
		font: 600 0.8rem var(--sans);
		padding: 3px 12px;
		transition: border-color 0.15s, background-color 0.15s;
	}
	button:hover:not(:disabled) {
		border-color: var(--rule);
		background: var(--surface-hover);
	}
	button[aria-pressed='true'] {
		border-color: var(--accent);
		background: var(--accent);
		color: var(--accent-text);
	}
	button:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
	}
	button:disabled {
		cursor: default;
	}
	.err {
		color: var(--error);
	}
	@media print {
		.helpful {
			display: none;
		}
	}
</style>
