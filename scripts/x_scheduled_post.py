#!/usr/bin/env python3
"""
X予約投稿実行スクリプト
cron（7:07, 12:13, 20:43）から呼び出され、
data/x_scheduled.json から該当スロットの投稿を実行する。

Usage:
    python3 scripts/x_scheduled_post.py --slot 1   # 7:07の投稿
    python3 scripts/x_scheduled_post.py --slot 2   # 12:13の投稿
    python3 scripts/x_scheduled_post.py --slot 3   # 20:43の投稿
"""

import os
import sys
import json
import logging
import argparse
import random
import time
from pathlib import Path
from datetime import datetime, timezone

# Playwright用ライブラリパス
_LOCAL_LIBS = Path("/tmp/locallibs/usr/lib/x86_64-linux-gnu")
if _LOCAL_LIBS.exists():
    _existing = os.environ.get("LD_LIBRARY_PATH", "")
    if str(_LOCAL_LIBS) not in _existing:
        os.environ["LD_LIBRARY_PATH"] = f"{_LOCAL_LIBS}:{_existing}"

BLOG_ROOT = Path(__file__).parent.parent.resolve()
SCHEDULE_FILE = BLOG_ROOT / "data" / "x_scheduled.json"
HISTORY_FILE = BLOG_ROOT / "data" / "x_post_history.json"
COOKIES_FILE = BLOG_ROOT / "config" / "x_cookies.json"
TELEGRAM_AUTH = Path("/mnt/c/tools/multi-agent-shogun/config/telegram_auth.env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def send_telegram(text: str):
    import requests
    env = {}
    if TELEGRAM_AUTH.exists():
        for line in TELEGRAM_AUTH.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip()
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


def post_to_x(text: str, image_path: str = None) -> bool:
    """Playwrightでx.comにツイート投稿（画像付き対応）"""
    import re as _re
    from playwright.sync_api import sync_playwright

    if not COOKIES_FILE.exists():
        logger.error(f"Cookieファイルなし: {COOKIES_FILE}")
        return False

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

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 900},
        )
        context.add_cookies(cookies)
        page = context.new_page()

        # まずホームで認証確認
        logger.info("x.comにアクセス中...")
        page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(3000)

        # URL判定
        if "/login" in page.url or "/i/flow/login" in page.url:
            logger.error("Cookie期限切れ（/loginへリダイレクト）")
            page.screenshot(path="/tmp/x_auth_fail.png")
            browser.close()
            return False
        # ランディングページ等でURL判定できない場合のログインボタン検出
        login_btn = page.locator('a[data-testid="loginButton"], a[href="/login"], [data-testid="login"]')
        if login_btn.count() > 0 and login_btn.first.is_visible():
            logger.error("Cookie期限切れ（ログインボタン検出）")
            page.screenshot(path="/tmp/x_auth_fail.png")
            browser.close()
            return False
        logger.info("Cookie認証成功")

        # 投稿ページへ遷移（複数URL試行）
        compose_urls = [
            "https://x.com/compose/tweet",
            "https://x.com/compose/post",
            "https://x.com/home",
        ]
        compose_ok = False
        for compose_url in compose_urls:
            logger.info(f"投稿ページを開く: {compose_url}")
            page.goto(compose_url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(4000)
            page.screenshot(path=f"/tmp/x_compose_nav_{compose_url.split('/')[-1]}.png")
            if "/login" not in page.url and "/i/flow/login" not in page.url:
                # ログインボタンも確認
                lb = page.locator('a[data-testid="loginButton"], a[href="/login"]')
                if lb.count() > 0 and lb.first.is_visible():
                    logger.warning(f"遷移後ログインボタン検出: {compose_url}")
                    continue
                compose_ok = True
                logger.info(f"ページ遷移成功: {page.url}")
                break
            logger.warning(f"遷移失敗（ログインページへ）: {compose_url}")

        if not compose_ok:
            logger.error("全ての投稿ページ遷移が失敗")
            browser.close()
            return False

        # ツイート入力欄を待つ（フォールバックセレクタ対応）
        tweet_selectors = [
            '[data-testid="tweetTextarea_0"]',
            '[data-testid^="tweetTextarea"]',
            'div[role="textbox"][contenteditable="true"]',
            'div[contenteditable="true"][data-text="true"]',
            'div[contenteditable="true"]',
        ]
        tweet_box = None
        for sel in tweet_selectors:
            try:
                candidate = page.locator(sel).first
                candidate.wait_for(state="visible", timeout=5000)
                tweet_box = candidate
                logger.info(f"ツイート入力欄セレクタヒット: {sel}")
                break
            except Exception:
                logger.warning(f"セレクタ不発: {sel}")
                continue

        if tweet_box is None:
            page.screenshot(path="/tmp/x_compose_selector_fail.png")
            logger.error("ツイート入力欄セレクタが全て失敗。/tmp/x_compose_selector_fail.png を確認")
            browser.close()
            return False
        page.wait_for_timeout(1000)

        # テキスト入力（fill使用。intent URL廃止のため手動入力）
        logger.info("テキスト入力中...")
        tweet_box.click()
        page.wait_for_timeout(500)
        tweet_box.fill(text)
        page.wait_for_timeout(1000)

        # 画像添付
        if image_path and Path(image_path).exists():
            logger.info(f"画像添付中: {image_path}")
            file_input = page.locator('input[data-testid="fileInput"]').first
            if file_input.count() > 0:
                file_input.set_input_files(image_path)
                page.wait_for_timeout(3000)
                logger.info("画像添付完了")
            else:
                logger.warning("画像添付ボタンが見つかりません")

        # デバッグスクリーンショット
        page.screenshot(path="/tmp/x_compose_before.png")

        # 投稿ボタン（フォールバックセレクタ対応）
        logger.info("投稿ボタンをクリック...")
        post_btn_selectors = [
            '[data-testid="tweetButton"]',
            '[data-testid="tweetButtonInline"]',
            'button[data-testid$="tweetButton"]',
            'button:has-text("ポスト")',
            'button:has-text("Post")',
        ]
        post_btn = None
        for sel in post_btn_selectors:
            try:
                candidate = page.locator(sel).first
                if candidate.count() > 0 and candidate.is_visible():
                    post_btn = candidate
                    logger.info(f"投稿ボタンセレクタヒット: {sel}")
                    break
            except Exception:
                continue
        if post_btn is None:
            page.screenshot(path="/tmp/x_compose_postbtn_fail.png")
            logger.error("投稿ボタンセレクタが全て失敗。/tmp/x_compose_postbtn_fail.png を確認")
            browser.close()
            return False
        post_btn.evaluate("el => el.click()")
        page.wait_for_timeout(5000)

        # Got itダイアログ処理
        got_it_btn = page.locator('button:has-text("Got it"), button:has-text("了解")')
        if got_it_btn.count() > 0 and got_it_btn.first.is_visible():
            got_it_btn.first.click()
            page.wait_for_timeout(2000)

        logger.info("投稿完了")
        browser.close()
        return True


def main():
    parser = argparse.ArgumentParser(description="X予約投稿実行")
    parser.add_argument("--slot", type=int, required=True, choices=[1, 2, 3],
                        help="投稿スロット (1=朝, 2=昼, 3=夜)")
    parser.add_argument("--no-delay", action="store_true",
                        help="ランダム遅延をスキップ（テスト用）")
    args = parser.parse_args()

    # BOT認定回避のためランダム遅延（0〜900秒 = ±15分）
    if not args.no_delay:
        delay = random.randint(0, 900)
        logger.info(f"ランダム遅延: {delay}秒 ({delay // 60}分{delay % 60}秒)")
        time.sleep(delay)
        logger.info(f"遅延終了。実際の投稿時刻: {datetime.now().strftime('%H:%M:%S')}")

    if not SCHEDULE_FILE.exists():
        logger.info("予約データなし。スキップ。")
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
    slug = slot_data.get("slug", "")

    logger.info(f"スロット{args.slot} 投稿開始: {slug}")
    logger.info(f"テキスト:\n{tweet_text}")

    success = post_to_x(tweet_text, image_path)

    if success:
        # ステータス更新
        slot_data["status"] = "posted"
        slot_data["posted_at"] = datetime.now(timezone.utc).isoformat()
        SCHEDULE_FILE.write_text(json.dumps(schedule, ensure_ascii=False, indent=2))

        # 履歴追加
        history = json.loads(HISTORY_FILE.read_text()) if HISTORY_FILE.exists() else {"posts": []}
        history.setdefault("posts", []).append({
            "slug": slug,
            "title": slot_data.get("title", ""),
            "posted_at": datetime.now(timezone.utc).isoformat(),
            "method": "shogun_sakura",
        })
        HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        HISTORY_FILE.write_text(json.dumps(history, ensure_ascii=False, indent=2))

        send_telegram(f"🌸 X投稿完了（スロット{args.slot}）\n{slug}")
        logger.info("履歴保存完了")
    else:
        slot_data["status"] = "failed"
        SCHEDULE_FILE.write_text(json.dumps(schedule, ensure_ascii=False, indent=2))
        send_telegram(f"❌ X投稿失敗（スロット{args.slot}）\n{slug}")
        logger.error("投稿失敗")


if __name__ == "__main__":
    main()
