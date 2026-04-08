import rss from '@astrojs/rss';
import { getCollection } from 'astro:content';

export async function GET(context) {
  const posts = await getCollection('posts');
  const sorted = posts.sort((a, b) =>
    new Date(b.data.publishDate).getTime() - new Date(a.data.publishDate).getTime()
  );
  return rss({
    title: '人生快適ブログ',
    description: '毎日の生活をもっと快適にするガジェット・便利グッズ情報',
    site: context.site,
    items: sorted.map((post) => ({
      title: post.data.title,
      pubDate: post.data.publishDate,
      description: post.data.description ?? '',
      link: `/posts/${post.id}/`,
    })),
    customData: '<language>ja</language>',
  });
}
