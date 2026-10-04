<script lang="ts">
	// B11: sections opened on this device, readable with no connection. The
	// service worker serves this page from its cache when the network is gone.
	import Header from '$lib/components/Header.svelte';
	import PublicToolNav from '$lib/components/PublicToolNav.svelte';
	import { forgetAll, forgetSource, KEEP, savedSources, type SavedSource } from '$lib/offline';
	import { parseBlocks, renderBlocks, safeUrl } from '$lib/source';

	let list = $state<SavedSource[]>([]);
	let loaded = $state(false);
	let online = $state(true);
	let openKey = $state('');

	async function load() {
		list = await savedSources();
		loaded = true;
	}

	$effect(() => {
		load();
		online = navigator.onLine;
		const up = () => (online = true);
		const down = () => (online = false);
		window.addEventListener('online', up);
		window.addEventListener('offline', down);
		return () => {
			window.removeEventListener('online', up);
			window.removeEventListener('offline', down);
		};
	});

	async function remove(key: string) {
		await forgetSource(key);
		if (openKey === key) openKey = '';
		await load();
	}

	async function clear() {
		await forgetAll();
		openKey = '';
		await load();
	}

	function when(iso: string) {
		const d = new Date(iso);
		return isNaN(d.getTime()) ? '' : d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
	}
</script>

<svelte:head>
	<title>Saved sections | Waterville Codes RAG</title>
</svelte:head>

<Header title="Saved sections" compact>
	{#snippet actions()}
		<a class="theme-toggle" href="/">Ask a question</a>
	{/snippet}
</Header>

<main class="wrap offline-page">
	<div class="page-head">
		<p class="page-lede">
			The last {KEEP} sections you opened on this device, kept for reading without a connection. Questions still need
			a connection.
		</p>
	</div>

	{#if !online}
		<p class="notice" role="status">You are offline. Saved sections still open below.</p>
	{/if}

	{#if !loaded}
		<p class="muted">Loading saved sections</p>
	{:else if list.length === 0}
		<div class="sheet">
			<p>No sections saved yet. Open a source from an answer and it is kept here for offline reading.</p>
		</div>
	{:else}
		<ul class="saved">
			{#each list as s (s.key)}
				{@const href = safeUrl(s.open_url) || safeUrl(s.url)}
				<li class="sheet" class:open={openKey === s.key}>
					<div class="row">
						<button
							type="button"
							class="saved-title"
							aria-expanded={openKey === s.key}
							onclick={() => (openKey = openKey === s.key ? '' : s.key)}
						>
							<span class="saved-cite">{s.citation || s.title}</span>
							{#if s.citation && s.title}<span class="sub">{s.title}</span>{/if}
						</button>
						<span class="saved-when muted">Saved {when(s.saved_at)}</span>
						<button type="button" class="btn secondary small" onclick={() => remove(s.key)}>Remove</button>
					</div>
					{#if openKey === s.key}
						{#if s.breadcrumb}<p class="crumbs muted">{s.breadcrumb}</p>{/if}
						<div class="panel-body">{@html renderBlocks(parseBlocks(s.text || ''))}</div>
						{#if href && online}<p><a {href} target="_blank" rel="noopener">Open original</a></p>{/if}
					{/if}
				</li>
			{/each}
		</ul>
		<p class="btn-row foot">
			<button type="button" class="btn secondary small" onclick={clear}>Remove all saved sections</button>
		</p>
	{/if}
</main>

<PublicToolNav />

<style>
	.saved {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		gap: 12px;
	}
	.saved .sheet + .sheet {
		margin-top: 0;
	}
	.sheet.open {
		border-top: 3px solid var(--accent);
	}
	.row {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 8px 14px;
	}
	.saved-title {
		flex: 1 1 260px;
		min-width: 0;
		display: grid;
		gap: 2px;
		text-align: left;
		cursor: pointer;
		border: 0;
		background: none;
		padding: 0;
		color: var(--text);
	}
	.saved-cite {
		font: 600 1rem/1.35 var(--sans);
		color: var(--accent);
	}
	.sub {
		font: 300 1rem/1.4 var(--serif);
	}
	.saved-title:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 3px;
	}
	.saved-when {
		font-size: 0.8rem;
	}
	.crumbs {
		margin: 14px 0 0;
		font-size: 0.82rem;
	}
	.foot {
		margin-top: 18px;
	}
</style>
