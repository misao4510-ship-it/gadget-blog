export const en = {
  site: { name: 'Gadget Price Comparison Blog', tagline: 'Find the Best Gadgets at the Best Prices' },
  nav: { home: 'Home', products: 'Products', rankingPrefix: 'Ranking' },
  article: { publishedOn: 'Published on', category: 'Category', amazonBtn: '🛒 Buy on Amazon ▶', rakutenBtn: '🛍️ Buy on Rakuten ▶' },
  ranking: { rank: 'Rank', product: 'Product', price: 'Price', feature: 'Feature', buyNow: 'Buy Now' },
  badge: { popular: 'Most Popular', recommended: 'Recommended', value: 'Best Value' },
  misc: { inJapanese: 'This article is written in Japanese.', viewOriginal: 'View original article (Japanese)', priceChart: 'Price History', updated: 'Updated:' }
} as const;
export type En = typeof en;
