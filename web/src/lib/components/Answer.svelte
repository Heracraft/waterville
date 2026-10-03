<script lang="ts">
	import type { Snippet } from 'svelte';
	import { parseAnswer, shownSources, chipHref, type Inline } from '$lib/answer';
	import { pages } from '$lib/source';
	import type { ActiveSource, BotMessage } from '$lib/chat.svelte';
	import CitationChip from './CitationChip.svelte';
	import Stamp from './Stamp.svelte';

	let {
		msg,
		active = null,
		onopen,
		extra
	}: {
		msg: BotMessage;
		active?: ActiveSource | null;
		/** Opens source n; occ is the chip index, or null for a sources-list link. */
		onopen?: (msg: BotMessage, n: number, occ: number | null, el: HTMLElement) => boolean;
		/** Rendered after the sources once the answer is done (checklists, save to case). */
		extra?: Snippet<[BotMessage]>;
	} = $props();

	const blocks = $derived(parseAnswer(msg.answer, msg.sources));
	const done = $derived(msg.status === 'done');
	const list = $derived(done ? shownSources(msg.sources, msg.answer) : null);
	const mine = $derived(active && active.msgId === msg.id ? active : null);

	function srcLabel(s: BotMessage['sources'][number]) {
		const page = pages(s) ? ` (${pages(s)})` : '';
		return (s.title || s.citation) + page;
	}

	function crumb(s: BotMessage['sources'][number]) {
		return (s.breadcrumb || '').split(' > ').slice(0, -1).join(' > ');
	}

	function srcClick(e: MouseEvent, n: number) {
		if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
		if (onopen?.(msg, n, null, e.currentTarget as HTMLElement)) e.preventDefault();
	}

	function srcKey(e: KeyboardEvent, n: number, href: string) {
		if (href || (e.key !== 'Enter' && e.key !== ' ')) return;
		if (onopen?.(msg, n, null, e.currentTarget as HTMLElement)) e.preventDefault();
	}
</script>

{#snippet inline(nodes: Inline[])}{#each nodes as node, i (i)}{#if node.t === 'text'}{node.s}{:else if node.t === 'strong'}<strong
				>{@render inline(node.c)}</strong
			>{:else if node.t === 'em'}<em>{@render inline(node.c)}</em>{:else}<CitationChip
				source={node.source}
				label={node.label}
				occ={node.occ}
				active={mine?.occ === node.occ}
				onopen={(el) => onopen?.(msg, node.n, node.occ, el) ?? false}
			/>{/if}{/each}{/snippet}

{#if msg.status === 'loading' && !done}
	<div class="loading" role="status">
		<span class="loading-label">{msg.loadingLabel}</span><span class="loading-bar" aria-hidden="true"></span>
	</div>
{:else if done && msg.error && !msg.answer}
	<p class="error">{msg.error}</p>
{:else}
	{#each blocks as b, i (i)}
		{#if b.t === 'p'}
			<p>{@render inline(b.c)}</p>
		{:else if b.t === 'ul'}
			<ul>
				{#each b.items as item, j (j)}<li>{@render inline(item)}</li>{/each}
			</ul>
		{:else if b.t === 'quote'}
			<blockquote>
				{#each b.lines as l, j (j)}<p>{@render inline(l)}</p>{/each}
			</blockquote>
		{:else}
			<ol>
				{#each b.items as item, j (j)}<li>{@render inline(item)}</li>{/each}
			</ol>
		{/if}
	{/each}
	{#if done && msg.error}<p class="error">{msg.error}</p>{/if}
	{#if list && list.shown.length}
		<details class="sources" open>
			<summary>{list.cited ? 'Sources' : 'Related sections'} ({list.shown.length})</summary>
			<ol>
				{#each list.shown as s (s.n)}
					{@const href = chipHref(s)}
					{@const on = mine?.occ === null && mine?.n === s.n}
					<li>
						<span class="n">{s.n}.</span>{#if href}<a
								class="src"
								class:is-active={on}
								aria-current={on ? 'true' : undefined}
								{href}
								target="_blank"
								rel="noopener"
								data-n={s.n}
								aria-controls="panel"
								onclick={(e) => srcClick(e, s.n)}
								onkeydown={(e) => srcKey(e, s.n, href)}>{srcLabel(s)}</a
							>{:else}<!-- svelte-ignore a11y_missing_attribute --><a
								class="src"
								class:is-active={on}
								aria-current={on ? 'true' : undefined}
								role="button"
								tabindex="0"
								data-n={s.n}
								aria-controls="panel"
								onclick={(e) => srcClick(e, s.n)}
								onkeydown={(e) => srcKey(e, s.n, href)}>{srcLabel(s)}</a
							>{/if}<span class="crumb">{crumb(s)}</span>
					</li>
				{/each}
			</ol>
		</details>
	{/if}
	{#if done && msg.meta?.mode === 'staff' && msg.answer}
		<Stamp />
	{/if}
	{#if done && msg.answer}{@render extra?.(msg)}{/if}
{/if}

<style>
	/* Verbatim quotes in staff answers: the controlling text on the page color, set off by an ink rule. */
	blockquote {
		margin: 4px 0 14px;
		padding: 10px 16px;
		background: var(--bg);
		border-left: 3px solid var(--rule);
	}
	blockquote p {
		margin: 0 0 8px;
	}
	blockquote p:last-child {
		margin-bottom: 0;
	}
</style>
