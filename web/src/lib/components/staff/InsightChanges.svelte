<script lang="ts">
	// Code change alerts from /api/staff/changes (written by the refresh job when
	// a section's text changes). null: the endpoint is not deployed yet.
	import { shortDay, type Change } from './InsightData';

	let { changes, error = '' }: { changes: Change[] | null; error?: string } = $props();
</script>

{#if error}
	<p class="notice error-text" role="alert">Could not load change alerts: {error}</p>
{:else if changes === null}
	<p class="muted">Change alerts appear here once the refresh job compares a new code crawl with the index.</p>
{:else if changes.length === 0}
	<p class="muted">No section has changed since the last refresh.</p>
{:else}
	<ul class="changes">
		{#each changes.slice(0, 50) as c, i (c.citation + i)}
			<li>
				<div class="head">
					{#if c.url}
						<a href={c.url} target="_blank" rel="noopener">{c.citation}</a>
					{:else}
						<span class="change-cite">{c.citation}</span>
					{/if}
					{#if c.kind}<span class="tag-pill">{c.kind}</span>{/if}
					{#if c.detected_at}<span class="muted when">{shortDay(c.detected_at, true)}</span>{/if}
				</div>
				{#if c.title}<div class="title">{c.title}</div>{/if}
				{#if c.summary}<div class="muted">{c.summary}</div>{/if}
			</li>
		{/each}
	</ul>
	{#if changes.length > 50}<p class="muted">Showing the 50 newest of {changes.length}.</p>{/if}
{/if}

<style>
	.changes {
		list-style: none;
		margin: 0;
		padding: 0;
		border-top: 1px solid var(--border);
	}
	li {
		padding: 10px 0;
		border-bottom: 1px solid var(--border);
		font-size: 0.92rem;
	}
	.head {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: 6px 10px;
		font-weight: 600;
	}
	.when {
		font-weight: 400;
		font-size: 0.82rem;
	}
	.title {
		font-family: var(--serif);
	}
</style>
