<script lang="ts">
	import type { Source } from '$lib/api';
	import { chipHref } from '$lib/answer';

	let {
		source,
		label,
		occ,
		active = false,
		onopen
	}: {
		source: Source;
		/** The number as the answer wrote it, e.g. "3" for [3] and [3.2]. */
		label: string;
		/** Index of this chip among all citations in the answer. */
		occ: number;
		active?: boolean;
		/** Opens the source panel. Return false to let the link act normally. */
		onopen?: (el: HTMLElement) => boolean;
	} = $props();

	const name = $derived(source.citation || source.title || '');
	const href = $derived(chipHref(source));
	let el = $state<HTMLElement>();

	function click(e: MouseEvent) {
		if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
		if (el && onopen?.(el)) e.preventDefault();
	}

	function keydown(e: KeyboardEvent) {
		// Links fire click on Enter by themselves.
		if (href || (e.key !== 'Enter' && e.key !== ' ')) return;
		if (el && onopen?.(el)) e.preventDefault();
	}
</script>

{#if href}<a
		bind:this={el}
		class="cite"
		class:is-active={active}
		{href}
		target="_blank"
		rel="noopener"
		data-n={source.n}
		data-occ={occ}
		aria-controls="panel"
		aria-current={active ? 'true' : undefined}
		title={name}
		aria-label="Source {source.n}: {name}"
		onclick={click}
		onkeydown={keydown}>{label}</a
	>{:else}<!-- svelte-ignore a11y_missing_attribute --><a
		bind:this={el}
		class="cite"
		class:is-active={active}
		role="button"
		tabindex="0"
		data-n={source.n}
		data-occ={occ}
		aria-controls="panel"
		aria-current={active ? 'true' : undefined}
		title={name}
		aria-label="Source {source.n}: {name}"
		onclick={click}
		onkeydown={keydown}>{label}</a
	>{/if}
