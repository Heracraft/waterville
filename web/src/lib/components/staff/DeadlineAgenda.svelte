<script lang="ts">
	// Calendar-style list of the clocks: one block per month, one ruled row per
	// date, with the event day and holidays marked. City Hall closed days
	// (Fridays and weekends) are shaded.
	import { STATUS_TEXT, agenda, fmtTime, statusOf, type ComputeResult, type Holiday } from './DeadlineData';

	let { result, holidays = [] }: { result: ComputeResult; holidays?: Holiday[] } = $props();

	const months = $derived(agenda(result, holidays));
	const closed = (wd: string) => wd === 'Fri' || wd === 'Sat' || wd === 'Sun';
</script>

<div class="agenda">
	{#each months as m (m.key)}
		<section class="month" aria-label={m.label}>
			<h3>{m.label}</h3>
			<ol>
				{#each m.days as d (d.date)}
					<li class="day" class:closed={closed(d.weekday) || !!d.holiday} class:event={d.event}>
						<div class="num">
							<span class="d">{d.day}</span>
							<span class="wd">{d.weekday}</span>
						</div>
						<div class="items">
							{#if d.event}
								<p class="ev"><span class="tag-pill">Event</span> {result.trigger.label}{result.time ? `, ${fmtTime(result.time)}` : ''}</p>
							{/if}
							{#if d.holiday}<p class="hol">{d.holiday}: courts and City Hall closed</p>{/if}
							{#each d.clocks as c (c.id)}
								<p class="it">
									<span class="lbl">{c.label}{c.time ? `, ${fmtTime(c.time)}` : ''}</span>
									<span class="cit">{c.citation}</span>
									{#if statusOf(c) !== 'verified'}<span class="warn">{STATUS_TEXT[statusOf(c)]}</span>{/if}
								</p>
							{/each}
						</div>
					</li>
				{/each}
			</ol>
		</section>
	{/each}
	<p class="key muted">Shaded rows: City Hall closed (Fridays, weekends, holidays).</p>
</div>

<style>
	.month + .month {
		margin-top: 20px;
	}
	h3 {
		margin: 0 0 8px;
		font: 300 1.3rem/1.2 var(--serif);
	}
	ol {
		list-style: none;
		margin: 0;
		padding: 0;
		border: 1px solid var(--rule);
		background: var(--surface);
	}
	.day {
		display: grid;
		grid-template-columns: 64px minmax(0, 1fr);
		border-bottom: 1px solid var(--border);
	}
	.day:last-child {
		border-bottom: 0;
	}
	.num {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: flex-start;
		padding: 10px 4px;
		border-right: 1px solid var(--border);
	}
	.day.closed .num {
		background: var(--bg);
	}
	.num {
		border-left: 3px solid transparent;
	}
	.day.event .num {
		border-left-color: var(--accent);
	}
	.d {
		font: 300 1.5rem/1 var(--serif);
	}
	.wd {
		margin-top: 2px;
		font: 600 0.72rem var(--sans);
		text-transform: uppercase;
		letter-spacing: 0.06em;
		color: var(--muted);
	}
	.items {
		padding: 8px 14px;
		min-width: 0;
	}
	.items p {
		margin: 0;
		padding: 3px 0;
	}
	.it {
		display: flex;
		flex-wrap: wrap;
		gap: 2px 10px;
		align-items: baseline;
	}
	.lbl {
		font: 600 0.92rem/1.4 var(--sans);
	}
	.cit {
		font: 0.82rem var(--sans);
		color: var(--muted);
	}
	.warn {
		font: 600 0.78rem var(--sans);
		color: var(--accent);
	}
	.ev {
		font: 0.9rem var(--sans);
	}
	.hol {
		font: 600 0.82rem var(--sans);
		color: var(--accent);
	}
	.key {
		margin: 10px 0 0;
		font-size: 0.82rem;
	}
</style>
