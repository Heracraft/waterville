<script lang="ts">
	// Staff shell: checks the session (GET /api/staff/me) and sends a logged-out
	// browser to /staff/login. The login page renders without the check and nav.
	import { page } from '$app/state';
	import Header from '$lib/components/Header.svelte';
	import StaffNav from '$lib/components/StaffNav.svelte';
	import { onUnauthorized, staffMe } from '$lib/api';
	import { staff, toLogin } from '$lib/staff.svelte';
	import { chrome } from '$lib/chrome.svelte';

	let { children } = $props();

	const isLogin = $derived(page.url.pathname.replace(/\/$/, '') === '/staff/login');
	let status = $state<'checking' | 'ok' | 'error'>(staff.user ? 'ok' : 'checking');
	let problem = $state('');

	async function check() {
		status = 'checking';
		try {
			const me = await staffMe();
			if (!me) {
				staff.user = null;
				await toLogin(page.url);
				return;
			}
			staff.user = me;
			status = 'ok';
		} catch (e) {
			problem = e instanceof Error ? e.message : String(e);
			status = 'error';
		}
	}

	// A staff request that comes back 401 means the session ran out.
	$effect(() => {
		onUnauthorized(() => {
			staff.user = null;
		});
		return () => onUnauthorized(null);
	});

	// Re-check whenever a staff page opens without a known user.
	$effect(() => {
		if (!isLogin && !staff.user) check();
		else if (staff.user) status = 'ok';
	});
</script>

{#if isLogin}
	{@render children()}
{:else}
	<Header
		title="Staff desk"
		eyebrow={staff.user?.env === 'preview' ? 'City of Waterville, Code Enforcement (preview)' : 'City of Waterville, Code Enforcement'}
		compact
		showNewChat={chrome.newChat !== null}
		onNewChat={() => chrome.newChat?.()}
	>
		<StaffNav />
	</Header>
	{#if status === 'ok' && staff.user}
		{@render children()}
	{:else if status === 'error'}
		<main class="wrap staff-main">
			<p class="notice error-text" role="alert">Could not check your session: {problem}</p>
			<button type="button" class="btn secondary" onclick={check}>Try again</button>
		</main>
	{:else}
		<main class="wrap staff-main" aria-busy="true">
			<div class="loading" role="status">
				<span class="loading-label">Checking your session</span><span class="loading-bar" aria-hidden="true"></span>
			</div>
		</main>
	{/if}
{/if}
