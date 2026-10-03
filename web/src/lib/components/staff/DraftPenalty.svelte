<script lang="ts">
	// Penalty computation helper for the Rule 80K packet: tier, inclusive
	// days and the range for the span, computed by the server
	// (POST /api/staff/drafts/penalty) from 30-A M.R.S. § 4452(3) and § 205-8.
	// With `onapply`, "Use in this draft" copies the inputs into the draft fields.
	import { drafts, money, type PenaltyResult, type PenaltyTier } from './DraftData';

	let {
		tier = '',
		start = '',
		end = '',
		perDay = '',
		onapply
	}: {
		tier?: string;
		start?: string;
		end?: string;
		perDay?: string;
		onapply?: (v: { penalty_tier: string; violation_start: string; violation_end: string; penalty_per_day: string }) => void;
	} = $props();

	const uid = $props.id();
	let tiers = $state<PenaltyTier[]>([]);
	// Local copies so the helper can be used without touching the draft.
	let t = $state('');
	let a = $state('');
	let b = $state('');
	let pd = $state('');
	let result = $state<PenaltyResult | null>(null);
	let error = $state('');
	let seeded = false;

	$effect(() => {
		drafts
			.penaltyTiers()
			.then((r) => (tiers = r.tiers))
			.catch((e) => (error = e instanceof Error ? e.message : String(e)));
	});

	// Seed from the draft once, when the helper opens.
	$effect(() => {
		if (seeded) return;
		seeded = true;
		t = tier;
		a = start;
		b = end;
		pd = perDay;
	});

	let timer: ReturnType<typeof setTimeout> | undefined;
	$effect(() => {
		const body = { tier: t, start: a || undefined, end: b || undefined, per_day: pd || undefined };
		clearTimeout(timer);
		if (!body.tier) {
			result = null;
			return;
		}
		timer = setTimeout(() => {
			drafts
				.penalty(body)
				.then((r) => {
					result = r;
					error = '';
				})
				.catch((e) => (error = e instanceof Error ? e.message : String(e)));
		}, 200);
	});
</script>

<section class="penalty sheet" aria-labelledby="{uid}-h">
	<h3 id="{uid}-h">Penalty computation</h3>
	<div class="grid">
		<label class="field wide" for="{uid}-tier">
			<span>Tier</span>
			<select id="{uid}-tier" bind:value={t}>
				<option value="">Choose a tier</option>
				{#each tiers as x (x.value)}<option value={x.value}>{x.label}</option>{/each}
			</select>
		</label>
		<label class="field" for="{uid}-a"><span>First day counted</span><input id="{uid}-a" type="date" bind:value={a} /></label>
		<label class="field" for="{uid}-b"><span>Last day counted</span><input id="{uid}-b" type="date" bind:value={b} /></label>
		<label class="field" for="{uid}-pd"><span>Per day to request</span><input id="{uid}-pd" inputmode="decimal" bind:value={pd} placeholder="Optional" /></label>
	</div>

	{#if error}<p class="notice error-text" role="alert">{error}</p>{/if}

	{#if result}
		<dl class="out" aria-live="polite">
			<div><dt>Per day</dt><dd>{result.min_per_day === result.max_per_day ? money(result.min_per_day) : `${money(result.min_per_day)} to ${money(result.max_per_day)}`}</dd></div>
			<div><dt>Days, inclusive</dt><dd>{result.days ?? 'Enter both dates'}</dd></div>
			<div><dt>Range for the span</dt><dd>{result.days ? `${money(result.min_total)} to ${money(result.max_total)}` : 'Not yet'}</dd></div>
			{#if result.requested_total != null}<div><dt>Requested</dt><dd>{money(result.requested_total)}</dd></div>{/if}
		</dl>
		<p class="cite">{result.cite}</p>
		{#each result.warnings as w (w)}<p class="notice error-text">{w}</p>{/each}
		{#if result.verify}<p class="notice verify">{result.verify}</p>{/if}
		<p class="muted small">{result.note}</p>
	{/if}

	{#if onapply}
		<button
			type="button"
			class="btn secondary small"
			disabled={!t}
			onclick={() => onapply?.({ penalty_tier: t, violation_start: a, violation_end: b, penalty_per_day: pd })}>Use in this draft</button
		>
	{/if}
</section>

<style>
	.penalty h3 {
		margin-bottom: 14px;
	}
	.grid {
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
		gap: 0 14px;
	}
	.wide {
		grid-column: 1 / -1;
	}
	.out {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
		margin: 0 0 12px;
		border: 1px solid var(--rule);
		background: var(--bg);
	}
	.out div {
		padding: 10px 12px;
		border-right: 1px solid var(--border);
	}
	.out div:last-child {
		border-right: 0;
	}
	dt {
		font: 600 0.72rem var(--sans);
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: var(--muted);
	}
	dd {
		margin: 4px 0 0;
		font: 600 1.05rem var(--sans);
		font-variant-numeric: tabular-nums;
	}
	.cite {
		margin: 0 0 10px;
		font: 600 0.85rem var(--sans);
		color: var(--accent);
	}
	.verify {
		background: var(--hl);
	}
	.small {
		font-size: 0.82rem;
	}
	@media (max-width: 640px) {
		.grid {
			grid-template-columns: 1fr;
		}
	}
</style>
