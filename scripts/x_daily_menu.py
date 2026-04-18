#!/usr/bin/env python3
"""
X投稿 朝メニュー送信スクリプト
毎朝6:00にcronで実行。未投稿の記事一覧をTelegramに送信し、
殿が番号で選択 → 将軍が処理する。

Usage:
    python3 scripts/x_daily_menu.py
"""

import json
import re
import sys
import yaml
from pathlib import Path

BLOG_ROOT = Path(__file__).parent.parent.resolve()
POSTS_DIR = BLOG_ROOT / "src" / "content" / "posts"
HISTORY_FILE = BLOG_ROOT / "data" / "x_post_history.json"
CONFIG_FILE = BLOG_ROOT / "config" / "x_auto_post.yaml"
TELEGRAM_AUTH = Path("/mnt/c/tools/multi-agent-shogun/config/telegram_auth.env")

# 直近N件は除外
RECENT_EXCLUDE = 10


def load_telegram_auth() -> tuple[str, str]:
    env = {}
    if TELEGRAM_AUTH.exists():
        for line in TELEGRAM_AUTH.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip()
    return env.get("TELEGRAM_BOT_TOKEN", ""), env.get("TELEGRAM_CHAT_ID", "")


def load_history() -> dict[str, int]:
    """各slugの投稿回数を返す"""
    if not HISTORY_FILE.exists():
        return {}
    data = json.loads(HISTORY_FILE.read_text())
    counts = {}
    for p in data.get("posts", []):
        slug = p.get("slug", "")
        counts[slug] = counts.get(slug, 0) + 1
    return counts


def load_articles() -> list[dict]:
    """全記事を返す（draft除外のみ、投稿済みも含む）"""
    post_counts = load_history()
    articles = []
    for md_file in sorted(POSTS_DIR.glob("*.md")):
        content = md_file.read_text(encoding="utf-8")
        match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
        if not match:
            continue
        try:
            meta = yaml.safe_load(match.group(1))
        except yaml.YAMLError:
            continue
        if not meta or meta.get("draft", False):
            continue
        slug = md_file.stem
        meta["slug"] = slug
        meta["post_count"] = post_counts.get(slug, 0)
        articles.append(meta)
    return articles


def send_telegram(text: str):
    import requests
    bot_token, chat_id = load_telegram_auth()
    if not bot_token or not chat_id:
        print("Telegram認証情報なし", file=sys.stderr)
        sys.exit(1)
    resp = requests.post(
        f"https://api.telegram.org/bot{bot_token}/sendMessage",
        json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
        timeout=30,
    )
    resp.raise_for_status()
    print("Telegram送信完了")


def main():
    articles = load_articles()
    if not articles:
        send_telegram("📝 投稿候補の記事がありません（全記事投稿済み）")
        return

    lines = ["🌸 <b>今日のX投稿メニュー</b>", "投稿したい記事の番号を3つ送ってください", "（例: 5, 12, 28）", ""]
    for i, a in enumerate(articles, 1):
        title = a.get("title", a["slug"])
        # タイトルが長い場合は短縮
        if len(title) > 35:
            title = title[:33] + "…"
        count = a.get("post_count", 0)
        mark = f"({count}回)" if count > 0 else "🆕"
        lines.append(f"{i}. {title} {mark}")

    lines.append(f"\n全{len(articles)}件 🆕=未投稿")
    text = "\n".join(lines)

    # 記事一覧をYAMLにも保存（将軍が番号→slug変換に使う）
    menu_file = BLOG_ROOT / "data" / "x_daily_menu.json"
    menu_file.parent.mkdir(parents=True, exist_ok=True)
    menu_data = [{"index": i + 1, "slug": a["slug"], "title": a.get("title", "")} for i, a in enumerate(articles)]
    menu_file.write_text(json.dumps(menu_data, ensure_ascii=False, indent=2))
    print(f"メニュー保存: {menu_file}")

    send_telegram(text)


if __name__ == "__main__":
    main()
