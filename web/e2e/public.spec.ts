import { expect, test } from '@playwright/test';

test('ask, open a cited source, close it, start a new chat', async ({ page }) => {
	await page.goto('/');
	await expect(page).toHaveTitle('Waterville Codes RAG');
	await page.getByRole('button', { name: 'Can I keep chickens in my backyard?' }).click();

	const bot = page.locator('.msg.bot').last();
	await expect(bot.locator('.sources')).toBeVisible();
	await expect(page.locator('#send')).toBeEnabled();
	await expect(page.locator('#clear-chat')).toBeVisible();

	await bot.locator('.cite').first().click();
	const panel = page.locator('#panel');
	await expect(panel).toBeVisible();
	await expect(panel).toHaveAttribute('role', 'complementary');
	await expect(page.locator('#panel-title')).toBeFocused();
	await expect(page.locator('#panel-body .hl').first()).toBeVisible();
	await expect(bot.locator('.cite.is-active')).toHaveCount(1);

	await page.keyboard.press('Escape');
	await expect(panel).toBeHidden();
	await expect(bot.locator('.cite').first()).toBeFocused();

	await page.locator('#clear-chat').click();
	await expect(page.locator('#thread li')).toHaveCount(0);
	await expect(page.locator('#intro')).toBeVisible();
	await expect(page.locator('#q')).toBeFocused();
});

test('the source panel is a modal sheet on a phone', async ({ page }) => {
	await page.setViewportSize({ width: 390, height: 844 });
	await page.goto('/');
	await page.locator('#q').fill('Can I keep chickens?');
	await page.keyboard.press('Enter');
	await page.locator('.msg.bot .cite').first().click();
	await expect(page.locator('#panel')).toHaveAttribute('role', 'dialog');
	await expect(page.locator('#panel-backdrop')).toBeVisible();
	expect(await page.evaluate(() => document.querySelector('main')!.inert)).toBe(true);
	await page.locator('#panel-backdrop').click({ position: { x: 10, y: 10 } });
	await expect(page.locator('#panel')).toBeHidden();
	expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
});

test('staff pages send a logged-out browser to the login page', async ({ page }) => {
	await page.goto('/staff/cases');
	await expect(page).toHaveURL(/\/staff\/login\?next=%2Fstaff%2Fcases$/);
	await expect(page.getByRole('heading', { name: 'Sign in to the staff desk' })).toBeVisible();
});
