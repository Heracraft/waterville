<script lang="ts">
	// Tools under each staff answer (B2 and save to case): copy the answer with
	// its citations resolved, copy the cited sections' citations, save the
	// answer into the chosen case notebook.
	import { api, ApiError } from '$lib/api';
	import type { BotMessage } from '$lib/chat.svelte';
	import { staff } from '$lib/staff.svelte';
	import DeskCopyButton from './DeskCopyButton.svelte';
	import { answerForCopy, citedNumbers, fullCitation, type DeskSource } from './DeskCite';

	let {
		msg,
		edition = null,
		caseId = '',
		caseName = '',
		onchoosecase
	}: {
		msg: BotMessage;
		edition?: string | null;
		/** The desk's chosen case ('' for none). */
		caseId?: string;
		caseName?: string;
		/** Brings the case picker into view when no case is chosen yet. */
		onchoosecase?: () => void;
	} = $props();

	const sources = $derived(msg.sources as DeskSource[]);
	const cited = $derived(citedNumbers(msg.answer).filter((n) => sources.some((s) => s.n === n)));
	const stamp = $derived((typeof staff.user?.stamp === 'string' && staff.user.stamp) || undefined);

	let saving = $state(false);
	let saved = $state<{ caseId: string; caseName: string } | null>(null);
	let problem = $state('');

	function copyAnswer() {
		return answerForCopy(msg.answer, sources, { edition, question: msg.question, stamp });
	}

	function copyCitations() {
		return cited
			.map((n) => `[${n}] ${fullCitation(sources.find((s) => s.n === n)!, { edition })}`)
			.join('\n');
	}

	async function save() {
		problem = '';
		if (!caseId) {
			problem = 'Choose a case at the top of the desk first.';
			onchoosecase?.();
			return;
		}
		saving = true;
		try {
			await api.post(`/api/staff/cases/${encodeURIComponent(caseId)}/items`, {
				kind: 'answer',
				...(msg.meta?.answer_id ? { answer_id: msg.meta.answer_id } : {}),
				question: msg.question,
				answer: msg.answer,
				sources: sources.slice(0, 40).map((s) => ({ ...s, text: s.text ? s.text.slice(0, 20000) : s.text }))
			});
			saved = { caseId, caseName };
		} catch (e) {
			problem =
				e instanceof ApiError && e.status === 404
					? 'That case no longer exists. Choose another.'
					: e instanceof Error
						? `Could not save: ${e.message}`
						: 'Could not save.';
		} finally {
			saving = false;
		}
	}
</script>

<div class="desk-tools no-print">
	<div class="btn-row">
		<DeskCopyButton label="Copy answer" testid="copy-answer" copy={copyAnswer} />
		{#if cited.length}
			<DeskCopyButton label={cited.length === 1 ? 'Copy citation' : 'Copy citations'} testid="copy-citations" copy={copyCitations} />
		{/if}
		<button type="button" class="btn small" data-testid="save-to-case" disabled={saving} onclick={save}>
			{saving ? 'Saving' : caseId ? `Save to ${caseName || 'case'}` : 'Save to case'}
		</button>
	</div>
	{#if saved}
		<div class="desk-saved" role="status">
			Saved to <a href="/staff/cases/{encodeURIComponent(saved.caseId)}">{saved.caseName || `case ${saved.caseId}`}</a>.
		</div>
	{/if}
	{#if problem}
		<div class="desk-problem" role="alert">{problem}</div>
	{/if}
</div>

<style>
	.desk-tools {
		margin-top: 14px;
		padding-top: 14px;
		border-top: 1px solid var(--border);
		font-family: var(--sans);
	}
	.desk-tools .btn-row {
		gap: 8px;
	}
	.desk-saved,
	.desk-problem {
		margin: 10px 0 0;
		font-size: 0.88rem;
	}
	.desk-problem {
		color: var(--error);
	}
</style>
