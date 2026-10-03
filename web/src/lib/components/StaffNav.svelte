<script lang="ts" module>
	export const STAFF_LINKS = [
		{ href: '/staff', label: 'Research desk' },
		{ href: '/staff/cases', label: 'Cases' },
		{ href: '/staff/drafts', label: 'Drafts' },
		{ href: '/staff/deadlines', label: 'Deadlines' },
		{ href: '/staff/gates', label: 'Project gates' },
		{ href: '/staff/insights', label: 'Insights' }
	];
</script>

<script lang="ts">
	// Staff section tabs, rendered inside the compact header on every staff page.
	import { page } from '$app/state';
	import { staff, logout } from '$lib/staff.svelte';


	const here = (href: string) => {
		const p = page.url.pathname.replace(/\/$/, '') || '/';
		if (href === '/staff') return p === '/staff';
		return p === href || p.startsWith(href + '/');
	};
</script>

<nav class="staff-nav" aria-label="Staff">
	<ul>
		{#each STAFF_LINKS as l (l.href)}
			<li><a href={l.href} aria-current={here(l.href) ? 'page' : undefined}>{l.label}</a></li>
		{/each}
	</ul>
	{#if staff.user}
		<div class="who">
			<span class="user">{staff.user.username}</span>
			<button type="button" onclick={logout}>Log out</button>
		</div>
	{/if}
</nav>

<style>
	.staff-nav {
		display: flex;
		flex-wrap: wrap;
		align-items: stretch;
		justify-content: space-between;
		gap: 12px 24px;
		margin-top: 20px;
		border-top: 1px solid var(--hero-rule);
		font: 500 0.88rem var(--sans);
	}
	ul {
		display: flex;
		flex-wrap: wrap;
		margin: 0;
		padding: 0;
		list-style: none;
	}
	li {
		border-right: 1px solid var(--hero-rule);
	}
	li:first-child {
		border-left: 1px solid var(--hero-rule);
	}
	a {
		display: block;
		padding: 10px 16px 9px;
		color: var(--hero-text);
		text-decoration: none;
		border-top: 3px solid transparent;
		margin-top: -1px;
		transition: background-color 0.15s;
	}
	a:hover {
		background: rgb(225 220 216 / 0.08);
	}
	a[aria-current='page'] {
		border-top-color: var(--accent);
		color: var(--blush);
		background: rgb(225 220 216 / 0.06);
		font-weight: 600;
	}
	a:focus-visible,
	button:focus-visible {
		outline: 2px solid var(--blush);
		outline-offset: -2px;
	}
	.who {
		display: flex;
		align-items: center;
		gap: 12px;
		padding: 8px 0;
		color: var(--blush);
	}
	button {
		cursor: pointer;
		border: 1px solid var(--hero-rule);
		background: transparent;
		color: var(--hero-text);
		font: 500 0.8rem var(--sans);
		padding: 5px 10px;
	}
	button:hover {
		border-color: var(--blush);
	}
	/* Phones: all six tabs stay visible, three to a row, ruled like a ledger. */
	@media (max-width: 640px) {
		ul {
			width: 100%;
			display: grid;
			grid-template-columns: repeat(3, minmax(0, 1fr));
			border-left: 1px solid var(--hero-rule);
		}
		li {
			border-bottom: 1px solid var(--hero-rule);
		}
		li:first-child {
			border-left: 0;
		}
		a {
			height: 100%;
			padding: 9px 6px 8px;
			text-align: center;
			font-size: 0.82rem;
		}
	}
</style>
