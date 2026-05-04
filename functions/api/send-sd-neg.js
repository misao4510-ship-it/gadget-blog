export async function onRequestPost(context) {
  const { request, env } = context;
  const { command } = await request.json();
  if (!command) return Response.json({ error: "command required" }, { status: 400 });

  const token = env.TELEGRAM_SD_BOT_TOKEN;
  const chatId = env.LORD_CHAT_ID;
  if (!token || !chatId) return Response.json({ error: "not configured" }, { status: 500 });

  const res = await fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ chat_id: parseInt(chatId), text: command }),
  });
  const data = await res.json();
  if (data.ok) return Response.json({ ok: true });
  return Response.json({ error: data.description }, { status: 500 });
}
