<script lang="ts">
	// Links to the public tools, under the example questions on the home page.
	let { external = false }: { external?: boolean } = $props();

	const TOOLS = [
		{ href: '/permits', title: 'Permit guide', text: 'Which permits and forms your project needs, and what to bring.' },
		{ href: '/fees', title: 'Fee estimator', text: 'Electrical and Fire review fees from the published formulas.' },
		{ href: '/complaint', title: 'Complaint sheet', text: 'Write down a property concern to bring to your appointment.' }
	];
</script>

<nav class="ptools" aria-label="Tools">
	<p class="ptools-hint">Or use a tool</p>
	<ul>
		{#each TOOLS as t (t.href)}
			<li>
				<a href={t.href} target={external ? '_blank' : undefined} rel={external ? 'noopener' : undefined}>
					<span class="ptools-title">{t.title}</span>
					<span class="ptools-text">{t.text}</span>
				</a>
			</li>
		{/each}
	</ul>
</nav>

<style>
	.ptools {
		margin-top: 28px;
	}
	.ptools-hint {
		margin: 0 0 12px;
		color: var(--accent);
		font-weight: 600;
		font-size: 0.9rem;
	}
	ul {
		display: grid;
		grid-template-columns: repeat(3, 1fr);
		margin: 0;
		padding: 0;
		list-style: none;
		border-top: 1px solid var(--rule);
		border-left: 1px solid var(--rule);
	}
	li {
		display: flex;
		border-right: 1px solid var(--rule);
		border-bottom: 1px solid var(--rule);
	}
	a {
		flex: 1;
		display: block;
		padding: 14px 18px 16px;
		background: var(--bg);
		color: var(--text);
		text-decoration: none;
		transition: background-color 0.15s;
	}
	a:hover,
	a:focus-visible {
		background: var(--surface-hover);
	}
	a:focus-visible {
		outline: none;
		box-shadow: inset 0 0 0 2px var(--accent);
	}
	.ptools-title {
		display: block;
		font: 600 0.95rem/1.3 var(--sans);
	}
	.ptools-title::after {
		content: ' \2192';
		color: var(--accent);
	}
	.ptools-text {
		display: block;
		margin-top: 4px;
		color: var(--muted);
		font-size: 0.88rem;
		line-height: 1.45;
	}
	@media (min-width: 1100px) {
		ul {
			max-width: 75%;
		}
	}
	@media (max-width: 640px) {
		ul {
			grid-template-columns: 1fr;
		}
		a {
			padding: 12px 16px 14px;
		}
	}
</style>
