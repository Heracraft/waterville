<script lang="ts" module>
	export const PUBLIC_EXAMPLES = [
		'How tall can a fence be in a residential zone?',
		'What does a short-term rental license cost?',
		'Can I keep chickens in my backyard?',
		'Are consumer fireworks allowed in Waterville?'
	];
</script>

<script lang="ts">
	// The thread, the ask bar and the source panel. Ported from app/web/app.js.
	import { tick, untrack, type Snippet } from 'svelte';
	import { MediaQuery } from 'svelte/reactivity';
	import { citedSentence, sentencesFor } from '$lib/source';
	import { autoFollow } from '$lib/scroll';
	import { chrome } from '$lib/chrome.svelte';
	import type { BotMessage, ChatSession } from '$lib/chat.svelte';
	import type { Source } from '$lib/api';
	import Answer from './Answer.svelte';
	import SourcePanel, { type PanelView } from './SourcePanel.svelte';

	let {
		session,
		examples = PUBLIC_EXAMPLES,
		hint = 'Try one of these',
		placeholder = 'Ask about the City Code...',
		before,
		intro,
		extra,
		panelActions
	}: {
		session: ChatSession;
		examples?: string[];
		hint?: string;
		placeholder?: string;
		/** Rendered at the top of main, above the intro and thread (filters, tools). */
		before?: Snippet;
		/** Replaces the example grid inside #intro. */
		intro?: Snippet<[(q: string) => void]>;
		/** Rendered under each finished answer. */
		extra?: Snippet<[BotMessage]>;
		/** Rendered in the source panel footer for the open source (staff: copy citation). */
		panelActions?: Snippet<[Source]>;
	} = $props();

	/** Opens a source that no answer cites (the research desk's citation lookup).
	 * Focus returns to `trigger` when the panel closes. */
	export function showSource(source: Source, trigger: HTMLElement, kicker?: string) {
		session.active = { msgId: -1, n: source.n, occ: null, trigger };
		view = { source, sentences: [], key: ++opens, kicker };
		tick().then(() => panel?.focusTitle());
	}

	const wideQ = new MediaQuery('min-width: 960px', true);
	const calmQ = new MediaQuery('prefers-reduced-motion: reduce', false);
	const wide = $derived(wideQ.current);

	let input = $state('');
	let inputEl = $state<HTMLTextAreaElement>();
	let formEl = $state<HTMLFormElement>();
	let panel = $state<ReturnType<typeof SourcePanel>>();
	let view = $state<PanelView | null>(null);
	let opens = 0;

	const open = $derived(view !== null);

	// Modal on narrow screens: header and main go inert, the backdrop shows.
	$effect(() => {
		session.modal = chrome.modal = open && !wide;
		return () => (chrome.modal = false);
	});
	$effect(() => {
		document.body.classList.toggle('panel-open', open);
		return () => document.body.classList.remove('panel-open');
	});
	$effect(() => {
		if (session.modal && !panel?.contains(document.activeElement)) panel?.focusTitle();
	});
	// The session dropped the active source (New chat).
	$effect(() => {
		if (!session.active && view) view = null;
	});

	function openSource(msg: BotMessage, n: number, occ: number | null, trigger: HTMLElement): boolean {
		const s = msg.sources.find((x) => x.n === n);
		if (!s) return false;
		const sentences = occ == null ? sentencesFor(msg.answer, n) : [citedSentence(msg.answer, occ)].filter(Boolean);
		session.active = { msgId: msg.id, n, occ, trigger };
		view = { source: s, sentences, key: ++opens };
		tick().then(() => {
			panel?.focusTitle();
			if (wide && formEl && trigger.getBoundingClientRect().bottom > formEl.getBoundingClientRect().top) {
				trigger.scrollIntoView({ block: 'center', behavior: calmQ.current ? 'auto' : 'smooth' });
			}
		});
		return true;
	}

	async function closePanel() {
		if (!view) return;
		view = null;
		const a = session.active;
		session.active = null;
		if (!a) return;
		await tick();
		const sel = a.occ == null ? `.sources a[data-n="${a.n}"]` : `.cite[data-occ="${a.occ}"]`;
		const back = a.trigger.isConnected
			? a.trigger
			: document.querySelector<HTMLElement>(`#thread .msg[data-id="${a.msgId}"] ${sel}`);
		back?.focus();
	}

	function onKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape' && view) {
			e.preventDefault();
			closePanel();
		}
	}

	async function ask(question: string) {
		// undefined: New chat cut the answer off, and New chat handles focus.
		const bot = await session.ask(question);
		if (!bot) return;
		// No answer came back: put the question back so it can be sent again.
		if (bot.error && !bot.answer && !input.trim()) {
			input = question;
			await tick();
			grow();
		}
		inputEl?.focus();
	}

	function submit(e: SubmitEvent) {
		e.preventDefault();
		const q = input.trim();
		if (!q || session.busy) return;
		input = '';
		if (inputEl) inputEl.style.height = '';
		ask(q);
	}

	function keydown(e: KeyboardEvent) {
		if (e.key === 'Enter' && !e.shiftKey) {
			e.preventDefault();
			formEl?.requestSubmit();
		}
	}

	function grow() {
		if (!inputEl) return;
		inputEl.style.height = 'auto';
		inputEl.style.height = inputEl.scrollHeight + 'px';
	}

	// New chat: reset the ask bar, scroll to the top and focus the input.
	let seenResets = untrack(() => session.resets);
	$effect(() => {
		if (session.resets === seenResets) return;
		seenResets = session.resets;
		view = null;
		input = '';
		if (inputEl) inputEl.style.height = '';
		window.scrollTo({ top: 0 });
		inputEl?.focus();
	});
</script>

<svelte:window onkeydown={onKeydown} />

<main class="wrap" inert={session.modal}>
	{@render before?.()}
	<section id="intro" aria-label="Example questions" hidden={session.started}>
		{#if intro}
			{@render intro(ask)}
		{:else}
			<p class="hint">{hint}</p>
			<div class="examples">
				{#each examples as q (q)}
					<button type="button" onclick={() => ask(q)}>{q}</button>
				{/each}
			</div>
		{/if}
	</section>

	<ol id="thread" aria-live="polite" use:autoFollow>
		{#each session.messages as m (m.id)}
			{#if m.role === 'user'}
				<li class="msg user">{m.text}</li>
			{:else}
				<li class="msg bot" data-id={m.id}>
					<Answer msg={m} active={session.active} onopen={openSource} {extra} />
				</li>
			{/if}
		{/each}
	</ol>

	<form id="ask" autocomplete="off" bind:this={formEl} onsubmit={submit}>
		<label for="q" class="sr-only">Your question</label>
		<textarea
			id="q"
			rows="1"
			maxlength="1000"
			{placeholder}
			required
			bind:this={inputEl}
			bind:value={input}
			onkeydown={keydown}
			oninput={grow}
		></textarea>
		<button type="submit" id="send" disabled={session.busy}>Ask</button>
	</form>
</main>

<SourcePanel bind:this={panel} {view} {wide} calm={calmQ.current} onclose={closePanel} actions={panelActions} />
