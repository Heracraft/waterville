<script lang="ts">
	import type { Snippet } from 'svelte';
	import ThemeToggle from './ThemeToggle.svelte';
	import { chrome } from '$lib/chrome.svelte';

	let {
		title = 'Waterville Codes RAG',
		eyebrow = 'City of Waterville, Maine',
		showNewChat = false,
		onNewChat,
		inert = false,
		compact = false,
		actions,
		children
	}: {
		title?: string;
		/** Small meta line above the title. */
		eyebrow?: string;
		showNewChat?: boolean;
		onNewChat?: () => void;
		/** Set while a modal source panel covers the page. */
		inert?: boolean;
		/** Smaller title block, for staff pages and the embed. */
		compact?: boolean;
		/** Extra buttons in the meta line, before New chat. */
		actions?: Snippet;
		/** Rendered under the title, e.g. StaffNav. */
		children?: Snippet;
	} = $props();
</script>

<header class="site" class:compact inert={inert || chrome.modal}>
	<div class="wrap">
		<div class="meta">
			<span>{eyebrow}</span>
			<span class="meta-actions">
				{@render actions?.()}
				<button type="button" id="clear-chat" class="theme-toggle" hidden={!showNewChat} onclick={() => onNewChat?.()}>
					<svg viewBox="0 0 16 16" aria-hidden="true"
						><path
							d="M2.5 8a5.5 5.5 0 1 0 1.6-3.9M2.5 2.5v3h3"
							fill="none"
							stroke="currentColor"
							stroke-width="1.4"
							stroke-linecap="round"
							stroke-linejoin="round"
						/></svg
					>
					<span>New chat</span>
				</button>
				<ThemeToggle />
			</span>
		</div>
		<h1>{title}</h1>
		{@render children?.()}
	</div>
</header>
