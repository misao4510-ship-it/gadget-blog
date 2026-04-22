#!/usr/bin/env python3
"""
X自動フォロースクリプト (cmd_204 / Xフォロワー獲得戦略)

ガジェット/テック系キーワードでアカウントを検索し、自動フォローする。
1回5〜10件、1日上限10件でBOT判定回避。

Usage:
    python3 scripts/x_auto_follow.py              # 通常実行
    python3 scripts/x_auto_follow.py --dry-run    # ログのみ（フォローしない）
    python3 scripts/x_auto_follow.py --no-delay   # 遅延なし（テスト用）
"""

import argparse
import json
import logging
import os
import random
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
FOLLOWED_FILE = BLOG_ROOT / "data" / "x_followed.json"
COOKIES_FILE = BLOG_ROOT / "config" / "x_cookies.json"

DAILY_LIMIT = 10

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# 検索キーワードリスト（ランダムで1つ選択）
SEARCH_KEYWORDS = [
    "ガジェット",
    "テック",
    "充電器 レビュー",
    "イヤホン おすすめ",
    "PC周辺機器",
    "スマホ ガジェット",
]


def load_followed_data() -> dict:
    """フォロー済みデータを読み込む"""
    if not FOLLOWED_FILE.exists():
        return {"followed_ids": [], "daily_count": {}}
    try:
        return json.loads(FOLLOWED_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning(f"x_followed.json読み込み失敗: {e}")
        return {"followed_ids": [], "daily_count": {}}


def save_followed_data(data: dict):
    """フォロー済みデータを保存"""
    FOLLOWED_FILE.parent.mkdir(parents=True, exist_ok=True)
    FOLLOWED_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def get_today_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def get_today_count(data: dict) -> int:
    today = get_today_str()
    return data.get("daily_count", {}).get(today, 0)


def increment_today_count(data: dict) -> dict:
    today = get_today_str()
    if "daily_count" not in data:
        data["daily_count"] = {}
    data["daily_count"][today] = data["daily_count"].get(today, 0) + 1
    return data


def search_and_follow(keyword: str, followed_data: dict, dry_run: bool = False, no_delay: bool = False, count: int = None) -> int:
    """
    指定キーワードでXのPeopleタブを検索し、未フォローアカウントをフォローする。
    フォロー件数を返す。count指定時はその件数、未指定は5〜10件ランダム。
    """
    from playwright.sync_api import sync_playwright
    import urllib.parse

    if not COOKIES_FILE.exists():
        logger.error(f"Cookieファイルなし: {COOKIES_FILE}")
        return 0

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

    followed_ids = followed_data.get("followed_ids", [])
    today_count = get_today_count(followed_data)
    remaining = DAILY_LIMIT - today_count

    if remaining <= 0:
        logger.info("本日のフォロー上限に達しました（10件/日）")
        return 0

    if count is not None:
        follow_target = count
    else:
        follow_target = random.randint(5, 10)
    follow_target = min(follow_target, remaining)
    logger.info(f"キーワード「{keyword}」でPeople検索。目標フォロー数: {follow_target}件（残上限: {remaining}件）")

    followed_this_run = 0

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
            return 0
        logger.info("Cookie認証成功")

        # Peopleタブで人物検索
        search_url = f"https://x.com/search?q={urllib.parse.quote(keyword)}&src=typed_query&f=user"
        logger.info(f"検索URL: {search_url}")
        page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(5000)

        # ユーザーカードを収集
        user_cells = page.locator('[data-testid="UserCell"]').all()
        logger.info(f"検索結果: {len(user_cells)}件のアカウント")

        # 候補リスト作成（未フォロー + フォローボタンあり）
        candidates = []
        for cell in user_cells:
            try:
                # スクリーンネームを取得（href="/username" 形式）
                links = cell.locator('a').all()
                username = None
                for link in links:
                    href = link.get_attribute("href") or ""
                    if href and href.startswith("/") and "/" not in href[1:]:
                        username = href.lstrip("/")
                        break
                if not username:
                    continue

                # フォロー済みチェック（data/x_followed.json）
                if username in followed_ids:
                    logger.debug(f"フォロー済みスキップ: @{username}")
                    continue

                # フォローボタン確認: data-testid="{user_id}-follow"（末尾が "-follow"）
                # 既フォロー中は data-testid="{user_id}-unfollow"
                buttons = cell.locator('button').all()
                follow_btn = None
                for btn in buttons:
                    testid = btn.get_attribute("data-testid") or ""
                    if testid.endswith("-follow") and not testid.endswith("-unfollow"):
                        follow_btn = btn
                        break

                if follow_btn is None:
                    logger.debug(f"フォローボタンなしスキップ: @{username}")
                    continue

                candidates.append((username, cell, follow_btn))

            except Exception as e:
                logger.debug(f"ユーザーカード解析失敗: {e}")
                continue

        logger.info(f"フォロー候補: {len(candidates)}件")

        if not candidates:
            logger.info("フォロー可能なアカウントが見つかりませんでした")
            browser.close()
            return 0

        # 候補からランダム選択
        random.shuffle(candidates)
        selected = candidates[:follow_target]

        for username, cell, follow_btn in selected:
            if followed_this_run >= follow_target:
                break

            today_count = get_today_count(followed_data)
            if today_count >= DAILY_LIMIT:
                logger.info("本日のフォロー上限に達しました（10件/日）")
                break

            logger.info(f"フォロー対象: @{username}")

            if dry_run:
                logger.info(f"[DRY RUN] @{username} フォロースキップ")
                followed_this_run += 1
                continue

            # ランダム遅延（30〜120秒）
            if not no_delay and followed_this_run > 0:
                delay = random.randint(30, 120)
                logger.info(f"ランダム遅延: {delay}秒")
                time.sleep(delay)

            try:
                follow_btn.scroll_into_view_if_needed()
                follow_btn.click()
                page.wait_for_timeout(2000)

                logger.info(f"フォロー完了: @{username}")
                followed_data["followed_ids"].append(username)
                followed_data = increment_today_count(followed_data)
                save_followed_data(followed_data)
                followed_this_run += 1

            except Exception as e:
                logger.error(f"フォロー失敗 (@{username}): {e}")
                continue

        browser.close()

    return followed_this_run


def main():
    parser = argparse.ArgumentParser(description="X自動フォロースクリプト")
    parser.add_argument("--dry-run", action="store_true", help="実際にフォローせずログのみ表示")
    parser.add_argument("--no-delay", action="store_true", help="ランダム遅延をスキップ（テスト用）")
    parser.add_argument("--count", type=int, default=None, help="フォロー件数を指定（未指定時は5〜10件ランダム）")
    args = parser.parse_args()

    # フォロー済みデータ読み込み
    followed_data = load_followed_data()
    today_count = get_today_count(followed_data)
    total_followed = len(followed_data.get("followed_ids", []))
    logger.info(f"フォロー済み総数: {total_followed}件 / 本日フォロー済み: {today_count}件")

    if today_count >= DAILY_LIMIT:
        logger.info("本日のフォロー上限に達しました（10件/日）。終了します。")
        return

    # キーワードをランダムで1つ選択
    keyword = random.choice(SEARCH_KEYWORDS)
    logger.info(f"選択キーワード: {keyword}")

    # 検索＆フォロー
    followed_count = search_and_follow(
        keyword, followed_data,
        dry_run=args.dry_run,
        no_delay=args.no_delay,
        count=args.count,
    )

    if followed_count > 0:
        mode = "[DRY RUN] " if args.dry_run else ""
        logger.info(f"{mode}完了。フォロー実行: {followed_count}件")
    else:
        logger.info("フォロー実行なし")


if __name__ == "__main__":
    main()
