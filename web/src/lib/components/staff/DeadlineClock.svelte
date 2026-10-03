<script lang="ts">
	// One computed legal clock: the date, what it means, how it was counted,
	// the controlling text and its citation, and a button to add it to a case.
	import { dueLabel, fmtDay } from './CaseData';
	import { KIND_TEXT, STATUS_TEXT, fmtTime, longDay, statusOf, type Clock } from './DeadlineData';

	let {
		clock,
		canSave = false,
		saveState = 'idle',
		onsave
	}: {
		clock: Clock;
		canSave?: boolean;
		saveState?: 'idle' | 'saving' | 'saved' | 'error';
		onsave?: (c: Clock) => void;
	} = $props();

	const status = $derived(statusOf(clock));
	const uid = $props.id();
</script>

<article class="clock" class:unverified={status === 'unverified'} aria-labelledby="{uid}-t">
	<div class="when">
		<span class="kind">{KIND_TEXT[clock.kind]}</span>
		<span class="date">{fmtDay(clock.date)}</span>
		<span class="dow">{clock.weekday}{clock.time ? `, ${fmtTime(clock.time)}` : ''}</span>
		<span class="due">{dueLabel(clock.date)}</span>
	</div>

	<div class="body">
		<p class="status status-{status}">{STATUS_TEXT[status]}</p>
		<h3 id="{uid}-t">{clock.label}</h3>
		<p class="actor-line">
			{clock.actor}<span class="sep">{' · '}</span>{clock.offset}<span class="sep"
				>{' · '}</span
			>{clock.convention.label}
		</p>

		{#if clock.closed && clock.plan_by}
			<p class="flag">
				City Hall is closed that day ({clock.closed}). Last open day before it: <strong>{longDay(clock.plan_by)}</strong>.
			</p>
		{:else if clock.raw_date && clock.convention.id === 'city_before'}
			<p class="flag">
				{longDay(clock.raw_date)} falls on a day City Hall is closed, so the date moves back to the last open day.
			</p>
		{:else if clock.raw_date}
			<p class="flag">Day {clock.amount} falls on {longDay(clock.raw_date)}, a court holiday or weekend; the period runs to the next court day.</p>
		{:else if clock.closed && clock.unit === 'hours'}
			<p class="flag">That day City Hall is closed ({clock.closed}).</p>
		{/if}
		{#if clock.alt}
			<p class="flag">
				Counting {clock.alt.basis.toLowerCase()} instead gives {longDay(clock.alt.date)}, the earlier date.
			</p>
		{/if}
		{#if clock.caution}<p class="flag caution">{clock.caution}</p>{/if}

		<blockquote>
			<p>{clock.quote}</p>
			<footer>
				{#if clock.url}<a href={clock.url} target="_blank" rel="noopener noreferrer">{clock.citation}</a>{:else}{clock.citation}{/if}
			</footer>
		</blockquote>
		{#if clock.note}<p class="note">{clock.note}</p>{/if}

		<details>
			<summary>How this date was counted</summary>
			<ol class="steps">
				{#each clock.steps as s, i (i)}<li>{s}</li>{/each}
			</ol>
			<p class="conv"><strong>{clock.convention.label}.</strong> {clock.convention.summary}</p>
			{#if clock.convention.caution}<p class="conv muted">{clock.convention.caution}</p>{/if}
			{#each clock.also as a (a.citation)}
				<blockquote class="also">
					<p>{a.quote}</p>
					<footer><a href={a.url} target="_blank" rel="noopener noreferrer">{a.citation}</a></footer>
				</blockquote>
			{/each}
			<p class="muted src">
				Source: {clock.source || clock.url}{clock.verified ? `; quote checked ${clock.checked}` : ''}.
			</p>
		</details>

		<div class="save no-print">
			<button
				type="button"
				class="btn secondary small"
				disabled={!canSave || saveState === 'saving' || saveState === 'saved'}
				onclick={() => onsave?.(clock)}
			>
				{saveState === 'saved' ? 'Added to case' : saveState === 'saving' ? 'Adding' : 'Add to case'}
			</button>
			{#if saveState === 'error'}<span class="error-text">Could not add it. Try again.</span>{/if}
		</div>
	</div>
</article>

<style>
	.clock {
		display: grid;
		grid-template-columns: 168px minmax(0, 1fr);
		background: var(--surface);
		border: 1px solid var(--rule);
		border-top: 3px solid var(--accent);
	}
	.clock.unverified {
		border-top-style: dashed;
	}
	.when {
		display: flex;
		flex-direction: column;
		gap: 2px;
		padding: 16px;
		border-right: 1px solid var(--border);
		background: var(--bg);
	}
	.kind {
		font: 600 0.72rem var(--sans);
		text-transform: uppercase;
		letter-spacing: 0.06em;
		color: var(--accent);
	}
	.date {
		font: 300 1.45rem/1.15 var(--serif);
		color: var(--text);
	}
	.dow {
		font: 500 0.85rem var(--sans);
		color: var(--muted);
	}
	.due {
		margin-top: 8px;
		font: 600 0.8rem var(--sans);
		color: var(--text);
	}
	.body {
		padding: 14px 18px 16px;
		min-width: 0;
	}
	h3 {
		margin: 2px 0 4px;
		font: 600 1.02rem/1.35 var(--sans);
	}
	.actor-line {
		margin: 0 0 10px;
		font: 0.85rem/1.45 var(--sans);
		color: var(--muted);
	}
	.status {
		display: inline-block;
		margin: 0;
		padding: 0 8px;
		font: 600 0.74rem/1.7 var(--sans);
		letter-spacing: 0.02em;
		border: 1px solid currentColor;
	}
	.status-verified {
		color: var(--muted);
	}
	.status-check {
		color: var(--accent);
	}
	.status-unverified {
		color: var(--accent-text);
		background: var(--accent);
		border-color: var(--accent);
	}
	.flag {
		margin: 0 0 8px;
		padding: 6px 10px;
		border-left: 3px solid var(--accent);
		background: var(--bg);
		font: 0.88rem/1.45 var(--sans);
	}
	.flag.caution {
		border-left-color: var(--rule);
	}
	blockquote {
		margin: 10px 0 8px;
		padding: 2px 0 2px 14px;
		border-left: 1px solid var(--rule);
		font: 400 0.98rem/1.55 var(--serif);
	}
	blockquote p {
		margin: 0 0 4px;
	}
	blockquote footer {
		font: 600 0.82rem var(--sans);
	}
	blockquote a {
		color: var(--text);
		text-decoration-color: var(--accent);
	}
	.note {
		margin: 0 0 8px;
		font-size: 0.88rem;
		color: var(--muted);
	}
	details {
		margin: 8px 0 0;
		font-size: 0.88rem;
	}
	summary {
		cursor: pointer;
		font: 600 0.84rem var(--sans);
		color: var(--text);
	}
	summary:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
	}
	.steps {
		margin: 8px 0;
		padding-left: 1.4em;
	}
	.conv {
		margin: 0 0 6px;
	}
	.also {
		font-size: 0.92rem;
	}
	.src {
		margin: 6px 0 0;
		overflow-wrap: anywhere;
		font-size: 0.8rem;
	}
	.save {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 10px;
		margin-top: 12px;
	}
	@media (max-width: 640px) {
		.clock {
			grid-template-columns: 1fr;
		}
		.when {
			flex-direction: row;
			flex-wrap: wrap;
			align-items: baseline;
			gap: 4px 10px;
			border-right: 0;
			border-bottom: 1px solid var(--border);
			padding: 12px 14px;
		}
		.kind {
			width: 100%;
		}
		.due {
			margin: 0 0 0 auto;
		}
		.body {
			padding: 12px 14px 14px;
		}
	}
	@media print {
		.clock {
			break-inside: avoid;
		}
		details {
			display: none;
		}
	}
</style>
