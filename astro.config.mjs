import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';

export default defineConfig({
  site: 'https://gadget-blog-dxq.pages.dev',
  integrations: [sitemap()],
  build: { assets: '_assets' },
  i18n: {
    defaultLocale: 'ja',
    locales: ['ja', 'en', 'zh'],
    routing: {
      prefixDefaultLocale: false
    }
  }
});
