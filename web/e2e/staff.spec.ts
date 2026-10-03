import { expect, test } from '@playwright/test';

// Staff sign-in against the backend's STAFF_USERS. playwright.config.ts makes a
// throwaway user for the server it starts; E2E_STAFF_USER/E2E_STAFF_PASSWORD
// point these tests at a user on a server you started yourself.
const user = process.env.E2E_STAFF_USER || 'e2e';
const password = process.env.E2E_STAFF_PASSWORD || '';

test('a wrong password shows an error and stays on the login page', async ({ page }) => {
	await page.goto('/staff/login');
	await page.getByLabel('Username').fill(user);
	await page.getByLabel('Password').fill('not-the-password');
	await page.getByRole('button', { name: 'Sign in' }).click();
	await expect(page.getByRole('alert')).toHaveText(/^That username and password do not match\./);
	await expect(page).toHaveURL(/\/staff\/login/);
});

test('sign in, reach the staff pages, ask in staff mode, sign out', async ({ page }) => {
	test.skip(!password, 'E2E_STAFF_PASSWORD is not set');
	await page.goto('/staff/cases');
	await expect(page).toHaveURL(/\/staff\/login\?next=%2Fstaff%2Fcases$/);
	await page.getByLabel('Username').fill(user);
	await page.getByLabel('Password').fill(password);
	await page.getByRole('button', { name: 'Sign in' }).click();

	// Back to the page the browser was going to, with the staff nav and the user.
	await expect(page).toHaveURL(/\/staff\/cases$/);
	const nav = page.getByRole('navigation', { name: 'Staff' });
	await expect(nav.getByRole('link', { name: 'Cases' })).toHaveAttribute('aria-current', 'page');
	await expect(nav.getByText(user, { exact: true })).toBeVisible();

	// The session cookie works for the API from the same browser context.
	const me = await page.request.get('/api/staff/me');
	expect(me.status()).toBe(200);
	expect((await me.json()).username).toBe(user);

	// Staff-mode chat: CSRF header required, and the meta event says staff.
	const body = { messages: [{ role: 'user', content: 'Can I keep chickens?' }], mode: 'staff' };
	const noCsrf = await page.request.post('/api/chat', { data: body });
	expect(noCsrf.status()).toBe(403);
	const chat = await page.request.post('/api/chat', { data: body, headers: { 'X-Requested-With': 'wv' } });
	expect(chat.status()).toBe(200);
	const text = await chat.text();
	expect(text.startsWith('event: meta')).toBe(true);
	expect(text).toContain('"mode": "staff"');
	expect(text).toContain('event: done');

	// A client-side hop to another staff page keeps the session.
	await nav.getByRole('link', { name: 'Research desk' }).click();
	await expect(page).toHaveURL(/\/staff$/);
	await expect(nav.getByRole('link', { name: 'Research desk' })).toHaveAttribute('aria-current', 'page');

	await nav.getByRole('button', { name: 'Log out' }).click();
	await expect(page).toHaveURL(/\/staff\/login/);
	expect((await page.request.get('/api/staff/me')).status()).toBe(401);
});
