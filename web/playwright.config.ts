import { randomBytes, scryptSync } from 'node:crypto';
import { defineConfig } from '@playwright/test';

// End-to-end tests against the real FastAPI app in FAKE_AZURE mode, serving
// the built UI from web/build. Run `pnpm build` first, then `pnpm test:e2e`.
// E2E_PORT picks the backend port (default 8199) so parallel agents do not collide.
const port = Number(process.env.E2E_PORT || 8199);

// A throwaway staff user for the started server. The password is random per
// run and reaches the test workers through the environment. Against a server
// you started yourself, set E2E_STAFF_USER and E2E_STAFF_PASSWORD to a user
// in that server's STAFF_USERS.
process.env.E2E_STAFF_USER ||= 'e2e';
process.env.E2E_STAFF_PASSWORD ||= randomBytes(18).toString('base64url');

function staffHash(password: string): string {
	// Same format as `python -m app.auth hash`: scrypt$N$r$p$salt$hash, unpadded urlsafe base64.
	const [N, r, p] = [2 ** 15, 8, 1];
	const salt = randomBytes(16);
	const digest = scryptSync(password, salt, 32, { N, r, p, maxmem: 64 * 1024 * 1024 });
	return `scrypt$${N}$${r}$${p}$${salt.toString('base64url')}$${digest.toString('base64url')}`;
}

export default defineConfig({
	testDir: 'e2e',
	timeout: 30_000,
	use: { baseURL: `http://localhost:${port}`, viewport: { width: 1280, height: 900 } },
	webServer: {
		command: `uv run uvicorn app.main:app --port ${port}`,
		cwd: '..',
		env: {
			FAKE_AZURE: '1',
			APP_ENV: 'local',
			STAFF_USERS: JSON.stringify({ [process.env.E2E_STAFF_USER]: staffHash(process.env.E2E_STAFF_PASSWORD) })
		},
		url: `http://localhost:${port}/healthz`,
		reuseExistingServer: !process.env.CI
	}
});
