#!/usr/bin/env python3
"""
Xガジェット系ツイート自動リプライスクリプト (cmd_203 / Xリプライ戦略)

ガジェット系キーワードを含むツイートを検索し、サクラ口調でリプライを送信する。
様子見フェーズのため1回1〜2件、1日3〜5件程度。

Usage:
    python3 scripts/x_sakura_reply.py              # 通常実行
    python3 scripts/x_sakura_reply.py --dry-run    # ログのみ（投稿しない）
    python3 scripts/x_sakura_reply.py --no-delay   # 遅延なし（テスト用）
"""

import argparse
import json
import logging
import os
import random
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Playwright用ライブラリパス
_LOCAL_LIBS = Path("/tmp/locallibs/usr/lib/x86_64-linux-gnu")
if _LOCAL_LIBS.exists():
    _existing = os.environ.get("LD_LIBRARY_PATH", "")
    if str(_LOCAL_LIBS) not in _existing:
        os.environ["LD_LIBRARY_PATH"] = f"{_LOCAL_LIBS}:{_existing}"

BLOG_ROOT = Path(__file__).parent.parent.resolve()
REPLIED_FILE = BLOG_ROOT / "data" / "x_replied.json"
COOKIES_FILE = BLOG_ROOT / "config" / "x_cookies.json"
TELEGRAM_AUTH = Path("/mnt/c/tools/multi-agent-shogun/config/telegram_auth.env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# 検索キーワードリスト（ランダムで1つ選択）
SEARCH_KEYWORDS = [
    "充電器",
    "イヤホン",
    "モニターアーム",
    "USB-C",
    "ワイヤレスイヤホン",
    "ガジェット レビュー",
    "買った 充電",
]

# サクラ口調リプライテンプレート
# {keyword} プレースホルダーはキーワードに置換
REPLY_TEMPLATES = [
    "🌸 わぁ、{keyword}に興味があるんですね！サクラもよく調べてますよ✨ よかったらブログも見てみてくださいね♪",
    "🌸 {keyword}、気になりますよね！サクラのブログでもレビューしてるので参考になれば嬉しいです✨",
    "🌸 それすごく良さそうですね！サクラも愛用してますよ〜♪ ガジェット好きさんと繋がれて嬉しいです✨",
    "🌸 わかります！{keyword}はコスパも大事ですよね✨ サクラもいろいろ比較してみました♪",
    "🌸 {keyword}って本当に便利ですよね！サクラのブログでも詳しく紹介してます✨ ぜひ見てみてくださいね！",
    "🌸 {keyword}選び、迷いますよね〜！サクラも実際に使って比較してみましたよ✨ 参考になれば嬉しいです♪",
]


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


def load_replied_ids() -> list:
    """既リプライ済みツイートIDを読み込む"""
    if not REPLIED_FILE.exists():
        return []
    try:
        data = json.loads(REPLIED_FILE.read_text(encoding="utf-8"))
        return data.get("replied_ids", [])
    except Exception as e:
        logger.warning(f"x_replied.json読み込み失敗: {e}")
        return []


def save_replied_id(tweet_id: str):
    """リプライ済みIDを保存"""
    replied_ids = load_replied_ids()
    if tweet_id not in replied_ids:
        replied_ids.append(tweet_id)
    data = {"replied_ids": replied_ids}
    REPLIED_FILE.parent.mkdir(parents=True, exist_ok=True)
    REPLIED_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def generate_reply_text(keyword: str) -> str:
    """サクラ口調のリプライ文を生成（ランダム選択）"""
    template = random.choice(REPLY_TEMPLATES)
    return template.format(keyword=keyword)


def search_and_reply(keyword: str, replied_ids: list, dry_run: bool = False, no_delay: bool = False) -> list:
    """
    指定キーワードでXを検索し、未リプライのツイートに1〜2件リプライ送信。
    送信済みのツイートIDリストを返す。
    """
    from playwright.sync_api import sync_playwright

    if not COOKIES_FILE.exists():
        logger.error(f"Cookieファイルなし: {COOKIES_FILE}")
        return []

    cookies_raw = json.loads(COOKIES_FILE.read_text())
    cookies = []
    for c in cookies_raw:
        cookie = {
            "name": c["name"], "value": c["value"],
            "domain": c["domain"], "path": c.get("path", "/"),
        }
        ss = c.get("sameSite")
        if ss == "no_restriction":
            cookie["sameSite"] = "None"
        elif ss in ("Strict", "Lax", "None"):
            cookie["sameSite"] = ss
        else:
            cookie["sameSite"] = "Lax"
        cookie["secure"] = c.get("secure", False)
        cookie["httpOnly"] = c.get("httpOnly", False)
        cookies.append(cookie)

    sent_ids = []
    reply_count = random.randint(1, 2)
    logger.info(f"キーワード「{keyword}」で検索。目標リプライ数: {reply_count}件")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 900},
        )
        context.add_cookies(cookies)
        page = context.new_page()

        # 認証確認
        logger.info("x.comにアクセス中...")
        page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(3000)

        if "/login" in page.url or "/i/flow/login" in page.url:
            logger.error("Cookie期限切れ")
            browser.close()
            return []
        logger.info("Cookie認証成功")

        # キーワード検索
        import urllib.parse
        search_url = f"https://x.com/search?q={urllib.parse.quote(keyword)}&src=typed_query&f=live"
        logger.info(f"検索URL: {search_url}")
        page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(5000)

        # ツイートを収集
        tweet_articles = page.locator('article[data-testid="tweet"]').all()
        logger.info(f"検索結果: {len(tweet_articles)}件のツイート")

        replied_this_run = 0
        for article in tweet_articles:
            if replied_this_run >= reply_count:
                break

            # ツイートIDを取得（リンクから）
            tweet_id = None
            try:
                links = article.locator('a[href*="/status/"]').all()
                for link in links:
                    href = link.get_attribute("href")
                    if href:
                        m = re.search(r"/status/(\d+)", href)
                        if m:
                            tweet_id = m.group(1)
                            break
            except Exception as e:
                logger.debug(f"ツイートID取得失敗: {e}")
                continue

            if not tweet_id:
                continue

            # 既リプライ済みチェック
            if tweet_id in replied_ids or tweet_id in sent_ids:
                logger.debug(f"リプライ済みスキップ: {tweet_id}")
                continue

            # 自分のツイートは除外（自分のスクリーンネーム確認は省略、IDが一致しなければOK）
            reply_text = generate_reply_text(keyword)
            logger.info(f"リプライ対象: tweet_id={tweet_id}")
            logger.info(f"リプライ文:\n{reply_text}")

            if dry_run:
                logger.info("[DRY RUN] リプライスキップ")
                sent_ids.append(tweet_id)
                replied_this_run += 1
                continue

            # ランダム遅延
            if not no_delay:
                delay = random.randint(0, 900)
                logger.info(f"ランダム遅延: {delay}秒 ({delay // 60}分{delay % 60}秒)")
                time.sleep(delay)

            # リプライUI操作
            try:
                reply_btn = article.locator('[data-testid="reply"]').first
                if reply_btn.count() == 0:
                    logger.warning(f"リプライボタンが見つかりません: {tweet_id}")
                    continue
                reply_btn.click()
                page.wait_for_timeout(3000)

                # リプライ入力欄
                reply_box = page.locator('[data-testid="tweetTextarea_0"]').last
                reply_box.wait_for(state="visible", timeout=10000)
                reply_box.click()
                reply_box.fill(reply_text)
                page.wait_for_timeout(1000)

                # 送信ボタン
                post_btn = page.locator('[data-testid="tweetButton"]').last
                if post_btn.count() == 0:
                    post_btn = page.locator('[data-testid="tweetButtonInline"]').last
                post_btn.evaluate("el => el.click()")
                page.wait_for_timeout(5000)

                logger.info(f"リプライ送信完了: {tweet_id}")
                sent_ids.append(tweet_id)
                save_replied_id(tweet_id)
                replied_this_run += 1

            except Exception as e:
                logger.error(f"リプライ送信失敗 ({tweet_id}): {e}")
                continue

        browser.close()

    return sent_ids


def main():
    parser = argparse.ArgumentParser(description="Xガジェット系ツイート自動リプライスクリプト")
    parser.add_argument("--dry-run", action="store_true", help="実際にリプライせずログのみ表示")
    parser.add_argument("--no-delay", action="store_true", help="ランダム遅延をスキップ（テスト用）")
    args = parser.parse_args()

    # 既リプライ済みID読み込み
    replied_ids = load_replied_ids()
    logger.info(f"既リプライ済みID数: {len(replied_ids)}")

    # キーワードをランダムで1つ選択
    keyword = random.choice(SEARCH_KEYWORDS)
    logger.info(f"選択キーワード: {keyword}")

    # 検索＆リプライ
    sent_ids = search_and_reply(keyword, replied_ids, dry_run=args.dry_run, no_delay=args.no_delay)

    if sent_ids:
        mode = "[DRY RUN] " if args.dry_run else ""
        send_telegram(
            f"🌸 {mode}サクラXリプライ完了\n"
            f"キーワード: {keyword}\n"
            f"送信数: {len(sent_ids)}件"
        )
        logger.info(f"完了。リプライ送信: {len(sent_ids)}件")
    else:
        logger.info("リプライ送信なし（未リプライのツイートが見つからなかった可能性あり）")


if __name__ == "__main__":
    main()
