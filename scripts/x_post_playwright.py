#!/usr/bin/env python3
"""
X (Twitter) Playwright投稿スクリプト
Cookie認証でブラウザ操作によりツイートを投稿する（API課金不要）

Usage:
    python3 scripts/x_post_playwright.py --text "ツイート内容"
    python3 scripts/x_post_playwright.py --text "ツイート内容" --dry-run
    python3 scripts/x_post_playwright.py --auto                # ブログ記事ランダム投稿
    python3 scripts/x_post_playwright.py --auto --dry-run
"""

import os
import sys
import json
import random
import logging
import argparse
import yaml
import re
from pathlib import Path
from datetime import datetime, timezone

# Playwright用システムライブラリのパスを設定
_LOCAL_LIBS = Path("/tmp/locallibs/usr/lib/x86_64-linux-gnu")
if _LOCAL_LIBS.exists():
    _existing = os.environ.get("LD_LIBRARY_PATH", "")
    if str(_LOCAL_LIBS) not in _existing:
        os.environ["LD_LIBRARY_PATH"] = f"{_LOCAL_LIBS}:{_existing}"

# パス設定
BLOG_ROOT = Path(__file__).parent.parent.resolve()
CONFIG_FILE = BLOG_ROOT / "config" / "x_auto_post.yaml"
COOKIES_FILE = BLOG_ROOT / "config" / "x_cookies.json"
HISTORY_FILE = BLOG_ROOT / "data" / "x_post_history.json"
POSTS_DIR = BLOG_ROOT / "src" / "content" / "posts"

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


# ===== 設定・履歴 =====

def load_config() -> dict:
    if not CONFIG_FILE.exists():
        raise FileNotFoundError(f"設定ファイルが見つかりません: {CONFIG_FILE}")
    with open(CONFIG_FILE, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_history() -> dict:
    if not HISTORY_FILE.exists():
        return {"posts": []}
    with open(HISTORY_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_history(history: dict):
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


# ===== 記事選択 =====

def parse_frontmatter(md_file: Path) -> dict | None:
    content = md_file.read_text(encoding="utf-8")
    match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return None
    try:
        meta = yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        return None
    if not meta or meta.get("draft", False):
        return None
    meta["slug"] = md_file.stem
    return meta


def load_articles() -> list[dict]:
    articles = []
    for md_file in sorted(POSTS_DIR.glob("*.md")):
        meta = parse_frontmatter(md_file)
        if meta:
            articles.append(meta)
    logger.info(f"記事読み込み完了: {len(articles)}件")
    return articles


def get_category_hashtags(meta: dict, config: dict) -> str:
    hashtags_map = config.get("category_hashtags", {})
    default = hashtags_map.get("default", "#ガジェット #レビュー")
    tags_set = set()
    for key in [meta.get("category", ""), meta.get("subcategory", ""), meta.get("type", "")]:
        if key and key in hashtags_map:
            for tag in hashtags_map[key].split():
                tags_set.add(tag)
    return " ".join(sorted(tags_set)) if tags_set else default


def build_post_text(article: dict, config: dict) -> str:
    title = article.get("title", "記事タイトル")
    slug = article["slug"]
    base_url = config["post_format"]["base_url"].rstrip("/")
    url = f"{base_url}/{slug}/"
    category_tags = get_category_hashtags(article, config)
    return f"📝 {title}\n{url}\n{category_tags}"


def select_article(articles: list[dict], history: dict, config: dict) -> dict | None:
    exclude_count = config.get("recent_exclude_count", 10)
    exclude_slugs = set(config.get("exclude_slugs", []))
    exclude_categories = set(config.get("exclude_categories", []))
    recent_slugs = set(p["slug"] for p in history.get("posts", [])[-exclude_count:])

    candidates = [
        a for a in articles
        if a["slug"] not in exclude_slugs
        and a["slug"] not in recent_slugs
        and a.get("category", "") not in exclude_categories
        and a.get("subcategory", "") not in exclude_categories
    ]

    if not candidates:
        logger.warning("候補記事なし（全記事投稿済み）。履歴をリセットして再選択します。")
        candidates = [a for a in articles if a["slug"] not in exclude_slugs]

    if not candidates:
        logger.error("投稿可能な記事がありません")
        return None

    return random.choice(candidates)


# ===== Playwright投稿 =====

def post_to_x_playwright(text: str) -> str:
    """Playwrightでx.comにCookieログインしてツイートを投稿する

    Returns:
        投稿後のページURL
    """
    from playwright.sync_api import sync_playwright

    if not COOKIES_FILE.exists():
        raise FileNotFoundError(
            f"Cookieファイルが見つかりません: {COOKIES_FILE}\n"
            "x.comにブラウザでログイン後、Cookie EditorでCookieをJSON形式でエクスポートしてください。"
        )

    cookies_raw = json.loads(COOKIES_FILE.read_text(encoding="utf-8"))

    # Playwright用にCookieを整形
    cookies = []
    for c in cookies_raw:
        cookie = {
            "name": c["name"],
            "value": c["value"],
            "domain": c["domain"],
            "path": c.get("path", "/"),
        }
        # sameSite変換
        ss = c.get("sameSite")
        if ss == "no_restriction":
            cookie["sameSite"] = "None"
        elif ss in ("Strict", "Lax", "None"):
            cookie["sameSite"] = ss
        else:
            cookie["sameSite"] = "Lax"
        # secure
        cookie["secure"] = c.get("secure", False)
        cookie["httpOnly"] = c.get("httpOnly", False)
        cookies.append(cookie)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 900},
        )

        # Cookie設定
        context.add_cookies(cookies)
        page = context.new_page()

        # まずホームで認証確認
        logger.info("x.comにアクセス中...")
        page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(3000)

        if "/login" in page.url or "/i/flow/login" in page.url:
            browser.close()
            raise RuntimeError(
                "Cookie期限切れ: config/x_cookies.jsonを更新してください\n"
                "x.comにブラウザでログイン後、Cookie EditorでCookieをJSON形式でエクスポートして保存"
            )
        logger.info("Cookie認証成功")

        # 投稿ダイアログを開く（URLが折り返されない広い入力欄）
        page.goto("https://x.com/compose/post", wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(3000)

        # ツイート入力欄
        logger.info("ツイート入力中...")
        tweet_box = page.locator('[data-testid="tweetTextarea_0"]').first
        tweet_box.wait_for(state="visible", timeout=10000)
        tweet_box.click()
        page.wait_for_timeout(500)

        import re as _re
        lines = text.split("\n")
        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                if i < len(lines) - 1:
                    page.keyboard.press("Enter")
                continue
            if _re.match(r'^https?://', stripped):
                page.evaluate('(url) => { document.execCommand("insertText", false, url); }', stripped)
                page.wait_for_timeout(1500)
            else:
                page.keyboard.type(stripped, delay=3)
            if i < len(lines) - 1:
                page.keyboard.press("Enter")
            page.wait_for_timeout(300)
        page.wait_for_timeout(1500)

        # デバッグ用スクリーンショット
        page.screenshot(path="/tmp/x_before_post.png")
        logger.info("スクリーンショット保存: /tmp/x_before_post.png")

        # 投稿ボタン（compose/postでは tweetButton）
        logger.info("投稿ボタンをクリック...")
        post_btn = page.locator('[data-testid="tweetButton"]')
        if post_btn.count() == 0:
            post_btn = page.locator('[data-testid="tweetButtonInline"]')
        post_btn.evaluate("el => el.click()")
        page.wait_for_timeout(5000)

        # graduated-access / "Got it" ダイアログ処理
        got_it_btn = page.locator('button:has-text("Got it"), button:has-text("了解")')
        if got_it_btn.count() > 0 and got_it_btn.first.is_visible():
            logger.info("'Got it'ダイアログを閉じます")
            got_it_btn.first.click()
            page.wait_for_timeout(2000)

        # 投稿後スクリーンショット
        page.screenshot(path="/tmp/x_after_post.png")
        logger.info("投稿後スクリーンショット: /tmp/x_after_post.png")

        # graduated-accessページが出た場合は通過を試みる
        final_url = page.url
        if "graduated-access" in final_url:
            logger.warning("graduated-accessページが表示されました（アカウント制限の可能性）")
            # プロフィールページで投稿を確認
            page.goto("https://x.com/JINSEI_KAITEKI", wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(5000)
            page.screenshot(path="/tmp/x_profile_check.png")
            final_url = page.url
            logger.info(f"プロフィール確認: {final_url}")

        logger.info(f"投稿完了: {final_url}")
        browser.close()
        return final_url


# ===== メイン =====

def main():
    parser = argparse.ArgumentParser(description="X Playwright投稿スクリプト")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--text", help="投稿するテキスト")
    group.add_argument("--auto", action="store_true", help="ブログ記事をランダムに自動投稿")
    parser.add_argument("--dry-run", action="store_true", help="投稿せずにテキストのみ表示")
    args = parser.parse_args()

    if args.text:
        tweet_text = args.text
        logger.info(f"投稿テキスト:\n{tweet_text}")
        if args.dry_run:
            logger.info("[DRY RUN] 投稿をスキップしました")
            return
        post_to_x_playwright(tweet_text)
        return

    # --auto モード
    config = load_config()
    history = load_history()
    articles = load_articles()
    if not articles:
        logger.error("記事が見つかりません")
        sys.exit(1)

    article = select_article(articles, history, config)
    if article is None:
        sys.exit(1)

    tweet_text = build_post_text(article, config)
    logger.info(f"選択記事: {article['slug']}")
    logger.info(f"投稿テキスト:\n{tweet_text}")

    if args.dry_run:
        logger.info("[DRY RUN] 投稿をスキップしました")
        return

    post_to_x_playwright(tweet_text)

    # 履歴保存
    history.setdefault("posts", []).append({
        "slug": article["slug"],
        "title": article.get("title", ""),
        "posted_at": datetime.now(timezone.utc).isoformat(),
        "method": "playwright",
    })
    save_history(history)
    logger.info(f"履歴保存完了: {HISTORY_FILE}")


if __name__ == "__main__":
    main()
