import adapter from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
const config = {
	preprocess: vitePreprocess(),
	vitePlugin: {
		// Runes mode for every component in this project, not for libraries.
		dynamicCompileOptions: ({ filename }) =>
			filename.includes('node_modules') ? undefined : { runes: true }
	},
	kit: {
		// SPA: FastAPI serves build/ and falls back to index.html for client routes.
		adapter: adapter({ pages: 'build', assets: 'build', fallback: 'index.html', strict: false })
	}
};

export default config;
