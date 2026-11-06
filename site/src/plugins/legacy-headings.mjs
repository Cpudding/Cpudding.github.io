import legacyHeadings from '../data/legacy-headings.json' with { type: 'json' };

// Hexo and Astro slug duplicate headings differently. Keep existing bookmarks
// attached to the same sections, including repeated headings such as “定义”.
export default function preserveLegacyHeadings() {
	return (tree, file) => {
		const saved = legacyHeadings[file.data.astro?.frontmatter?.permalink];
		if (!saved) return;
		const remaining = [...saved];
		const textOf = (node) => node.type === 'text' ? node.value : (node.children ?? []).map(textOf).join('');
		const walk = (node) => {
			if (node.type === 'element' && /^h[2-6]$/.test(node.tagName)) {
				const text = textOf(node).replace(/\s+/g, ' ').trim();
				const index = remaining.findIndex((heading) => heading.text === text && heading.depth === Number(node.tagName[1]));
				if (index >= 0) {
					node.properties ??= {};
					node.properties.id = remaining.splice(index, 1)[0].id;
				}
			}
			for (const child of node.children ?? []) walk(child);
		};
		walk(tree);
	};
}
