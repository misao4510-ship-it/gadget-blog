#!/usr/bin/env python3
"""
Misskey.io 自動投稿スクリプト

X投稿スケジュール(x_scheduled.json)をもとにMisskey.ioに自動投稿する。
投稿時刻はXより46分後。

Usage:
    python3 scripts/misskey_post.py --slot 1   # 7:53の投稿
    python3 scripts/misskey_post.py --slot 2   # 12:59の投稿
    python3 scripts/misskey_post.py --slot 3   # 21:29の投稿
    python3 scripts/misskey_post.py --dry-run --slot 1
"""

import os
import sys
import json
import time
import random
import logging
import argparse
from pathlib import Path
from datetime import datetime, timezone

BLOG_ROOT = Path(__file__).parent.parent.resolve()
X_SCHEDULE = BLOG_ROOT / "data" / "x_scheduled.json"
HISTORY_FILE = BLOG_ROOT / "data" / "misskey_post_history.json"
AUTH_FILE = BLOG_ROOT / "config" / "misskey_auth.env"
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


def post_to_misskey(text: str, image_path: str = None) -> str | None:
    """Misskey.ioに投稿する。Returns: ノートIDまたはNone"""
    import requests

    auth = load_env(AUTH_FILE)
    instance = auth.get("MISSKEY_INSTANCE", "https://misskey.io")
    token = auth.get("MISSKEY_TOKEN", "")

    if not token:
        logger.error(f"Misskey認証情報が設定されていません: {AUTH_FILE}")
        return None

    # 画像アップロード
    file_id = None
    if image_path and Path(image_path).exists():
        try:
            with open(image_path, "rb") as f:
                resp = requests.post(
                    f"{instance}/api/drive/files/create",
                    data={"i": token},
                    files={"file": (Path(image_path).name, f)},
                    timeout=60,
                )
            if resp.status_code == 200:
                file_id = resp.json()["id"]
                logger.info(f"画像アップロード完了: {image_path}")
            else:
                logger.warning(f"画像アップロード失敗: {resp.text}")
        except Exception as e:
            logger.warning(f"画像アップロード失敗（テキストのみ投稿）: {e}")

    # ノート投稿
    try:
        payload = {
            "i": token,
            "text": text,
            "visibility": "public",
        }
        if file_id:
            payload["fileIds"] = [file_id]

        resp = requests.post(f"{instance}/api/notes/create", json=payload, timeout=30)
        if resp.status_code == 200:
            note_id = resp.json()["createdNote"]["id"]
            logger.info(f"Misskey投稿完了: {instance}/notes/{note_id}")
            return note_id
        else:
            logger.error(f"Misskey投稿失敗: {resp.text}")
            return None
    except Exception as e:
        logger.error(f"Misskey投稿失敗: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Misskey予約投稿実行")
    parser.add_argument("--slot", type=int, required=True, choices=[1, 2, 3],
                        help="投稿スロット (1=朝, 2=昼, 3=夜)")
    parser.add_argument("--dry-run", action="store_true",
                        help="実際に投稿せずログのみ表示")
    parser.add_argument("--no-delay", action="store_true",
                        help="ランダム遅延をスキップ（テスト用）")
    args = parser.parse_args()

    # BOT認定回避のためランダム遅延（0〜900秒 = ±15分）
    if not args.no_delay and not args.dry_run:
        delay = random.randint(0, 900)
        logger.info(f"ランダム遅延: {delay}秒 ({delay // 60}分{delay % 60}秒)")
        time.sleep(delay)
        logger.info(f"遅延終了。実際の投稿時刻: {datetime.now().strftime('%H:%M:%S')}")

    if not X_SCHEDULE.exists():
        logger.info("X予約データなし。スキップ。")
        return

    schedule = json.loads(X_SCHEDULE.read_text())
    today = datetime.now().strftime("%Y-%m-%d")

    if schedule.get("date") != today:
        logger.info(f"予約データが今日({today})のものではありません。スキップ。")
        return

    slots = schedule.get("slots", [])
    slot_data = None
    for s in slots:
        if s.get("slot") == args.slot:
            slot_data = s
            break

    if not slot_data:
        logger.info(f"スロット{args.slot}のデータなし。スキップ。")
        return

    tweet_text = slot_data["text"]
    image_path = slot_data.get("image")
    slug = slot_data.get("slug", "")

    logger.info(f"スロット{args.slot} 投稿開始: {slug}")

    if args.dry_run:
        logger.info(f"[DRY RUN] 投稿スキップ。テキスト: {tweet_text[:50]}...")
        return

    note_id = post_to_misskey(tweet_text, image_path)

    if note_id:
        history = json.loads(HISTORY_FILE.read_text()) if HISTORY_FILE.exists() else {"posts": []}
        history.setdefault("posts", []).append({
            "slug": slug,
            "title": slot_data.get("title", ""),
            "posted_at": datetime.now(timezone.utc).isoformat(),
            "note_id": note_id,
        })
        HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        HISTORY_FILE.write_text(json.dumps(history, ensure_ascii=False, indent=2))

        send_telegram(f"📝 Misskey投稿完了（スロット{args.slot}）\n{slug}\nhttps://misskey.io/notes/{note_id}")
        logger.info("履歴保存完了")
    else:
        send_telegram(f"❌ Misskey投稿失敗（スロット{args.slot}）\n{slug}")
        logger.error("投稿失敗")


if __name__ == "__main__":
    main()
