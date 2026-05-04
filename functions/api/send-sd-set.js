export async function onRequestPost(context) {
  const { request, env } = context;
  const { settings } = await request.json();
  if (!settings || Object.keys(settings).length === 0) {
    return Response.json({ error: "settings required" }, { status: 400 });
  }

  const token = env.TELEGRAM_SD_BOT_TOKEN;
  const chatId = env.LORD_CHAT_ID;
  if (!token || !chatId) return Response.json({ error: "not configured" }, { status: 500 });

  const parts = Object.entries(settings)
    .filter(([, v]) => v !== null && v !== undefined && v !== '')
    .map(([k, v]) => `${k}=${v}`);
  const cmd = `/sd_set ${parts.join(' ')}`;

  const res = await fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ chat_id: parseInt(chatId), text: cmd }),
  });
  const data = await res.json();
  if (data.ok) return Response.json({ ok: true });
  return Response.json({ error: data.description }, { status: 500 });
}
