<script lang="ts">
	// Project facts for the gate checklist. Binds `input`; calls onsubmit.
	import { FLAG_GROUPS, toCount, type GateInput, type GateOptions } from './GateData';

	let {
		input = $bindable(),
		options,
		busy = false,
		onsubmit,
		onreset
	}: {
		input: GateInput;
		options: GateOptions | null;
		busy?: boolean;
		onsubmit: () => void;
		onreset: () => void;
	} = $props();

	const uid = $props.id();
	const residential = $derived(input.use === 'one_two_family' || input.use === 'multifamily');

	function num(key: 'units' | 'footprint' | 'impervious' | 'construction_cost', e: Event) {
		input[key] = toCount((e.currentTarget as HTMLInputElement).value);
	}
</script>

<form
	class="sheet accent gate-form"
	aria-label="Project facts"
	onsubmit={(e) => {
		e.preventDefault();
		onsubmit();
	}}
>
	<fieldset>
		<legend>Project</legend>
		<label class="field" for="{uid}-type">
			<span>Type of project</span>
			<select id="{uid}-type" bind:value={input.project_type} disabled={!options}>
				{#each options?.project_types ?? [] as o (o.value)}<option value={o.value}>{o.label}</option>{/each}
			</select>
		</label>
		<label class="field" for="{uid}-use">
			<span>Use after the project</span>
			<select id="{uid}-use" bind:value={input.use} disabled={!options}>
				{#each options?.uses ?? [] as o (o.value)}<option value={o.value}>{o.label}</option>{/each}
			</select>
		</label>
		<!-- Stacked: district names are long and a half-width select cuts them off. -->
		<div>
			<label class="field" for="{uid}-district">
				<span>Zoning district</span>
				<select id="{uid}-district" bind:value={input.district} disabled={!options}>
					{#each options?.districts ?? [] as o (o.value)}<option value={o.value}>{o.label}</option>{/each}
				</select>
			</label>
			{#if residential}
				<label class="field" for="{uid}-units">
					<span>Dwelling units</span>
					<input id="{uid}-units" type="number" min="0" step="1" inputmode="numeric" value={input.units} oninput={(e) => num('units', e)} />
				</label>
			{/if}
		</div>
	</fieldset>

	<fieldset>
		<legend>Size and cost</legend>
		<div class="two">
			<label class="field" for="{uid}-fp">
				<span>New footprint (sq ft)</span>
				<input id="{uid}-fp" type="number" min="0" step="1" inputmode="numeric" value={input.footprint} oninput={(e) => num('footprint', e)} />
				<span class="help">Of the new building or addition</span>
			</label>
			<label class="field" for="{uid}-imp">
				<span>New impervious area (sq ft)</span>
				<input id="{uid}-imp" type="number" min="0" step="1" inputmode="numeric" value={input.impervious} oninput={(e) => num('impervious', e)} />
				<span class="help">Paving, parking, roofs not in the footprint</span>
			</label>
		</div>
		<label class="field" for="{uid}-cost">
			<span>Construction cost ($)</span>
			<input id="{uid}-cost" type="number" min="0" step="1" inputmode="numeric" value={input.construction_cost} oninput={(e) => num('construction_cost', e)} />
		</label>
	</fieldset>

	<fieldset>
		<legend>Historic status</legend>
		<label class="field" for="{uid}-hist">
			<span>Historic preservation</span>
			<select id="{uid}-hist" bind:value={input.historic} disabled={!options}>
				{#each options?.historic ?? [] as o (o.value)}<option value={o.value}>{o.label}</option>{/each}
			</select>
		</label>
		{#if input.historic !== 'none'}
			<label class="check">
				<input type="checkbox" bind:checked={input.visible_from_street} />
				<span>Work visible from the street or public land</span>
			</label>
		{/if}
	</fieldset>

	{#each FLAG_GROUPS as g (g.title)}
		<fieldset>
			<legend>{g.title}</legend>
			{#each g.flags as f (f.key)}
				<label class="check">
					<input type="checkbox" bind:checked={input[f.key]} />
					<span>{f.label}{#if f.help}<span class="help"> {f.help}</span>{/if}</span>
				</label>
			{/each}
		</fieldset>
	{/each}

	<div class="btn-row">
		<button type="submit" class="btn" disabled={busy || !options}>{busy ? 'Checking' : 'Check gates'}</button>
		<button type="button" class="btn secondary" onclick={onreset}>Clear</button>
	</div>
</form>

<style>
	fieldset {
		margin: 0 0 16px;
		padding: 0 0 14px;
		border: 0;
		border-bottom: 1px solid var(--border);
		min-width: 0;
	}
	legend {
		padding: 0;
		margin-bottom: 10px;
		font: 600 0.78rem var(--sans);
		text-transform: uppercase;
		letter-spacing: 0.06em;
		color: var(--accent);
	}
	.two {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 12px;
	}
	.check {
		margin-bottom: 8px;
		font: 0.92rem/1.4 var(--sans);
	}
	.check .help {
		display: block;
		font-size: 0.8rem;
		color: var(--muted);
	}
	.field .help {
		font-size: 0.78rem;
	}
	@media (max-width: 400px) {
		.two {
			grid-template-columns: 1fr;
		}
	}
</style>
