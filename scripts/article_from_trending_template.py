#!/usr/bin/env python3
"""
cmd_358-D: 売れ筋選択商品 → 記事化cmd YAML雛形生成
使い方:
  python3 scripts/article_from_trending_template.py --indices 1,3
  python3 scripts/article_from_trending_template.py --indices 1,3 --output /tmp/cmd_draft.yaml

YouTube版 (cmd_359-F):
  python3 scripts/article_from_trending_template.py --source youtube --indices 1,2
  python3 scripts/article_from_trending_template.py --source youtube --indices 1 --output /tmp/cmd_draft.yaml

注意:
  - publishDate を使用すること（pubDate不可）
  - x_scheduled.json の status は 'pending' 必須（'scheduled' はスキップされるバグあり）
"""
import argparse
import json
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import yaml

BLOG_DIR = Path(__file__).parent.parent
TODAY_FILE = BLOG_DIR / "data" / "trending_today.yaml"
YOUTUBE_TODAY_FILE = BLOG_DIR / "data" / "youtube_today.yaml"
POSTS_DIR = BLOG_DIR / "src" / "content" / "posts"


def get_next_cmd_id() -> str:
    karo_file = Path("/mnt/c/tools/multi-agent-shogun/queue/shogun_to_karo.yaml")
    if not karo_file.exists():
        return "cmd_???"
    content = karo_file.read_text()
    ids = re.findall(r"^- id: (cmd_\d+)", content, re.MULTILINE)
    if not ids:
        return "cmd_???"
    last_num = int(ids[-1].split("_")[1])
    return f"cmd_{last_num + 1}"


def get_next_publish_date() -> str:
    """既存記事の最新publishDateの翌日を返す（1日1本ルール）"""
    dates = []
    if POSTS_DIR.exists():
        for md_file in POSTS_DIR.glob("*.md"):
            content = md_file.read_text(errors="ignore")
            m = re.search(r'^publishDate:\s*["\']?(\d{4}-\d{2}-\d{2})["\']?', content, re.MULTILINE)
            if m:
                dates.append(date.fromisoformat(m.group(1)))
    if dates:
        next_date = max(dates) + timedelta(days=1)
    else:
        next_date = date.today()
    # 今日以降であること
    if next_date < date.today():
        next_date = date.today()
    return next_date.isoformat()


def build_trending_commands(indices, today_data, cmd_id, next_publish):
    top5 = today_data.get("top5", [])
    commands = []
    for i, idx in enumerate(indices):
        if not (1 <= idx <= len(top5)):
            continue
        item = top5[idx - 1]
        name = item.get("name", "")[:40]
        price = item.get("price", 0)
        url = item.get("url", "")
        cat = item.get("category", "")
        rank = item.get("rank", "?")
        score = item.get("score", 0)

        publish_date = (
            date.fromisoformat(next_publish) + timedelta(days=i)
        ).isoformat()

        commands.append(
            {
                "id": cmd_id,
                "timestamp": datetime.now().isoformat(),
                "north_star": f"{name} の比較記事で商品認知→購買を促進。アフィリ報酬獲得。",
                "purpose": f"trending検出商品 ({cat} 楽天rank:{rank}): {name} の3ショップ比較記事を作成。",
                "acceptance_criteria": [
                    f"{name} の比較記事 1本（2000字以上・サクラ口調・PR表記）",
                    "Amazon/楽天/Yahoo! 3ショップのもしもアフィリリンク掲載",
                    "サクラ商品シーン画像 OG(1200x624) + 挿絵(1024x1024) 4〜5枚",
                    f"publishDate: {publish_date}（1日1本ルール・重複禁止）",
                    "x_scheduled.json へ status=pending で投稿予約（scheduledはスキップバグあり）",
                    "gadget-blog git commit + push + Cloudflare Pages deploy",
                ],
                "command": (
                    f"# 【要確認】以下の商品URLから記事を作成せよ\n"
                    f"# 商品名: {name}\n"
                    f"# 価格: ¥{price:,}\n"
                    f"# カテゴリ: {cat}\n"
                    f"# 楽天URL: {url}\n"
                    f"# ↑ 将軍が楽天・Yahoo!リンクをもしも経由に変換して提供すること\n"
                    f"# Amazon ASINは商品URLから特定 or もしも検索で補完\n"
                    f"# publishDate: {publish_date}（frontmatterに必ずこの形式で設定）\n"
                    f"\n"
                    f"既存の3ショップ比較記事Engineを流用して記事化。\n"
                    f"サクラ口調・PR表記・画像生成・publishDate連番・SNS投稿予約まで一気通貫。"
                ),
                "project": "gadget-blog",
                "priority": "high",
                "status": "pending",
                "source": "trending_auto",
                "trending_date": today_data.get("date"),
                "trending_score": score,
                "rakuten_url": url,
            }
        )
    return commands


def build_youtube_commands(indices, today_data, cmd_id, next_publish):
    videos = today_data.get("videos", [])
    commands = []
    for i, idx in enumerate(indices):
        if not (1 <= idx <= len(videos)):
            continue
        video = videos[idx - 1]
        title = video.get("title", "")[:60]
        channel_name = video.get("channel_name", "")
        channel_id = video.get("channel_id", "")
        video_id = video.get("video_id", "")
        product_name = video.get("product_name", title)[:40]
        price = video.get("price", 0)
        cat = video.get("category", "")
        amazon_url = video.get("amazon_url", "")

        publish_date = (
            date.fromisoformat(next_publish) + timedelta(days=i)
        ).isoformat()

        channel_url = f"https://www.youtube.com/channel/{channel_id}" if channel_id else ""

        commands.append(
            {
                "id": cmd_id,
                "timestamp": datetime.now().isoformat(),
                "north_star": f"{product_name} のYouTuber紹介記事で商品認知→購買を促進。アフィリ報酬獲得。",
                "purpose": (
                    f"YouTuber紹介商品: {product_name}（{cat}）の紹介記事を作成。"
                    f"YouTube動画埋め込み付き。元動画: {title}"
                ),
                "acceptance_criteria": [
                    f"{product_name} の紹介記事 1本（2000字以上・サクラ口調・PR表記）",
                    "Amazon/楽天/Yahoo! 3ショップのもしもアフィリリンク掲載",
                    f"frontmatterに youtube_video_id: {video_id} を設定",
                    f"frontmatterに youtube_channel_name: {channel_name} を設定",
                    f"frontmatterに youtube_channel_url: {channel_url} を設定",
                    "サクラ商品シーン画像 OG(1200x624) + 挿絵(1024x1024) 4〜5枚",
                    f"publishDate: {publish_date}（1日1本ルール・重複禁止）",
                    "x_scheduled.json へ status=pending で投稿予約（scheduledはスキップバグあり）",
                    "gadget-blog git commit + push + Cloudflare Pages deploy",
                ],
                "command": (
                    f"# 【YouTube紹介商品記事】以下の情報から記事を作成せよ\n"
                    f"# 商品名: {product_name}\n"
                    f"# 動画タイトル: {title}\n"
                    f"# チャンネル名: {channel_name}\n"
                    f"# YouTube動画ID: {video_id}\n"
                    f"# YouTube動画URL: https://www.youtube.com/watch?v={video_id}\n"
                    f"# チャンネルURL: {channel_url}\n"
                    f"# カテゴリ: {cat}\n"
                    f"# 参考価格: ¥{price:,}\n"
                    f"# AmazonURL: {amazon_url}\n"
                    f"# publishDate: {publish_date}（frontmatterに必ずこの形式で設定）\n"
                    f"\n"
                    f"frontmatterに youtube_video_id / youtube_channel_name / youtube_channel_url を必ず設定。\n"
                    f"記事末尾に動画が自動埋め込まれる。\n"
                    f"サクラ口調・PR表記・画像生成・publishDate連番・SNS投稿予約まで一気通貫。"
                ),
                "project": "gadget-blog",
                "priority": "high",
                "status": "pending",
                "source": "youtube_auto",
                "youtube_video_id": video_id,
                "youtube_channel_name": channel_name,
                "youtube_channel_url": channel_url,
                "youtube_date": today_data.get("date"),
                "amazon_url": amazon_url,
            }
        )
    return commands


def main():
    parser = argparse.ArgumentParser(
        description="trending_today.yaml / youtube_today.yaml + 選択番号 → 記事化cmd YAML雛形生成"
    )
    parser.add_argument("--indices", required=True, help="選択番号カンマ区切り (例: 1,3)")
    parser.add_argument("--source", default="trending", choices=["trending", "youtube"],
                        help="データソース: trending (default) または youtube")
    parser.add_argument("--output", help="出力先ファイルパス（省略時はstdout）")
    args = parser.parse_args()

    indices = [int(x.strip()) for x in args.indices.split(",") if x.strip().isdigit()]

    if args.source == "youtube":
        data_file = YOUTUBE_TODAY_FILE
    else:
        data_file = TODAY_FILE

    if not data_file.exists():
        print(f"[ERROR] {data_file.name} が見つかりません", file=sys.stderr)
        sys.exit(1)

    with open(data_file) as f:
        today_data = yaml.safe_load(f)

    cmd_id = get_next_cmd_id()
    next_publish = get_next_publish_date()

    if args.source == "youtube":
        commands = build_youtube_commands(indices, today_data, cmd_id, next_publish)
    else:
        commands = build_trending_commands(indices, today_data, cmd_id, next_publish)

    if not commands:
        print("[ERROR] 有効な商品が選択されていません", file=sys.stderr)
        sys.exit(1)

    output_yaml = yaml.dump(commands, allow_unicode=True, default_flow_style=False)

    if args.output:
        Path(args.output).write_text(output_yaml)
        print(f"[article_template] 雛形 → {args.output}")
        print(f"[article_template] 次のpublishDate開始: {next_publish}")
        print(f"[article_template] ソース: {args.source}")
    else:
        print("# ===== 記事化cmd YAML雛形 =====")
        print("# 将軍が内容確認の上 shogun_to_karo.yaml に追記→家老へ発令すること")
        print(f"# 次のpublishDate開始: {next_publish}")
        print(f"# ソース: {args.source}")
        print(output_yaml)


if __name__ == "__main__":
    main()
