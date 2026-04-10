#!/usr/bin/env python3
"""Send sakura chibi v2 nobg images to Telegram"""

import os
import requests

BOT_TOKEN = "8704876777:AAH48f-0qkCPVnIkMbyhBASSTNpAlVy2_lE"
CHAT_ID = "7871900133"
OUTPUT_DIR = "/home/misao/gadget-blog/output_sd"

POSE_LABELS = [
    "01: 喜び・ジャンプ",
    "02: 驚き・目を見開く",
    "03: 考えポーズ",
    "04: ガッツポーズ",
    "05: 手を振る",
    "06: 指差し・ピース",
    "07: ハートハンド",
    "08: 泣き顔",
    "09: 怒り・腕組み",
    "10: 眠い・あくび",
]

def send_photo(img_path: str, caption: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    with open(img_path, "rb") as f:
        resp = requests.post(url, data={"chat_id": CHAT_ID, "caption": caption}, files={"photo": f}, timeout=60)
    resp.raise_for_status()
    return resp.json()

# Send intro message
requests.post(
    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
    json={"chat_id": CHAT_ID, "text": "🌸 サクラちびキャラv2（ロングヘア・ピンク+青インナーカラー）10枚 生成完了！"},
    timeout=30
)

for i, label in enumerate(POSE_LABELS, start=1):
    img_path = os.path.join(OUTPUT_DIR, f"sakura_chibi_v2_{i:02d}_nobg.png")
    if not os.path.exists(img_path):
        print(f"MISSING: {img_path}")
        continue
    print(f"Sending {i:02d}/10: {label}...")
    try:
        send_photo(img_path, f"🌸 サクラちびキャラv2 {label}")
        print(f"  OK")
    except Exception as e:
        print(f"  ERROR: {e}")

print("Telegram送信完了。")
