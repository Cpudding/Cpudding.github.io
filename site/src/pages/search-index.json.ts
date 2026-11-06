import type { APIRoute } from 'astro';
import { getCollection } from 'astro:content';

export const prerender = true;

function searchableText(markdown: string): string {
	const body = markdown.replace(/^---\r?\n[\s\S]*?\r?\n---(?:\r?\n|$)/, '');
	let fence: string | undefined;
	const lines = body.split(/\r?\n/).map((line) => {
		const marker = line.match(/^\s*(`{3,}|~{3,})/);
		if (marker && !fence) {
			fence = marker[1][0];
			return '';
		}
		if (marker && fence === marker[1][0]) {
			fence = undefined;
			return '';
		}
		if (fence) return line;
		return line
			.replace(/<[^>]*>/g, ' ')
			.replace(/!?\[([^\]]*)\]\([^)]*\)/g, '$1')
			.replace(/^\s{0,3}#{1,6}\s+/, '')
			.replace(/[`*_]/g, '');
	});
	return lines.join(' ').replace(/\s+/g, ' ').trim();
}

export const GET: APIRoute = async () => {
	const posts = (await getCollection('blog')).sort(
		(a, b) => b.data.pubDate.valueOf() - a.data.pubDate.valueOf(),
	);
	const index = posts.map((post) => ({
		title: post.data.title,
		description: post.data.description,
		url: encodeURI(post.data.permalink),
		pubDate: post.data.pubDate.toISOString(),
		tags: post.data.tags,
		content: searchableText(post.body ?? ''),
	}));
	return new Response(JSON.stringify(index), {
		headers: { 'Content-Type': 'application/json; charset=utf-8' },
	});
};
