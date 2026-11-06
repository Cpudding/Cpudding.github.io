import type { APIRoute } from 'astro';

export const GET: APIRoute = () => new Response(JSON.stringify({
	framework: 'Astro',
	revision: process.env.GITHUB_SHA ?? 'local',
}), { headers: { 'Content-Type': 'application/json; charset=utf-8' } });
