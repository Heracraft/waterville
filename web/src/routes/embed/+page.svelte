<script lang="ts">
	// A6: compact chat for an iframe on the city site. The server allows
	// framing of /embed only, and only from EMBED_ORIGINS; every other page
	// refuses to be framed, so links out of the embed open a new tab.
	import Header from '$lib/components/Header.svelte';
	import Chat from '$lib/components/Chat.svelte';
	import PublicAnswerCards from '$lib/components/PublicAnswerCards.svelte';
	import PublicTools from '$lib/components/PublicTools.svelte';
	import InsightFeedback from '$lib/components/InsightFeedback.svelte';
	import { ChatSession } from '$lib/chat.svelte';

	const session = new ChatSession({ mode: 'public' });

	const EXAMPLES = [
		'Do I need a permit to build a deck?',
		'How tall can a fence be in a residential zone?',
		'Can I keep chickens in my backyard?',
		'What does a short-term rental license cost?'
	];
</script>

<svelte:head>
	<title>Ask about the City Code | Waterville Codes RAG</title>
</svelte:head>

<div class="embed">
	<Header title="Ask about the City Code" compact showNewChat={session.started} onNewChat={() => session.clear()}>
		{#snippet actions()}
			<a class="theme-toggle" href="/" target="_blank" rel="noopener">Full page</a>
		{/snippet}
	</Header>
	<Chat {session}>
		{#snippet intro(ask)}
			<p class="hint">Try one of these</p>
			<div class="examples">
				{#each EXAMPLES as q (q)}
					<button type="button" onclick={() => ask(q)}>{q}</button>
				{/each}
			</div>
			<PublicTools external />
			<p class="embed-note">
				Answers quote the Waterville City Code and Maine law.
			</p>
		{/snippet}
		{#snippet extra(msg)}
			<PublicAnswerCards {msg} external />
			<InsightFeedback {msg} />
		{/snippet}
	</Chat>
</div>

<style>
	/* No box of its own, so main stays a flex child of body. Tighter than the
	   full page: the iframe is usually a sidebar or a short box. */
	.embed {
		display: contents;
	}
	.embed :global(header.site.compact .wrap) {
		padding-block: 12px 0;
	}
	.embed :global(header.site.compact .meta) {
		margin-bottom: 14px;
	}
	.embed :global(header.site.compact h1) {
		font-size: clamp(1.5rem, 4vw, 2rem);
	}
	.embed :global(header.site.compact:not(:has(.staff-nav)) .wrap) {
		padding-bottom: 18px;
	}
	.embed :global(main.wrap) {
		padding-top: 20px;
	}
	.embed :global(.examples button) {
		min-height: 0;
		padding: 12px 16px 14px;
		font-size: 0.98rem;
	}
	.embed :global(a.theme-toggle) {
		text-decoration: none;
		white-space: nowrap;
	}
	.embed-note {
		margin: 18px 0 0;
		color: var(--muted);
		font-size: 0.85rem;
		max-width: 42em;
	}
	@media (min-width: 1100px) {
		.embed :global(.examples) {
			grid-template-columns: repeat(4, 1fr);
		}
	}
</style>
