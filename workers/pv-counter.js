/**
 * Cloudflare Workers PV Counter
 * KV namespace: PV_COUNTER
 *
 * GET  /api/pv?path=/posts/xxx  → { path, count }
 * POST /api/pv?path=/posts/xxx  → カウントアップ後 { path, count }
 */

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    // CORS
    const corsHeaders = {
      'Access-Control-Allow-Origin': 'https://gadget-blog-dxq.pages.dev',
      'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
    };

    if (request.method === 'OPTIONS') {
      return new Response(null, { headers: corsHeaders });
    }

    if (url.pathname !== '/api/pv') {
      return new Response('Not found', { status: 404 });
    }

    const path = url.searchParams.get('path');
    if (!path) {
      return new Response(JSON.stringify({ error: 'path required' }), {
        status: 400,
        headers: { 'Content-Type': 'application/json', ...corsHeaders },
      });
    }

    const key = `pv:${path}`;

    if (request.method === 'POST') {
      // カウントアップ (アトミック操作)
      const current = parseInt(await env.PV_COUNTER.get(key) || '0', 10);
      const next = current + 1;
      await env.PV_COUNTER.put(key, String(next));
      return new Response(JSON.stringify({ path, count: next }), {
        headers: { 'Content-Type': 'application/json', ...corsHeaders },
      });
    }

    // GET
    const count = parseInt(await env.PV_COUNTER.get(key) || '0', 10);
    return new Response(JSON.stringify({ path, count }), {
      headers: {
        'Content-Type': 'application/json',
        'Cache-Control': 'no-cache',
        ...corsHeaders,
      },
    });
  },
};
