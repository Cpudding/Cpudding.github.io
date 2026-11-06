import { defineCollection } from 'astro:content';
import { glob } from 'astro/loaders';
import { z } from 'astro/zod';

const blog = defineCollection({
	// Load Markdown and MDX files in the `src/content/blog/` directory.
	loader: glob({ base: './src/content/blog', pattern: '**/*.{md,mdx}' }),
	// Type-check frontmatter using a schema
	schema: ({ image }) =>
		z.object({
			title: z.string(),
			description: z.string(),
			// Keep published URLs independent of filenames and content collection IDs.
			permalink: z.string().regex(/^\/\d{4}\/\d{2}\/\d{2}\/[^/?#]+\/$/),
			// Transform string to Date object
			pubDate: z.coerce.date(),
			updatedDate: z.coerce.date().optional(),
			tags: z.array(z.string()).default([]),
			mathjax: z.boolean().default(false),
			heroImage: z.optional(image()),
		}),
});

export const collections = { blog };
