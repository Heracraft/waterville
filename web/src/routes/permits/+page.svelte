<script lang="ts">
	// A3: permit guide. Pick a project, answer a few questions, and see the
	// permits and forms it needs, whether the Fire Department's General Life
	// Safety Review applies, and what to bring (A1 checklist).
	import { page } from '$app/state';
	import { replaceState } from '$app/navigation';
	import { untrack } from 'svelte';
	import Header from '$lib/components/Header.svelte';
	import PublicToolNav from '$lib/components/PublicToolNav.svelte';
	import PublicChecklistCard from '$lib/components/PublicChecklistCard.svelte';
	import { publicApi, telHref, type RouterOptions, type RouterResult } from '$lib/components/PublicData';

	let options = $state<RouterOptions | null>(null);
	let project = $state(untrack(() => page.url.searchParams.get('project')) || '');
	let answers = $state<Record<string, boolean>>({});
	let result = $state<RouterResult | null>(null);
	let error = $state('');
	let seq = 0;

	const fireQuestions = $derived(options?.questions.filter((q) => q.fire) ?? []);
	const otherQuestions = $derived(options?.questions.filter((q) => !q.fire) ?? []);

	$effect(() => {
		publicApi
			.routerOptions()
			.then((o) => {
				options = o;
				const known = o.projects.find((p) => p.id === project);
				if (known) pick(known.id, false);
				else project = '';
			})
			.catch((e) => (error = e instanceof Error ? e.message : String(e)));
	});

	function pick(id: string, focusResult = true) {
		const p = options?.projects.find((x) => x.id === id);
		if (!p) return;
		project = id;
		answers = Object.fromEntries((options?.questions ?? []).map((q) => [q.id, !!p.defaults[q.id]]));
		try {
			const u = new URL(page.url);
			u.searchParams.set('project', id);
			replaceState(u, {});
		} catch {
			/* history unavailable (before the router starts) */
		}
		run().then(() => {
			if (focusResult) document.getElementById('result-title')?.focus({ preventScroll: true });
		});
	}

	async function run() {
		if (!project) return;
		const mine = ++seq;
		error = '';
		try {
			const r = await publicApi.route(project, $state.snapshot(answers));
			if (mine === seq) result = r;
		} catch (e) {
			if (mine === seq) error = e instanceof Error ? e.message : String(e);
		}
	}

	function toggle(id: string, value: boolean) {
		answers[id] = value;
		run();
	}

	const fireLabel = {
		required: 'Applies',
		ask: 'Ask the office',
		not_indicated: 'Not indicated'
	} as const;
</script>

<svelte:head>
	<title>Permit guide | Waterville Codes RAG</title>
</svelte:head>

<Header title="Permit guide" compact>
	{#snippet actions()}
		<a class="theme-toggle" href="/">Ask a question</a>
	{/snippet}
</Header>
<main class="wrap permits">
	<div class="page-head">
		<p class="page-lede">
			Pick your project to see the permits and forms it needs, whether the Fire Department reviews it, and what to bring to
			the Code Enforcement office.
		</p>
	</div>

	{#if error}<p class="notice error-text" role="alert">{error}</p>{/if}

	<section class="step" aria-labelledby="step-1">
		<h2 id="step-1" class="step-title"><span class="step-n">1</span> What are you doing?</h2>
		{#if options}
			<div class="projects" role="group" aria-labelledby="step-1">
				{#each options.projects as p (p.id)}
					<button type="button" class="project" aria-pressed={project === p.id} onclick={() => pick(p.id)}>{p.label}</button>
				{/each}
			</div>
		{:else if !error}
			<p class="muted">Loading the project list...</p>
		{/if}
	</section>

	{#if options && project}
		<section class="step" aria-labelledby="step-2">
			<h2 id="step-2" class="step-title"><span class="step-n">2</span> About the work</h2>
			<div class="questions">
				<fieldset>
					<legend>Fire Department review triggers</legend>
					{#each fireQuestions as q (q.id)}
						<label class="check">
							<input type="checkbox" checked={!!answers[q.id]} onchange={(e) => toggle(q.id, e.currentTarget.checked)} />
							<span>{q.label}<small>{q.help}</small></span>
						</label>
					{/each}
				</fieldset>
				<fieldset>
					<legend>Other details</legend>
					{#each otherQuestions as q (q.id)}
						<label class="check">
							<input type="checkbox" checked={!!answers[q.id]} onchange={(e) => toggle(q.id, e.currentTarget.checked)} />
							<span>{q.label}<small>{q.help}</small></span>
						</label>
					{/each}
				</fieldset>
			</div>
		</section>
	{/if}

	{#if result && project}
		<section class="step result" aria-labelledby="result-title" aria-live="polite">
			<h2 id="result-title" class="step-title" tabindex="-1">
				<span class="step-n">3</span> What you need for: {result.project.label}
			</h2>

			<div class="sheet accent">
				<h3>Permits and forms</h3>
				{#if result.permits.length}
					<table class="ledger">
						<thead><tr><th scope="col">Form</th><th scope="col">Issued by</th><th scope="col">Why</th></tr></thead>
						<tbody>
							{#each result.permits as f (f.id)}
								<tr>
									<td><a href={f.url} target="_blank" rel="noopener">{f.title}</a></td>
									<td>{f.who}</td>
									<td>{f.why}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				{/if}
				{#if result.ask_office}<p class="notice">{result.ask_office}</p>{/if}
				{#if !result.permits.length && !result.ask_office}
					<p class="notice">Ask the office which application to file.</p>
				{/if}
				<p class="muted small">
					All city applications are on the <a href={result.applications_page} target="_blank" rel="noopener"
						>Building Permit Applications</a
					> page.
				</p>
			</div>

			<div class="sheet fire fire-{result.fire_review.status}">
				<h3>
					Fire Department General Life Safety Review:
					<span class="tag-pill">{fireLabel[result.fire_review.status]}</span>
				</h3>
				<p>{result.fire_review.text}</p>
				{#if result.fire_review.reasons.length}
					<ul class="reasons">
						{#each result.fire_review.reasons as r (r)}<li>{r}</li>{/each}
					</ul>
				{/if}
				<p class="small">
					<a href={result.fire_review.form.url} target="_blank" rel="noopener">{result.fire_review.form.title}</a>
					{#if result.fire_review.status !== 'not_indicated'}
						<span class="muted"> · </span><a href="/fees">Estimate the review fee</a>
					{/if}
				</p>
			</div>

			{#if result.also.length}
				<div class="sheet">
					<h3>Other approvals that may apply</h3>
					<ul class="also">
						{#each result.also as a (a.title)}
							<li>
								<strong>{a.title}</strong> <span class="muted">({a.who})</span>
								<p>{a.why} <a href={a.url} target="_blank" rel="noopener">{a.citation}</a></p>
							</li>
						{/each}
					</ul>
				</div>
			{/if}

			<p class="confirm">
				{result.confirm_line}
				<a href={telHref(result.office_phone)}>Call {result.office_phone}</a>
			</p>

			{#if result.checklist}
				<div class="sheet checklist">
					<PublicChecklistCard checklist={result.checklist} open showGuide={false} headingLevel={2} />
				</div>
			{/if}

			<p class="btn-row no-print">
				<button type="button" class="btn secondary" onclick={() => window.print()}>Print this list</button>
				<a class="btn secondary" href="/">Ask a question instead</a>
			</p>
		</section>
	{/if}
</main>

<PublicToolNav />

<style>
	.step {
		margin-bottom: 28px;
	}
	.step-title {
		display: flex;
		align-items: baseline;
		gap: 10px;
		margin: 0 0 12px;
		font: 300 1.45rem/1.25 var(--serif);
		color: var(--text);
	}
	.step-title:focus {
		outline: none;
	}
	.step-n {
		color: var(--accent);
		font: 400 1rem var(--serif);
	}
	.step-n::after {
		content: '.';
	}
	.projects {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
		border-top: 1px solid var(--rule);
		border-left: 1px solid var(--rule);
	}
	.project {
		text-align: left;
		cursor: pointer;
		border: 0;
		border-right: 1px solid var(--rule);
		border-bottom: 1px solid var(--rule);
		background: var(--surface);
		color: var(--text);
		padding: 12px 14px;
		font: 400 0.95rem/1.35 var(--sans);
		transition: background-color 0.15s;
	}
	.project:hover {
		background: var(--surface-hover);
	}
	.project[aria-pressed='true'] {
		background: var(--accent);
		color: var(--accent-text);
		font-weight: 600;
	}
	.project:focus-visible {
		outline: none;
		box-shadow: inset 0 0 0 2px var(--accent);
	}
	.project[aria-pressed='true']:focus-visible {
		box-shadow: inset 0 0 0 2px var(--accent-text);
	}
	.questions {
		display: grid;
		gap: 16px;
	}
	@media (min-width: 760px) {
		.questions {
			grid-template-columns: 1fr 1fr;
		}
	}
	fieldset {
		margin: 0;
		padding: 12px 16px 6px;
		border: 1px solid var(--rule);
		background: var(--surface);
		min-width: 0;
	}
	legend {
		padding: 0 6px;
		margin-left: -6px;
		font: 600 0.85rem var(--sans);
		color: var(--accent);
	}
	.check {
		margin-bottom: 10px;
		cursor: pointer;
	}
	.check span {
		font-size: 0.95rem;
	}
	.check small {
		display: block;
		color: var(--muted);
		font-size: 0.82rem;
	}
	.result .sheet {
		margin-top: 0;
		margin-bottom: 16px;
	}
	.ledger a {
		font-weight: 600;
	}
	.small {
		font-size: 0.85rem;
	}
	.fire h3 {
		display: flex;
		flex-wrap: wrap;
		gap: 6px 10px;
		align-items: center;
	}
	.fire-required {
		border-left: 4px solid var(--accent);
	}
	.fire-not_indicated .tag-pill {
		border-color: var(--rule);
		color: var(--text);
	}
	.reasons {
		margin: 0 0 10px;
		padding-left: 20px;
	}
	.reasons li::marker {
		color: var(--accent);
	}
	.also {
		margin: 0;
		padding: 0;
		list-style: none;
	}
	.also li {
		padding: 8px 0;
		border-bottom: 1px solid var(--border);
	}
	.also li:last-child {
		border-bottom: 0;
	}
	.also p {
		margin: 4px 0 0;
	}
	.confirm {
		margin: 0 0 16px;
		padding: 12px 14px;
		border: 1px solid var(--accent);
		background: var(--surface);
		font-weight: 600;
	}
	.confirm a {
		margin-left: 8px;
		white-space: nowrap;
	}
	.checklist :global(.pc) {
		margin-top: 0;
		padding-top: 0;
		border-top: 0;
	}
	@media (max-width: 640px) {
		.projects {
			grid-template-columns: 1fr 1fr;
		}
		.ledger thead {
			display: none;
		}
		.ledger tr {
			display: block;
			padding: 8px 12px;
			border-bottom: 1px solid var(--border);
		}
		.ledger td {
			display: block;
			padding: 2px 0;
			border: 0;
		}
	}
	@media print {
		.projects,
		.questions,
		.step:not(.result) {
			display: none;
		}
		.sheet {
			break-inside: avoid;
		}
	}
</style>
