#!/usr/bin/env python3
"""
cmd_359-D: YouTube新着商品 Telegram提案スクリプト
cron 45 6 * * * で実行。youtube_trending_collector.py実行後に動かす。
"""
import os, sys, requests, yaml, datetime
from pathlib import Path
from dotenv import load_dotenv

DRY_RUN = os.environ.get('DRY_RUN', '0') == '1'

sys.path.insert(0, str(Path(__file__).parent))
if not DRY_RUN:
    from _telegram_gate import check_shogun_auth
    check_shogun_auth("youtube_propose.py")

BLOG_DIR    = Path(__file__).parent.parent
TODAY_FILE  = BLOG_DIR / 'data' / 'youtube_today.yaml'
PROPOSE_LOG = BLOG_DIR / 'data' / 'youtube_propose_log.yaml'

MA_DIR = Path('/mnt/c/tools/multi-agent-shogun')
if not DRY_RUN:
    load_dotenv(MA_DIR / 'config' / 'telegram_auth.env')
    BOT_TOKEN = os.environ['TELEGRAM_BOT_TOKEN']
    CHAT_ID   = os.environ['TELEGRAM_CHAT_ID']
else:
    BOT_TOKEN = ''
    CHAT_ID   = ''

RANK_EMOJI = ['1️⃣','2️⃣','3️⃣','4️⃣','5️⃣','6️⃣','7️⃣','8️⃣','9️⃣']

def send_message(text: str):
    if DRY_RUN:
        print(f'[DRY_RUN] sendMessage: {text[:100]}')
        return
    requests.post(f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage',
                  json={'chat_id': int(CHAT_ID), 'text': text, 'parse_mode': 'HTML'},
                  timeout=10)

def send_photo(photo_url: str, caption: str):
    if DRY_RUN:
        print(f'[DRY_RUN] sendPhoto: {caption[:80]}')
        return
    try:
        requests.post(f'https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto',
                      json={'chat_id': int(CHAT_ID), 'photo': photo_url, 'caption': caption},
                      timeout=15)
    except Exception:
        send_message(caption)

def main():
    if not TODAY_FILE.exists():
        send_message('⚠️ youtube_today.yaml が見つかりません。')
        sys.exit(1)

    with open(TODAY_FILE) as f:
        data = yaml.safe_load(f)

    videos = data.get('new_videos', [])
    if not videos:
        print('[youtube_propose] 新着なし、スキップ')
        sys.exit(0)

    date_str = data.get('date', '本日')
    send_message(f'📺 <b>{date_str} YouTuber紹介商品 新着</b>\n━━━━━━━━━━')

    log_items = []
    for i, video in enumerate(videos[:9]):
        emoji   = RANK_EMOJI[i]
        channel = video.get('channel_name', '')
        title   = video.get('title', '')[:50]
        products= video.get('products', [])
        prod_text = ''
        if products:
            p = products[0]
            name  = p.get('name', p.get('query', '商品'))[:40]
            price = f"¥{p.get('price', '?'):,}" if isinstance(p.get('price'), int) else '価格確認中'
            prod_text = f'\n🛒 {name} {price}'

        caption = (
            f'{emoji} <b>{channel}</b>\n'
            f'📹 {title}\n'
            f'{prod_text}\n'
            f'🔗 {video.get("url", "")}'
        )
        thumb = video.get('thumbnail', '')
        if thumb:
            send_photo(thumb, caption)
        else:
            send_message(caption)

        log_items.append({
            'index': i + 1,
            'video_id': video.get('video_id'),
            'title': title,
            'channel': channel,
        })

    send_message(
        '━━━━━━━━━━\n'
        '📺 気になる番号をカンマ区切りで返信されたし（例: <code>1,3</code>）\n'
        '記事化して公開スケジュールに追加いたす。'
    )

    if not DRY_RUN:
        log = []
        if PROPOSE_LOG.exists():
            with open(PROPOSE_LOG) as f:
                log = yaml.safe_load(f) or []
        log.append({
            'proposed_at': datetime.datetime.now().isoformat(),
            'date': date_str,
            'items': log_items,
        })
        log = log[-7:]
        with open(PROPOSE_LOG, 'w') as f:
            yaml.dump(log, f, allow_unicode=True, default_flow_style=False)

    print(f'[youtube_propose] {len(videos)}件{"(DRY_RUN)" if DRY_RUN else "送信完了"}')

if __name__ == '__main__':
    main()
