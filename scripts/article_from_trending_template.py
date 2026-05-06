#!/usr/bin/env python3
"""
cmd_358-D: 売れ筋選択商品 → 記事化cmd YAML雛形生成
使い方:
  python3 scripts/article_from_trending_template.py --indices 1,3
  python3 scripts/article_from_trending_template.py --indices 1,3 --output /tmp/cmd_draft.yaml

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


def main():
    parser = argparse.ArgumentParser(
        description="trending_today.yaml + 選択番号 → 記事化cmd YAML雛形生成"
    )
    parser.add_argument("--indices", required=True, help="選択番号カンマ区切り (例: 1,3)")
    parser.add_argument("--output", help="出力先ファイルパス（省略時はstdout）")
    args = parser.parse_args()

    indices = [int(x.strip()) for x in args.indices.split(",") if x.strip().isdigit()]

    if not TODAY_FILE.exists():
        print("[ERROR] trending_today.yaml が見つかりません", file=sys.stderr)
        sys.exit(1)

    with open(TODAY_FILE) as f:
        today_data = yaml.safe_load(f)
    top5 = today_data.get("top5", [])

    selected = []
    for idx in indices:
        if 1 <= idx <= len(top5):
            selected.append(top5[idx - 1])

    if not selected:
        print("[ERROR] 有効な商品が選択されていません", file=sys.stderr)
        sys.exit(1)

    cmd_id = get_next_cmd_id()
    next_publish = get_next_publish_date()

    commands = []
    for i, item in enumerate(selected):
        name = item.get("name", "")[:40]
        price = item.get("price", 0)
        url = item.get("url", "")
        cat = item.get("category", "")
        rank = item.get("rank", "?")
        score = item.get("score", 0)

        # publishDateを1本ずつズラす（1日1本ルール）
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
                    f"publishDate: {publish_date}（1日1本ルール・重複禁止）",  # publishDate
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

    output_yaml = yaml.dump(commands, allow_unicode=True, default_flow_style=False)

    if args.output:
        Path(args.output).write_text(output_yaml)
        print(f"[article_template] 雛形 → {args.output}")
        print(f"[article_template] 次のpublishDate開始: {next_publish}")
    else:
        print("# ===== 記事化cmd YAML雛形 =====")
        print("# 将軍が内容確認の上 shogun_to_karo.yaml に追記→家老へ発令すること")
        print(f"# 次のpublishDate開始: {next_publish}")
        print(output_yaml)


if __name__ == "__main__":
    main()
