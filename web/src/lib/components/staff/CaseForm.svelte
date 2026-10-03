<script lang="ts">
	// Create or edit a case: address, map/lot, owner, type tags, status, summary.
	import { untrack } from 'svelte';
	import { ApiError } from '$lib/api';
	import { STATUSES, TAGS, emptyCase, type CaseFields } from './CaseData';

	let {
		initial = emptyCase(),
		heading,
		submitLabel = 'Save case',
		busyLabel = 'Saving',
		onsubmit,
		oncancel
	}: {
		initial?: CaseFields;
		heading?: string;
		submitLabel?: string;
		busyLabel?: string;
		onsubmit: (fields: CaseFields) => Promise<void>;
		oncancel?: () => void;
	} = $props();

	const start = untrack(() => initial);
	let f = $state<CaseFields>({ ...start, tags: [...start.tags] });
	let busy = $state(false);
	let error = $state('');
	const uid = $props.id();

	function toggle(tag: CaseFields['tags'][number], on: boolean) {
		f.tags = on ? [...f.tags, tag] : f.tags.filter((t) => t !== tag);
	}

	async function submit(e: SubmitEvent) {
		e.preventDefault();
		if (busy) return;
		if (!f.address.trim()) {
			error = 'Enter the property address.';
			return;
		}
		busy = true;
		error = '';
		try {
			await onsubmit({ ...f, tags: TAGS.map((t) => t.value).filter((t) => f.tags.includes(t)) });
		} catch (err) {
			error =
				err instanceof ApiError && err.status === 422
					? 'Check the fields: the address is required and each field has a length limit.'
					: err instanceof Error
						? err.message
						: String(err);
		} finally {
			busy = false;
		}
	}
</script>

<form class="sheet accent case-form" onsubmit={submit} aria-labelledby={heading ? `${uid}-h` : undefined}>
	{#if heading}<h3 id="{uid}-h" class="form-heading">{heading}</h3>{/if}
	<div class="grid">
		<label class="field wide">
			<span>Property address</span>
			<input name="address" required maxlength="200" autocomplete="off" bind:value={f.address} placeholder="12 Main Street" />
		</label>
		<label class="field">
			<span>Map/lot</span>
			<input name="map_lot" maxlength="64" autocomplete="off" bind:value={f.map_lot} placeholder="041-112" />
		</label>
		<label class="field">
			<span>Owner</span>
			<input name="owner" maxlength="200" autocomplete="off" bind:value={f.owner} placeholder="From the registry deed" />
		</label>
		<label class="field wide">
			<span>Case title <span class="opt">optional</span></span>
			<input name="title" maxlength="200" autocomplete="off" bind:value={f.title} placeholder="Shed inside the side setback" />
		</label>
	</div>

	<fieldset class="field tags">
		<legend class="field-label">Type</legend>
		<div class="tag-grid">
			{#each TAGS as t (t.value)}
				<label class="tag-check">
					<input
						type="checkbox"
						name="tags"
						value={t.value}
						checked={f.tags.includes(t.value)}
						onchange={(e) => toggle(t.value, e.currentTarget.checked)}
					/>
					<span>{t.label}</span>
				</label>
			{/each}
		</div>
	</fieldset>

	<fieldset class="field status">
		<legend class="field-label">Status</legend>
		<div class="seg" role="radiogroup">
			{#each STATUSES as s (s.value)}
				<label class:on={f.status === s.value}>
					<input type="radio" name="{uid}-status" value={s.value} bind:group={f.status} />
					<span>{s.label}</span>
				</label>
			{/each}
		</div>
	</fieldset>

	<label class="field">
		<span>Summary <span class="opt">optional</span></span>
		<textarea name="summary" maxlength="4000" rows="3" bind:value={f.summary} placeholder="What was reported, what you found, what happens next."></textarea>
	</label>

	{#if error}<p class="notice error-text" role="alert">{error}</p>{/if}
	<div class="btn-row">
		<button type="submit" class="btn" disabled={busy}>{busy ? busyLabel : submitLabel}</button>
		{#if oncancel}<button type="button" class="btn secondary" onclick={oncancel} disabled={busy}>Cancel</button>{/if}
	</div>
</form>

<style>
	.case-form {
		margin-bottom: 24px;
	}
	.form-heading {
		font: 300 1.35rem/1.25 var(--serif) !important;
		margin: 0 0 16px !important;
	}
	.grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 0 16px;
	}
	.wide {
		grid-column: 1 / -1;
	}
	.opt {
		font-weight: 400;
		color: var(--muted);
		margin-left: 4px;
	}
	fieldset {
		border: 0;
		padding: 0;
		margin: 0 0 16px;
		min-width: 0;
	}
	legend {
		padding: 0;
		margin-bottom: 6px;
	}
	.tag-grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(190px, 1fr));
		border-top: 1px solid var(--border);
		border-left: 1px solid var(--border);
	}
	.tag-check {
		display: flex;
		align-items: center;
		gap: 10px;
		padding: 8px 12px;
		border-right: 1px solid var(--border);
		border-bottom: 1px solid var(--border);
		font: 400 0.92rem var(--sans);
		cursor: pointer;
		background: var(--surface);
	}
	.tag-check:has(input:checked) {
		background: var(--bg);
		box-shadow: inset 3px 0 0 var(--accent);
		font-weight: 600;
	}
	.tag-check input {
		accent-color: var(--accent);
		margin: 0;
	}
	.seg {
		display: inline-flex;
		border: 1px solid var(--rule);
	}
	.seg label {
		position: relative;
		cursor: pointer;
		padding: 7px 16px;
		font: 500 0.9rem var(--sans);
		border-right: 1px solid var(--rule);
		background: var(--surface);
	}
	.seg label:last-child {
		border-right: 0;
	}
	.seg input {
		position: absolute;
		opacity: 0;
		inset: 0;
		margin: 0;
		cursor: pointer;
	}
	.seg label.on {
		background: var(--text);
		color: var(--bg);
		font-weight: 600;
	}
	.seg label:has(input:focus-visible) {
		outline: 2px solid var(--accent);
		outline-offset: -2px;
	}
	@media (max-width: 640px) {
		.grid {
			grid-template-columns: 1fr;
		}
		.tag-grid {
			grid-template-columns: 1fr 1fr;
		}
		.tag-check {
			padding: 8px 10px;
			font-size: 0.86rem;
		}
	}
</style>
