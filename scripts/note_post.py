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
"""

import os
import sys
import logging
import argparse
import yaml
import re
import json
from pathlib import Path
from datetime import datetime, timezone

# パス設定
BLOG_ROOT = Path(__file__).parent.parent.resolve()
CONFIG_FILE = BLOG_ROOT / "config" / "note_post.yaml"
AUTH_ENV_FILE = BLOG_ROOT / "config" / "note_auth.env"
POSTS_DIR = BLOG_ROOT / "src" / "content" / "posts"

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# scripts/libをインポートパスに追加
sys.path.insert(0, str(Path(__file__).parent))
from lib.note_converter import NoteConverter


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
    """未投稿の記事スラッグ一覧を返す"""
    history = load_history(config)
    posted_slugs = {item["slug"] for item in history["posted"]}
    all_slugs = []
    for md_file in sorted(POSTS_DIR.glob("*.md")):
        slug = md_file.stem
        if slug not in posted_slugs:
            all_slugs.append(slug)
    return all_slugs


# ===== note.com 投稿 =====

class NoteClient:
    """
    note.com 内部API クライアント

    note.comは公式APIを公開していないため、ブラウザが使用する
    内部APIエンドポイントを利用する。
    認証: セッションクッキー（メールアドレス + パスワードでログイン）
    """

    BASE_URL = "https://note.com"
    API_BASE = "https://note.com/api/v2"

    def __init__(self, email: str, password: str):
        import requests
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
            "Origin": self.BASE_URL,
            "Referer": self.BASE_URL + "/",
        })
        self.email = email
        self.password = password
        self._logged_in = False

    def login(self) -> None:
        """note.comにログイン（セッションクッキー取得）"""
        import requests

        # まずCSRFトークンを取得
        resp = self.session.get(self.BASE_URL + "/login")
        resp.raise_for_status()

        # ログインAPIを呼び出し
        login_url = f"{self.API_BASE}/session"
        payload = {
            "login": self.email,
            "password": self.password,
        }
        resp = self.session.post(login_url, json=payload)
        if resp.status_code not in (200, 201):
            raise RuntimeError(
                f"ログイン失敗: HTTP {resp.status_code}\n"
                f"認証情報を確認してください（config/note_auth.env）"
            )
        logger.info("note.comにログインしました")
        self._logged_in = True

    def post_article(self, title: str, body: str, hashtags: list[str],
                     publish_status: str = "public") -> str:
        """
        記事を投稿して投稿URLを返す

        Args:
            title: 記事タイトル
            body: 本文（Markdown）
            hashtags: ハッシュタグリスト
            publish_status: "public" または "draft"

        Returns:
            投稿されたnote記事のURL
        """
        if not self._logged_in:
            self.login()

        # noteの内部APIでテキスト記事を投稿
        post_url = f"{self.API_BASE}/text_notes"
        payload = {
            "body": body,
            "name": title,
            "hashtag_list": hashtags,
            "status": publish_status,
        }
        resp = self.session.post(post_url, json=payload)
        if resp.status_code not in (200, 201):
            raise RuntimeError(
                f"投稿失敗: HTTP {resp.status_code}\n"
                f"レスポンス: {resp.text[:200]}"
            )

        data = resp.json()
        # レスポンスからnote URLを取得
        note_key = data.get("data", {}).get("key", "")
        user_urlname = data.get("data", {}).get("user", {}).get("urlname", "")
        if note_key and user_urlname:
            return f"{self.BASE_URL}/{user_urlname}/n/{note_key}"
        return f"{self.BASE_URL}/"


# ===== メイン処理 =====

def process_slug(slug: str, converter: NoteConverter, config: dict,
                 dry_run: bool, client=None) -> bool:
    """
    1記事を変換して投稿する

    Returns:
        成功した場合True
    """
    try:
        post_path = get_post_path(slug)
        md_content = post_path.read_text(encoding="utf-8")
        result = converter.convert(md_content, slug)

        if dry_run:
            print("=" * 60)
            print(f"[DRY RUN] スラッグ: {slug}")
            print(f"タイトル: {result['title']}")
            print(f"ハッシュタグ: {result['hashtags']}")
            print(f"Canonical URL: {result['canonical_url']}")
            print("-" * 60)
            print(result["body"][:500] + ("..." if len(result["body"]) > 500 else ""))
            print("=" * 60)
            return True

        # 実際に投稿
        publish_status = config.get("publish_status", "public")
        note_url = client.post_article(
            title=result["title"],
            body=result["body"],
            hashtags=result["hashtags"],
            publish_status=publish_status,
        )
        record_posted(slug, note_url, config)
        logger.info(f"投稿完了: {slug} → {note_url}")
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

        # APIトークンがあればトークン認証、なければメール+パスワード
        api_token = auth.get("NOTE_API_TOKEN", "")
        if api_token:
            logger.info("APIトークン認証（将来の公式API対応）")
            # 公式APIが公開された場合はここに実装
            logger.warning("note公式APIは現在非公開。メール+パスワード認証を使用します。")

        email = auth.get("NOTE_EMAIL", "")
        password = auth.get("NOTE_PASSWORD", "")
        if not email or not password:
            logger.error("NOTE_EMAIL / NOTE_PASSWORD が設定されていません（config/note_auth.env）")
            sys.exit(1)

        client = NoteClient(email, password)
        try:
            client.login()
        except RuntimeError as e:
            logger.error(str(e))
            sys.exit(1)

    # 投稿対象を決定
    if args.slug:
        slugs = [args.slug]
    else:
        slugs = get_unposted_slugs(config)
        if not slugs:
            logger.info("未投稿の記事はありません")
            return
        logger.info(f"未投稿記事: {len(slugs)}件")

    # 投稿実行
    success_count = 0
    fail_count = 0
    for slug in slugs:
        ok = process_slug(slug, converter, config, args.dry_run, client)
        if ok:
            success_count += 1
        else:
            fail_count += 1

    logger.info(f"完了: 成功={success_count}, 失敗={fail_count}")
    if fail_count > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
