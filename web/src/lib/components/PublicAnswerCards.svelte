<script lang="ts">
	// The A1 checklist or A2 triage card the server sent with a public answer.
	import type { BotMessage } from '$lib/chat.svelte';
	import PublicChecklistCard from './PublicChecklistCard.svelte';
	import PublicTriageCard from './PublicTriageCard.svelte';
	import { answerCards } from './PublicData';

	let { msg, external = false }: { msg: BotMessage; external?: boolean } = $props();
	const cards = $derived(answerCards(msg));
</script>

{#if cards.triage}
	<PublicTriageCard triage={cards.triage} {external} />
{:else if cards.checklist}
	<PublicChecklistCard checklist={cards.checklist} {external} />
{/if}
