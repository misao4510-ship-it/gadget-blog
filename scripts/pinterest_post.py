#!/usr/bin/env python3
"""
Pinterest 自動ピン投稿スクリプト (cmd_207, cmd_365)

Pinterest API v5でピンを投稿する。
APIトークンがない場合はPlaywright+Cookie方式にフォールバック。

OG画像（public/images/og/{slug}.png）をピン画像として使用。
投稿済みスラッグは data/pinterest_post_history.json で管理。

Usage:
    python3 scripts/pinterest_post.py --slug anker-nano-charger-100w-review
    python3 scripts/pinterest_post.py --all
    python3 scripts/pinterest_post.py --slug anker-nano-charger-100w-review --dry-run
    python3 scripts/pinterest_post.py --all --dry-run --no-delay
    python3 scripts/pinterest_post.py --list-boards   # ボード一覧を表示（API方式のみ）
    python3 scripts/pinterest_post.py --site misaki --slug first-credit-card --dry-run
    python3 scripts/pinterest_post.py --site misaki --all
"""

import os
import sys
import json
import time
import random
import base64
import logging
import argparse
import re
from pathlib import Path
from datetime import datetime, timezone

# パス設定（gadget-blogデフォルト — --site misaki 指定時はmain()で上書き）
BLOG_ROOT = Path(__file__).parent.parent.resolve()
AUTH_FILE = BLOG_ROOT / "config" / "pinterest_auth.env"
COOKIES_FILE = BLOG_ROOT / "config" / "pinterest_cookies.json"
HISTORY_FILE = BLOG_ROOT / "data" / "pinterest_post_history.json"
POSTS_DIR = BLOG_ROOT / "src" / "content" / "posts"
OG_DIR = BLOG_ROOT / "public" / "images" / "og"
BLOG_BASE_URL = "https://gadget-blog-dxq.pages.dev"

PINTEREST_API_BASE = "https://api.pinterest.com/v5"

# misaki-money 設定
MISAKI_BLOG_ROOT = Path("/home/misao/misaki-money")
MISAKI_BLOG_BASE_URL = "https://misaki-money.com"
MISAKI_HASHTAGS = "#節約 #クレカ #NISA #20代女性 #お金 #マネープラン #FP #資産形成"

# カテゴリ→ハッシュタグマッピング
CATEGORY_HASHTAGS = {
    "charger": "#充電器 #ガジェット #USB #GaN",
    "wireless-charger": "#ワイヤレス充電器 #ガジェット #Qi",
    "earphone": "#イヤホン #ガジェット #音楽",
    "usb-hub": "#USBハブ #ガジェット #PC周辺機器",
    "mobile-battery": "#モバイルバッテリー #ガジェット",
    "gadget": "#ガジェット #レビュー #おすすめ",
    "review": "#ガジェット #レビュー",
    "health": "#健康グッズ #レビュー",
    "default": "#ガジェット #レビュー #おすすめ",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


# ===== ユーティリティ =====

def load_env(path: Path) -> dict:
    """envファイルをロード"""
    env = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip()
    return env


def load_history() -> dict:
    if not HISTORY_FILE.exists():
        return {"posted_slugs": [], "pins": []}
    return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))


def save_history(history: dict):
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_FILE.write_text(json.dumps(history, ensure_ascii=False, indent=2))


def parse_frontmatter(md_file: Path) -> dict | None:
    """Markdownのfrontmatterをパース"""
    try:
        import yaml
    except ImportError:
        # yamlなしの簡易パーサー
        yaml = None

    content = md_file.read_text(encoding="utf-8")
    match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return None

    if yaml:
        try:
            meta = yaml.safe_load(match.group(1))
        except Exception:
            return None
    else:
        meta = {}
        for line in match.group(1).splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                meta[k.strip()] = v.strip().strip('"').strip("'")

    if not meta or meta.get("draft", False):
        return None
    meta["slug"] = md_file.stem
    return meta


def load_all_articles() -> list[dict]:
    """全記事のfrontmatterをロード"""
    articles = []
    for md_file in sorted(POSTS_DIR.glob("*.md")):
        meta = parse_frontmatter(md_file)
        if meta:
            articles.append(meta)
    logger.info(f"記事数: {len(articles)}件")
    return articles


def get_hashtags(category: str) -> str:
    """カテゴリに応じたハッシュタグを返す"""
    return CATEGORY_HASHTAGS.get(category, CATEGORY_HASHTAGS["default"])


def build_pin_description(article: dict, site: str = "gadget") -> str:
    """ピン説明文を生成（site='misaki'の場合は misaki-money 用テンプレ）"""
    title = article.get("title", "")
    slug = article["slug"]
    url = f"{BLOG_BASE_URL}/posts/{slug}/"

    if site == "misaki":
        summary = article.get("description", article.get("summary", ""))
        parts = [title]
        if summary:
            parts.append(summary)
        parts.append("")
        parts.append(MISAKI_HASHTAGS)
        parts.append(url)
        return "\n".join(parts)

    # gadget-blog: サクラ口調
    category = article.get("category", "gadget")
    hashtags = get_hashtags(category)
    return f"✨ {title}\n\nサクラが詳しくレビューしていますよ！\n気になる方はチェックしてみてくださいね🌸\n\n{url}\n\n{hashtags}"


def get_board_id_for_category(auth: dict, category: str) -> str | None:
    """カテゴリに対応するボードIDを取得（設定ファイル優先）"""
    # config から category_board_mapping を読む
    # 例: PINTEREST_BOARD_charger=xxx
    key = f"PINTEREST_BOARD_{category.upper().replace('-', '_')}"
    if key in auth:
        return auth[key]
    # デフォルトボード
    return auth.get("PINTEREST_DEFAULT_BOARD_ID")


# ===== Pinterest API v5 =====

def api_get_boards(access_token: str) -> list[dict]:
    """ボード一覧を取得"""
    import urllib.request
    import urllib.error

    url = f"{PINTEREST_API_BASE}/boards?page_size=25"
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {access_token}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            return data.get("items", [])
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        logger.error(f"ボード取得失敗 {e.code}: {body}")
        return []
    except Exception as e:
        logger.error(f"ボード取得エラー: {e}")
        return []


def api_create_pin(
    access_token: str,
    board_id: str,
    title: str,
    description: str,
    link: str,
    image_path: Path,
) -> dict | None:
    """Pinterest API v5でピンを作成"""
    import urllib.request
    import urllib.error

    # 画像をbase64エンコード
    if not image_path.exists():
        logger.error(f"OG画像が見つかりません: {image_path}")
        return None

    img_bytes = image_path.read_bytes()
    img_b64 = base64.b64encode(img_bytes).decode()

    payload = {
        "board_id": board_id,
        "title": title,
        "description": description,
        "link": link,
        "media_source": {
            "source_type": "image_base64",
            "content_type": "image/png",
            "data": img_b64,
        },
    }

    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{PINTEREST_API_BASE}/pins",
        data=body,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode())
            logger.info(f"ピン作成成功: id={data.get('id')}")
            return data
    except urllib.error.HTTPError as e:
        body_str = e.read().decode()
        logger.error(f"ピン作成失敗 {e.code}: {body_str}")
        return None
    except Exception as e:
        logger.error(f"ピン作成エラー: {e}")
        return None


def post_via_api(article: dict, auth: dict, dry_run: bool = False, site: str = "gadget") -> bool:
    """API v5でピンを投稿"""
    slug = article["slug"]
    title = article.get("title", slug)
    description = build_pin_description(article, site)
    link = f"{BLOG_BASE_URL}/posts/{slug}/"
    image_path = OG_DIR / f"{slug}.png"
    category = article.get("category", "gadget")
    board_id = get_board_id_for_category(auth, category)

    logger.info(f"[API] ピン投稿: {slug}")
    logger.info(f"  ボードID: {board_id}")
    logger.info(f"  タイトル: {title[:50]}")
    logger.info(f"  リンク: {link}")
    logger.info(f"  画像: {image_path}")
    logger.info(f"  説明文:\n{description}")

    if dry_run:
        logger.info("[DRY RUN] 投稿スキップ")
        return True

    access_token = auth.get("PINTEREST_ACCESS_TOKEN", "")
    if not access_token:
        logger.error("PINTEREST_ACCESS_TOKEN が設定されていません")
        return False

    if not board_id:
        logger.error("ボードIDが設定されていません。config/pinterest_auth.env に PINTEREST_DEFAULT_BOARD_ID を設定してください")
        return False

    result = api_create_pin(access_token, board_id, title, description, link, image_path)
    return result is not None


# ===== Playwright方式 =====

def post_via_playwright(article: dict, dry_run: bool = False, site: str = "gadget") -> bool:
    """Playwright+CookieでPinterestにピンを投稿"""
    slug = article["slug"]
    title = article.get("title", slug)
    description = build_pin_description(article, site)
    link = f"{BLOG_BASE_URL}/posts/{slug}/"
    image_path = OG_DIR / f"{slug}.png"

    logger.info(f"[Playwright] ピン投稿: {slug}")
    logger.info(f"  タイトル: {title[:50]}")
    logger.info(f"  リンク: {link}")
    logger.info(f"  画像: {image_path}")
    logger.info(f"  説明文:\n{description}")

    if dry_run:
        logger.info("[DRY RUN] 投稿スキップ")
        return True

    if not COOKIES_FILE.exists():
        logger.error(
            f"Cookieファイルが見つかりません: {COOKIES_FILE}\n"
            "Pinterestにブラウザでログイン後、Cookie EditorでCookieをJSON形式でエクスポートして保存してください。"
        )
        return False

    # Playwright用ライブラリパス設定
    _LOCAL_LIBS = Path("/tmp/locallibs/usr/lib/x86_64-linux-gnu")
    if _LOCAL_LIBS.exists():
        existing = os.environ.get("LD_LIBRARY_PATH", "")
        if str(_LOCAL_LIBS) not in existing:
            os.environ["LD_LIBRARY_PATH"] = f"{_LOCAL_LIBS}:{existing}"

    slug = article["slug"]
    title = article.get("title", slug)
    description = build_pin_description(article, site)
    link = f"{BLOG_BASE_URL}/posts/{slug}/"
    image_path = OG_DIR / f"{slug}.png"

    if not image_path.exists():
        logger.error(f"OG画像が見つかりません: {image_path}")
        return False

    logger.info(f"[Playwright] ピン投稿: {slug}")
    logger.info(f"  タイトル: {title[:50]}")
    logger.info(f"  リンク: {link}")
    logger.info(f"  画像: {image_path}")

    if dry_run:
        logger.info("[DRY RUN] 投稿スキップ")
        return True

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.error("playwrightがインストールされていません: pip3 install playwright && playwright install chromium")
        return False

    cookies_raw = json.loads(COOKIES_FILE.read_text(encoding="utf-8"))

    # Playwright用Cookie整形
    cookies = []
    for c in cookies_raw:
        cookie = {
            "name": c["name"],
            "value": c["value"],
            "domain": c.get("domain", ".pinterest.com"),
            "path": c.get("path", "/"),
        }
        ss = c.get("sameSite", "Lax")
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
            locale="ja-JP",
        )
        # BOT検知回避: playwright-stealth適用
        try:
            from playwright_stealth import Stealth
            stealth = Stealth(
                navigator_languages_override=("ja", "ja-JP"),
            )
            stealth.apply_stealth_sync(context)
            logger.info("playwright-stealth 適用済み")
        except ImportError:
            logger.warning("playwright-stealth 未インストール。BOT検知される可能性あり")
        context.add_cookies(cookies)
        page = context.new_page()

        try:
            # Pinterestホームで認証確認
            logger.info("Pinterest にアクセス中...")
            page.goto("https://jp.pinterest.com/", wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)

            # デバッグ: ページ状態を記録
            page.screenshot(path="/tmp/pinterest_login_check.png")
            logger.info(f"現在のURL: {page.url}")
            login_in_url = "login" in page.url
            login_btn = page.locator('[data-test-id="simple-login-button"]').count()
            logger.info(f"login in URL: {login_in_url}, login button count: {login_btn}")

            # ログイン確認
            if login_in_url or login_btn > 0:
                browser.close()
                logger.error("Cookie期限切れ。config/pinterest_cookies.json を更新してください")
                return False

            logger.info("Cookie認証成功")

            # ピン作成ページへ
            page.goto("https://jp.pinterest.com/pin-builder/", wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)

            page.screenshot(path="/tmp/pinterest_before_upload.png")
            logger.info("スクリーンショット: /tmp/pinterest_before_upload.png")

            # 画像アップロード
            upload_input = page.locator('input[type="file"]').first
            if upload_input.count() == 0:
                upload_input = page.locator('[data-test-id="storyboard-upload-input"]')
            upload_input.set_input_files(str(image_path))
            logger.info("画像アップロード中...")
            page.wait_for_timeout(5000)

            page.screenshot(path="/tmp/pinterest_after_upload.png")
            logger.info("スクリーンショット: /tmp/pinterest_after_upload.png")

            # タイトル入力
            title_input = page.locator('[data-test-id="pin-draft-title"] input, [placeholder*="タイトル"], [placeholder*="title"]').first
            if title_input.count() > 0:
                title_input.click()
                title_input.fill(title[:100])
                logger.info(f"タイトル入力: {title[:50]}")
                page.wait_for_timeout(500)

            # 説明文入力
            desc_input = page.locator('[data-test-id="pin-draft-description"] textarea, [placeholder*="説明"], [placeholder*="description"]').first
            if desc_input.count() > 0:
                desc_input.click()
                desc_input.fill(description[:500])
                logger.info("説明文入力完了")
                page.wait_for_timeout(500)

            # リンク入力
            link_input = page.locator('[data-test-id="pin-draft-link"] input, [placeholder*="リンク"], [placeholder*="link"], [placeholder*="URL"]').first
            if link_input.count() > 0:
                link_input.click()
                link_input.fill(link)
                logger.info(f"リンク入力: {link}")
                page.wait_for_timeout(500)

            page.screenshot(path="/tmp/pinterest_before_publish.png")

            # 公開ボタン
            publish_btn = page.locator('[data-test-id="board-dropdown-select-button"], button:has-text("公開"), button:has-text("Publish")').first
            if publish_btn.count() > 0:
                publish_btn.click()
                page.wait_for_timeout(5000)
                logger.info("ピン公開完了")
            else:
                logger.warning("公開ボタンが見つかりません")
                page.screenshot(path="/tmp/pinterest_no_publish_btn.png")
                browser.close()
                return False

            page.screenshot(path="/tmp/pinterest_after_publish.png")
            browser.close()
            return True

        except Exception as e:
            logger.error(f"Playwright投稿エラー: {e}")
            try:
                page.screenshot(path="/tmp/pinterest_error.png")
            except Exception:
                pass
            browser.close()
            return False


# ===== ボード一覧表示 =====

def list_boards():
    """API v5でボード一覧を表示"""
    auth = load_env(AUTH_FILE)
    access_token = auth.get("PINTEREST_ACCESS_TOKEN", "")
    if not access_token:
        logger.error(f"APIトークンがありません: {AUTH_FILE}")
        print(f"\n設定方法:\n{AUTH_FILE} に以下を記載してください:\n")
        print("PINTEREST_ACCESS_TOKEN=<your_access_token>")
        print("PINTEREST_DEFAULT_BOARD_ID=<default_board_id>")
        return

    logger.info("ボード一覧を取得中...")
    boards = api_get_boards(access_token)
    if not boards:
        logger.error("ボードが取得できませんでした")
        return

    print("\n=== Pinterest ボード一覧 ===")
    for b in boards:
        print(f"  ID: {b['id']} | 名前: {b['name']} | URL: {b.get('url', '')}")
    print(f"\n合計: {len(boards)}件")
    print("\nconfig/pinterest_auth.env に以下のように設定してください:")
    print("PINTEREST_DEFAULT_BOARD_ID=<最初のボードのID>")


# ===== メイン処理 =====

def post_article(article: dict, auth: dict | None, dry_run: bool = False, site: str = "gadget") -> bool:
    """1記事をPinterestに投稿（API優先、fallbackはPlaywright）"""
    slug = article["slug"]
    image_path = OG_DIR / f"{slug}.png"

    if not image_path.exists():
        if dry_run:
            logger.info(f"[DRY RUN] OG画像なし（投稿時は要生成）: {image_path}")
        else:
            logger.warning(f"OG画像が存在しないためスキップ: {image_path}")
            return False

    # API方式を試みる（dry-runでも選択）
    if auth and (auth.get("PINTEREST_ACCESS_TOKEN") or dry_run):
        logger.info(f"API方式で投稿: {slug}")
        return post_via_api(article, auth or {}, dry_run, site)

    # Playwright方式にフォールバック
    logger.info(f"Playwright方式で投稿: {slug}")
    return post_via_playwright(article, dry_run, site)


def main():
    parser = argparse.ArgumentParser(description="Pinterest 自動ピン投稿スクリプト")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--slug", help="投稿する記事のスラッグ")
    group.add_argument("--all", action="store_true", help="未投稿記事を全て投稿（1日1件）")
    group.add_argument("--list-boards", action="store_true", help="Pinterest ボード一覧を表示")
    parser.add_argument("--site", choices=["gadget", "misaki"], default="gadget", help="投稿対象サイト (gadget | misaki)")
    parser.add_argument("--dry-run", action="store_true", help="投稿せずにログのみ表示")
    parser.add_argument("--no-delay", action="store_true", help="ランダム遅延をスキップ（テスト用）")
    args = parser.parse_args()

    # --site misaki 時はグローバルパス変数を misaki-money 用に切り替える
    global BLOG_ROOT, AUTH_FILE, COOKIES_FILE, HISTORY_FILE, POSTS_DIR, OG_DIR, BLOG_BASE_URL
    if args.site == "misaki":
        BLOG_ROOT = MISAKI_BLOG_ROOT
        AUTH_FILE = BLOG_ROOT / "config" / "pinterest_auth.env"
        # Cookieは gadget-blog のものを共用（同じPinterestアカウント）
        COOKIES_FILE = Path("/home/misao/gadget-blog/config/pinterest_cookies.json")
        HISTORY_FILE = BLOG_ROOT / "data" / "pinterest_post_history.json"
        POSTS_DIR = BLOG_ROOT / "src" / "content" / "posts"
        OG_DIR = BLOG_ROOT / "public" / "images" / "og"
        BLOG_BASE_URL = MISAKI_BLOG_BASE_URL
        logger.info("サイト: misaki-money")
    else:
        logger.info("サイト: gadget-blog")

    # ボード一覧表示
    if args.list_boards:
        list_boards()
        return

    # ランダム遅延（BOT判定回避）
    if not args.no_delay and not args.dry_run:
        delay = random.randint(0, 300)
        logger.info(f"ランダム遅延: {delay}秒")
        time.sleep(delay)

    # 認証情報ロード
    auth = load_env(AUTH_FILE) if AUTH_FILE.exists() else None
    if not auth or not auth.get("PINTEREST_ACCESS_TOKEN"):
        logger.info(f"APIトークンなし → Playwright方式を使用")
        if not COOKIES_FILE.exists():
            logger.warning(
                f"Pinterest Cookieも見つかりません。\n"
                f"API方式: {AUTH_FILE} に PINTEREST_ACCESS_TOKEN を設定\n"
                f"Playwright方式: {COOKIES_FILE} にCookieをエクスポートして保存"
            )
    else:
        logger.info("API v5方式を使用")

    history = load_history()
    posted_slugs = set(history.get("posted_slugs", []))

    # --slug モード
    if args.slug:
        slug = args.slug
        md_file = POSTS_DIR / f"{slug}.md"
        if not md_file.exists():
            logger.error(f"記事が見つかりません: {md_file}")
            sys.exit(1)

        article = parse_frontmatter(md_file)
        if not article:
            logger.error(f"frontmatterのパースに失敗: {md_file}")
            sys.exit(1)

        success = post_article(article, auth, args.dry_run, args.site)
        if success and not args.dry_run:
            history.setdefault("posted_slugs", [])
            if slug not in history["posted_slugs"]:
                history["posted_slugs"].append(slug)
            history.setdefault("pins", []).append({
                "slug": slug,
                "title": article.get("title", ""),
                "posted_at": datetime.now(timezone.utc).isoformat(),
            })
            save_history(history)
            logger.info(f"履歴保存完了: {slug}")
        return

    # --all モード: 未投稿記事を1件ずつ投稿
    if args.all:
        articles = load_all_articles()
        # draft以外、OG画像あり、未投稿の記事を選ぶ
        candidates = [
            a for a in articles
            if a["slug"] not in posted_slugs
            and (OG_DIR / f"{a['slug']}.png").exists()
        ]

        if not candidates:
            logger.info("未投稿記事なし（全記事投稿済み）")
            return

        # 1回の実行で1件だけ投稿（cronで毎日呼ぶ想定）
        article = candidates[0]
        slug = article["slug"]
        logger.info(f"投稿対象: {slug}（残り{len(candidates)}件）")

        success = post_article(article, auth, args.dry_run, args.site)
        if success and not args.dry_run:
            history.setdefault("posted_slugs", [])
            if slug not in history["posted_slugs"]:
                history["posted_slugs"].append(slug)
            history.setdefault("pins", []).append({
                "slug": slug,
                "title": article.get("title", ""),
                "posted_at": datetime.now(timezone.utc).isoformat(),
            })
            save_history(history)
            logger.info(f"履歴保存完了: {slug}")
        return

    # 引数なし → ヘルプ
    parser.print_help()


if __name__ == "__main__":
    main()
