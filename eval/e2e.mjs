#!/usr/bin/env node
// End-to-end walk through every feature, against any running deployment:
// a local FAKE_AZURE server, the preview on Azure, or production (public part only).
//
//   node eval/e2e.mjs --url http://localhost:8118
//   node eval/e2e.mjs --url https://waterville-preview.<env>.azurecontainerapps.io
//   node eval/e2e.mjs --url https://... --public-only
//
// Public: chat, source panel, permit router, fee estimator, complaint sheet (print),
//         checklist card and feedback, /embed (frame headers, chat), offline sections.
// Staff:  login, case create, desk citation lookup, desk filters, staff answer saved
//         to the case, copy buttons, draft create and .docx download, deadline
//         calculator with add to case, project gates saved as a note, insights, logout.
//
// Staff password: E2E_STAFF_PASSWORD, or the "Password:" line of
// ~/waterville-preview-credentials.txt (written by infra/deploy-preview.sh).
// User: E2E_STAFF_USER (default "inspector"). Never pass the password as an argument.
//
// The staff steps create one case and one draft, both titled "E2E check ...",
// and delete them at the end (set E2E_KEEP=1 to keep them).
//
// Options: --url URL (or E2E_BASE_URL), --public-only, --phone (390x844),
// --dark, --headed, --shots DIR (screenshots of every step; failures always
// get one, by default in <tmp>/waterville-e2e-shots). Exit status 1 when a step fails.
//
// Uses @playwright/test from web/node_modules (run `pnpm install` in web/ first).

import { createRequire } from 'node:module';
import { existsSync, mkdirSync, readFileSync } from 'node:fs';
import { homedir, tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const require = createRequire(join(here, '..', 'web', 'package.json'));
const { chromium, expect } = require('@playwright/test');

// ------------------------------------------------------------------ options

function parseArgs(argv) {
	const o = { url: process.env.E2E_BASE_URL || '', publicOnly: false, phone: false, dark: false, headed: false, shots: '' };
	for (let i = 0; i < argv.length; i++) {
		const a = argv[i];
		if (a === '--url') o.url = argv[++i];
		else if (a === '--public-only') o.publicOnly = true;
		else if (a === '--phone') o.phone = true;
		else if (a === '--dark') o.dark = true;
		else if (a === '--headed') o.headed = true;
		else if (a === '--shots') o.shots = argv[++i];
		else if (a === '-h' || a === '--help') {
			console.log(readFileSync(fileURLToPath(import.meta.url), 'utf8').split('\n').slice(1, 26).join('\n'));
			process.exit(0);
		} else throw new Error(`unknown argument ${a}`);
	}
	if (!o.url) throw new Error('give --url or E2E_BASE_URL');
	o.url = o.url.replace(/\/+$/, '');
	return o;
}

function staffPassword() {
	if (process.env.E2E_STAFF_PASSWORD) return process.env.E2E_STAFF_PASSWORD;
	const f = process.env.E2E_CREDENTIALS || join(homedir(), 'waterville-preview-credentials.txt');
	if (existsSync(f)) {
		const m = readFileSync(f, 'utf8').match(/^Password:\s*(.+)$/m);
		if (m) return m[1].trim();
	}
	return '';
}

const opts = parseArgs(process.argv.slice(2));
const user = process.env.E2E_STAFF_USER || 'inspector';
const password = opts.publicOnly ? '' : staffPassword();
const keep = process.env.E2E_KEEP === '1';
const shotDir = opts.shots || join(tmpdir(), 'waterville-e2e-shots');
const CSRF = { 'X-Requested-With': 'wv' };
const stamp = new Date().toISOString().slice(0, 16).replace('T', ' ');

// ------------------------------------------------------------------ runner

const results = [];
let page;
let context;

async function shot(name) {
	mkdirSync(shotDir, { recursive: true });
	const file = join(shotDir, `${String(results.length + 1).padStart(2, '0')}-${name}.png`);
	await page.screenshot({ path: file, fullPage: true }).catch(() => {});
	return file;
}

async function step(name, fn, { needs } = {}) {
	if (needs && !needs()) {
		results.push({ name, status: 'skip', detail: 'an earlier step it depends on failed' });
		console.log(`  skip  ${name}`);
		return;
	}
	const t0 = Date.now();
	try {
		const detail = await fn();
		const ms = Date.now() - t0;
		if (opts.shots) await shot(name);
		results.push({ name, status: 'pass', ms, detail: detail || '' });
		console.log(`  pass  ${name} (${(ms / 1000).toFixed(1)}s)${detail ? `: ${detail}` : ''}`);
	} catch (e) {
		const file = await shot(`${name}-failed`);
		const msg = String(e?.message || e).split('\n')[0];
		results.push({ name, status: 'fail', detail: msg, shot: file });
		console.log(`  FAIL  ${name}: ${msg}\n        screenshot: ${file}`);
	}
}

const passed = (name) => results.some((r) => r.name === name && r.status === 'pass');

// Waits for a chat answer to finish: sources shown and the Ask button back.
async function waitForAnswer(timeout = 180_000) {
	const bot = page.locator('.msg.bot').last();
	await expect(bot.locator('.sources')).toBeVisible({ timeout });
	await expect(page.locator('#send')).toBeEnabled({ timeout });
	return bot;
}

// ------------------------------------------------------------------ main

const browser = await chromium.launch({ headless: !opts.headed });
context = await browser.newContext({
	baseURL: opts.url,
	viewport: opts.phone ? { width: 390, height: 844 } : { width: 1280, height: 900 },
	colorScheme: opts.dark ? 'dark' : 'light',
	acceptDownloads: true
});
// The desk copy buttons write to the clipboard; the check reads it back.
await context.grantPermissions(['clipboard-read', 'clipboard-write'], { origin: opts.url }).catch(() => {});
page = await context.newPage();
const consoleErrors = [];
// A 401 from /api/staff/me before sign-in is expected.
page.on('console', (m) => m.type() === 'error' && !/status of 401/.test(m.text()) && consoleErrors.push(m.text()));
page.on('pageerror', (e) => consoleErrors.push(String(e)));

console.log(`e2e against ${opts.url} (${opts.phone ? 'phone' : 'desktop'}, ${opts.dark ? 'dark' : 'light'})`);
console.log('Public');

await step('health', async () => {
	// A scaled-to-zero preview takes about 20 seconds to wake.
	for (let i = 0; i < 20; i++) {
		const r = await page.request.get('/healthz', { timeout: 30_000 }).catch(() => null);
		if (r?.ok()) return `HTTP ${r.status()}`;
		await new Promise((res) => setTimeout(res, 3000));
	}
	throw new Error('/healthz never answered');
});

await step('public chat', async () => {
	await page.goto('/');
	await page.locator('#q').fill('Can I keep chickens in my backyard?');
	await page.locator('#send').click();
	const bot = await waitForAnswer();
	// The answer is the bot message's text before its sources list.
	const text = await bot.evaluate((el) => {
		const c = el.cloneNode(true);
		c.querySelectorAll('.sources').forEach((x) => x.remove());
		return c.textContent || '';
	});
	if (text.trim().length < 40) throw new Error('answer is too short');
	const cites = await bot.locator('.cite').count();
	if (!cites) throw new Error('answer has no citation chips');
	return `${cites} citation chips`;
});

await step(
	'source panel',
	async () => {
		const bot = page.locator('.msg.bot').last();
		await bot.locator('.cite').first().click();
		const panel = page.locator('#panel');
		await expect(panel).toBeVisible();
		await expect(page.locator('#panel-title')).not.toBeEmpty();
		await expect(page.locator('#panel-body')).not.toBeEmpty();
		const title = await page.locator('#panel-title').innerText();
		const highlighted = await page.locator('#panel-body .hl').count();
		await page.keyboard.press('Escape');
		await expect(panel).toBeHidden();
		return `${title.replace(/\s+/g, ' ').trim()}${highlighted ? ', cited passage highlighted' : ''}`;
	},
	{ needs: () => passed('public chat') }
);

await step('permit router', async () => {
	await page.goto('/permits');
	const projects = page.locator('button.project');
	await expect(projects.first()).toBeVisible({ timeout: 20_000 });
	const deck = projects.filter({ hasText: /deck/i });
	const pick = (await deck.count()) ? deck.first() : projects.first();
	const label = (await pick.innerText()).trim();
	await pick.click();
	await expect(pick).toHaveAttribute('aria-pressed', 'true');
	await expect(page.locator('#result-title')).toBeVisible({ timeout: 20_000 });
	const result = page.locator('section.result');
	await expect(result).toContainText(/form|application|call|office/i);
	return label;
});

await step('fee estimator', async () => {
	await page.goto('/fees');
	const cost = page.getByLabel('Adjusted construction cost');
	await expect(cost).toBeVisible({ timeout: 20_000 });
	await cost.fill('25000');
	// The Fire review fee is 0.15% of the cost: $37.50.
	await expect(page.locator('#lsr').locator('..').locator('.amount')).toHaveText('$37.50', { timeout: 10_000 });
	await expect(page.getByText('Estimate', { exact: true }).first()).toBeVisible();
	return 'life safety review on $25,000 = $37.50';
});

await step('complaint sheet print', async () => {
	await page.goto('/complaint');
	await page.getByLabel('Street address of the property').fill('1 Example Street');
	const concern = page.locator('input[type="checkbox"]').first();
	await concern.check();
	const sheet = page.getByRole('article', { name: 'Printable complaint sheet' });
	await expect(sheet).toContainText('1 Example Street');
	await page.evaluate(() => {
		window.__printed = 0;
		window.print = () => {
			window.__printed++;
		};
	});
	await page.getByRole('button', { name: 'Print the sheet' }).click();
	if ((await page.evaluate(() => window.__printed)) !== 1) throw new Error('Print did not call window.print');
	await page.emulateMedia({ media: 'print' });
	await expect(sheet).toBeVisible();
	await expect(page.getByRole('button', { name: 'Print the sheet' })).toBeHidden();
	await page.emulateMedia({ media: 'screen' });
	// Nothing is stored: no request leaves the page for the complaint.
	return 'sheet filled, print view shows only the sheet';
});

await step('checklist card and feedback', async () => {
	await page.goto('/');
	await page.locator('#q').fill('Do I need a permit to build a deck?');
	await page.locator('#send').click();
	const bot = await waitForAnswer();
	// A1: a permit question carries a checklist card (or an A2 triage card).
	const card = bot.locator('section.pc, section.pt').first();
	await expect(card).toBeVisible({ timeout: 10_000 });
	const label = await card.getAttribute('aria-label');
	const group = bot.getByRole('group', { name: 'Was this answer helpful?' });
	const yes = group.getByRole('button', { name: 'Yes' });
	const [resp] = await Promise.all([
		page.waitForResponse((r) => r.url().endsWith('/api/feedback') && r.request().method() === 'POST'),
		yes.click()
	]);
	if (!resp.ok()) throw new Error(`/api/feedback answered ${resp.status()}`);
	await expect(yes).toHaveAttribute('aria-pressed', 'true');
	return `${label}; feedback recorded`;
});

await step('embed and frame headers', async () => {
	const home = await page.request.get('/');
	const homeCsp = home.headers()['content-security-policy'] || '';
	if (!homeCsp.includes("frame-ancestors 'none'")) throw new Error(`/ CSP is "${homeCsp}"`);
	if ((home.headers()['x-frame-options'] || '').toUpperCase() !== 'DENY') throw new Error('/ has no X-Frame-Options DENY');
	const embed = await page.request.get('/embed');
	const csp = embed.headers()['content-security-policy'] || '';
	if (!/frame-ancestors 'self' .*waterville-me\.gov/.test(csp)) throw new Error(`/embed CSP is "${csp}"`);
	if (embed.headers()['x-frame-options']) throw new Error('/embed sends X-Frame-Options, so the city site cannot frame it');
	await page.goto('/embed');
	await page.getByRole('button', { name: 'Can I keep chickens in my backyard?' }).click();
	const bot = await waitForAnswer();
	const sameTab = await page
		.locator('main a[href^="http"]')
		.evaluateAll((as) => as.filter((a) => a.target !== '_blank').length);
	if (sameTab) throw new Error(`${sameTab} links in the embedded answer open in the frame`);
	return csp;
});

await step(
	'offline sections',
	async () => {
		// The source opened in "source panel" is kept for offline reading.
		await page.goto('/offline');
		const saved = page.locator('ul.saved > li');
		await expect(saved.first()).toBeVisible({ timeout: 10_000 });
		const sw = await page.evaluate(async () => !!(await navigator.serviceWorker?.getRegistration()));
		return `${await saved.count()} saved; service worker ${sw ? 'registered' : 'not registered'}`;
	},
	{ needs: () => passed('source panel') }
);

let caseId = '';
let draftId = '';

if (opts.publicOnly) {
	console.log('Staff: skipped (--public-only)');
} else if (!password) {
	console.log('Staff: skipped (no E2E_STAFF_PASSWORD and no credentials file)');
	results.push({ name: 'staff', status: 'skip', detail: 'no staff password' });
} else {
	console.log('Staff');
	await step('staff login', async () => {
		await page.goto('/staff/cases');
		await expect(page).toHaveURL(/\/staff\/login/);
		await page.getByLabel('Username').fill(user);
		await page.getByLabel('Password').fill(password);
		await page.getByRole('button', { name: 'Sign in' }).click();
		await expect(page).toHaveURL(/\/staff\/cases$/, { timeout: 20_000 });
		const me = await (await page.request.get('/api/staff/me')).json();
		return `${me.username}, env ${me.env}`;
	});
	const signedIn = () => passed('staff login');

	await step(
		'case create',
		async () => {
			await page.getByRole('button', { name: 'New case' }).click();
			await page.getByLabel('Property address').fill('1 Example Street (E2E)');
			await page.getByLabel(/Case title/).fill(`E2E check ${stamp}`);
			await page.getByRole('button', { name: 'Create case' }).click();
			await expect(page).toHaveURL(/\/staff\/cases\/[^/]+$/, { timeout: 20_000 });
			caseId = decodeURIComponent(page.url().split('/').pop());
			await expect(page.getByText(`E2E check ${stamp}`).first()).toBeVisible();
			return caseId;
		},
		{ needs: signedIn }
	);

	async function openDeskPanel(name) {
		const toggle = page.locator('.desk-bar').getByRole('button', { name });
		if ((await toggle.getAttribute('aria-expanded')) !== 'true') await toggle.click();
		await expect(toggle).toHaveAttribute('aria-expanded', 'true');
	}

	await step(
		'desk lookup',
		async () => {
			await page.goto(caseId ? `/staff?case=${encodeURIComponent(caseId)}` : '/staff');
			// Lookup, filters and case are closed until opened.
			await openDeskPanel('Citation lookup');
			await page.getByLabel('Look up a citation').fill('205-7');
			await page.getByRole('button', { name: 'Open', exact: true }).click();
			const result = page.locator('.desk-result');
			await expect(result).toContainText('205-7', { timeout: 30_000 });
			// A lookup opens the section text in the source panel by itself.
			const panel = page.locator('#panel');
			await expect(panel).toBeVisible();
			await expect(page.locator('#panel-body')).toContainText(/enforce/i);
			await page.keyboard.press('Escape');
			await expect(panel).toBeHidden();
			// "Read the text" opens it again.
			await result.getByRole('button', { name: /^Read/ }).click();
			await expect(panel).toBeVisible();
			await page.keyboard.press('Escape');
			await expect(panel).toBeHidden();
			const city = (await result.locator('.desk-result-cite').innerText()).trim();
			// A state statute typed the short way.
			await page.getByLabel('Look up a citation').fill('30-A §4452');
			await page.getByRole('button', { name: 'Open', exact: true }).click();
			await expect(result).toContainText('30-A M.R.S. § 4452', { timeout: 30_000 });
			await expect(panel).toBeVisible();
			await page.keyboard.press('Escape');
			await expect(panel).toBeHidden();
			return `${city.split('\n')[0]}; 30-A M.R.S. § 4452`;
		},
		{ needs: signedIn }
	);


	await step(
		'desk filters',
		async () => {
			if (!new URL(page.url()).pathname.startsWith('/staff')) await page.goto(`/staff?case=${encodeURIComponent(caseId)}`);
			await openDeskPanel(/^Filters/);
			const chip = page.getByRole('button', { name: 'City Code', exact: true });
			await expect(chip).toBeVisible({ timeout: 20_000 });
			await chip.click();
			await expect(chip).toHaveAttribute('aria-pressed', 'true');
			await expect(page.locator('.desk-scope')).toContainText('Searching only');
			return 'City Code chip on';
		},
		{ needs: signedIn }
	);

	let chatBody = null;
	await step(
		'save answer to case',
		async () => {
			if (!page.url().includes('/staff')) await page.goto(`/staff?case=${encodeURIComponent(caseId)}`);
			await page.locator('#q').fill('What notice does § 205-7 require before a penalty?');
			const [req] = await Promise.all([
				page.waitForRequest((r) => r.url().endsWith('/api/chat') && r.method() === 'POST'),
				page.locator('#send').click()
			]);
			chatBody = req.postDataJSON();
			if (chatBody.mode !== 'staff') throw new Error('the desk did not ask in staff mode');
			if (passed('desk filters') && !(chatBody.filters?.source_types || []).includes('code'))
				throw new Error('the City Code filter was not sent with the question');
			if (chatBody.case_id !== caseId) throw new Error('the chosen case was not sent with the question');
			const bot = await waitForAnswer();
			await expect(bot.locator('.stamp, [class*="stamp"]').first()).toBeVisible();
			const select = page.getByLabel('Working on case');
			await expect(select).toHaveValue(caseId);
			await bot.getByTestId('save-to-case').click();
			await expect(bot.getByRole('status').filter({ hasText: 'Saved to' })).toBeVisible({ timeout: 20_000 });
			const c = await (await page.request.get(`/api/staff/cases/${encodeURIComponent(caseId)}`)).json();
			const answers = (c.items || []).filter((i) => i.kind === 'answer');
			if (!answers.length) throw new Error('the case has no saved answer');
			return `${answers.length} answer on the case timeline`;
		},
		{ needs: () => signedIn() && caseId }
	);


	await step(
		'copy buttons',
		async () => {
			const bot = page.locator('.msg.bot').last();
			const read = () => page.evaluate(() => navigator.clipboard.readText());
			await bot.getByTestId('copy-answer').click();
			await expect.poll(read, { timeout: 5_000 }).toMatch(/Sources/);
			const answer = await read();
			const cites = bot.getByTestId('copy-citations');
			let citations = '';
			if (await cites.count()) {
				await cites.click();
				await expect.poll(read, { timeout: 5_000 }).toMatch(/^\[\d+\] /);
				citations = await read();
			}
			await bot.locator('.cite').first().click();
			await expect(page.locator('#panel')).toBeVisible();
			await page.getByTestId('panel-copy-citation').click();
			await expect.poll(read, { timeout: 5_000 }).not.toBe(citations || answer);
			const one = await read();
			await page.keyboard.press('Escape');
			return `answer ${answer.length} chars, ${citations.split('\n').filter(Boolean).length} citations, panel: ${one.slice(0, 60)}`;
		},
		{ needs: () => passed('save answer to case') }
	);

	await step(
		'draft create and .docx',
		async () => {
			await page.goto(`/staff/drafts/new?template=nov-1&case=${encodeURIComponent(caseId)}`);
			const save = page.getByRole('button', { name: 'Save draft' });
			await expect(save).toBeVisible({ timeout: 20_000 });
			await page.getByLabel('Draft title').fill(`E2E check ${stamp}`);
			await save.click();
			await expect(page).toHaveURL(/\/staff\/drafts\/d[^/?]+/, { timeout: 20_000 });
			draftId = decodeURIComponent(new URL(page.url()).pathname.split('/').pop());
			const [download] = await Promise.all([
				page.waitForEvent('download', { timeout: 30_000 }),
				page.getByRole('button', { name: 'Export .docx' }).click()
			]);
			const name = download.suggestedFilename();
			if (!name.endsWith('.docx')) throw new Error(`download is ${name}`);
			const path = await download.path();
			const head = readFileSync(path).subarray(0, 2).toString('latin1');
			if (head !== 'PK') throw new Error('the .docx is not a zip file');
			const c = await (await page.request.get(`/api/staff/cases/${encodeURIComponent(caseId)}`)).json();
			if (!(c.items || []).some((i) => i.kind === 'draft')) throw new Error('the draft is not on the case timeline');
			return `${draftId}, ${name}, ${readFileSync(path).length} bytes`;
		},
		{ needs: () => signedIn() && caseId }
	);

	await step(
		'deadlines',
		async () => {
			await page.goto(`/staff/deadlines?trigger=zba-decision&date=2026-10-01&case=${encodeURIComponent(caseId)}`);
			const clocks = page.locator('article.clock');
			await expect(clocks.first()).toBeVisible({ timeout: 20_000 });
			const n = await clocks.count();
			await expect(page.locator('main')).toContainText(/80B/);
			if (!caseId) return `${n} clocks for a ZBA decision on 2026-10-01`;
			const first = clocks.first();
			await first.getByRole('button', { name: 'Add to case' }).click();
			await expect(first.getByRole('button', { name: 'Added to case' })).toBeVisible({ timeout: 20_000 });
			const c = await (await page.request.get(`/api/staff/cases/${encodeURIComponent(caseId)}`)).json();
			const d = (c.items || []).filter((i) => i.kind === 'deadline');
			if (!d.length) throw new Error('the deadline is not on the case timeline');
			return `${n} clocks for a ZBA decision on 2026-10-01; ${d[0].date} ${d[0].label} added to the case`;
		},
		{ needs: signedIn }
	);


	await step(
		'project gates',
		async () => {
			await page.goto(caseId ? `/staff/gates?case=${encodeURIComponent(caseId)}` : '/staff/gates');
			const form = page.getByRole('form', { name: 'Project facts' });
			await expect(form.getByLabel('Type of project')).toBeEnabled({ timeout: 20_000 });
			await form.getByLabel('Type of project').selectOption('new_building');
			await form.getByLabel('Use after the project').selectOption('commercial');
			await form.getByLabel('New footprint (sq ft)').fill('6000');
			await form.getByLabel('Construction cost ($)').fill('900000');
			await form.getByRole('button', { name: 'Check gates' }).click();
			const head = page.locator('.results .sum h3');
			await expect(head).toContainText(/approval/, { timeout: 20_000 });
			const summary = (await head.innerText()).trim();
			if (!caseId) return summary;
			await page.getByRole('button', { name: 'Save as a case note' }).click();
			await expect(page.getByRole('status').filter({ hasText: 'Checklist saved' })).toBeVisible({ timeout: 20_000 });
			const c = await (await page.request.get(`/api/staff/cases/${encodeURIComponent(caseId)}`)).json();
			if (!(c.items || []).some((i) => i.kind === 'note')) throw new Error('the checklist note is not on the case');
			return `${summary}, saved to the case as a note`;
		},
		{ needs: signedIn }
	);

	await step(
		'case timeline',
		async () => {
			await page.goto(`/staff/cases/${encodeURIComponent(caseId)}`);
			const kinds = ['answer', 'draft', 'deadline', 'note'];
			const c = await (await page.request.get(`/api/staff/cases/${encodeURIComponent(caseId)}`)).json();
			const have = new Set((c.items || []).map((i) => i.kind));
			const missing = kinds.filter((k) => !have.has(k) && passed({ answer: 'save answer to case', draft: 'draft create and .docx', deadline: 'deadlines', note: 'project gates' }[k]));
			if (missing.length) throw new Error(`the case has no ${missing.join(', ')} item`);
			await expect(page.locator('main')).toContainText(`E2E check ${stamp}`);
			return `${(c.items || []).length} items: ${[...have].join(', ')}`;
		},
		{ needs: () => signedIn() && caseId }
	);

	await step(
		'insights',
		async () => {
			await page.goto('/staff/insights');
			await expect(page.getByRole('heading', { name: 'Insights' })).toBeVisible();
			await expect(page.getByRole('heading', { name: 'Code change alerts' })).toBeVisible({ timeout: 20_000 });
			await expect(page.getByRole('heading', { name: 'Question volume' })).toBeVisible({ timeout: 20_000 });
			return 'digest, change alerts and reports render';
		},
		{ needs: signedIn }
	);

	await step(
		'cleanup',
		async () => {
			if (keep) return `kept case ${caseId} and draft ${draftId} (E2E_KEEP=1)`;
			const done = [];
			if (draftId) {
				const r = await page.request.delete(`/api/staff/drafts/${encodeURIComponent(draftId)}`, { headers: CSRF });
				if (!r.ok()) throw new Error(`draft delete: HTTP ${r.status()}`);
				done.push(`draft ${draftId}`);
			}
			if (caseId) {
				const r = await page.request.delete(`/api/staff/cases/${encodeURIComponent(caseId)}`, { headers: CSRF });
				if (!r.ok()) throw new Error(`case delete: HTTP ${r.status()}`);
				done.push(`case ${caseId}`);
			}
			return done.length ? `deleted ${done.join(' and ')}` : 'nothing to delete';
		},
		{ needs: signedIn }
	);

	await step(
		'logout',
		async () => {
			await page.goto('/staff');
			await page.getByRole('navigation', { name: 'Staff' }).getByRole('button', { name: 'Log out' }).click();
			await expect(page).toHaveURL(/\/staff\/login/);
			const me = await page.request.get('/api/staff/me');
			if (me.status() !== 401) throw new Error(`/api/staff/me answers ${me.status()} after logout`);
		},
		{ needs: signedIn }
	);
}

await browser.close();

const failed = results.filter((r) => r.status === 'fail');
const skipped = results.filter((r) => r.status === 'skip');
console.log(
	`\n${results.length - failed.length - skipped.length} passed, ${failed.length} failed, ${skipped.length} skipped` +
		(consoleErrors.length ? `; ${consoleErrors.length} console errors (first: ${consoleErrors[0].slice(0, 160)})` : '')
);
process.exit(failed.length ? 1 : 0);
