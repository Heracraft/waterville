<script lang="ts">
	// A7b and B13: what the public asks, what the sources could not answer, which
	// sections get cited, what visitors thought of the answers, code change
	// alerts, and the periodic reports assembled from case notebooks.
	import { page } from '$app/state';
	import { replaceState } from '$app/navigation';
	import { untrack } from 'svelte';
	import InsightVolume from '$lib/components/staff/InsightVolume.svelte';
	import InsightRanked from '$lib/components/staff/InsightRanked.svelte';
	import InsightChanges from '$lib/components/staff/InsightChanges.svelte';
	import InsightReport from '$lib/components/staff/InsightReport.svelte';
	import {
		RANGES,
		digestText,
		insightsApi,
		loadChanges,
		pct,
		shortDay,
		type Change,
		type Insights,
		type Topic
	} from '$lib/components/staff/InsightData';

	const initial = Number(untrack(() => page.url.searchParams.get('days'))) || 30;
	let days = $state(RANGES.some((r) => r.days === initial) ? initial : 30);
	let data = $state<Insights | null>(null);
	let error = $state('');
	let changes = $state<Change[] | null>(null);
	let changesError = $state('');
	let copied = $state('');
	let seq = 0;

	async function load() {
		const mine = ++seq;
		error = '';
		try {
			const d = await insightsApi.get(days);
			if (mine === seq) data = d;
		} catch (e) {
			if (mine === seq) error = e instanceof Error ? e.message : String(e);
		}
	}

	$effect(() => {
		void days;
		load();
		const url = new URL(page.url);
		if (days === 30) url.searchParams.delete('days');
		else url.searchParams.set('days', String(days));
		untrack(() => {
			try {
				replaceState(url, {});
			} catch {
				/* router not ready on first run */
			}
		});
	});

	$effect(() => {
		loadChanges()
			.then((c) => (changes = c))
			.catch((e) => (changesError = e instanceof Error ? e.message : String(e)));
	});

	async function copyDigest() {
		if (!data) return;
		try {
			await navigator.clipboard.writeText(digestText(data, changes));
			copied = 'Digest copied. Paste it into an email.';
		} catch {
			copied = 'Could not reach the clipboard. Use Print instead.';
		}
		setTimeout(() => (copied = ''), 4000);
	}

	const t = $derived(data?.totals);
</script>

<svelte:head>
	<title>Insights | Staff | Waterville Codes RAG</title>
</svelte:head>

<main class="wrap staff-main insights">
	<div class="page-head head-row">
		<div>
			<h2 class="page-title">Insights</h2>
			<p class="page-lede">
				What the public asks, what the sources could not answer, which sections get cited, code change alerts, and
				reports from the case notebooks.
			</p>
		</div>
		<div class="head-actions no-print">
			<label class="field range">
				<span class="sr-only">Period</span>
				<select bind:value={days}>
					{#each RANGES as r (r.days)}<option value={r.days}>{r.label}</option>{/each}
				</select>
			</label>
			<button type="button" class="btn secondary small" onclick={copyDigest} disabled={!data}>Copy digest</button>
			<button type="button" class="btn secondary small" onclick={() => window.print()}>Print</button>
		</div>
	</div>
	{#if copied}<p class="notice no-print" role="status">{copied}</p>{/if}

	{#if error}
		<p class="notice error-text" role="alert">Could not load insights: {error}</p>
		<button type="button" class="btn secondary" onclick={load}>Try again</button>
	{:else if !data || !t}
		<div class="loading" role="status">
			<span class="loading-label">Reading the question log</span><span class="loading-bar" aria-hidden="true"></span>
		</div>
	{:else}
		{#if !data.logging.enabled}
			<p class="notice">
				The public question log is off on this server (<code>QUESTION_LOG</code> is not 1), so no new questions are
				recorded. Earlier records and feedback still show below.
			</p>
		{/if}

		<section class="stats" aria-label="Totals for {shortDay(data.range.start, true)} to {shortDay(data.range.end, true)}">
			<div class="stat">
				<span class="k">Questions</span>
				<span class="v">{t.questions}</span>
				<span class="s">{shortDay(data.range.start)} to {shortDay(data.range.end)}</span>
			</div>
			<div class="stat">
				<span class="k">Not answered</span>
				<span class="v">{pct(t.unanswered_rate)}</span>
				<span class="s"
					>{t.questions - t.failed > 0
						? `${t.unanswered} of ${t.questions - t.failed} not covered by the sources`
						: 'No questions yet'}</span
				>
			</div>
			<div class="stat">
				<span class="k">Found helpful</span>
				<span class="v">{pct(data.feedback.helpful_rate)}</span>
				<span class="s">{data.feedback.yes} yes, {data.feedback.no} no</span>
			</div>
			<div class="stat">
				<span class="k">Failed</span>
				<span class="v">{t.failed}</span>
				<span class="s">Errors, limits or filtered answers{t.avg_answer_chars ? `; answers average ${t.avg_answer_chars} characters` : ''}</span>
			</div>
		</section>

		<section class="sheet sec" aria-labelledby="vol-h">
			<h3 id="vol-h">Question volume</h3>
			{#if t.questions === 0}
				<p class="muted">No public questions were logged in this period.</p>
			{:else}
				<InsightVolume volume={data.volume} />
			{/if}
		</section>

		<div class="cols">
			<section class="sheet sec" aria-labelledby="topics-h">
				<h3 id="topics-h">Top topics</h3>
				<p class="muted small">Grouped by keyword. Open a topic for recent questions.</p>
				<InsightRanked
					rows={data.topics}
					caption="Top topics"
					label={(g: Topic) => g.label}
					count={(g: Topic) => g.count}
					note={(g: Topic) => (g.unanswered ? `${g.unanswered} not answered` : '')}
					empty="No questions in this period."
				>
					{#snippet detail(g: Topic)}
						<ul class="examples">
							{#each g.examples as ex (ex)}<li>{ex}</li>{/each}
						</ul>
					{/snippet}
				</InsightRanked>
			</section>

			<section class="sheet sec" aria-labelledby="cited-h">
				<h3 id="cited-h">Most cited sections</h3>
				<p class="muted small">Sections the public answers cited, counted once per question.</p>
				<InsightRanked
					rows={data.top_sections}
					caption="Most cited sections"
					label={(s: { citation: string }) => s.citation}
					count={(s: { count: number }) => s.count}
					empty="No citations in this period."
				/>
			</section>
		</div>

		<div class="cols">
			<section class="sheet sec" aria-labelledby="un-h">
				<h3 id="un-h">Questions the sources did not answer</h3>
				<p class="muted small">Candidates for a staff note, a checklist or a clearer page on the city site.</p>
				{#if data.unanswered_examples.length === 0}
					<p class="muted">None in this period.</p>
				{:else}
					<ul class="qlist">
						{#each data.unanswered_examples as q, i (i)}
							<li>
								<span class="date">{shortDay(q.date)}</span>{q.question}
								{#if q.times > 1}<span class="times">asked {q.times} times</span>{/if}
							</li>
						{/each}
					</ul>
				{/if}
			</section>

			<section class="sheet sec" aria-labelledby="fb-h">
				<h3 id="fb-h">Visitor feedback</h3>
				<p class="muted small">
					From "Was this helpful?" under public answers: {data.feedback.total} response{data.feedback.total === 1 ? '' : 's'}.
				</p>
				{#if data.feedback.not_helpful.length === 0}
					<p class="muted">No answer was marked not helpful in this period.</p>
				{:else}
					<h4 class="sub">Marked not helpful</h4>
					<ul class="qlist">
						{#each data.feedback.not_helpful as q, i (i)}
							<li>
								<span class="date">{shortDay(q.date)}</span>{q.question}
								{#if q.times > 1}<span class="times">{q.times} times</span>{/if}
								{#if q.cited.length}<div class="muted small">Cited {q.cited.join(', ')}</div>{/if}
							</li>
						{/each}
					</ul>
				{/if}
			</section>
		</div>
	{/if}

	<section class="sheet sec" aria-labelledby="ch-h">
		<h3 id="ch-h">Code change alerts</h3>
		<p class="muted small">Sections whose text changed in the latest code refresh. Check cases and drafts that cite them.</p>
		<InsightChanges {changes} error={changesError} />
	</section>

	<section class="sheet accent sec report-sec" aria-labelledby="rep-h">
		<h3 id="rep-h" class="no-print">Reports</h3>
		<InsightReport />
	</section>

	<p class="privacy muted small">
		Public questions are stored with names, street addresses, map and lot numbers, phone numbers and email addresses
		replaced by tags. Feedback keeps only yes or no and the answer it belongs to.
	</p>
</main>

<style>
	.head-row {
		display: flex;
		flex-wrap: wrap;
		align-items: flex-end;
		justify-content: space-between;
		gap: 12px 24px;
	}
	.head-actions {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 8px;
	}
	.head-actions .range {
		margin: 0;
	}
	.head-actions select {
		padding: 5px 10px;
		font-size: 0.88rem;
	}
	.stats {
		display: grid;
		grid-template-columns: repeat(4, minmax(0, 1fr));
		border: 1px solid var(--rule);
		background: var(--surface);
		margin-bottom: 20px;
	}
	.stat {
		display: grid;
		align-content: start;
		gap: 2px;
		padding: 14px 18px;
		border-left: 1px solid var(--border);
	}
	.stat:first-child {
		border-left: 0;
	}
	.stat .k {
		font: 600 0.8rem var(--sans);
		color: var(--accent);
	}
	.stat .v {
		font: 300 2rem/1.15 var(--serif);
		font-variant-numeric: tabular-nums;
	}
	.stat .s {
		font-size: 0.8rem;
		color: var(--muted);
	}
	.sec {
		min-width: 0;
	}
	.sec + .sec,
	.cols + .sec,
	.sec + .cols,
	.cols + .cols {
		margin-top: 20px;
	}
	.cols {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 20px;
	}
	.cols .sheet + .sheet {
		margin-top: 0;
	}
	.small {
		font-size: 0.84rem;
	}
	.sec > p.small {
		margin-top: -4px;
	}
	.examples {
		margin: 0;
		padding-left: 18px;
		font-family: var(--serif);
	}
	.qlist {
		list-style: none;
		margin: 0;
		padding: 0;
		border-top: 1px solid var(--border);
	}
	.qlist li {
		padding: 8px 0;
		border-bottom: 1px solid var(--border);
		font: 300 1rem/1.45 var(--serif);
		overflow-wrap: anywhere;
	}
	.date {
		display: inline-block;
		min-width: 4.2em;
		margin-right: 8px;
		font: 600 0.78rem var(--sans);
		color: var(--muted);
	}
	.times {
		margin-left: 8px;
		font: 600 0.75rem var(--sans);
		color: var(--accent);
		white-space: nowrap;
	}
	h4.sub {
		margin: 4px 0 6px;
		font: 600 0.88rem var(--sans);
	}
	.privacy {
		margin-top: 20px;
	}
	code {
		font-size: 0.88em;
	}
	@media (max-width: 900px) {
		.cols {
			grid-template-columns: 1fr;
		}
		.stats {
			grid-template-columns: repeat(2, minmax(0, 1fr));
		}
		.stat:nth-child(3) {
			border-left: 0;
		}
		.stat:nth-child(n + 3) {
			border-top: 1px solid var(--border);
		}
	}
	@media print {
		:global(body[data-print-only='report']) .insights > :not(.report-sec) {
			display: none !important;
		}
		:global(body[data-print-only='report']) .report-sec {
			border: 0;
			padding: 0;
		}
		.sheet {
			break-inside: avoid;
			background: #fff;
		}
	}
</style>
