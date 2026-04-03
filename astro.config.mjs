// @ts-check

import mdx from '@astrojs/mdx';
import sitemap from '@astrojs/sitemap';
import tailwind from '@astrojs/tailwind';
import { defineConfig, passthroughImageService } from 'astro/config';

// https://astro.build/config
export default defineConfig({
	site: 'https://intheblueshirt.com',
	integrations: [mdx(), sitemap(), tailwind()],
	image: {
		service: passthroughImageService(),
	},
});
