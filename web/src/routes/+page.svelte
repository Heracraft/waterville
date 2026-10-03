<script lang="ts">
	// The public page: ask about the City Code, read answers with citations.
	import Header from '$lib/components/Header.svelte';
	import Chat, { PUBLIC_EXAMPLES } from '$lib/components/Chat.svelte';
	import PublicAnswerCards from '$lib/components/PublicAnswerCards.svelte';
	import PublicTools from '$lib/components/PublicTools.svelte';
	import InsightFeedback from '$lib/components/InsightFeedback.svelte';
	import InsightPrivacyNote from '$lib/components/InsightPrivacyNote.svelte';
	import { ChatSession } from '$lib/chat.svelte';

	const session = new ChatSession({ mode: 'public' });
</script>

<svelte:head>
	<title>Waterville Codes RAG</title>
</svelte:head>

<Header showNewChat={session.started} onNewChat={() => session.clear()} />
<Chat {session}>
	{#snippet intro(ask)}
		<!-- The same example grid Chat renders by default, then links to the tools (A3 to A5). -->
		<p class="hint">Try one of these</p>
		<div class="examples">
			{#each PUBLIC_EXAMPLES as q (q)}
				<button type="button" onclick={() => ask(q)}>{q}</button>
			{/each}
		</div>
		<PublicTools />
	{/snippet}
	{#snippet extra(msg)}
		<PublicAnswerCards {msg} />
		<InsightFeedback {msg} />
	{/snippet}
</Chat>
<InsightPrivacyNote />
