#!/usr/bin/env python3
"""
Bluesky 自動投稿スクリプト (cmd_175)

AT Protocol (atproto) を使用してBlueskyにブログ記事を投稿する。
X投稿（x_scheduled_post.py）と同様の仕組みで、
data/bluesky_scheduled.json の予約データをもとに投稿する。

Usage:
    python3 scripts/bluesky_post.py --slot 1   # 7:30の投稿
    python3 scripts/bluesky_post.py --slot 2   # 12:30の投稿
    python3 scripts/bluesky_post.py --slot 3   # 21:00の投稿
    python3 scripts/bluesky_post.py --dry-run --slot 1
"""

import os
import sys
import json
import logging
import argparse
from pathlib import Path
from datetime import datetime, timezone

BLOG_ROOT = Path(__file__).parent.parent.resolve()
SCHEDULE_FILE = BLOG_ROOT / "data" / "bluesky_scheduled.json"
HISTORY_FILE = BLOG_ROOT / "data" / "bluesky_post_history.json"
AUTH_FILE = BLOG_ROOT / "config" / "bluesky_auth.env"
TELEGRAM_AUTH = Path("/mnt/c/tools/multi-agent-shogun/config/telegram_auth.env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def load_env(path: Path) -> dict:
    env = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip()
    return env


def send_telegram(text: str):
    import requests
    env = load_env(TELEGRAM_AUTH)
    bot_token = env.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = env.get("TELEGRAM_CHAT_ID", "")
    if bot_token and chat_id:
        try:
            requests.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={"chat_id": chat_id, "text": text},
                timeout=30,
            )
        except Exception as e:
            logger.warning(f"Telegram通知失敗: {e}")


def post_to_bluesky(text: str, image_path: str = None, url: str = None) -> str | None:
    """
    Blueskyに投稿する。
    Returns: 投稿URIまたはNone（失敗時）
    """
    from atproto import Client, client_utils

    auth = load_env(AUTH_FILE)
    handle = auth.get("BLUESKY_HANDLE", "")
    password = auth.get("BLUESKY_APP_PASSWORD", "")

    if not handle or not password:
        logger.error(f"Bluesky認証情報が設定されていません: {AUTH_FILE}")
        logger.error("BLUESKY_HANDLE と BLUESKY_APP_PASSWORD を設定してください")
        return None

    client = Client()
    try:
        client.login(handle, password)
        logger.info(f"Bluesky ログイン成功: {handle}")
    except Exception as e:
        logger.error(f"Bluesky ログイン失敗: {e}")
        return None

    # テキストビルダー（URLをリッチリンクに変換）
    tb = client_utils.TextBuilder()

    # URL を除いたテキスト部分とURL部分を分離
    if url and url in text:
        before_url = text[:text.index(url)]
        after_url = text[text.index(url) + len(url):]
        if before_url:
            tb.text(before_url)
        tb.link(url, url)
        if after_url:
            tb.text(after_url)
    else:
        tb.text(text)

    # 画像添付
    image_data = None
    if image_path and Path(image_path).exists():
        try:
            img_bytes = Path(image_path).read_bytes()
            # 画像MIME type判定
            if image_path.lower().endswith(".png"):
                mime = "image/png"
            elif image_path.lower().endswith((".jpg", ".jpeg")):
                mime = "image/jpeg"
            else:
                mime = "image/png"
            upload = client.upload_blob(img_bytes)
            image_data = upload.blob
            logger.info(f"画像アップロード完了: {image_path}")
        except Exception as e:
            logger.warning(f"画像アップロード失敗（テキストのみ投稿）: {e}")

    # 投稿
    try:
        if image_data:
            from atproto import models
            embed = models.AppBskyEmbedImages.Main(
                images=[
                    models.AppBskyEmbedImages.Image(
                        image=image_data,
                        alt="サクラのイラスト",
                    )
                ]
            )
            post = client.send_post(tb, embed=embed)
        else:
            post = client.send_post(tb)
        logger.info(f"Bluesky投稿完了: {post.uri}")
        return post.uri
    except Exception as e:
        logger.error(f"Bluesky投稿失敗: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Bluesky予約投稿実行")
    parser.add_argument("--slot", type=int, required=True, choices=[1, 2, 3],
                        help="投稿スロット (1=7:30, 2=12:30, 3=21:00)")
    parser.add_argument("--dry-run", action="store_true",
                        help="実際に投稿せずログのみ表示")
    args = parser.parse_args()

    if not SCHEDULE_FILE.exists():
        logger.info("Bluesky予約データなし。スキップ。")
        return

    schedule = json.loads(SCHEDULE_FILE.read_text())
    today = datetime.now().strftime("%Y-%m-%d")

    if schedule.get("date") != today:
        logger.info(f"予約データが今日({today})のものではありません。スキップ。")
        return

    slots = schedule.get("slots", [])
    slot_data = None
    for s in slots:
        if s.get("slot") == args.slot and s.get("status") == "pending":
            slot_data = s
            break

    if not slot_data:
        logger.info(f"スロット{args.slot}の未投稿データなし。スキップ。")
        return

    tweet_text = slot_data["text"]
    image_path = slot_data.get("image")
    url = slot_data.get("url", "")
    slug = slot_data.get("slug", "")

    logger.info(f"スロット{args.slot} 投稿開始: {slug}")
    logger.info(f"テキスト:\n{tweet_text}")

    if args.dry_run:
        logger.info(f"[DRY RUN] 投稿スキップ。テキスト: {tweet_text[:50]}...")
        return

    uri = post_to_bluesky(tweet_text, image_path, url)

    if uri:
        slot_data["status"] = "posted"
        slot_data["posted_at"] = datetime.now(timezone.utc).isoformat()
        slot_data["bluesky_uri"] = uri
        SCHEDULE_FILE.write_text(json.dumps(schedule, ensure_ascii=False, indent=2))

        history = json.loads(HISTORY_FILE.read_text()) if HISTORY_FILE.exists() else {"posts": []}
        history.setdefault("posts", []).append({
            "slug": slug,
            "title": slot_data.get("title", ""),
            "posted_at": datetime.now(timezone.utc).isoformat(),
            "bluesky_uri": uri,
        })
        HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        HISTORY_FILE.write_text(json.dumps(history, ensure_ascii=False, indent=2))

        send_telegram(f"🦋 Bluesky投稿完了（スロット{args.slot}）\n{slug}\n{uri}")
        logger.info("履歴保存完了")
    else:
        slot_data["status"] = "failed"
        SCHEDULE_FILE.write_text(json.dumps(schedule, ensure_ascii=False, indent=2))
        send_telegram(f"❌ Bluesky投稿失敗（スロット{args.slot}）\n{slug}")
        logger.error("投稿失敗")


if __name__ == "__main__":
    main()
