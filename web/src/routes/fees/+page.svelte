<script lang="ts">
	// A4: fee estimator from published formulas only: the electrical permit
	// form's line items and the Fire Department's 0.15% review fee. The
	// building permit schedule is not published online, so this page says so
	// and gives no figure for it. Every figure is labeled an estimate.
	import Header from '$lib/components/Header.svelte';
	import PublicToolNav from '$lib/components/PublicToolNav.svelte';
	import {
		money,
		parseDollars,
		publicApi,
		telHref,
		type FeeEstimate,
		type FeeItem,
		type FeeSchedule
	} from '$lib/components/PublicData';

	let schedule = $state<FeeSchedule | null>(null);
	let error = $state('');
	let costText = $state('');
	let occupancy = $state('single_family');
	let qty = $state<Record<string, number | null | undefined>>({});
	let est = $state<FeeEstimate | null>(null);
	let seq = 0;
	let timer: ReturnType<typeof setTimeout> | undefined;

	const cost = $derived(parseDollars(costText));
	const costInvalid = $derived(costText.trim() !== '' && cost === null);
	const items = $derived(
		Object.fromEntries(
			Object.entries(qty).filter(
				(e): e is [string, number] => typeof e[1] === 'number' && Number.isInteger(e[1]) && e[1] > 0 && e[1] <= 10000
			)
		)
	);
	const groups = $derived.by(() => {
		const out: { name: string; items: FeeItem[] }[] = [];
		for (const it of schedule?.electrical.items ?? []) {
			const g = out.find((x) => x.name === it.group);
			if (g) g.items.push(it);
			else out.push({ name: it.group, items: [it] });
		}
		return out;
	});

	$effect(() => {
		publicApi
			.fees()
			.then((s) => (schedule = s))
			.catch((e) => (error = e instanceof Error ? e.message : String(e)));
	});

	// Recompute on the server (one source of truth for the formulas), shortly after typing stops.
	$effect(() => {
		const body = {
			electrical: { occupancy: occupancy || null, items },
			...(cost !== null ? { life_safety: { construction_cost: cost } } : {})
		};
		if (!schedule) return;
		clearTimeout(timer);
		timer = setTimeout(async () => {
			const mine = ++seq;
			try {
				const r = await publicApi.estimate(body);
				if (mine === seq) {
					est = r;
					error = '';
				}
			} catch (e) {
				if (mine === seq) error = e instanceof Error ? e.message : String(e);
			}
		}, 200);
		return () => clearTimeout(timer);
	});

	function reset() {
		qty = {};
		costText = '';
		occupancy = 'single_family';
	}
</script>

<svelte:head>
	<title>Fee estimator | Waterville Codes RAG</title>
</svelte:head>

<Header title="Fee estimator" compact>
	{#snippet actions()}
		<a class="theme-toggle" href="/">Ask a question</a>
	{/snippet}
</Header>
<main class="wrap fees">
	<div class="page-head">
		<p class="page-lede">
			Estimates from the fee formulas the city publishes on its forms.
		</p>
	</div>

	{#if error}<p class="notice error-text" role="alert">{error}</p>{/if}

	{#if schedule}
		<section class="sheet accent building" aria-labelledby="bldg">
			<h2 id="bldg">Building permit fee: not published online</h2>
			<p>{schedule.building.note}</p>
			<blockquote>
				<p>"{schedule.building.quote}"</p>
				<footer>
					<a href={schedule.building.url} target="_blank" rel="noopener">Waterville City Code {schedule.building.citation}</a>
				</footer>
			</blockquote>
			<p class="btn-row">
				<a class="btn" href={telHref(schedule.office_phone)}>Call Code Enforcement, {schedule.office_phone}</a>
			</p>
		</section>

		<div class="cols">
			<section class="sheet" aria-labelledby="lsr">
				<h2 id="lsr">{schedule.life_safety.title}</h2>
				<p class="muted small">{schedule.life_safety.formula}</p>
				<label class="field">
					<span>Adjusted construction cost</span>
					<input
						class="input"
						inputmode="decimal"
						autocomplete="off"
						placeholder="$0"
						bind:value={costText}
						aria-invalid={costInvalid}
						aria-describedby="lsr-help"
					/>
					<span class="help" id="lsr-help">{schedule.life_safety.excludes}</span>
				</label>
				{#if costInvalid}<p class="error-text small" role="alert">Enter a dollar amount, like 25000 or $25,000.</p>{/if}
				<div class="figure" aria-live="polite">
					<span class="tag-pill">Estimate</span>
					<span class="amount">{est?.life_safety ? money(est.life_safety.estimate_cents) : '$0.00'}</span>
					<span class="muted small">review fee at 0.15%</span>
				</div>
				<p class="small">
					Source: <a href={schedule.life_safety.source_url} target="_blank" rel="noopener">{schedule.life_safety.source}</a>.
					<a href="/permits">Does the review apply to my project?</a>
				</p>
			</section>

			<section class="sheet" aria-labelledby="elec">
				<h2 id="elec">{schedule.electrical.title}</h2>
				<p class="muted small">{schedule.electrical.scope}</p>

				<fieldset class="occupancy">
					<legend class="field-label">Minimum fee</legend>
					{#each schedule.electrical.minimum as m (m.id)}
						<label class="check">
							<input type="radio" name="occupancy" value={m.id} bind:group={occupancy} />
							<span>{m.label}, {money(m.cents)} minimum</span>
						</label>
					{/each}
					<label class="check">
						<input type="radio" name="occupancy" value="" bind:group={occupancy} />
						<span>None of these</span>
					</label>
				</fieldset>

				{#each groups as g (g.name)}
					<fieldset class="items">
						<legend class="field-label">{g.name}</legend>
						{#each g.items as it (it.id)}
							<label class="item">
								<span class="item-label">{it.label}<small>{money(it.cents)}</small></span>
								<input
									class="input qty"
									type="number"
									min="0"
									max="10000"
									step="1"
									inputmode="numeric"
									placeholder="0"
									aria-label="{it.label}: how many"
									bind:value={qty[it.id]}
								/>
							</label>
						{/each}
					</fieldset>
				{/each}
			</section>
		</div>

		{#if est?.electrical}
			{@const e = est.electrical}
			<section class="sheet accent total" aria-labelledby="elec-total" aria-live="polite">
				<h2 id="elec-total">Electrical permit estimate</h2>
				<div class="table-scroll">
					<table class="ledger">
						<thead>
							<tr><th scope="col">Item</th><th scope="col" class="num">Qty</th><th scope="col" class="num">Each</th><th scope="col" class="num">Estimate</th></tr>
						</thead>
						<tbody>
							{#each e.lines as l (l.id)}
								<tr><td>{l.label}</td><td class="num">{l.qty}</td><td class="num">{money(l.unit_cents)}</td><td class="num">{money(l.cents)}</td></tr>
							{:else}
								<tr><td colspan="4" class="muted">No line items yet. Enter how many of each item above.</td></tr>
							{/each}
							<tr class="sub"><td colspan="3">Line items</td><td class="num">{money(e.subtotal_cents)}</td></tr>
							{#if e.minimum}
								<tr class="sub"><td colspan="3">Minimum fee: {e.minimum.label}</td><td class="num">{money(e.minimum.cents)}</td></tr>
							{/if}
						</tbody>
					</table>
				</div>
				<div class="figure">
					<span class="tag-pill">Estimate</span>
					<span class="amount">{money(e.estimate_cents)}</span>
					<span class="muted small">{e.basis === 'minimum' ? 'the minimum fee applies' : 'from the line items'}</span>
				</div>
				<p class="muted small">{schedule.electrical.minimum_note}</p>
				<p class="small">
					Source: <a href={schedule.electrical.source_url} target="_blank" rel="noopener">{schedule.electrical.source}</a>.
				</p>
			</section>
		{/if}

		<section class="sheet" aria-labelledby="other">
			<h2 id="other">Other fees printed in the City Code</h2>
			<table class="ledger">
				<tbody>
					{#each schedule.fixed as f (f.label)}
						<tr>
							<td>{f.label}</td>
							<td class="num">{money(f.cents)}</td>
							<td><a href={f.url} target="_blank" rel="noopener">{f.citation}</a></td>
						</tr>
					{/each}
				</tbody>
			</table>
			<p class="small"><strong>Work started before the permit.</strong> {schedule.after_the_fact}</p>
		</section>

		<p class="confirm">
			Code Enforcement sets the fee when you apply: {schedule.office_phone}.
		</p>
		<p class="btn-row no-print">
			<button type="button" class="btn secondary" onclick={reset}>Clear</button>
			<button type="button" class="btn secondary" onclick={() => window.print()}>Print</button>
		</p>
	{:else if !error}
		<p class="muted">Loading the fee formulas...</p>
	{/if}
</main>

<PublicToolNav />

<style>
	.sheet h2 {
		font: 300 1.3rem/1.3 var(--serif);
		margin: 0 0 10px;
	}
	.building blockquote {
		margin: 12px 0;
		padding: 10px 14px;
		background: var(--bg);
		border-left: 3px solid var(--rule);
		font: 400 1rem/1.55 var(--serif);
	}
	.building blockquote p {
		margin: 0 0 6px;
	}
	.building blockquote footer {
		font: 600 0.85rem var(--sans);
	}
	.cols {
		display: grid;
		gap: 20px;
		margin: 20px 0;
		align-items: start;
	}
	.cols > .sheet + .sheet {
		margin-top: 0;
	}
	@media (min-width: 960px) {
		.cols {
			grid-template-columns: 2fr 3fr;
		}
	}
	.small {
		font-size: 0.85rem;
	}
	.figure {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: 6px 12px;
		margin: 6px 0 12px;
		padding: 10px 0;
		border-top: 1px solid var(--border);
		border-bottom: 1px solid var(--border);
	}
	.amount {
		font: 300 2rem/1.1 var(--serif);
		color: var(--text);
	}
	fieldset {
		margin: 0 0 14px;
		padding: 0;
		border: 0;
		min-width: 0;
	}
	fieldset legend {
		margin-bottom: 6px;
		padding: 0;
	}
	.occupancy .check {
		margin-bottom: 6px;
	}
	.items {
		border-top: 1px solid var(--border);
		padding-top: 10px;
	}
	.item {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 12px;
		padding: 4px 0;
	}
	.item-label {
		font-size: 0.92rem;
		min-width: 0;
	}
	.item-label small {
		display: block;
		color: var(--muted);
		font-size: 0.8rem;
	}
	.qty {
		width: 88px;
		flex: none;
		text-align: right;
		padding: 6px 8px;
	}
	.num {
		text-align: right;
		white-space: nowrap;
	}
	.total .sub td {
		font-weight: 600;
		background: var(--bg);
	}
	.total {
		margin-bottom: 20px;
	}
	.confirm {
		margin: 20px 0 16px;
		padding: 12px 14px;
		border: 1px solid var(--accent);
		background: var(--surface);
		font-weight: 600;
	}
</style>
