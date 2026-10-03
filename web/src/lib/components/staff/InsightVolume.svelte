<script lang="ts">
	// Question volume per day (per week past 90 days): answered and not answered,
	// stacked. Hover or focus a bar for its numbers; the table below holds them all.
	import { bucket, type DayCount } from './InsightData';

	let { volume }: { volume: DayCount[] } = $props();

	const bars = $derived(bucket(volume));
	const max = $derived(Math.max(1, ...bars.map((b) => b.answered + b.unanswered)));
	const step = $derived(niceStep(max));
	const top = $derived(Math.ceil(max / step) * step);
	const ticks = $derived(Array.from({ length: Math.round(top / step) + 1 }, (_, i) => i * step));

	let width = $state(720);
	const H = 180;
	const PAD = { l: 36, r: 8, t: 10, b: 24 };
	const plotW = $derived(Math.max(100, width - PAD.l - PAD.r));
	const slot = $derived(plotW / Math.max(1, bars.length));
	const barW = $derived(Math.max(2, Math.min(24, slot - 2)));
	const y = (v: number) => PAD.t + (H - PAD.t - PAD.b) * (1 - v / top);
	const labelEvery = $derived(Math.max(1, Math.ceil(bars.length / Math.max(1, Math.floor(plotW / 64)))));

	let hover = $state<number | null>(null);
	const tip = $derived(hover == null ? null : bars[hover]);

	function niceStep(m: number): number {
		const raw = m / 4;
		const p = 10 ** Math.floor(Math.log10(Math.max(raw, 1)));
		for (const k of [1, 2, 5, 10]) if (k * p >= raw) return k * p;
		return 10 * p;
	}
</script>

<figure class="vol">
	<div class="legend" aria-hidden="true">
		<span><i class="key ans"></i>Answered from the sources</span>
		<span><i class="key un"></i>Not answered</span>
	</div>
	<div class="plot" bind:clientWidth={width}>
		<svg
			viewBox="0 0 {width} {H}"
			width={width}
			height={H}
			role="img"
			aria-label="Questions per {bars.length > 0 && volume.length > 90 ? 'week' : 'day'}, answered and not answered. The table below lists the numbers."
		>
			{#each ticks as t (t)}
				<line class="grid" x1={PAD.l} x2={width - PAD.r} y1={y(t)} y2={y(t)} />
				<text class="axis" x={PAD.l - 6} y={y(t) + 4} text-anchor="end">{t}</text>
			{/each}
			{#each bars as b, i (b.start)}
				{@const x = PAD.l + i * slot + (slot - barW) / 2}
				{#if b.answered > 0}
					<rect class="ans" {x} y={y(b.answered)} width={barW} height={Math.max(0, y(0) - y(b.answered))} />
				{/if}
				{#if b.unanswered > 0}
					<rect
						class="un"
						{x}
						y={y(b.answered + b.unanswered)}
						width={barW}
						height={Math.max(0, y(b.answered) - y(b.answered + b.unanswered) - (b.answered > 0 ? 2 : 0))}
					/>
				{/if}
				{#if i % labelEvery === 0}
					<text class="axis" x={PAD.l + i * slot + slot / 2} y={H - 6} text-anchor="middle">{b.label.replace('Week of ', '')}</text>
				{/if}
				<!-- Hit target: the whole slot, taller than the bar. -->
				<rect
					class="hit"
					x={PAD.l + i * slot}
					y={PAD.t}
					width={slot}
					height={H - PAD.t - PAD.b}
					role="presentation"
					onpointerenter={() => (hover = i)}
					onpointerleave={() => (hover = null)}
				/>
			{/each}
			{#if tip && hover != null}
				<line class="cross" x1={PAD.l + hover * slot + slot / 2} x2={PAD.l + hover * slot + slot / 2} y1={PAD.t} y2={y(0)} />
			{/if}
		</svg>
		{#if tip && hover != null}
			<div
				class="tip"
				style:left="{Math.min(Math.max(PAD.l + hover * slot + slot / 2, 90), width - 90)}px"
				role="status"
			>
				<strong>{tip.label}</strong>
				<span>{tip.count} question{tip.count === 1 ? '' : 's'}</span>
				<span><i class="key ans"></i>{tip.answered} answered</span>
				<span><i class="key un"></i>{tip.unanswered} not answered</span>
				{#if tip.failed}<span class="muted">{tip.failed} failed</span>{/if}
			</div>
		{/if}
	</div>
	<details class="as-table">
		<summary>Show as a table</summary>
		<div class="table-scroll">
			<table class="ledger">
				<thead><tr><th scope="col">{volume.length > 90 ? 'Week' : 'Day'}</th><th scope="col">Questions</th><th scope="col">Answered</th><th scope="col">Not answered</th><th scope="col">Failed</th></tr></thead>
				<tbody>
					{#each bars as b (b.start)}
						<tr><td>{b.label}</td><td>{b.count}</td><td>{b.answered}</td><td>{b.unanswered}</td><td>{b.failed}</td></tr>
					{/each}
				</tbody>
			</table>
		</div>
	</details>
</figure>

<style>
	/* Validated pair (dataviz validator, light on #f8f7f5, dark on #06394c). */
	.vol {
		--c-ans: #0b7ea6;
		--c-un: #ba351a;
		margin: 0;
	}
	@media (prefers-color-scheme: dark) {
		:global(:root:not([data-theme='light'])) .vol {
			--c-ans: #2f97b8;
			--c-un: #d96a45;
		}
	}
	:global(:root[data-theme='dark']) .vol {
		--c-ans: #2f97b8;
		--c-un: #d96a45;
	}
	.legend {
		display: flex;
		flex-wrap: wrap;
		gap: 6px 18px;
		margin-bottom: 8px;
		font: 500 0.82rem var(--sans);
		color: var(--muted);
	}
	.key {
		display: inline-block;
		width: 10px;
		height: 10px;
		margin-right: 6px;
		vertical-align: -1px;
	}
	.key.ans,
	rect.ans {
		background: var(--c-ans);
		fill: var(--c-ans);
	}
	.key.un,
	rect.un {
		background: var(--c-un);
		fill: var(--c-un);
	}
	.plot {
		position: relative;
		width: 100%;
	}
	svg {
		display: block;
		max-width: 100%;
	}
	.grid {
		stroke: var(--border);
		stroke-width: 1;
	}
	.cross {
		stroke: var(--muted);
		stroke-width: 1;
		pointer-events: none;
	}
	.axis {
		fill: var(--muted);
		font: 500 10.5px var(--sans);
	}
	.hit {
		fill: transparent;
	}
	.tip {
		position: absolute;
		top: 0;
		transform: translateX(-50%);
		display: grid;
		gap: 2px;
		min-width: 150px;
		padding: 8px 10px;
		background: var(--surface);
		border: 1px solid var(--rule);
		font: 0.8rem/1.4 var(--sans);
		color: var(--text);
		pointer-events: none;
	}
	.as-table {
		margin-top: 10px;
		font-size: 0.88rem;
	}
	.as-table summary {
		cursor: pointer;
		color: var(--accent);
		font-weight: 600;
	}
	.as-table .table-scroll {
		max-height: 320px;
		overflow: auto;
		margin-top: 8px;
	}
</style>
