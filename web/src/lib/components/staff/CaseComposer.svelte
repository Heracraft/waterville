<script lang="ts">
	// Adds a note or a deadline to a case. Saved answers come from the research
	// desk and deadlines usually from the calculator; this covers the rest.
	import { ApiError } from '$lib/api';
	import { cases, todayYmd, type CaseItem, type NewItem } from './CaseData';

	let { caseId, onadded }: { caseId: string; onadded: (item: CaseItem) => void } = $props();

	type Tab = 'note' | 'deadline';
	let tab = $state<Tab>('note');
	let text = $state('');
	let label = $state('');
	let date = $state('');
	let citation = $state('');
	let busy = $state(false);
	let error = $state('');
	const uid = $props.id();

	function select(t: Tab) {
		tab = t;
		error = '';
	}

	function onTabKey(e: KeyboardEvent) {
		if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
		e.preventDefault();
		select(tab === 'note' ? 'deadline' : 'note');
		document.getElementById(`${uid}-tab-${tab}`)?.focus();
	}

	async function submit(e: SubmitEvent) {
		e.preventDefault();
		if (busy) return;
		let body: NewItem;
		if (tab === 'note') {
			if (!text.trim()) return void (error = 'Write the note first.');
			body = { kind: 'note', text };
		} else {
			if (!label.trim() || !date) return void (error = 'A deadline needs a label and a date.');
			body = { kind: 'deadline', label, date, citation };
		}
		busy = true;
		error = '';
		try {
			const item = await cases.addItem(caseId, body);
			onadded(item);
			if (tab === 'note') text = '';
			else label = date = citation = '';
		} catch (err) {
			error = err instanceof ApiError && err.status === 422 ? 'Check the fields and try again.' : err instanceof Error ? err.message : String(err);
		} finally {
			busy = false;
		}
	}
</script>

<form class="composer no-print" onsubmit={submit}>
	<div class="tabs" role="tablist" aria-label="Add to the case">
		{#each [['note', 'Note'], ['deadline', 'Deadline']] as [value, name] (value)}
			<button
				type="button"
				role="tab"
				id="{uid}-tab-{value}"
				aria-selected={tab === value}
				aria-controls="{uid}-panel"
				tabindex={tab === value ? 0 : -1}
				onclick={() => select(value as Tab)}
				onkeydown={onTabKey}>Add {name.toLowerCase()}</button
			>
		{/each}
	</div>
	<div class="panel-body" role="tabpanel" id="{uid}-panel" aria-labelledby="{uid}-tab-{tab}">
		{#if tab === 'note'}
			<label class="field">
				<span class="sr-only">Note</span>
				<textarea name="note" rows="3" maxlength="20000" bind:value={text} placeholder="Site visit, phone call, what the owner said, what you saw."></textarea>
			</label>
		{:else}
			<div class="dl-grid">
				<label class="field">
					<span>What is due</span>
					<input name="label" maxlength="300" bind:value={label} placeholder="Compliance deadline in the first notice" />
				</label>
				<label class="field">
					<span>Date</span>
					<input name="date" type="date" min="2000-01-01" bind:value={date} placeholder={todayYmd()} />
				</label>
				<label class="field">
					<span>Citation</span>
					<input name="citation" maxlength="300" bind:value={citation} placeholder="§ 205-7" />
				</label>
			</div>
			<p class="help">The <a href="/staff/deadlines">deadline calculator</a> adds clocks with their citations for you.</p>
		{/if}
		{#if error}<p class="notice error-text" role="alert">{error}</p>{/if}
		<button type="submit" class="btn" disabled={busy}>{busy ? 'Adding' : tab === 'note' ? 'Add note' : 'Add deadline'}</button>
	</div>
</form>

<style>
	.composer {
		margin: 0 0 28px;
		border: 1px solid var(--rule);
		background: var(--surface);
	}
	.tabs {
		display: flex;
		border-bottom: 1px solid var(--rule);
		background: var(--bg);
	}
	.tabs button {
		cursor: pointer;
		border: 0;
		border-right: 1px solid var(--rule);
		border-top: 3px solid transparent;
		background: transparent;
		color: var(--muted);
		font: 500 0.88rem var(--sans);
		padding: 8px 16px 9px;
	}
	.tabs button[aria-selected='true'] {
		border-top-color: var(--accent);
		background: var(--surface);
		color: var(--text);
		font-weight: 600;
		margin-bottom: -1px;
		padding-bottom: 10px;
	}
	.tabs button:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: -2px;
	}
	.panel-body {
		padding: 16px;
	}
	.panel-body .field {
		margin-bottom: 12px;
	}
	.dl-grid {
		display: grid;
		grid-template-columns: 2fr 1fr 1fr;
		gap: 0 12px;
	}
	.help {
		margin: 0 0 12px;
		font-size: 0.85rem;
		color: var(--muted);
	}
	.help a {
		color: inherit;
		text-decoration-color: var(--accent);
	}
	.sr-only {
		position: absolute;
		width: 1px;
		height: 1px;
		overflow: hidden;
		clip-path: inset(50%);
		white-space: nowrap;
	}
	@media (max-width: 640px) {
		.dl-grid {
			grid-template-columns: 1fr 1fr;
		}
		.dl-grid .field:first-child {
			grid-column: 1 / -1;
		}
	}
</style>
