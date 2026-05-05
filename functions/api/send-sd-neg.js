const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
};

export async function onRequestOptions() {
  return new Response(null, { status: 204, headers: CORS_HEADERS });
}

export async function onRequestPost(context) {
  const { request, env } = context;
  const { command } = await request.json();
  if (!command) return Response.json({ error: "command required" }, { status: 400, headers: CORS_HEADERS });

  const token = env.TELEGRAM_SD_BOT_TOKEN;
  const chatId = env.LORD_CHAT_ID;
  if (!token || !chatId) return Response.json({ error: "not configured" }, { status: 500, headers: CORS_HEADERS });

  const res = await fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ chat_id: parseInt(chatId), text: command }),
  });
  const data = await res.json();
  if (data.ok) return Response.json({ ok: true }, { headers: CORS_HEADERS });
  return Response.json({ error: data.description }, { status: 500, headers: CORS_HEADERS });
}
