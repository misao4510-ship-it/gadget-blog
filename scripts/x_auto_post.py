#!/usr/bin/env python3
"""
X (Twitter) 自動投稿スクリプト
過去記事をランダムに選んでXに定期投稿する

Usage:
    python3 scripts/x_auto_post.py           # 実際に投稿
    python3 scripts/x_auto_post.py --dry-run  # 投稿内容確認のみ（投稿しない）
"""

import os
import sys
import json
import random
import logging
import argparse
import yaml
from pathlib import Path
from datetime import datetime, timezone
import re
import tweepy

# ===== パス設定 =====
BLOG_ROOT = Path(__file__).parent.parent.resolve()
CONFIG_FILE = BLOG_ROOT / "config" / "x_auto_post.yaml"
HISTORY_FILE = BLOG_ROOT / "data" / "x_post_history.json"
AUTH_ENV_FILE = Path("/mnt/c/tools/multi-agent-shogun/config/x_auth.env")
POSTS_DIR = BLOG_ROOT / "src" / "content" / "posts"

# ===== ログ設定 =====
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger(__name__)


def load_env(env_file: Path) -> dict:
    """環境変数ファイルを読み込む（ハードコード禁止）"""
    env = {}
    if not env_file.exists():
        raise FileNotFoundError(f"認証ファイルが見つかりません: {env_file}")
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                env[key.strip()] = value.strip()
    return env


def load_config() -> dict:
    """設定ファイルを読み込む"""
    if not CONFIG_FILE.exists():
        raise FileNotFoundError(f"設定ファイルが見つかりません: {CONFIG_FILE}")
    with open(CONFIG_FILE) as f:
        return yaml.safe_load(f)


def load_history() -> dict:
    """投稿履歴を読み込む"""
    if not HISTORY_FILE.exists():
        return {"posts": []}
    with open(HISTORY_FILE) as f:
        return json.load(f)


def save_history(history: dict):
    """投稿履歴を保存する"""
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def parse_frontmatter(md_file: Path) -> dict | None:
    """Markdownファイルのfrontmatterをパースしてメタデータを返す"""
    content = md_file.read_text(encoding="utf-8")
    # YAMLフロントマターを抽出
    match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return None
    try:
        meta = yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        return None

    if not meta:
        return None

    # draftをスキップ
    if meta.get("draft", False):
        return None

    # slugはファイル名から生成
    slug = md_file.stem
    meta["slug"] = slug
    return meta


def load_articles() -> list[dict]:
    """全記事のメタデータを読み込む"""
    articles = []
    for md_file in sorted(POSTS_DIR.glob("*.md")):
        meta = parse_frontmatter(md_file)
        if meta:
            articles.append(meta)
    logger.info(f"記事読み込み完了: {len(articles)}件")
    return articles


def get_category_hashtags(meta: dict, config: dict) -> str:
    """カテゴリに対応するハッシュタグを返す"""
    hashtags_map = config.get("category_hashtags", {})
    default = hashtags_map.get("default", "#ガジェット #レビュー")

    # categoryフィールドを確認
    category = meta.get("category", "")
    subcategory = meta.get("subcategory", "")
    post_type = meta.get("type", "")

    tags_set = set()

    for key in [category, subcategory, post_type]:
        if key and key in hashtags_map:
            for tag in hashtags_map[key].split():
                tags_set.add(tag)

    if not tags_set:
        return default

    return " ".join(sorted(tags_set))


def build_post_text(article: dict, config: dict) -> str:
    """投稿テキストを生成する"""
    title = article.get("title", "記事タイトル")
    slug = article["slug"]
    base_url = config["post_format"]["base_url"].rstrip("/")
    url = f"{base_url}/{slug}/"
    category_tags = get_category_hashtags(article, config)

    text = f"📝 {title}\n{url}\n{category_tags}"
    return text


def select_article(articles: list[dict], history: dict, config: dict) -> dict | None:
    """投稿する記事を選択する（重複防止・除外ルール適用）"""
    exclude_count = config.get("recent_exclude_count", 10)
    exclude_slugs = set(config.get("exclude_slugs", []))
    exclude_categories = set(config.get("exclude_categories", []))

    # 直近N件の投稿済みスラッグを除外
    recent_posts = history.get("posts", [])
    recent_slugs = set(p["slug"] for p in recent_posts[-exclude_count:])

    candidates = []
    for article in articles:
        slug = article["slug"]
        category = article.get("category", "")
        subcategory = article.get("subcategory", "")

        # 除外チェック
        if slug in exclude_slugs:
            continue
        if slug in recent_slugs:
            continue
        if category in exclude_categories or subcategory in exclude_categories:
            continue

        candidates.append(article)

    if not candidates:
        # 全記事が除外対象の場合、履歴をリセットして再選択
        logger.warning("候補記事なし（全記事投稿済み）。履歴をリセットして再選択します。")
        candidates = [
            a for a in articles
            if a["slug"] not in exclude_slugs
        ]

    if not candidates:
        logger.error("投稿可能な記事がありません")
        return None

    return random.choice(candidates)


def post_to_x(text: str, env: dict) -> dict:
    """X APIに投稿する（OAuth 1.0a User Context）"""
    client = tweepy.Client(
        consumer_key=env["X_API_KEY"],
        consumer_secret=env["X_API_KEY_SECRET"],
        access_token=env["X_ACCESS_TOKEN"],
        access_token_secret=env["X_ACCESS_TOKEN_SECRET"],
    )
    response = client.create_tweet(text=text)
    return response.data


def record_post(history: dict, article: dict, tweet_id: str):
    """投稿履歴を記録する"""
    entry = {
        "slug": article["slug"],
        "title": article.get("title", ""),
        "tweet_id": tweet_id,
        "posted_at": datetime.now(timezone.utc).isoformat(),
    }
    history.setdefault("posts", []).append(entry)


def main():
    parser = argparse.ArgumentParser(description="X 自動投稿スクリプト")
    parser.add_argument("--dry-run", action="store_true", help="投稿せずにテキストのみ表示")
    args = parser.parse_args()

    # 設定・認証・履歴読み込み
    try:
        config = load_config()
    except Exception as e:
        logger.error(f"設定ファイル読み込みエラー: {e}")
        sys.exit(1)

    try:
        env = load_env(AUTH_ENV_FILE)
    except Exception as e:
        logger.error(f"認証ファイル読み込みエラー: {e}")
        sys.exit(1)

    history = load_history()

    # 記事一覧取得
    articles = load_articles()
    if not articles:
        logger.error("記事が見つかりません")
        sys.exit(1)

    # 記事選択
    article = select_article(articles, history, config)
    if article is None:
        sys.exit(1)

    # 投稿テキスト生成
    text = build_post_text(article, config)

    logger.info(f"選択記事: {article['slug']}")
    logger.info(f"投稿テキスト:\n{text}")

    if args.dry_run:
        logger.info("[DRY RUN] 投稿をスキップしました")
        return

    # X に投稿
    try:
        response = post_to_x(text, env)
        tweet_id = str(response.get("id", "unknown"))
        logger.info(f"投稿成功: tweet_id={tweet_id}")
    except tweepy.TweepyException as e:
        logger.error(f"X API エラー: {e}")
        if hasattr(e, "response") and e.response is not None:
            logger.error(f"レスポンス: {e.response.text}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"予期しないエラー: {e}")
        sys.exit(1)

    # 履歴保存
    record_post(history, article, tweet_id)
    save_history(history)
    logger.info(f"履歴保存完了: {HISTORY_FILE}")


if __name__ == "__main__":
    main()
