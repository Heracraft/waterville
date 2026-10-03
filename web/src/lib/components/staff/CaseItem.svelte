<script lang="ts">
	// One entry on a case timeline: a note, a saved answer with its sources,
	// a deadline or a linked draft. ondelete asks the page to confirm.
	import Answer from '$lib/components/Answer.svelte';
	import Stamp from '$lib/components/Stamp.svelte';
	import type { BotMessage } from '$lib/chat.svelte';
	import { KIND_LABELS, dueLabel, daysUntil, fmtDay, fmtWhen, type CaseItem } from './CaseData';

	let { item, ondelete }: { item: CaseItem; ondelete?: (item: CaseItem) => void } = $props();

	// Answer renders a BotMessage; a saved answer is a finished one.
	const msg = $derived<BotMessage | null>(
		item.kind === 'answer'
			? {
					id: 0,
					role: 'bot',
					question: item.question,
					answer: item.answer,
					sources: item.sources || [],
					meta: null,
					status: 'done',
					error: null,
					loadingLabel: ''
				}
			: null
	);
	const due = $derived(item.kind === 'deadline' ? daysUntil(item.date) : 0);
</script>

<li class="entry kind-{item.kind}" id="item-{item.id}">
	<div class="rail" aria-hidden="true"></div>
	<div class="head">
		<span class="kind">{KIND_LABELS[item.kind]}</span>
		<span class="when"><time datetime={item.created_at}>{fmtWhen(item.created_at)}</time>, {item.created_by}</span>
		{#if ondelete}
			<button type="button" class="del no-print" onclick={() => ondelete?.(item)} aria-label="Delete this {KIND_LABELS[item.kind].toLowerCase()}">
				Delete
			</button>
		{/if}
	</div>

	{#if item.kind === 'note'}
		<div class="note">{item.text}</div>
	{:else if item.kind === 'deadline'}
		<div class="deadline" class:past={due < 0} class:soon={due >= 0 && due <= 7}>
			<div class="date">
				<strong>{fmtDay(item.date)}</strong>
				<span class="due">{dueLabel(item.date)}</span>
			</div>
			<div class="what">
				<span class="dl-label">{item.label}</span>
				{#if item.citation}<span class="cite-text">{item.citation}</span>{/if}
				{#if item.trigger}<span class="trigger">Trigger: {item.trigger}</span>{/if}
				{#if item.note}<p class="dl-note">{item.note}</p>{/if}
			</div>
		</div>
	{:else if item.kind === 'draft'}
		<div class="draft">
			<a href="/staff/drafts/{encodeURIComponent(item.draft_id)}">{item.title || item.template || 'Draft'}</a>
			{#if item.template && item.title}<span class="muted">{item.template}</span>{/if}
		</div>
	{:else if item.kind === 'answer' && msg}
		{#if item.question}<p class="question">{item.question}</p>{/if}
		<div class="msg bot saved">
			<Answer {msg} />
			<Stamp text={item.stamp || undefined} />
		</div>
		{#if item.note}<p class="answer-note"><span>Note</span>{item.note}</p>{/if}
	{/if}
</li>

<style>
	.entry {
		position: relative;
		padding: 0 0 26px 26px;
	}
	.rail {
		position: absolute;
		left: 4px;
		top: 0;
		bottom: 0;
		border-left: 1px solid var(--rule);
	}
	.entry:last-child .rail {
		bottom: auto;
		height: 14px;
	}
	.entry::before {
		content: '';
		position: absolute;
		left: 0;
		top: 5px;
		width: 9px;
		height: 9px;
		background: var(--bg);
		border: 1px solid var(--rule);
	}
	.kind-answer::before,
	.kind-deadline::before {
		background: var(--accent);
		border-color: var(--accent);
	}
	.head {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: 4px 12px;
		margin-bottom: 8px;
		font: 0.82rem/1.4 var(--sans);
	}
	.kind {
		color: var(--accent);
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		font-size: 0.72rem;
	}
	.when {
		color: var(--muted);
	}
	.del {
		margin-left: auto;
		cursor: pointer;
		border: 1px solid transparent;
		background: transparent;
		color: var(--muted);
		font: 500 0.78rem var(--sans);
		padding: 2px 8px;
	}
	.del:hover,
	.del:focus-visible {
		border-color: var(--error);
		color: var(--error);
		outline: none;
	}
	.note {
		white-space: pre-wrap;
		background: var(--surface);
		border: 1px solid var(--border);
		padding: 12px 16px;
		font: 400 1rem/1.6 var(--serif);
		overflow-wrap: anywhere;
	}
	.deadline {
		display: grid;
		grid-template-columns: 11em 1fr;
		background: var(--surface);
		border: 1px solid var(--rule);
	}
	.deadline .date {
		display: grid;
		align-content: start;
		gap: 2px;
		padding: 10px 14px;
		border-right: 1px solid var(--rule);
		background: var(--bg);
		font: 0.9rem var(--sans);
	}
	.deadline .date strong {
		font: 400 1.1rem/1.25 var(--serif);
	}
	.due {
		color: var(--muted);
		font-size: 0.8rem;
	}
	.soon .due {
		color: var(--accent);
		font-weight: 600;
	}
	.past .due {
		color: var(--error);
		font-weight: 600;
	}
	.what {
		display: grid;
		gap: 2px;
		padding: 10px 14px;
		font: 0.92rem/1.45 var(--sans);
		min-width: 0;
	}
	.dl-label {
		font-weight: 600;
	}
	.cite-text {
		color: var(--accent);
		font-weight: 600;
		font-size: 0.85rem;
	}
	.trigger {
		color: var(--muted);
		font-size: 0.85rem;
	}
	.dl-note {
		margin: 4px 0 0;
		white-space: pre-wrap;
	}
	.draft {
		display: flex;
		flex-wrap: wrap;
		gap: 4px 12px;
		align-items: baseline;
		padding: 10px 14px;
		background: var(--surface);
		border: 1px solid var(--border);
		font: 0.95rem var(--sans);
	}
	.draft a {
		color: var(--text);
		font-weight: 600;
		text-decoration-color: var(--accent);
	}
	.question {
		margin: 0 0 10px;
		font: 300 1.3rem/1.3 var(--serif);
		overflow-wrap: anywhere;
	}
	.msg.bot.saved {
		margin-left: 0;
	}
	.saved :global(.stamp) {
		margin-top: 14px;
	}
	.answer-note {
		margin: 10px 0 0;
		padding: 8px 14px;
		border-left: 3px solid var(--rule);
		background: var(--surface);
		font: 0.92rem/1.5 var(--sans);
		white-space: pre-wrap;
	}
	.answer-note span {
		display: block;
		font-weight: 600;
		font-size: 0.78rem;
		color: var(--muted);
	}
	@media (max-width: 640px) {
		.entry {
			padding-left: 20px;
		}
		.deadline {
			grid-template-columns: 1fr;
		}
		.deadline .date {
			border-right: 0;
			border-bottom: 1px solid var(--rule);
			grid-auto-flow: column;
			justify-content: space-between;
			align-items: baseline;
		}
		.msg.bot.saved {
			padding: 16px 16px 18px;
		}
		.msg.bot.saved :global(.sources) {
			margin: 18px -16px -18px;
			padding: 12px 16px 4px;
		}
	}
	@media print {
		.entry {
			break-inside: avoid-page;
		}
		.saved :global(details.sources) {
			display: block;
		}
	}
</style>
