// The logged-in staff user, set by web/src/routes/staff/+layout.svelte after
// GET /api/staff/me. Staff pages read staff.user; it is non-null inside the
// staff layout (except on /staff/login).
import { goto } from '$app/navigation';
import { api, type StaffUser } from './api';

export const staff = $state<{ user: StaffUser | null }>({ user: null });

export async function logout() {
	try {
		await api.post('/api/staff/logout');
	} finally {
		staff.user = null;
		await goto('/staff/login', { replaceState: true });
	}
}

// Sends the browser to the login page, remembering where it was going.
export function toLogin(from: URL) {
	const next = from.pathname + from.search;
	return goto(`/staff/login${next && next !== '/staff/login' ? `?next=${encodeURIComponent(next)}` : ''}`, {
		replaceState: true
	});
}
