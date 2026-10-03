<script lang="ts">
	// A confirm step for deletes: a modal <dialog> in the ledger look.
	// Call open() from the parent; onconfirm runs on the destructive button.
	import type { Snippet } from 'svelte';

	let {
		title,
		confirmLabel = 'Delete',
		busyLabel = 'Deleting',
		onconfirm,
		children
	}: {
		title: string;
		confirmLabel?: string;
		busyLabel?: string;
		onconfirm: () => Promise<void> | void;
		children?: Snippet;
	} = $props();

	let dialog = $state<HTMLDialogElement>();
	let busy = $state(false);
	let error = $state('');
	const uid = $props.id();

	export function open() {
		error = '';
		dialog?.showModal();
	}

	export function close() {
		dialog?.close();
	}

	async function confirm() {
		if (busy) return;
		busy = true;
		error = '';
		try {
			await onconfirm();
			dialog?.close();
		} catch (e) {
			error = e instanceof Error ? e.message : String(e);
		} finally {
			busy = false;
		}
	}
</script>

<dialog bind:this={dialog} class="confirm" aria-labelledby="{uid}-t" onclick={(e) => e.target === dialog && !busy && dialog?.close()}>
	<div class="box">
		<h3 id="{uid}-t">{title}</h3>
		{#if children}<div class="body">{@render children()}</div>{/if}
		{#if error}<p class="notice error-text" role="alert">{error}</p>{/if}
		<div class="btn-row">
			<button type="button" class="btn danger" onclick={confirm} disabled={busy}>{busy ? busyLabel : confirmLabel}</button>
			<!-- svelte-ignore a11y_autofocus -->
			<button type="button" class="btn secondary" onclick={() => dialog?.close()} disabled={busy} autofocus>Keep it</button>
		</div>
	</div>
</dialog>

<style>
	.confirm {
		padding: 0;
		border: 1px solid var(--rule);
		border-top: 3px solid var(--accent);
		border-radius: 0;
		background: var(--surface);
		color: var(--text);
		width: min(440px, calc(100vw - 32px));
		box-shadow: none;
	}
	.confirm::backdrop {
		background: rgb(3 44 60 / 0.55);
	}
	.box {
		padding: 22px 24px;
	}
	h3 {
		margin: 0 0 10px;
		font: 300 1.35rem/1.25 var(--serif);
	}
	.body {
		margin: 0 0 18px;
		font-size: 0.95rem;
		color: var(--muted);
	}
	.body :global(p) {
		margin: 0 0 8px;
	}
	.btn.danger {
		background: var(--error);
		border-color: var(--error);
		color: #fff;
	}
	:global(:root[data-theme='dark']) .btn.danger {
		color: var(--ink);
	}
	@media (prefers-color-scheme: dark) {
		:global(:root:not([data-theme='light'])) .btn.danger {
			color: var(--ink);
		}
	}
</style>
