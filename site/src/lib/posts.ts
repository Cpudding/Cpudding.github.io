import { getCollection, type CollectionEntry } from 'astro:content';

export type BlogPost = CollectionEntry<'blog'>;
export interface TagEntry { name: string; href: string; posts: BlogPost[] }
export interface ArchiveMonth { year: string; month: string; href: string; posts: BlogPost[] }
export interface ArchiveYear { year: string; href: string; posts: BlogPost[]; months: ArchiveMonth[] }

const archiveDate = new Intl.DateTimeFormat('en', {
	timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit',
});

export async function getPosts(): Promise<BlogPost[]> {
	return (await getCollection('blog')).sort(
		(a, b) => b.data.pubDate.valueOf() - a.data.pubDate.valueOf(),
	);
}

export function postHref(post: BlogPost): string {
	return encodeURI(post.data.permalink);
}

export function tagHref(tag: string): string {
	return `/tags/${encodeURIComponent(tag)}/`;
}

export function getTagEntries(posts: BlogPost[]): TagEntry[] {
	const entries = new Map<string, BlogPost[]>();
	for (const post of posts) {
		for (const tag of new Set(post.data.tags)) {
			const tagged = entries.get(tag) ?? [];
			tagged.push(post);
			entries.set(tag, tagged);
		}
	}
	return [...entries.entries()]
		.sort(([a], [b]) => a.localeCompare(b, 'zh-CN'))
		.map(([name, tagged]) => ({ name, href: tagHref(name), posts: tagged }));
}

export function getArchiveGroups(posts: BlogPost[]): ArchiveYear[] {
	const groups = new Map<string, Map<string, BlogPost[]>>();
	for (const post of posts) {
		const parts = archiveDate.formatToParts(post.data.pubDate);
		const year = parts.find((part) => part.type === 'year')!.value;
		const month = parts.find((part) => part.type === 'month')!.value;
		const months = groups.get(year) ?? new Map<string, BlogPost[]>();
		const entries = months.get(month) ?? [];
		entries.push(post);
		months.set(month, entries);
		groups.set(year, months);
	}
	return [...groups.entries()]
		.sort(([a], [b]) => b.localeCompare(a))
		.map(([year, groupsByMonth]) => {
			const months = [...groupsByMonth.entries()]
				.sort(([a], [b]) => b.localeCompare(a))
				.map(([month, entries]) => ({
					year, month, href: `/archives/${year}/${month}/`, posts: entries,
				}));
			return {
				year, href: `/archives/${year}/`,
				posts: months.flatMap((month) => month.posts), months,
			};
		});
}
