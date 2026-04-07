export const zh = {
  site: { name: '数码产品比价博客', tagline: '找到最好的数码产品，享受最优惠的价格' },
  nav: { home: '首页', products: '商品列表', rankingPrefix: '排行榜' },
  article: { publishedOn: '发布日期', category: '类别', amazonBtn: '🛒 在Amazon购买 ▶', rakutenBtn: '🛍️ 在乐天购买 ▶' },
  ranking: { rank: '排名', product: '商品', price: '价格', feature: '特点', buyNow: '立即购买' },
  badge: { popular: '最受欢迎', recommended: '推荐', value: '性价比最高' },
  misc: { inJapanese: '本文为日语原文。', viewOriginal: '查看原文（日语）', priceChart: '价格历史', updated: '更新日期：' }
} as const;
export type Zh = typeof zh;
