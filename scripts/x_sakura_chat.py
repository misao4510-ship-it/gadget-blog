#!/usr/bin/env python3
"""
サクラ雑談ツイートスクリプト (cmd_179 / cmd_171 施策⑥)

記事紹介以外の「サクラキャラとしての雑談ツイート」を投稿する。
data/x_chat_templates.json から未使用（または7日以上経過）のテンプレートを
ランダム選択して投稿。

Usage:
    python3 scripts/x_sakura_chat.py              # 通常投稿
    python3 scripts/x_sakura_chat.py --dry-run    # ログのみ（投稿しない）
    python3 scripts/x_sakura_chat.py --category 豆知識  # カテゴリ指定
    python3 scripts/x_sakura_chat.py --list       # テンプレート一覧表示
"""

import argparse
import json
import logging
import random
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

BLOG_ROOT = Path(__file__).parent.parent.resolve()
TEMPLATES_FILE = BLOG_ROOT / "data" / "x_chat_templates.json"
TELEGRAM_AUTH = Path("/mnt/c/tools/multi-agent-shogun/config/telegram_auth.env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# 7日以上経過したテンプレートは再利用可能とみなす
REUSE_DAYS = 7


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


def load_templates() -> dict:
    if not TEMPLATES_FILE.exists():
        logger.error(f"テンプレートファイルが見つかりません: {TEMPLATES_FILE}")
        sys.exit(1)
    return json.loads(TEMPLATES_FILE.read_text(encoding="utf-8"))


def save_templates(data: dict):
    TEMPLATES_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def is_available(tmpl: dict) -> bool:
    """テンプレートが使用可能か判定"""
    if not tmpl.get("used", False):
        return True
    last_used = tmpl.get("last_used")
    if not last_used:
        return True
    try:
        last_dt = datetime.fromisoformat(last_used)
        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        return (now - last_dt) >= timedelta(days=REUSE_DAYS)
    except Exception:
        return True


def pick_template(templates: list, category: str = None) -> dict:
    """
    未使用（または7日以上経過）のテンプレートからランダム選択。
    全て使用済みの場合は最も古いものを選択。
    """
    candidates = [t for t in templates if is_available(t)]
    if category:
        cat_candidates = [t for t in candidates if t.get("category") == category]
        if cat_candidates:
            candidates = cat_candidates
        else:
            logger.warning(f"カテゴリ '{category}' に利用可能なテンプレートがありません。全テンプレートから選択します。")

    if candidates:
        return random.choice(candidates)

    # 全て使用済み → 最も古いものを選択
    logger.info("全テンプレート使用済み。最も古いものを再利用します。")
    fallback = templates
    if category:
        cat_fallback = [t for t in templates if t.get("category") == category]
        if cat_fallback:
            fallback = cat_fallback

    def last_used_key(t):
        lu = t.get("last_used")
        if not lu:
            return "0000-01-01T00:00:00+00:00"
        return lu

    return min(fallback, key=last_used_key)


def mark_used(data: dict, tmpl_id: int):
    """テンプレートを使用済みとしてマーク"""
    now_str = datetime.now(timezone.utc).isoformat()
    for t in data["templates"]:
        if t["id"] == tmpl_id:
            t["used"] = True
            t["last_used"] = now_str
            break


def main():
    parser = argparse.ArgumentParser(description="サクラ雑談ツイート投稿スクリプト")
    parser.add_argument("--dry-run", action="store_true", help="実際に投稿せずログのみ表示")
    parser.add_argument("--category", type=str, help="指定カテゴリから選択 (豆知識/季節ネタ/テック小話/日常サクラ/おすすめ小ネタ/防災・備蓄)")
    parser.add_argument("--list", action="store_true", help="テンプレート一覧を表示して終了")
    args = parser.parse_args()

    data = load_templates()
    templates = data.get("templates", [])

    if args.list:
        for t in templates:
            avail = "✓" if is_available(t) else "✗"
            print(f"[{avail}] id={t['id']} [{t['category']}] {t['text'][:60]}...")
        return

    tmpl = pick_template(templates, args.category)
    tweet_text = tmpl["text"]
    tmpl_id = tmpl["id"]

    logger.info(f"選択テンプレート: id={tmpl_id} [{tmpl.get('category')}]")
    logger.info(f"ツイート内容:\n{tweet_text}")

    if args.dry_run:
        logger.info("[DRY RUN] 投稿スキップ。")
        return

    # x_post_playwright.py の関数を直接使用
    try:
        sys.path.insert(0, str(BLOG_ROOT / "scripts"))
        from x_post_playwright import post_to_x_playwright
        post_url = post_to_x_playwright(tweet_text)
        logger.info(f"投稿完了: {post_url}")

        # 使用済みマーク + 保存
        mark_used(data, tmpl_id)
        save_templates(data)
        logger.info("テンプレート使用状態を更新しました。")

        send_telegram(f"🌸 サクラ雑談ツイート投稿完了\n[{tmpl.get('category')}]\n{tweet_text[:80]}...")
        logger.info("Telegram通知済み。")
    except Exception as e:
        logger.error(f"投稿失敗: {e}")
        send_telegram(f"❌ サクラ雑談ツイート失敗\n{e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
