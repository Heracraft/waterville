<script lang="ts">
	// Footer row on the public tool pages (/permits, /fees, /complaint, /offline):
	// the question page and every tool, with the current page marked.
	import { page } from '$app/state';

	const LINKS = [
		{ href: '/', label: 'Ask a question' },
		{ href: '/permits', label: 'Permit guide' },
		{ href: '/fees', label: 'Fee estimator' },
		{ href: '/complaint', label: 'Complaint sheet' },
		{ href: '/offline', label: 'Saved sections' }
	];

	const here = $derived(page.url.pathname.replace(/\/$/, '') || '/');
</script>

<nav class="tool-nav no-print" aria-label="Public tools">
	<div class="wrap">
		<p class="tool-nav-hint">More from the City Code assistant</p>
		<ul>
			{#each LINKS as l (l.href)}
				<li><a href={l.href} aria-current={here === l.href ? 'page' : undefined}>{l.label}</a></li>
			{/each}
		</ul>
	</div>
</nav>

<style>
	.tool-nav {
		border-top: 1px solid var(--rule);
		background: var(--bg);
		padding: 20px 0 28px;
	}
	.tool-nav-hint {
		margin: 0 0 10px;
		color: var(--accent);
		font: 600 0.85rem var(--sans);
	}
	ul {
		display: flex;
		flex-wrap: wrap;
		margin: 0;
		padding: 0;
		list-style: none;
		border-top: 1px solid var(--rule);
		border-left: 1px solid var(--rule);
	}
	li {
		border-right: 1px solid var(--rule);
		border-bottom: 1px solid var(--rule);
		flex: 1 1 auto;
	}
	a {
		display: block;
		padding: 10px 16px;
		background: var(--surface);
		color: var(--text);
		font: 500 0.9rem var(--sans);
		text-decoration: none;
		white-space: nowrap;
		transition: background-color 0.15s;
	}
	a:hover {
		background: var(--bg);
	}
	a:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: -2px;
	}
	a[aria-current='page'] {
		border-top: 3px solid var(--accent);
		padding-top: 7px;
		font-weight: 600;
	}
	@media (max-width: 640px) {
		li {
			flex: 1 1 45%;
		}
		a {
			padding: 10px 12px;
		}
	}
</style>
