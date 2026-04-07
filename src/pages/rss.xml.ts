import rss from '@astrojs/rss';
import { getCollection } from 'astro:content';

export async function GET(context) {
  const posts = await getCollection('posts');
  const sorted = posts.sort((a, b) =>
    new Date(b.data.pubDate).getTime() - new Date(a.data.pubDate).getTime()
  );
  return rss({
    title: 'ガジェット価格比較ブログ',
    description: '最新ガジェットの価格比較・ランキング情報',
    site: context.site,
    items: sorted.map((post) => ({
      title: post.data.title,
      pubDate: post.data.pubDate,
      description: post.data.description ?? '',
      link: `/posts/${post.slug}/`,
    })),
    customData: '<language>ja</language>',
  });
}
