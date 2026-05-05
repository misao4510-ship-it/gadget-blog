export async function onRequestPost(context) {
  const { request, env } = context;
  const body = await request.json();
  const { prompt, count, width, height, steps, cfg, sampler, lora } = body;
  if (!prompt) return Response.json({ error: "prompt required" }, { status: 400 });

  const webhookUrl = env.SD_BOT_WEBHOOK_URL;
  if (!webhookUrl) return Response.json({ error: "SD_BOT_WEBHOOK_URL not configured" }, { status: 500 });

  const payload = { prompt };
  if (count !== undefined) payload.count = count;
  if (width !== undefined) payload.width = width;
  if (height !== undefined) payload.height = height;
  if (steps !== undefined) payload.steps = steps;
  if (cfg !== undefined) payload.cfg = cfg;
  if (sampler !== undefined) payload.sampler = sampler;
  if (lora !== undefined) payload.lora = lora;

  // Fire-and-forget: Workerはwebhookのレスポンスを待たず即時返却
  context.waitUntil(
    fetch(`${webhookUrl}/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout(8000),
    }).catch(() => {})
  );
  return Response.json({ ok: true, queued: payload.count || 1 });
}
