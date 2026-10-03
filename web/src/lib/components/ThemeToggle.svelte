<script lang="ts">
	// Light/dark toggle in the header. With no saved choice the page follows the
	// system setting; a click saves the opposite of whatever is showing.
	import { onMount } from 'svelte';

	let now = $state<'light' | 'dark'>('light');

	function current(): 'light' | 'dark' {
		const t = document.documentElement.dataset.theme;
		if (t === 'light' || t === 'dark') return t;
		return matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
	}

	function sync() {
		now = current();
		document.documentElement.dataset.themeNow = now;
	}

	function toggle() {
		const next = current() === 'dark' ? 'light' : 'dark';
		document.documentElement.dataset.theme = next;
		try {
			localStorage.setItem('theme', next);
		} catch {
			/* storage blocked */
		}
		sync();
	}

	onMount(() => {
		const system = matchMedia('(prefers-color-scheme: dark)');
		system.addEventListener('change', sync);
		sync();
		return () => system.removeEventListener('change', sync);
	});
</script>

<button
	type="button"
	id="theme-toggle"
	class="theme-toggle"
	aria-pressed={now === 'dark'}
	aria-label="Dark mode is {now === 'dark' ? 'on' : 'off'}. Switch to {now === 'dark' ? 'light' : 'dark'} mode"
	onclick={toggle}
>
	<svg class="sun" viewBox="0 0 16 16" aria-hidden="true"
		><circle cx="8" cy="8" r="3" fill="none" stroke="currentColor" stroke-width="1.4" /><path
			d="M8 1v2M8 13v2M1 8h2M13 8h2M3 3l1.4 1.4M11.6 11.6L13 13M3 13l1.4-1.4M11.6 4.4L13 3"
			stroke="currentColor"
			stroke-width="1.4"
			stroke-linecap="round"
		/></svg
	>
	<svg class="moon" viewBox="0 0 16 16" aria-hidden="true"
		><path
			d="M13.5 10.2A6 6 0 0 1 5.8 2.5a6 6 0 1 0 7.7 7.7z"
			fill="none"
			stroke="currentColor"
			stroke-width="1.4"
			stroke-linejoin="round"
		/></svg
	>
	<span class="label">{now === 'dark' ? 'Dark' : 'Light'}</span>
</button>
