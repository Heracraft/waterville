<script lang="ts">
	// B13: DEP biennial shoreland summary and LPI annual report, assembled from
	// case notebooks. Printable; the permit records stay the source of truth.
	import { download, insightsApi, reportCsv, shortDay, type Report } from './InsightData';

	const now = new Date();
	const thisYear = now.getFullYear();

	let kind = $state<'shoreland' | 'lpi'>('shoreland');
	let start = $state(`${thisYear - 1}-01-01`);
	let end = $state(`${thisYear}-12-31`);
	let year = $state(thisYear);
	let report = $state<Report | null>(null);
	let loading = $state(false);
	let error = $state('');
	let seq = 0;

	const years = Array.from({ length: 8 }, (_, i) => thisYear - i);

	async function load() {
		const mine = ++seq;
		loading = true;
		error = '';
		try {
			const r = kind === 'shoreland' ? await insightsApi.shoreland(start, end) : await insightsApi.lpi(year);
			if (mine === seq) report = r;
		} catch (e) {
			if (mine === seq) {
				report = null;
				error = e instanceof Error ? e.message : String(e);
			}
		} finally {
			if (mine === seq) loading = false;
		}
	}

	$effect(() => {
		// Reload when the report or its period changes.
		void [kind, start, end, year];
		if (kind === 'shoreland' && (!start || !end)) return;
		load();
	});

	function printReport() {
		document.body.dataset.printOnly = 'report';
		const done = () => {
			delete document.body.dataset.printOnly;
			window.removeEventListener('afterprint', done);
		};
		window.addEventListener('afterprint', done);
		window.print();
	}

	function csv() {
		if (report) download(`${report.id}-report-${report.start}-to-${report.end}.csv`, reportCsv(report));
	}

	const STATUS_LABEL: Record<string, string> = { open: 'Open', monitoring: 'Monitoring', closed: 'Closed' };
</script>

<div class="controls no-print">
	<div class="tabs" role="tablist" aria-label="Report">
		<button type="button" role="tab" aria-selected={kind === 'shoreland'} onclick={() => (kind = 'shoreland')}>
			DEP biennial shoreland
		</button>
		<button type="button" role="tab" aria-selected={kind === 'lpi'} onclick={() => (kind = 'lpi')}>LPI annual</button>
	</div>
	<div class="period">
		{#if kind === 'shoreland'}
			<label class="field"><span>From</span><input type="date" bind:value={start} /></label>
			<label class="field"><span>To</span><input type="date" bind:value={end} /></label>
		{:else}
			<label class="field">
				<span>Year</span>
				<select bind:value={year}>
					{#each years as y (y)}<option value={y}>{y}</option>{/each}
				</select>
			</label>
		{/if}
		<div class="btn-row">
			<button type="button" class="btn secondary small" onclick={csv} disabled={!report}>Download CSV</button>
			<button type="button" class="btn small" onclick={printReport} disabled={!report}>Print report</button>
		</div>
	</div>
</div>

{#if error}
	<p class="notice error-text" role="alert">{error}</p>
{:else if !report}
	<p class="muted" aria-busy="true">Loading the report</p>
{:else}
	<article class="report" aria-busy={loading}>
		<header>
			<span class="eyebrow">City of Waterville, Code Enforcement</span>
			<h3>{report.title}</h3>
			<p class="period-line">
				{shortDay(report.start, true)} to {shortDay(report.end, true)}. For: {report.recipient}.
			</p>
		</header>

		<p class="notice source-note"><strong>Source of truth.</strong> {report.note}</p>

		<blockquote>
			<p>{report.quote}</p>
			<footer>{report.citation}</footer>
		</blockquote>
		{#if report.verify}<p class="verify">{report.verify}</p>{/if}

		<h4>Summary</h4>
		<div class="table-scroll">
			<table class="ledger stack summary">
				<thead>
					<tr><th scope="col">Category</th><th scope="col" class="count-col">From case notebooks</th><th scope="col">Counted from</th><th scope="col">Confirm in</th></tr>
				</thead>
				<tbody>
					{#each report.summary as s (s.label)}
						<tr>
							<th scope="row">{s.label}</th>
							<td class="count-col" data-label="From case notebooks">{s.count ?? 'Not tracked'}</td>
							<td data-label="Counted from">{s.basis}</td>
							<td data-label="Confirm in">{s.confirm}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
		<p class="muted small">
			{report.cases.length} case{report.cases.length === 1 ? '' : 's'} tagged {report.tags.join(' or ')} active in the period
			({report.opened_in_period} opened in it). Open {report.status.open}, monitoring {report.status.monitoring}, closed {report.status.closed}.
		</p>

		<h4>Cases</h4>
		{#if report.cases.length === 0}
			<p class="muted">No case notebook tagged {report.tags.join(' or ')} was active in this period.</p>
		{:else}
			<div class="table-scroll">
				<table class="ledger cases stack">
					<thead>
						<tr>
							<th scope="col">Case</th>
							<th scope="col">Property</th>
							<th scope="col">Status</th>
							<th scope="col">Opened</th>
							<th scope="col">Last activity</th>
							<th scope="col">Actions in period</th>
						</tr>
					</thead>
					<tbody>
						{#each report.cases as c (c.id)}
							<tr>
								<td data-label="Case"><a href="/staff/cases/{c.id}">{c.id}</a></td>
								<td data-label="Property">
									<div>
										{c.address}{#if c.map_lot}{' '}<span class="muted">(map/lot {c.map_lot})</span>{/if}
										{#if c.title}<div class="muted small">{c.title}</div>{/if}
										<div class="small">{c.tags.join(', ')}</div>
									</div>
								</td>
								<td data-label="Status">{STATUS_LABEL[c.status] ?? c.status}</td>
								<td class="d" data-label="Opened">{c.opened}</td>
								<td class="d" data-label="Last activity">{c.last_activity}</td>
								<td data-label="Actions in period">
									<div>
										{#if c.actions.length}{c.actions.join('; ')}{:else}<span class="muted">None drafted</span>{/if}
										<div class="muted small">{c.notes} note{c.notes === 1 ? '' : 's'}, {c.deadlines} deadline{c.deadlines === 1 ? '' : 's'}</div>
									</div>
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
		<p class="muted small generated">
			Generated {new Date(report.generated_at).toLocaleString()} from the staff case notebooks. Draft for review.
		</p>
	</article>
{/if}

<style>
	.controls {
		display: grid;
		gap: 14px;
		margin-bottom: 18px;
	}
	.tabs {
		display: flex;
		flex-wrap: wrap;
		border-bottom: 1px solid var(--rule);
	}
	.tabs button {
		cursor: pointer;
		border: 1px solid var(--rule);
		border-bottom: 0;
		margin-right: -1px;
		background: var(--bg);
		color: var(--text);
		font: 600 0.88rem var(--sans);
		padding: 8px 14px;
	}
	.tabs button[aria-selected='true'] {
		background: var(--surface);
		border-top: 3px solid var(--accent);
		padding-top: 6px;
	}
	.tabs button:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: -2px;
	}
	.period {
		display: flex;
		flex-wrap: wrap;
		align-items: flex-end;
		gap: 0 14px;
	}
	.period .field {
		margin-bottom: 0;
		min-width: 150px;
	}
	.period .btn-row {
		margin-left: auto;
		padding-bottom: 2px;
	}
	.report header h3 {
		margin: 0;
		font: 300 1.5rem/1.25 var(--serif);
	}
	.period-line {
		margin: 4px 0 14px;
		color: var(--muted);
	}
	h4 {
		margin: 22px 0 8px;
		font: 600 0.95rem var(--sans);
	}
	blockquote {
		margin: 0 0 10px;
		padding: 2px 0 2px 14px;
		border-left: 3px solid var(--rule);
		font: 300 0.98rem/1.55 var(--serif);
	}
	blockquote p {
		margin: 0 0 4px;
	}
	blockquote footer {
		font: 600 0.8rem var(--sans);
		color: var(--muted);
	}
	.verify {
		font-size: 0.85rem;
		background: var(--hl);
		padding: 6px 10px;
		border-left: 3px solid var(--accent);
	}
	.ledger .count-col {
		text-align: right;
		font-variant-numeric: tabular-nums;
		white-space: nowrap;
	}
	.ledger tbody th {
		font-weight: 600;
		background: transparent;
		border-bottom-color: var(--border);
	}
	.cases td:first-child,
	.cases td.d {
		white-space: nowrap;
	}
	.small {
		font-size: 0.82rem;
	}
	.generated {
		margin-top: 14px;
	}
	/* Phones: each row becomes a block with labeled cells. */
	@media screen and (max-width: 640px) {
		.stack thead {
			display: none;
		}
		.stack,
		.stack tbody,
		.stack tr,
		.stack th,
		.stack td {
			display: block;
			width: 100%;
		}
		.stack tr {
			padding: 8px 12px;
			border-bottom: 1px solid var(--border);
		}
		.stack tr:last-child {
			border-bottom: 0;
		}
		.stack th,
		.stack td {
			padding: 2px 0;
			border: 0;
			text-align: left;
		}
		.stack td[data-label] {
			display: grid;
			grid-template-columns: 8.5em 1fr;
			gap: 8px;
		}
		.stack td[data-label]::before {
			content: attr(data-label);
			color: var(--muted);
			font-size: 0.8rem;
		}
		.stack .count-col {
			text-align: left;
			white-space: normal;
		}
		.cases td:first-child {
			font-weight: 600;
		}
	}
	@media print {
		.report {
			color: #000;
		}
		.report a {
			color: #000;
			text-decoration: none;
		}
		.verify {
			background: #f4f4f4;
		}
		.table-scroll {
			overflow: visible;
		}
		.ledger {
			font-size: 9.5pt;
			background: #fff;
		}
		.ledger th {
			background: #eee;
		}
	}
</style>
