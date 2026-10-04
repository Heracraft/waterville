<script lang="ts">
	// Edit one draft: fields, the text itself, a live preview, review flags,
	// AI help for the facts field, the penalty helper, save, .docx export,
	// print and delete. Used for a new draft (no `draft`; Save creates it) and
	// for a saved one. Key it on the draft id: it copies its inputs once.
	//
	// Nothing here sends a letter. The status banner rides on paper and in the
	// .docx footer.
	import { beforeNavigate } from '$app/navigation';
	import { untrack } from 'svelte';
	import CasePicker from './CasePicker.svelte';
	import CaseConfirm from './CaseConfirm.svelte';
	import DraftForm from './DraftForm.svelte';
	import DraftPenalty from './DraftPenalty.svelte';
	import DraftPreview from './DraftPreview.svelte';
	import {
		BANNER,
		cleanValues,
		drafts,
		flagCounts,
		fmtWhen,
		noteBlocks,
		type Draft,
		type RenderResult,
		type TemplateFull
	} from './DraftData';

	let {
		template,
		draft = null,
		caseId: initialCase = '',
		oncreated,
		ondeleted
	}: {
		template: TemplateFull;
		draft?: Draft | null;
		caseId?: string;
		oncreated?: (d: Draft) => void;
		ondeleted?: () => void;
	} = $props();

	const start = untrack(() => ({
		values: { ...(draft?.values ?? template.defaults) },
		body: draft?.body ?? '',
		edited: draft?.edited ?? false,
		title: draft?.title ?? '',
		caseId: draft?.case_id ?? initialCase,
		status: draft?.status ?? 'draft',
		preview: draft
			? { body: draft.body, html: draft.html, missing: draft.missing, checks: draft.checks, derived: draft.derived }
			: null
	}));

	let values = $state<Record<string, string>>(start.values);
	let body = $state(start.body);
	let edited = $state(start.edited);
	let title = $state(start.title);
	let caseId = $state(start.caseId);
	let reviewed = $state(start.status === 'reviewed');
	let preview = $state<RenderResult | null>(start.preview);
	let saved = $state<Draft | null>(untrack(() => draft));

	let mode = $state<'fields' | 'text' | 'preview'>('fields');
	let dirty = $state(!untrack(() => draft));
	let saving = $state(false);
	let rendering = $state(false);
	let error = $state('');
	let flash = $state('');
	let aiBusy = $state('');
	let suggestion = $state<{ field: string; text: string } | null>(null);
	let confirmDelete = $state<CaseConfirm>();
	let confirmRebuild = $state<CaseConfirm>();
	let showPenalty = $state(false);

	const uid = $props.id();
	const isNew = $derived(!saved);
	const flags = $derived(flagCounts(body));
	const missing = $derived(preview?.missing ?? []);
	const checks = $derived(preview?.checks ?? []);
	const failing = $derived(checks.filter((c) => !c.ok));
	const label = (name: string) => template.fields.find((f) => f.name === name)?.label ?? name;
	const notes = $derived(noteBlocks(template.notes));

	// ------------------------------------------------------------ preview

	let seq = 0;
	let timer: ReturnType<typeof setTimeout> | undefined;
	function scheduleRender(delay = 300) {
		clearTimeout(timer);
		timer = setTimeout(doRender, delay);
	}
	async function doRender() {
		const mine = ++seq;
		rendering = true;
		try {
			const r = await drafts.render({ template: template.id, values: cleanValues(values), body: edited ? body : undefined });
			if (mine !== seq) return;
			preview = r;
			if (!edited) body = r.body;
			error = '';
		} catch (e) {
			if (mine === seq) error = e instanceof Error ? e.message : String(e);
		} finally {
			if (mine === seq) rendering = false;
		}
	}

	// A new draft has no preview yet.
	$effect(() => {
		if (untrack(() => preview) === null) doRender();
	});

	function fieldsChanged() {
		dirty = true;
		scheduleRender();
	}

	function textChanged(v: string) {
		body = v;
		edited = true;
		dirty = true;
		scheduleRender(350);
	}

	async function rebuild() {
		edited = false;
		dirty = true;
		await doRender();
		say('Text rebuilt from the fields.');
	}

	// ------------------------------------------------------------ save

	async function save(): Promise<Draft | null> {
		if (saving) return null;
		saving = true;
		error = '';
		try {
			let d: Draft;
			if (!saved) {
				d = await drafts.create({
					template: template.id,
					values: cleanValues(values),
					case_id: caseId || undefined,
					title: title.trim() || undefined,
					body: edited ? body : undefined
				});
				saved = d;
				dirty = false;
				oncreated?.(d);
			} else {
				d = await drafts.update(saved.id, {
					values: cleanValues(values),
					body,
					edited,
					title: title.trim(),
					case_id: caseId,
					status: reviewed ? 'reviewed' : 'draft'
				});
				saved = d;
				dirty = false;
				say('Draft saved.');
			}
			title = d.title;
			preview = { body: d.body, html: d.html, missing: d.missing, checks: d.checks, derived: d.derived };
			return d;
		} catch (e) {
			error = e instanceof Error ? e.message : String(e);
			return null;
		} finally {
			saving = false;
		}
	}

	async function exportDocx() {
		const d = dirty || !saved ? await save() : saved;
		if (!d) return;
		const a = document.createElement('a');
		a.href = drafts.exportUrl(d.id);
		a.download = '';
		document.body.append(a);
		a.click();
		a.remove();
		say('Word file downloaded. It carries the DRAFT footer.');
	}

	function print() {
		mode = 'preview';
		// Let the preview pane show on phones before the dialog opens.
		setTimeout(() => window.print(), 50);
	}

	async function remove() {
		if (!saved) return;
		await drafts.remove(saved.id);
		dirty = false;
		ondeleted?.();
	}

	// ------------------------------------------------------------ AI facts

	async function draftFacts(field: string) {
		aiBusy = field;
		error = '';
		try {
			const r = await drafts.facts({ template: template.id, case_id: caseId || undefined, field, values: cleanValues(values) });
			suggestion = { field: r.field, text: r.text };
		} catch (e) {
			error = e instanceof Error ? e.message : String(e);
		} finally {
			aiBusy = '';
		}
	}

	function useSuggestion(how: 'replace' | 'append') {
		if (!suggestion) return;
		const cur = values[suggestion.field] ?? '';
		values[suggestion.field] = how === 'append' && cur.trim() ? `${cur.trim()}\n\n${suggestion.text}` : suggestion.text;
		suggestion = null;
		fieldsChanged();
	}

	function applyPenalty(v: Record<string, string>) {
		for (const [k, x] of Object.entries(v)) if (template.fields.some((f) => f.name === k)) values[k] = x;
		fieldsChanged();
		say('Penalty inputs copied into the draft.');
	}

	function goTo(name: string) {
		mode = 'fields';
		setTimeout(() => {
			const el = document.getElementById(`field-${name}`);
			el?.scrollIntoView({ block: 'center' });
			el?.querySelector<HTMLElement>('input,select,textarea')?.focus();
		}, 30);
	}

	// ------------------------------------------------------------ misc

	let flashTimer: ReturnType<typeof setTimeout> | undefined;
	function say(msg: string) {
		flash = msg;
		clearTimeout(flashTimer);
		flashTimer = setTimeout(() => (flash = ''), 4000);
	}

	beforeNavigate((nav) => {
		if (dirty && saved && nav.type !== 'leave' && !confirm('This draft has unsaved changes. Leave without saving?')) nav.cancel();
	});

	$effect(() => {
		const warn = (e: BeforeUnloadEvent) => {
			if (dirty && saved) e.preventDefault();
		};
		window.addEventListener('beforeunload', warn);
		return () => window.removeEventListener('beforeunload', warn);
	});
</script>

<div class="draft-editor">
	<div class="top no-print">
		<div class="title-field field">
			<label for="{uid}-title">Draft title</label>
			<input id="{uid}-title" bind:value={title} oninput={() => (dirty = true)} placeholder={`${template.title}: address`} />
		</div>
		<CasePicker bind:value={caseId} label="Case" none="No case" />
	</div>

	<div class="bar no-print">
		<div class="btn-row">
			<button type="button" class="btn" onclick={save} disabled={saving || (!dirty && !isNew)}>
				{saving ? 'Saving' : isNew ? 'Save draft' : dirty ? 'Save changes' : 'Saved'}
			</button>
			<button type="button" class="btn secondary" onclick={exportDocx} disabled={saving}>Export .docx</button>
			<button type="button" class="btn secondary" onclick={print}>Print</button>
			{#if !isNew}
				<button type="button" class="btn secondary danger-outline" onclick={() => confirmDelete?.open()}>Delete</button>
			{/if}
		</div>
		<p class="state" aria-live="polite">
			{#if flash}<span class="flash">{flash}</span>
			{:else if isNew}Not saved yet. Saving {caseId ? `links it to case ${caseId}` : 'keeps it in the office drafts'}.
			{:else if saved}Saved {fmtWhen(saved.updated_at)} by {saved.updated_by}{dirty ? '. Unsaved changes.' : '.'}{/if}
		</p>
	</div>

	{#if error}<p class="notice error-text no-print" role="alert">{error}</p>{/if}

	<div class="tabs no-print" role="tablist" aria-label="Draft view">
		<button type="button" role="tab" aria-selected={mode === 'fields'} onclick={() => (mode = 'fields')}>Fields</button>
		<button type="button" role="tab" aria-selected={mode === 'text'} onclick={() => (mode = 'text')}>
			Text{edited ? ' (edited)' : ''}
		</button>
		<button type="button" role="tab" class="phone-only" aria-selected={mode === 'preview'} onclick={() => (mode = 'preview')}>Preview</button>
	</div>

	<div class="layout" data-mode={mode}>
		<div class="pane pane-edit no-print">
			<section class="review sheet" aria-label="Review">
				<h3>Review</h3>
				<ul class="review-list">
					<li class:bad={missing.length > 0}>
						{#if missing.length === 0}
							Every required field is filled.
						{:else}
							{missing.length} required {missing.length === 1 ? 'field is' : 'fields are'} empty:
							{#each missing as m, i (m.name)}<button type="button" class="linkish" onclick={() => goTo(m.name)}>{m.label}</button>{i < missing.length - 1 ? ', ' : ''}{/each}
						{/if}
					</li>
					<li class:bad={flags.verify > 0}>
						{flags.verify === 0 ? 'No [VERIFY] tags in the text.' : `${flags.verify} [VERIFY] ${flags.verify === 1 ? 'tag marks a statement' : 'tags mark statements'} not yet checked against primary text. Check, then edit or remove each one.`}
					</li>
					{#if flags.open > 0}
						<li class="bad">{flags.open} [MISSING], [FILL] or [FACT NEEDED] {flags.open === 1 ? 'mark is' : 'marks are'} still in the text.</li>
					{/if}
					{#each checks as c (c.message)}
						<li class:bad={!c.ok} class:good={c.ok}><span class="ck">{c.ok ? 'Pass' : 'Check'}</span> {c.message}</li>
					{/each}
				</ul>
				{#if !isNew}
					<label class="check reviewed">
						<input type="checkbox" bind:checked={reviewed} onchange={() => (dirty = true)} />
						<span>I checked every citation in this draft against the primary source.</span>
					</label>
				{/if}
				{#if notes.length}
					<details class="notes">
						<summary>Sources and practice notes for this template</summary>
						{#each notes as n, i (i)}
							{#if n.type === 'p'}<p>{n.lines[0]}</p>
							{:else}<ul>{#each n.lines as l (l)}<li>{l}</li>{/each}</ul>{/if}
						{/each}
					</details>
				{/if}
			</section>

			<div class="pane-fields">
				{#if suggestion}
					<section class="suggestion sheet accent" aria-label="AI draft">
						<h3>AI draft for {label(suggestion.field)}</h3>
						<p class="muted small">From the case record.</p>
						<p class="sug-text">{suggestion.text}</p>
						<div class="btn-row">
							<button type="button" class="btn small" onclick={() => useSuggestion('replace')}>Use this text</button>
							<button type="button" class="btn secondary small" onclick={() => useSuggestion('append')}>Add below what is there</button>
							<button type="button" class="btn secondary small" onclick={() => (suggestion = null)}>Discard</button>
						</div>
					</section>
				{/if}

				{#if edited}
					<p class="notice">
						You edited the text directly, so field changes no longer rewrite it.
						<button type="button" class="linkish" onclick={() => confirmRebuild?.open()}>Rebuild the text from the fields</button>
					</p>
				{/if}

				<DraftForm
					fields={template.fields}
					bind:values
					missing={missing.map((m) => m.name)}
					onchange={fieldsChanged}
					onai={draftFacts}
					{aiBusy}
					aiNote={caseId ? 'Drafts this field from the case notes and the form.' : 'No case is linked, so the AI sees only the form. Link a case for better facts.'}
				/>

				{#if template.tools.includes('penalty')}
					{#if showPenalty}
						<DraftPenalty
							tier={values.penalty_tier}
							start={values.violation_start}
							end={values.violation_end}
							perDay={values.penalty_per_day}
							onapply={applyPenalty}
						/>
					{:else}
						<button type="button" class="btn secondary small" onclick={() => (showPenalty = true)}>Open the penalty helper</button>
					{/if}
				{/if}
			</div>

			<div class="pane-text">
				<label class="field" for="{uid}-body">
					<span>Text of the draft</span>
					<span class="help">Markdown: ## heading, - list, **bold**. Placeholders are already filled in. Edits here stop field changes from rewriting the text.</span>
					<textarea id="{uid}-body" class="body-text" value={body} oninput={(e) => textChanged(e.currentTarget.value)} spellcheck="true"></textarea>
				</label>
				{#if edited}
					<button type="button" class="btn secondary small" onclick={() => confirmRebuild?.open()}>Rebuild from fields</button>
				{/if}
			</div>
		</div>

		<div class="pane pane-preview">
			{#if failing.length}
				<p class="notice error-text no-print">{failing.length} date {failing.length === 1 ? 'check needs' : 'checks need'} attention. See the review box.</p>
			{/if}
			{#if preview}
				<DraftPreview html={preview.html} banner={saved?.banner ?? template.banner ?? BANNER} busy={rendering} />
			{:else}
				<div class="loading" role="status"><span class="loading-label">Building the preview</span><span class="loading-bar" aria-hidden="true"></span></div>
			{/if}
		</div>
	</div>
</div>

<CaseConfirm bind:this={confirmDelete} title="Delete this draft?" confirmLabel="Delete draft" onconfirm={remove}>
	<p>It is removed for every staff user, and its link leaves the case timeline. Export it first if you need a copy.</p>
</CaseConfirm>
<CaseConfirm bind:this={confirmRebuild} title="Rebuild the text from the fields?" confirmLabel="Rebuild" busyLabel="Rebuilding" onconfirm={rebuild}>
	<p>Your direct edits to the text are replaced by the template filled from the current fields.</p>
</CaseConfirm>

<style>
	.top {
		display: grid;
		grid-template-columns: minmax(0, 1.4fr) minmax(0, 1fr);
		gap: 0 20px;
		align-items: end;
	}
	.bar {
		display: flex;
		flex-wrap: wrap;
		justify-content: space-between;
		align-items: center;
		gap: 10px 20px;
		padding: 12px 0;
		margin-bottom: 16px;
		border-top: 1px solid var(--rule);
		border-bottom: 1px solid var(--rule);
	}
	.state {
		margin: 0;
		font: 0.85rem var(--sans);
		color: var(--muted);
	}
	.flash {
		color: var(--accent);
		font-weight: 600;
	}
	.danger-outline {
		border-color: var(--error);
		color: var(--error);
	}
	.tabs {
		display: flex;
		gap: 0;
		margin: 0 0 16px;
		border-bottom: 1px solid var(--rule);
	}
	.tabs button {
		cursor: pointer;
		border: 0;
		border-bottom: 3px solid transparent;
		margin-bottom: -1px;
		background: transparent;
		color: var(--muted);
		font: 600 0.9rem var(--sans);
		padding: 8px 16px;
	}
	.tabs button[aria-selected='true'] {
		color: var(--text);
		border-bottom-color: var(--accent);
	}
	.tabs button:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: -2px;
	}
	.layout {
		display: grid;
		grid-template-columns: minmax(0, 1fr) minmax(0, 1.15fr);
		gap: 28px;
		align-items: start;
	}
	.pane-preview {
		position: sticky;
		top: 16px;
	}
	.layout[data-mode='fields'] .pane-text,
	.layout[data-mode='text'] .pane-fields,
	.layout[data-mode='preview'] .pane-text {
		display: none;
	}
	.phone-only {
		display: none;
	}
	.review {
		margin-bottom: 20px;
	}
	.review-list {
		margin: 0 0 12px;
		padding: 0;
		list-style: none;
		font: 0.88rem/1.5 var(--sans);
	}
	.review-list li {
		padding: 6px 0 6px 12px;
		border-left: 3px solid var(--border);
		margin-bottom: 6px;
	}
	.review-list li.bad {
		border-left-color: var(--accent);
	}
	.review-list li.good {
		border-left-color: var(--rule);
	}
	.ck {
		font-weight: 700;
		margin-right: 4px;
	}
	.bad .ck {
		color: var(--accent);
	}
	.linkish {
		cursor: pointer;
		border: 0;
		background: none;
		padding: 0;
		color: var(--text);
		font: inherit;
		text-decoration: underline;
		text-decoration-color: var(--accent);
		text-underline-offset: 2px;
	}
	.linkish:focus-visible {
		outline: 2px solid var(--accent);
	}
	.reviewed {
		font: 0.88rem/1.45 var(--sans);
		margin-bottom: 10px;
	}
	.notes {
		border-top: 1px solid var(--border);
		padding-top: 10px;
		font-size: 0.88rem;
	}
	.notes summary {
		cursor: pointer;
		font: 600 0.85rem var(--sans);
	}
	.notes p,
	.notes ul {
		margin: 8px 0;
		color: var(--muted);
		line-height: 1.5;
	}
	.notes ul {
		padding-left: 1.2em;
	}
	.suggestion {
		margin-bottom: 20px;
	}
	.sug-text {
		white-space: pre-wrap;
		font-family: var(--serif);
		border-left: 2px solid var(--accent);
		padding-left: 12px;
	}
	.small {
		font-size: 0.85rem;
	}
	.body-text {
		min-height: 60vh;
		font: 0.9rem/1.55 ui-monospace, 'SFMono-Regular', Menlo, Consolas, monospace;
		background: var(--surface);
	}
	@media (max-width: 900px) {
		.layout {
			grid-template-columns: minmax(0, 1fr);
		}
		.pane-preview {
			position: static;
		}
		.phone-only {
			display: inline-block;
		}
		.layout[data-mode='fields'] .pane-preview,
		.layout[data-mode='text'] .pane-preview,
		.layout[data-mode='preview'] .pane-edit {
			display: none;
		}
	}
	@media (max-width: 640px) {
		.top {
			grid-template-columns: minmax(0, 1fr);
		}
		.tabs button {
			padding: 8px 12px;
		}
	}
	@media print {
		.layout {
			display: block;
		}
		.pane-edit {
			display: none !important;
		}
		.pane-preview {
			display: block !important;
			position: static;
		}
	}
</style>
