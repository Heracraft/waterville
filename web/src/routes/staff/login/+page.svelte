<script lang="ts">
	// Staff login: POST /api/staff/login {username, password}; the server sets
	// the wv_session cookie. Then back to the page the user was going to.
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import Header from '$lib/components/Header.svelte';
	import { api, ApiError, staffMe, type StaffUser } from '$lib/api';
	import { staff } from '$lib/staff.svelte';

	let username = $state('');
	let password = $state('');
	let busy = $state(false);
	let error = $state('');

	const next = $derived.by(() => {
		const n = page.url.searchParams.get('next') || '';
		// Only paths inside the staff area; never another origin.
		return /^\/staff(\/|$|\?)/.test(n) && !n.startsWith('/staff/login') ? n : '/staff';
	});

	// Readable messages for each way a sign-in can fail.
	function loginError(e: unknown): string {
		if (e instanceof ApiError) {
			if (e.status === 401) return 'That username and password do not match. Check both and try again.';
			if (e.status === 429) return e.message || 'Too many sign-in attempts. Wait 15 minutes and try again.';
			if (e.status === 503) return 'Staff sign-in is not set up on this server yet. Ask the administrator to add staff users.';
			if (e.status === 422) return 'Enter a username and a password.';
			if (e.status >= 500) return 'The server could not check your password. Try again in a minute.';
			return e.message;
		}
		if (e instanceof TypeError) return 'Could not reach the server. Check your connection and try again.';
		return e instanceof Error ? e.message : String(e);
	}

	const returning = $derived(Boolean(page.url.searchParams.get('next')));

	// Already signed in: go on to the staff desk (or ?next) instead of the form.
	onMount(() => {
		let gone = false;
		(async () => {
			const me = staff.user ?? (await staffMe().catch(() => null));
			if (gone || !me || busy) return;
			staff.user = me;
			await goto(next, { replaceState: true });
		})();
		return () => (gone = true);
	});

	async function submit(e: SubmitEvent) {
		e.preventDefault();
		if (busy) return;
		busy = true;
		error = '';
		try {
			const res = await api.post<StaffUser | Record<string, unknown>>('/api/staff/login', { username, password });
			staff.user =
				res && typeof res === 'object' && 'username' in res ? (res as StaffUser) : await staffMe();
			password = '';
			await goto(next, { replaceState: true });
		} catch (e) {
			error = loginError(e);
			if (e instanceof ApiError && e.status === 401) password = '';
		} finally {
			busy = false;
		}
	}
</script>

<svelte:head>
	<title>Staff login | Waterville Codes RAG</title>
</svelte:head>

<Header title="Staff login" eyebrow="City of Waterville, Code Enforcement" compact />
<main class="wrap staff-main">
	<form class="sheet accent login" onsubmit={submit}>
		<h2 class="page-title">Sign in to the staff desk</h2>
		<p class="muted">For Code Enforcement and Planning staff. Residents can ask questions on <a href="/">the public page</a>.</p>
		{#if returning && !error}<p class="notice" role="status">Sign in to continue to the page you opened.</p>{/if}
		<label class="field">
			<span>Username</span>
			<!-- svelte-ignore a11y_autofocus -->
			<input name="username" autocomplete="username" autocapitalize="none" spellcheck="false" required maxlength="64" autofocus bind:value={username} />
		</label>
		<label class="field">
			<span>Password</span>
			<input name="password" type="password" autocomplete="current-password" required maxlength="256" bind:value={password} aria-invalid={error ? 'true' : undefined} />
		</label>
		{#if error}<p class="notice error-text" role="alert">{error}</p>{/if}
		<button type="submit" class="btn" disabled={busy}>{busy ? 'Signing in' : 'Sign in'}</button>
		<p class="fine">Sessions last 12 hours on this device.</p>
	</form>
</main>

<style>
	.login {
		max-width: 440px;
	}
	.login .page-title {
		font: 300 1.6rem/1.2 var(--serif);
		margin-bottom: 8px;
	}
	.login p.muted {
		margin: 0 0 20px;
		font-size: 0.92rem;
	}
	.login .btn {
		width: 100%;
	}
	.fine {
		margin: 16px 0 0;
		padding-top: 12px;
		border-top: 1px solid var(--border);
		color: var(--muted);
		font-size: 0.8rem;
	}
</style>
