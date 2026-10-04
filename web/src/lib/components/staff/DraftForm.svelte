<script lang="ts">
	// The fields of a draft template, in sections. Bind `values`; `onchange`
	// runs after every edit so the parent can refresh the preview. A field
	// marked `ai` gets a "Draft with AI" button that calls `onai(name)`.
	import { isRequired, sections, type DraftField } from './DraftData';

	let {
		fields,
		values = $bindable({}),
		missing = [],
		onchange,
		onai,
		aiBusy = '',
		aiNote = ''
	}: {
		fields: DraftField[];
		values?: Record<string, string>;
		missing?: string[];
		onchange?: () => void;
		onai?: (name: string) => void;
		aiBusy?: string;
		aiNote?: string;
	} = $props();

	const uid = $props.id();
	const groups = $derived(sections(fields));
	const missingSet = $derived(new Set(missing));

	function set(name: string, v: string) {
		values[name] = v;
		onchange?.();
	}
</script>

<div class="draft-form">
	{#each groups as g (g.section)}
		<fieldset>
			<legend>{g.section}</legend>
			{#each g.fields as f (f.name)}
				{@const id = `${uid}-${f.name}`}
				{@const req = isRequired(f, values)}
				{@const gap = missingSet.has(f.name)}
				<div class="field" class:gap id="field-{f.name}">
					<div class="label-row">
						<label for={id}>
							{f.label}{#if req}<span class="req" aria-hidden="true"> *</span><span class="sr-only"> (required)</span>{/if}
						</label>
						{#if f.ai && onai}
							<button
								type="button"
								class="btn secondary small ai"
								onclick={() => onai?.(f.name)}
								disabled={!!aiBusy}
								aria-describedby="{id}-ai"
							>
								{aiBusy === f.name ? 'Drafting' : 'Draft with AI'}
							</button>
						{/if}
					</div>
					{#if f.kind === 'textarea'}
						<textarea
							{id}
							rows={f.rows ?? 4}
							value={values[f.name] ?? ''}
							oninput={(e) => set(f.name, e.currentTarget.value)}
							aria-invalid={gap || undefined}
						></textarea>
					{:else if f.kind === 'select'}
						<select {id} value={values[f.name] ?? ''} onchange={(e) => set(f.name, e.currentTarget.value)} aria-invalid={gap || undefined}>
							<option value="">Choose</option>
							{#each f.options ?? [] as o (o.value)}
								<option value={o.value}>{o.label}</option>
							{/each}
						</select>
					{:else}
						<input
							{id}
							type={f.kind === 'date' ? 'date' : 'text'}
							inputmode={f.kind === 'number' ? 'decimal' : undefined}
							value={values[f.name] ?? ''}
							oninput={(e) => set(f.name, e.currentTarget.value)}
							aria-invalid={gap || undefined}
						/>
					{/if}
					{#if f.help}<span class="help">{f.help}</span>{/if}
					{#if f.ai && onai}
						<span class="help ai-help" id="{id}-ai">{aiNote || 'Drafts this field from the case notes.'}</span>
					{/if}
				</div>
			{/each}
		</fieldset>
	{/each}
</div>

<style>
	fieldset {
		margin: 0 0 20px;
		padding: 16px 18px 2px;
		border: 1px solid var(--rule);
		background: var(--surface);
		min-width: 0;
	}
	legend {
		padding: 0 8px;
		margin-left: -8px;
		font: 600 0.78rem var(--sans);
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: var(--accent);
	}
	.field {
		min-width: 0;
	}
	.field input,
	.field select,
	.field textarea {
		background: var(--bg);
	}
	.label-row {
		display: flex;
		justify-content: space-between;
		align-items: flex-end;
		gap: 10px;
	}
	.label-row label {
		font: 600 0.85rem var(--sans);
	}
	.req {
		color: var(--accent);
	}
	.gap textarea,
	.gap input,
	.gap select {
		border-color: var(--error);
	}
	.ai {
		flex: none;
	}
	.ai-help {
		font-style: italic;
	}
	textarea {
		font-family: var(--serif);
	}
</style>
