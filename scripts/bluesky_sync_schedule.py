#!/usr/bin/env python3
"""
X投稿スケジュールからBluesky投稿スケジュールを生成するスクリプト

x_scheduled.json の内容をベースに bluesky_scheduled.json を生成する。
投稿時刻はXよりずらす（+23分）。
同じサクラ画像を共有。

Usage:
    python3 scripts/bluesky_sync_schedule.py
"""

import json
from pathlib import Path
from datetime import datetime

BLOG_ROOT = Path(__file__).parent.parent.resolve()
X_SCHEDULE = BLOG_ROOT / "data" / "x_scheduled.json"
BS_SCHEDULE = BLOG_ROOT / "data" / "bluesky_scheduled.json"

# Bluesky投稿時刻（X投稿より23分後）
SLOT_TIMES = {1: "07:30", 2: "12:30", 3: "21:00"}


def main():
    if not X_SCHEDULE.exists():
        print("x_scheduled.json が見つかりません")
        return

    x_data = json.loads(X_SCHEDULE.read_text())
    today = x_data.get("date", datetime.now().strftime("%Y-%m-%d"))

    bs_slots = []
    for slot in x_data.get("slots", []):
        slot_num = slot["slot"]
        slug = slot["slug"]
        # X投稿のURLをブログURLから取得
        url = f"https://gadget-blog-dxq.pages.dev/posts/{slug}/"

        bs_slots.append({
            "slot": slot_num,
            "time": SLOT_TIMES.get(slot_num, ""),
            "slug": slug,
            "title": slot.get("title", ""),
            "text": slot["text"],   # X投稿と同じサクラ口調テキスト
            "image": slot.get("image", ""),  # 同じサクラ画像を共有
            "url": url,
            "status": "pending",
        })

    bs_data = {"date": today, "slots": bs_slots}

    BS_SCHEDULE.parent.mkdir(parents=True, exist_ok=True)
    BS_SCHEDULE.write_text(json.dumps(bs_data, ensure_ascii=False, indent=2))
    print(f"Bluesky予約データ生成完了: {BS_SCHEDULE}")
    print(json.dumps(bs_data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
