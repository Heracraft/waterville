<script lang="ts">
	// Unknown URLs and other routing errors, in the site's own header and wrap.
	import { page } from '$app/state';
	import Header from '$lib/components/Header.svelte';

	const staffPath = $derived(page.url.pathname.startsWith('/staff'));
	const missing = $derived(page.status === 404);
</script>

<svelte:head>
	<title>{missing ? 'Page not found' : 'Something went wrong'} | Waterville Codes RAG</title>
</svelte:head>

<Header title={missing ? 'Page not found' : 'Something went wrong'} compact>
	{#snippet actions()}
		<a class="theme-toggle" href="/">Ask a question</a>
	{/snippet}
</Header>
<main class="wrap error-page">
	<section class="sheet accent">
		{#if missing}
			<p class="lead">This page does not exist.</p>
			<p class="muted">Check the address, or go to one of these pages.</p>
		{:else}
			<p class="lead">The page could not load.</p>
			<p class="muted">{page.error?.message || 'Reload to try again.'}</p>
		{/if}
		<ul class="error-links">
			<li><a href="/">Ask about the City Code</a></li>
			<li><a href="/permits">Permit guide</a></li>
			{#if staffPath}
				<li><a href="/staff">Staff desk</a></li>
			{/if}
		</ul>
	</section>
</main>

<style>
	.lead {
		margin: 0 0 6px;
		font: 300 1.4rem/1.3 var(--serif);
	}
	.muted {
		margin: 0 0 16px;
		color: var(--muted);
	}
	.error-links {
		display: flex;
		flex-wrap: wrap;
		gap: 8px 24px;
		margin: 0;
		padding: 16px 0 0;
		list-style: none;
		border-top: 1px solid var(--rule);
	}
	.error-links a {
		font-weight: 600;
	}
</style>
