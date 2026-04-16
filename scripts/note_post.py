#!/usr/bin/env python3
"""
note.com 転載スクリプト

ブログ記事をnote.comに転載する。公式APIが存在しないため、
内部APIをrequestsで呼び出す方式を採用。

Usage:
    python3 scripts/note_post.py --slug amazon-basics-aa-battery-review --dry-run
    python3 scripts/note_post.py --slug amazon-basics-aa-battery-review
    python3 scripts/note_post.py --all-new --dry-run
    python3 scripts/note_post.py --all-new

    # ブログ画像流用（サクラ口調変換なし・SD生成不要）
    python3 scripts/note_post.py --slug {slug} --no-sakura-voice --blog-images \\
        --eyecatch public/images/og/{slug}.png --telegram-notify
"""

import os
import sys
import logging
import argparse
import yaml
import re
import json
import requests
from pathlib import Path
from datetime import datetime, timezone

# Playwright用システムライブラリのパスを設定（libnspr4等がシステム未インストールの場合）
_LOCAL_LIBS = Path("/tmp/locallibs/usr/lib/x86_64-linux-gnu")
if _LOCAL_LIBS.exists():
    _existing = os.environ.get("LD_LIBRARY_PATH", "")
    if str(_LOCAL_LIBS) not in _existing:
        os.environ["LD_LIBRARY_PATH"] = f"{_LOCAL_LIBS}:{_existing}"

# パス設定
BLOG_ROOT = Path(__file__).parent.parent.resolve()
CONFIG_FILE = BLOG_ROOT / "config" / "note_post.yaml"
AUTH_ENV_FILE = BLOG_ROOT / "config" / "note_auth.env"
POSTS_DIR = BLOG_ROOT / "src" / "content" / "posts"
_TELEGRAM_AUTH_FILE = Path("/mnt/c/tools/multi-agent-shogun/config/telegram_auth.env")

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# scripts/libをインポートパスに追加
sys.path.insert(0, str(Path(__file__).parent))
from lib.note_converter import NoteConverter
from note_sakura_voice import convert_to_sakura_voice


# ===== ヘルパー関数 =====

# note本文中の区切り線（---）を除去する挿入位置マーカー
_SPLIT_MARKERS = [
    ("## 商品概要", "intro"),
    ("## 主な特徴", "features"),
    ("## メリット", "merit"),
    ("## デメリット", "demerit"),
    ("## まとめ", "summary"),
]


def strip_separator_lines(body: str) -> str:
    """note本文から区切り線（---）を除去し、連続空行を圧縮する"""
    body = re.sub(r'\n\s*---\s*\n', '\n\n', body)
    body = re.sub(r'^\s*---\s*\n', '', body)
    body = re.sub(r'\n\s*---\s*$', '', body.rstrip())
    body = re.sub(r'\n{3,}', '\n\n', body)
    return body


def _load_telegram_auth() -> tuple[str, str]:
    """Telegram BOT_TOKEN と CHAT_ID を返す"""
    env = {}
    if _TELEGRAM_AUTH_FILE.exists():
        with open(_TELEGRAM_AUTH_FILE, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    env[k.strip()] = v.strip()
    bot_token = env.get("TELEGRAM_BOT_TOKEN", os.environ.get("TELEGRAM_BOT_TOKEN", ""))
    chat_id = env.get("TELEGRAM_CHAT_ID", os.environ.get("TELEGRAM_CHAT_ID", ""))
    return bot_token, chat_id


def send_telegram_notification(slug: str, note_url: str) -> bool:
    """note投稿完了をTelegramに通知する"""
    bot_token, chat_id = _load_telegram_auth()
    if not bot_token or not chat_id:
        logger.warning("Telegram認証情報が未設定です（telegram_auth.env）")
        return False
    message = f"🌸 note転載完了！\n\nスラッグ: {slug}\nnote URL: {note_url}"
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={"chat_id": chat_id, "text": message},
            timeout=30,
        )
        resp.raise_for_status()
        logger.info("Telegram通知送信完了")
        return True
    except Exception as e:
        logger.warning(f"Telegram通知失敗: {e}")
        return False


# ===== 設定・認証読み込み =====

def load_config() -> dict:
    """設定ファイルを読み込む"""
    if not CONFIG_FILE.exists():
        raise FileNotFoundError(f"設定ファイルが見つかりません: {CONFIG_FILE}")
    with open(CONFIG_FILE, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_auth_env(env_file: Path) -> dict:
    """認証環境変数ファイルを読み込む"""
    env = {}
    if not env_file.exists():
        raise FileNotFoundError(
            f"認証ファイルが見つかりません: {env_file}\n"
            f"config/note_auth.env.template をコピーして設定してください。"
        )
    with open(env_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                env[key.strip()] = value.strip()
    return env


def load_history(config: dict) -> dict:
    """投稿済み履歴を読み込む"""
    history_file = BLOG_ROOT / config.get("history_file", "config/note_posted.yaml")
    if not history_file.exists():
        return {"posted": []}
    with open(history_file, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if "posted" not in data:
        data["posted"] = []
    return data


def record_posted(slug: str, note_url: str, config: dict) -> None:
    """投稿済み記録をYAMLに追記"""
    history_file = BLOG_ROOT / config.get("history_file", "config/note_posted.yaml")
    history = load_history(config)
    history["posted"].append({
        "slug": slug,
        "note_url": note_url,
        "posted_at": datetime.now(timezone.utc).isoformat(),
    })
    with open(history_file, "w", encoding="utf-8") as f:
        yaml.dump(history, f, allow_unicode=True, default_flow_style=False)
    logger.info(f"履歴に記録: {slug} → {note_url}")


# ===== 記事読み込み =====

def get_post_path(slug: str) -> Path:
    """スラッグからMarkdownファイルパスを取得"""
    path = POSTS_DIR / f"{slug}.md"
    if not path.exists():
        raise FileNotFoundError(f"記事が見つかりません: {path}")
    return path


def get_unposted_slugs(config: dict) -> list[str]:
    """未投稿の記事スラッグ一覧を返す（draft: true は除外）"""
    history = load_history(config)
    posted_slugs = {item["slug"] for item in history["posted"]}
    all_slugs = []
    for md_file in sorted(POSTS_DIR.glob("*.md")):
        slug = md_file.stem
        if slug in posted_slugs:
            continue
        # draft: true の記事は除外
        try:
            content = md_file.read_text(encoding="utf-8")
            match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
            if match:
                meta = yaml.safe_load(match.group(1)) or {}
                if meta.get("draft", False):
                    continue
        except Exception:
            pass
        all_slugs.append(slug)
    return all_slugs


# ===== note.com 投稿 =====

COOKIES_FILE = BLOG_ROOT / "config" / "note_cookies.json"


class NoteClient:
    """note.com投稿クライアント（Playwright方式）"""

    BASE_URL = "https://note.com"

    def __init__(self, email: str, password: str):
        self.email = email
        self.password = password

    @staticmethod
    def _type_text_block(page, text: str) -> None:
        """テキストブロックをProseMirrorに入力（連続空行を圧縮）"""
        lines = text.split("\n")
        prev_empty = False
        for i, line in enumerate(lines):
            is_empty = not line.strip()
            if is_empty and prev_empty:
                continue
            if line.strip():
                page.keyboard.type(line, delay=1)
            if i < len(lines) - 1:
                page.keyboard.press("Enter")
            prev_empty = is_empty

    @staticmethod
    def _insert_inline_image(page, image_path: str) -> None:
        """ProseMirrorエディタにインライン画像を挿入"""
        page.keyboard.press("Enter")
        page.wait_for_timeout(800)
        menu_btn = page.locator('button[aria-label="メニューを開く"]')
        menu_btn.wait_for(state="visible", timeout=5000)
        menu_btn.first.click()
        page.wait_for_timeout(1000)
        with page.expect_file_chooser(timeout=10000) as fc_info:
            page.get_by_text("画像", exact=True).click()
        fc_info.value.set_files(image_path)
        page.wait_for_timeout(4000)
        page.keyboard.press("ArrowDown")
        page.wait_for_timeout(300)
        page.keyboard.press("End")
        page.wait_for_timeout(300)

    @staticmethod
    def _upload_eyecatch(page, image_path: str) -> bool:
        """アイキャッチ画像をアップロード"""
        eyecatch_btn = page.locator('button[aria-label="画像を追加"]')
        if eyecatch_btn.count() == 0:
            return False
        eyecatch_btn.click()
        page.wait_for_timeout(2000)
        cancel_btn = page.locator('button:has-text("キャンセル")')
        if cancel_btn.count() > 0 and cancel_btn.first.is_visible():
            cancel_btn.first.click()
            page.wait_for_timeout(1000)
            eyecatch_btn.click()
            page.wait_for_timeout(2000)
        upload_option = page.locator(
            'button:has-text("画像をアップロード"), a:has-text("画像をアップロード")'
        )
        if upload_option.count() > 0:
            with page.expect_file_chooser(timeout=10000) as fc_info:
                upload_option.first.click()
            fc_info.value.set_files(image_path)
            page.wait_for_timeout(5000)
            save_btn = page.get_by_role("button", name="保存", exact=True)
            if save_btn.count() > 0:
                save_btn.click()
                page.wait_for_timeout(3000)
                logger.info("アイキャッチ設定完了")
                return True
        return False

    @staticmethod
    def _split_body_into_sections(body: str) -> list[dict]:
        """本文をセクションに分割し、各セクション後に挿入する挿絵キーを記録。
        マーカーが3つ未満しか一致しない場合は、## 見出しで均等分割しフォールバック。
        """
        # まずマーカーベースで分割を試みる
        sections = []
        remaining = body
        for marker, img_key in _SPLIT_MARKERS:
            idx = remaining.find(marker)
            if idx > 0:
                sections.append({"text": remaining[:idx].rstrip(), "image_after": img_key})
                remaining = remaining[idx:]
        if remaining.strip():
            sections.append({"text": remaining.strip(), "image_after": None})

        # マーカー一致が少ない場合、## 見出しで均等分割にフォールバック
        matched_images = sum(1 for s in sections if s["image_after"])
        if matched_images < 3:
            import re
            img_keys = ["intro", "features", "merit", "demerit", "summary"]
            # ## で始まる見出し位置で分割
            heading_positions = [m.start() for m in re.finditer(r'^## ', body, re.MULTILINE)]
            if len(heading_positions) >= 2:
                sections = []
                # 見出し位置に挿絵キーを均等配分
                split_points = heading_positions + [len(body)]
                for i in range(len(split_points) - 1):
                    text = body[split_points[i]:split_points[i + 1]].rstrip()
                    img_key = img_keys[i] if i < len(img_keys) else None
                    sections.append({"text": text, "image_after": img_key})
                # 先頭部分（最初の見出し前）があれば追加
                if heading_positions[0] > 0:
                    intro_text = body[:heading_positions[0]].rstrip()
                    if intro_text:
                        sections.insert(0, {"text": intro_text, "image_after": None})
                        # 挿絵キーを再配分（先頭はなし、以降の見出しセクションに割り当て）
                        for j, s in enumerate(sections):
                            if j == 0:
                                s["image_after"] = None
                            elif j - 1 < len(img_keys):
                                s["image_after"] = img_keys[j - 1]
                            else:
                                s["image_after"] = None

        return sections

    def post_article(self, title: str, body: str, hashtags: list[str] = None,
                     publish_status: str = "public",
                     eyecatch_path: str = None,
                     illustrations_dir: str = None) -> str:
        """Playwrightでnote.comにログインして記事を投稿

        Args:
            title: 記事タイトル
            body: 本文（Markdown変換済み）
            hashtags: ハッシュタグリスト
            publish_status: "public" or "draft"
            eyecatch_path: アイキャッチ画像パス（省略可）
            illustrations_dir: 挿絵ディレクトリパス（省略時は挿絵なし）
        """
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
            page = context.new_page()

            # 1. ログイン（Cookieファイルがあればそれを使用）
            if COOKIES_FILE.exists():
                logger.info("保存済みCookieでログイン中...")
                cookies = json.loads(COOKIES_FILE.read_text(encoding="utf-8"))
                for c in cookies:
                    if c.get("sameSite") is None or c.get("sameSite") not in ("Strict", "Lax", "None"):
                        c["sameSite"] = "Lax"
                    for key in ["hostOnly", "storeId", "session"]:
                        c.pop(key, None)
                context.add_cookies(cookies)
                page.goto(f"{self.BASE_URL}/")
                page.wait_for_load_state("networkidle")
                page.wait_for_timeout(2000)
                if "/login" in page.url:
                    raise RuntimeError(
                        "Cookie期限切れ: config/note_cookies.jsonを更新してください\n"
                        "手順: https://note.com にブラウザでログイン後、"
                        "Cookie Editorなどでnote.comのCookieをJSON形式でエクスポートし保存"
                    )
                logger.info("Cookie認証成功")
            else:
                logger.info("note.comにログイン中...")
                page.goto(f"{self.BASE_URL}/login")
                page.wait_for_load_state("networkidle")
                page.fill('input#email', self.email)
                page.fill('input#password', self.password)
                page.locator('button[data-type="primary"]').click()
                page.wait_for_load_state("networkidle")
                page.wait_for_timeout(2000)
                if "/login" in page.url:
                    raise RuntimeError(
                        "ログイン失敗: reCAPTCHAまたは認証エラー\n"
                        "解決策: ブラウザで手動ログイン後、Cookie Editorで"
                        "note.comのCookieをconfig/note_cookies.jsonに保存してください"
                    )
            logger.info("ログイン成功")

            # 2. 新規記事作成ページへ
            page.goto(f"{self.BASE_URL}/notes/new")
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(3000)
            logger.info(f"エディタURL: {page.url}")

            # 3. アイキャッチ設定（あれば）
            if eyecatch_path and Path(eyecatch_path).exists():
                logger.info(f"アイキャッチ設定中: {eyecatch_path}")
                self._upload_eyecatch(page, eyecatch_path)

            # 4. タイトル入力
            page.locator('textarea[placeholder="記事タイトル"]').fill(title)
            page.wait_for_timeout(500)

            # 5. 本文入力
            body_el = page.locator('.ProseMirror[contenteditable="true"]')
            body_el.click()
            page.wait_for_timeout(500)

            if illustrations_dir:
                illust_dir = Path(illustrations_dir)
                sections = self._split_body_into_sections(body)
                logger.info(f"セクション数: {len(sections)}（挿絵挿入モード）")
                for i, section in enumerate(sections):
                    self._type_text_block(page, section["text"])
                    page.wait_for_timeout(500)
                    if section["image_after"]:
                        img_path = illust_dir / f"{section['image_after']}.png"
                        if img_path.exists():
                            logger.info(f"  挿絵挿入: {section['image_after']}")
                            self._insert_inline_image(page, str(img_path))
                        else:
                            logger.warning(f"  挿絵なし（ファイル未存在）: {img_path}")
                    if i < len(sections) - 1:
                        page.keyboard.press("Enter")
                        page.wait_for_timeout(300)
            else:
                lines = body.split("\n")
                for i, line in enumerate(lines):
                    if line.strip():
                        page.keyboard.type(line, delay=1)
                    if i < len(lines) - 1:
                        page.keyboard.press("Enter")
            page.wait_for_timeout(2000)

            # 6. 「公開に進む」ボタンクリック
            page.locator('button:has-text("公開に進む")').click()
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(3000)

            # 7. ハッシュタグ入力
            if hashtags:
                try:
                    tag_input = page.locator('input[placeholder="ハッシュタグを追加する"]')
                    for tag in hashtags[:10]:
                        tag_input.fill(tag)
                        page.keyboard.press("Enter")
                        page.wait_for_timeout(500)
                except Exception:
                    logger.warning("ハッシュタグ入力欄が見つかりませんでした（スキップ）")

            # 8. 「投稿する」ボタンクリック
            if publish_status == "draft":
                logger.info("下書きモード: 投稿せず下書き保存のみ")
            else:
                page.locator('button:has-text("投稿する")').click()
                page.wait_for_load_state("networkidle")
                page.wait_for_timeout(5000)

            # 9. 投稿完了URLを取得
            note_url = page.url
            logger.info(f"投稿完了: {note_url}")
            browser.close()
            return note_url


# ===== メイン処理 =====

def _prepare_blog_images_for_note(slug: str, config: dict):
    """
    ブログの public/images/posts/{slug}/ 画像を note スクリプトが期待する
    /tmp/note_illustrations/{slug}/ にコピーし、ディレクトリパスを返す。

    マッピング:
      spec.png     → intro.png, features.png
      merit.png    → merit.png
      demerit.png  → demerit.png
      summary.png  → summary.png

    Returns:
        準備されたディレクトリパス（画像が1枚もなければ None）
    """
    import shutil
    blog_src = BLOG_ROOT / "public" / "images" / "posts" / slug
    illust_base = config.get("illustrations_dir", "/tmp/note_illustrations")
    dest_dir = Path(illust_base) / slug
    dest_dir.mkdir(parents=True, exist_ok=True)

    # ブログ画像名 → note画像名（複数コピー先あり）
    mapping = {
        "spec.png": ["intro.png", "features.png"],
        "merit.png": ["merit.png"],
        "demerit.png": ["demerit.png"],
        "summary.png": ["summary.png"],
    }

    copied = 0
    for src_name, dst_names in mapping.items():
        src = blog_src / src_name
        if src.exists():
            for dst_name in dst_names:
                dst = dest_dir / dst_name
                shutil.copy2(src, dst)
                copied += 1
                logger.info(f"  コピー: {src_name} → {dst_name}")

    if copied == 0:
        logger.warning(f"ブログ画像が見つかりません: {blog_src}")
        return None

    logger.info(f"ブログ画像を準備しました ({copied}ファイル): {dest_dir}")
    return str(dest_dir)


def process_slug(slug: str, converter: NoteConverter, config: dict,
                 dry_run: bool, client=None,
                 sakura_voice: bool = False,
                 with_illustrations: bool = False,
                 use_blog_images: bool = False,
                 eyecatch: str = None,
                 telegram_notify: bool = False) -> bool:
    """
    1記事を変換して投稿する

    Args:
        slug: 記事スラッグ
        converter: NoteConverter インスタンス
        config: 設定dict
        dry_run: Trueの場合は投稿せず変換結果を表示
        client: NoteClient インスタンス（dry_run=Falseの場合必須）
        sakura_voice: Trueの場合サクラ口調に変換
        with_illustrations: Trueの場合挿絵をインライン挿入
        use_blog_images: Trueの場合 public/images/posts/{slug}/ のブログ画像を流用
        eyecatch: アイキャッチ画像パス（省略可）
        telegram_notify: Trueの場合投稿後にTelegram通知

    Returns:
        成功した場合True
    """
    try:
        post_path = get_post_path(slug)
        md_content = post_path.read_text(encoding="utf-8")
        result = converter.convert(md_content, slug)

        # 区切り線（---）を除去
        body = strip_separator_lines(result["body"])

        # サクラ口調変換
        if sakura_voice:
            logger.info("サクラ口調変換を適用中...")
            body = convert_to_sakura_voice(body)

        # 挿絵ディレクトリ設定
        illustrations_dir = None
        if use_blog_images:
            # ブログの public/images/posts/{slug}/ 画像を流用
            logger.info("ブログ画像を流用して挿絵を準備します...")
            illustrations_dir = _prepare_blog_images_for_note(slug, config)
            with_illustrations = illustrations_dir is not None
            # ogImage を eyecatch として自動設定（未指定時）
            if not eyecatch:
                og_path = BLOG_ROOT / "public" / "images" / "og" / f"{slug}.png"
                if og_path.exists():
                    eyecatch = str(og_path)
                    logger.info(f"ogImageを自動eyecatch設定: {eyecatch}")
        elif with_illustrations:
            illust_base = config.get("illustrations_dir", "/tmp/note_illustrations")
            illustrations_dir = str(Path(illust_base) / slug)
            if not Path(illustrations_dir).exists() or not any(Path(illustrations_dir).glob("*.png")):
                logger.info(f"挿絵が未生成のため自動生成します: {slug}")
                import subprocess
                gen_script = Path(__file__).parent / "note_generate_illustrations.py"
                result_gen = subprocess.run(
                    ["python3", str(gen_script), "--slug", slug],
                    capture_output=True, text=True
                )
                if result_gen.returncode != 0:
                    logger.warning(f"挿絵自動生成に失敗（挿絵なしで続行）: {result_gen.stderr}")
                    illustrations_dir = None
                elif not Path(illustrations_dir).exists():
                    logger.warning(f"挿絵ディレクトリが存在しません: {illustrations_dir} （挿絵なしで続行）")
                    illustrations_dir = None

        # アイキャッチ自動検出（--eyecatch未指定時）
        if not eyecatch and illustrations_dir:
            auto_eyecatch = Path(illustrations_dir) / "eyecatch.png"
            if auto_eyecatch.exists():
                eyecatch = str(auto_eyecatch)
                logger.info(f"アイキャッチ自動検出: {eyecatch}")

        if dry_run:
            print("=" * 60)
            print(f"[DRY RUN] スラッグ: {slug}")
            print(f"タイトル: {result['title']}")
            print(f"ハッシュタグ: {result['hashtags']}")
            print(f"Canonical URL: {result['canonical_url']}")
            print(f"サクラ口調: {sakura_voice}")
            print(f"挿絵: {with_illustrations} (dir={illustrations_dir})")
            print(f"アイキャッチ: {eyecatch}")
            print("-" * 60)
            print(body[:500] + ("..." if len(body) > 500 else ""))
            print("=" * 60)
            return True

        # 実際に投稿
        publish_status = config.get("publish_status", "public")
        note_url = client.post_article(
            title=result["title"],
            body=body,
            hashtags=result["hashtags"],
            publish_status=publish_status,
            eyecatch_path=eyecatch,
            illustrations_dir=illustrations_dir,
        )
        record_posted(slug, note_url, config)
        logger.info(f"投稿完了: {slug} → {note_url}")

        # Telegram通知
        if telegram_notify:
            send_telegram_notification(slug, note_url)

        return True

    except FileNotFoundError as e:
        logger.error(str(e))
        return False
    except RuntimeError as e:
        logger.error(f"投稿失敗 ({slug}): {e}")
        return False
    except Exception as e:
        logger.error(f"予期しないエラー ({slug}): {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="ブログ記事をnote.comに転載するスクリプト"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--slug", help="転載する記事のスラッグ（ファイル名から.md除く）")
    group.add_argument("--all-new", action="store_true", help="未投稿の全記事を投稿")
    parser.add_argument("--dry-run", action="store_true",
                        help="実際に投稿せず変換結果を表示")
    parser.add_argument("--sakura-voice", action="store_true", default=True,
                        help="本文をサクラ口調に変換してから投稿（デフォルト: 有効）")
    parser.add_argument("--no-sakura-voice", action="store_false", dest="sakura_voice",
                        help="サクラ口調変換を無効化")
    parser.add_argument("--with-illustrations", action="store_true", default=True,
                        help="挿絵5枚をnote本文にインライン挿入（デフォルト: 有効）")
    parser.add_argument("--no-illustrations", action="store_false", dest="with_illustrations",
                        help="挿絵挿入を無効化")
    parser.add_argument("--blog-images", action="store_true", default=False,
                        help="public/images/posts/{slug}/ のブログ画像を挿絵として流用（SD生成不要）")
    parser.add_argument("--limit", type=int, default=0,
                        help="1回の実行で投稿する最大記事数（0=無制限、デフォルト: 0）")
    parser.add_argument("--eyecatch",
                        help="アイキャッチ画像パス（note投稿時に設定）")
    parser.add_argument("--telegram-notify", action="store_true", default=True,
                        help="投稿完了後にTelegram通知を送信（デフォルト: 有効）")
    parser.add_argument("--no-telegram-notify", action="store_false", dest="telegram_notify",
                        help="Telegram通知を無効化")
    args = parser.parse_args()

    # 設定読み込み
    try:
        config = load_config()
    except FileNotFoundError as e:
        logger.error(str(e))
        sys.exit(1)

    converter = NoteConverter(config)

    # クライアント初期化（dry-runでは不要）
    client = None
    if not args.dry_run:
        try:
            auth = load_auth_env(AUTH_ENV_FILE)
        except FileNotFoundError as e:
            logger.error(str(e))
            sys.exit(1)

        api_token = auth.get("NOTE_API_TOKEN", "")
        if api_token:
            logger.info("APIトークン認証（将来の公式API対応）")
            logger.warning("note公式APIは現在非公開。メール+パスワード認証を使用します。")

        email = auth.get("NOTE_EMAIL", "")
        password = auth.get("NOTE_PASSWORD", "")
        if not email or not password:
            logger.error("NOTE_EMAIL / NOTE_PASSWORD が設定されていません（config/note_auth.env）")
            sys.exit(1)

        client = NoteClient(email, password)

    # 投稿対象を決定
    if args.slug:
        slugs = [args.slug]
    else:
        slugs = get_unposted_slugs(config)
        if not slugs:
            logger.info("未投稿の記事はありません")
            return
        logger.info(f"未投稿記事: {len(slugs)}件")
        # --limit が指定されている場合は件数を制限
        if args.limit > 0 and len(slugs) > args.limit:
            logger.info(f"--limit {args.limit} により先頭{args.limit}件のみ処理します")
            slugs = slugs[:args.limit]

    # 投稿実行
    success_count = 0
    fail_count = 0
    for slug in slugs:
        ok = process_slug(
            slug, converter, config, args.dry_run, client,
            sakura_voice=args.sakura_voice,
            with_illustrations=args.with_illustrations,
            use_blog_images=args.blog_images,
            eyecatch=args.eyecatch,
            telegram_notify=args.telegram_notify,
        )
        if ok:
            success_count += 1
        else:
            fail_count += 1

    logger.info(f"完了: 成功={success_count}, 失敗={fail_count}")
    if fail_count > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
