import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vitest/config';

// The dev server proxies /api (and /healthz) to the FastAPI backend.
// Set API_PORT to the port your backend listens on.
const api = `http://localhost:${process.env.API_PORT || 8101}`;

export default defineConfig({
	plugins: [sveltekit()],
	server: {
		proxy: {
			'/api': { target: api, changeOrigin: false },
			'/healthz': { target: api }
		}
	},
	preview: {
		proxy: {
			'/api': { target: api, changeOrigin: false }
		}
	},
	test: {
		include: ['src/**/*.{test,spec}.{js,ts}'],
		environment: 'node'
	}
});
