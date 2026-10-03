<script lang="ts">
	// The letter as it will print: the server renders the Markdown body and the
	// letterhead to escaped HTML (app/routers/drafts.py to_html), so the preview,
	// the print view and the .docx all come from one renderer.
	import DraftBanner from './DraftBanner.svelte';

	let { html, banner, busy = false }: { html: string; banner?: string; busy?: boolean } = $props();
</script>

<section class="draft-preview" aria-label="Preview" aria-busy={busy}>
	<DraftBanner text={banner} />
	<article class="paper" class:busy>
		<!-- Server-rendered and escaped; see to_html in app/routers/drafts.py. -->
		{@html html}
	</article>
</section>

<style>
	.paper {
		background: var(--surface);
		border: 1px solid var(--rule);
		padding: 36px 44px 44px;
		font: 400 1rem/1.6 var(--serif);
		color: var(--text);
		overflow-wrap: anywhere;
		transition: opacity 0.15s;
	}
	.paper.busy {
		opacity: 0.75;
	}
	.paper :global(> :first-child) {
		margin-top: 0;
	}
	.paper :global(p) {
		margin: 0 0 0.9em;
	}
	.paper :global(h2) {
		margin: 1.4em 0 0.5em;
		font: 300 1.6rem/1.2 var(--serif);
		letter-spacing: 0.01em;
	}
	.paper :global(h3) {
		margin: 1.3em 0 0.4em;
		font: 600 0.98rem/1.35 var(--sans);
		color: var(--text);
	}
	.paper :global(h4) {
		margin: 1em 0 0.3em;
		font: 600 0.9rem/1.35 var(--sans);
	}
	.paper :global(ul),
	.paper :global(ol) {
		margin: 0 0 0.9em;
		padding-left: 1.4em;
	}
	.paper :global(li) {
		margin: 0 0 0.35em;
	}
	.paper :global(ul.checklist) {
		list-style: none;
		padding-left: 0;
	}
	.paper :global(li.check) {
		display: grid;
		grid-template-columns: 1.4em 1fr;
		gap: 4px;
	}
	.paper :global(.box) {
		font-family: var(--sans);
		color: var(--accent);
	}
	.paper :global(blockquote) {
		margin: 0 0 0.9em;
		padding-left: 14px;
		border-left: 2px solid var(--accent);
	}
	.paper :global(hr) {
		border: 0;
		border-top: 1px solid var(--border);
		margin: 1.2em 0;
	}
	.paper :global(mark.flag) {
		color: inherit;
		font: 600 0.88em/1.5 var(--sans);
		padding: 0 3px;
	}
	.paper :global(mark.verify) {
		background: var(--hl);
		box-shadow: inset 0 -2px 0 var(--hl-edge);
	}
	.paper :global(mark.missing) {
		background: transparent;
		color: var(--error);
		outline: 1px dashed var(--error);
		outline-offset: -1px;
	}
	.paper :global(.draft-letterhead) {
		text-align: center;
		border-bottom: 1px solid var(--rule);
		padding-bottom: 12px;
		margin: 0 0 28px;
		font-family: var(--sans);
	}
	.paper :global(.draft-letterhead p) {
		margin: 0;
		font-size: 0.82rem;
		color: var(--muted);
	}
	.paper :global(.draft-letterhead .lh-city) {
		font: 700 1.05rem/1.4 var(--sans);
		letter-spacing: 0.1em;
		text-transform: uppercase;
		color: var(--text);
	}
	.paper :global(.draft-letterhead .lh-office) {
		font-weight: 600;
		color: var(--text);
	}
	@media (max-width: 640px) {
		.paper {
			padding: 20px 16px 24px;
			font-size: 0.97rem;
		}
	}
	@media print {
		.paper {
			border: 0;
			padding: 0;
			background: #fff;
			color: #000;
			font-size: 11pt;
		}
		.paper :global(.draft-letterhead p),
		.paper :global(.draft-letterhead .lh-city) {
			color: #000;
		}
		.paper :global(mark.verify) {
			background: #fff3b0;
			box-shadow: none;
		}
		.paper :global(mark.missing) {
			color: #9b1c1c;
			outline-color: #9b1c1c;
		}
	}
</style>
