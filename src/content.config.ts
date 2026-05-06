import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';

const posts = defineCollection({
  loader: glob({ pattern: '**/*.{md,mdx}', base: './src/content/posts' }),
  schema: z.object({
    title: z.string(),
    description: z.string(),
    publishDate: z.string(),
    category: z.string(),
    subcategory: z.string().optional(),
    products: z.array(z.string()).default([]),
    type: z.enum(['review', 'comparison', 'roundup', 'ranking', 'guide']),
    draft: z.boolean().default(false),
    ogImage: z.string().optional(),
    recommendation: z.number().min(1).max(5).nullish(),
    priceUpdatedAt: z.string().optional(),
    tags: z.array(z.string()).default([]),
    youtube_video_id: z.string().optional(),
    youtube_channel_name: z.string().optional(),
    youtube_channel_url: z.string().optional(),
  }),
});

export const collections = { posts };
