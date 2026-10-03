<script lang="ts" module>
	/** kicker replaces the "Source n" line above the title (the research desk's citation lookup). */
	export type PanelView = { source: Source; sentences: string[]; key: number; kicker?: string };
</script>

<script lang="ts">
	// The source text beside the answer (docked on wide screens) or over it
	// (a modal sheet on narrow ones), with the cited passage highlighted.
	import type { Snippet } from 'svelte';
	import type { Source } from '$lib/api';
	import { markFigures, matchPassages, pages, parseBlocks, renderBlocks, safeUrl } from '$lib/source';
	import { rememberSource } from '$lib/offline';

	const TYPE_NAMES: Record<string, string> = { code: 'City Code', attachment: 'City Code attachment' };

	let {
		view,
		wide,
		calm = false,
		onclose,
		actions
	}: {
		view: PanelView | null;
		/** Docked panel (complementary) when true, modal dialog when false. */
		wide: boolean;
		/** prefers-reduced-motion */
		calm?: boolean;
		onclose: () => void;
		/** Extra controls in the footer beside "Open original" (staff: copy citation). */
		actions?: Snippet<[Source]>;
	} = $props();

	let titleEl = $state<HTMLElement>();
	let scrollEl = $state<HTMLElement>();
	let bodyEl = $state<HTMLElement>();

	export function focusTitle() {
		titleEl?.focus({ preventScroll: true });
	}

	export function contains(el: Element | null) {
		return !!el && !!titleEl?.closest('.panel')?.contains(el);
	}

	const s = $derived(view?.source);
	// B11: keep the opened text on this device for offline reading (not staff notes).
	$effect(() => {
		if (view) rememberSource(view.source);
	});
	const where = $derived(s ? pages(s) : '');
	const blocks = $derived(parseBlocks(s?.text || ''));
	const found = $derived(view && view.sentences.length ? matchPassages(blocks, view.sentences) : []);
	const html = $derived(renderBlocks(blocks, new Set(found.map((f) => f.i))));
	const href = $derived(s ? safeUrl(s.open_url) || safeUrl(s.url) : '');
	const note = $derived(
		!view
			? ''
			: s?.source_type === 'model_code_ref'
				? "The full text of this code is not available here. The link below opens the publisher's viewer."
				: view.sentences.length && !found.length
					? 'Could not pinpoint the exact passage. The full source text is below.'
					: ''
	);
	const openText = $derived(
		/\.pdf(?:$|[#?])/i.test(href) && s?.page_start ? `Open original PDF at page ${s.page_start}` : 'Open original'
	);

	// After each open: mark shared figures, then bring the first highlight into view.
	$effect(() => {
		if (!view || !bodyEl) return;
		void html;
		for (const f of found) markFigures(bodyEl.querySelector(`[data-b="${f.i}"]`), f.figs);
		const raf = requestAnimationFrame(scrollToHighlight);
		return () => cancelAnimationFrame(raf);
	});

	function scrollToHighlight() {
		if (!bodyEl || !scrollEl) return;
		const hit = bodyEl.querySelector('.hl');
		if (!hit) return void (scrollEl.scrollTop = 0);
		const top = hit.getBoundingClientRect().top - scrollEl.getBoundingClientRect().top + scrollEl.scrollTop;
		scrollEl.scrollTo({ top: Math.max(0, top - 72), behavior: calm ? 'auto' : 'smooth' });
	}
</script>

<div id="panel-backdrop" class="panel-backdrop" hidden={!view || wide} onclick={onclose} role="presentation"></div>
<aside
	id="panel"
	class="panel"
	hidden={!view}
	role={wide ? 'complementary' : 'dialog'}
	aria-label={wide ? 'Source text' : undefined}
	aria-labelledby={wide ? undefined : 'panel-title'}
	aria-modal={wide ? undefined : 'true'}
>
	<div class="panel-head">
		<div class="panel-id">
			<h2 id="panel-title" tabindex="-1" bind:this={titleEl}>
				{#if s}<span class="panel-n">{view?.kicker || `Source ${s.n}`}</span> {s.citation || s.title || ''}{:else}Source{/if}
			</h2>
			<div id="panel-meta" class="panel-meta">
				{#if s}<span class="tag">{s.label || TYPE_NAMES[s.source_type || ''] || 'Source'}</span
					>{#if where}<span class="pg">{where[0].toUpperCase() + where.slice(1)}</span>{/if}{#if s.breadcrumb}<span
							class="crumb">{s.breadcrumb}</span
						>{/if}{/if}
			</div>
		</div>
		<button type="button" class="panel-close" aria-label="Close source" onclick={onclose}>
			<svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true"
				><path d="M3.5 3.5l9 9m0-9l-9 9" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" fill="none" /></svg
			>
		</button>
	</div>
	<div id="panel-scroll" class="panel-scroll" bind:this={scrollEl}>
		<div id="panel-claim" class="panel-claim" hidden={!view?.sentences.length}>
			{#if view?.sentences.length}<span class="claim-label">The answer says</span
				>{#each view.sentences as t, i (i)}<q>{t}</q>{/each}{/if}
		</div>
		<p id="panel-note" class="panel-note" hidden={!note}>{note}</p>
		{#key view?.key}
			<div id="panel-body" class="panel-body" bind:this={bodyEl}>{@html html}</div>
		{/key}
	</div>
	<div class="panel-foot">
		<a id="panel-open" target="_blank" rel="noopener" hidden={!href} href={href || undefined}>{openText}</a>
		{#if s && actions}{@render actions(s)}{/if}
	</div>
</aside>
