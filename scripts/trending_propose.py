#!/usr/bin/env python3
"""
gadget-blog 売れ筋提案スクリプト (cmd_358-B)
trending_today.yaml のTOP5を画像付きTelegramメッセージで殿に送信する。
cron 30 6 * * * で毎朝実行。
"""
import os
import sys
import datetime
import requests
import yaml
from pathlib import Path
from dotenv import load_dotenv

# 将軍/cronのみ許可
sys.path.insert(0, str(Path(__file__).parent))
from _telegram_gate import check_shogun_auth
check_shogun_auth("trending_propose.py")

SCRIPT_DIR  = Path(__file__).parent
BLOG_DIR    = SCRIPT_DIR.parent
TODAY_FILE  = BLOG_DIR / 'data' / 'trending_today.yaml'
PROPOSE_LOG = BLOG_DIR / 'data' / 'trending_propose_log.yaml'

MA_DIR = Path('/mnt/c/tools/multi-agent-shogun')
load_dotenv(MA_DIR / 'config' / 'telegram_auth.env')
BOT_TOKEN = os.environ['TELEGRAM_BOT_TOKEN']
CHAT_ID   = os.environ['TELEGRAM_CHAT_ID']

RANK_EMOJI = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣']


def send_message(text: str):
    requests.post(
        f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage',
        json={'chat_id': int(CHAT_ID), 'text': text, 'parse_mode': 'HTML'},
        timeout=10,
    )


def send_photo(image_url: str, caption: str):
    try:
        requests.post(
            f'https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto',
            json={'chat_id': int(CHAT_ID), 'photo': image_url, 'caption': caption},
            timeout=15,
        )
    except Exception:
        send_message(caption)


def format_rank_change(change: int) -> str:
    if change > 0:  return f'↑{change}位上昇'
    if change < 0:  return f'↓{abs(change)}位下降'
    return '→ 横ばい'


def main():
    if not TODAY_FILE.exists():
        send_message('⚠️ trending_today.yaml が見つかりません。trending_products_collector.py を先に実行してください。')
        sys.exit(1)

    with open(TODAY_FILE) as f:
        data = yaml.safe_load(f)

    top5 = data.get('top5', [])
    if not top5:
        send_message('⚠️ 本日の売れ筋商品データが空です。')
        sys.exit(1)

    date_str = data.get('date', '本日')
    send_message(f'📊 <b>{date_str} 売れ筋ガジェットTOP5</b>（前日比急上昇順）\n━━━━━━━━━━')

    for i, item in enumerate(top5[:5]):
        emoji  = RANK_EMOJI[i]
        change = format_rank_change(item.get('rank_change', 0))
        price  = f"¥{item.get('price', 0):,}"
        cat    = item.get('category', '')
        name   = item.get('name', '')[:60]
        caption = (
            f"{emoji} <b>{name}</b>\n"
            f"💴 {price}　📈 {change}\n"
            f"🏷 {cat}\n"
            f"🔗 {item.get('url', '')}"
        )
        image_url = item.get('image_url', '')
        if image_url:
            send_photo(image_url, caption)
        else:
            send_message(caption)

    send_message(
        '━━━━━━━━━━\n'
        '⬆️ 気になる番号をカンマ区切りで返信されたし（例: <code>1,3</code>）\n'
        '記事化して公開スケジュールに追加いたす。'
    )

    log = []
    if PROPOSE_LOG.exists():
        with open(PROPOSE_LOG) as f:
            log = yaml.safe_load(f) or []
    log.append({
        'proposed_at': datetime.datetime.now().isoformat(),
        'date': date_str,
        'items': [{
            'index': i + 1,
            'item_code': item.get('item_code'),
            'name': item.get('name', '')[:60],
        } for i, item in enumerate(top5[:5])],
    })
    log = log[-7:]
    with open(PROPOSE_LOG, 'w') as f:
        yaml.dump(log, f, allow_unicode=True, default_flow_style=False)

    print(f'[trending_propose] TOP5送信完了。propose_log保存。')


if __name__ == '__main__':
    main()
