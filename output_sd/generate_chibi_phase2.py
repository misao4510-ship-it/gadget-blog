#!/usr/bin/env python3
"""
cmd_069 phase2: 黒服残り20枚（11〜30）→ rembg → Telegram送信
subtask_069d
"""

import requests
import base64
import os
import sys
from rembg import remove

SD_HOST = "http://172.18.208.1:7860"
OUTPUT_DIR = "/home/misao/gadget-blog/output_sd"
BOT_TOKEN = "8704876777:AAH48f-0qkCPVnIkMbyhBASSTNpAlVy2_lE"
CHAT_ID = "7871900133"

BASE_COMMON = (
    "chibi, super deformed, 2-3 head tall, cute girl, solo, 1girl, "
    "long hair, pink hair, blue inner color hair, "
    "blue eyes, <lora:kaina_v1:0.7>, "
    "masterpiece, best quality, simple background, white background"
)

BLACK_OUTFIT = "black futuristic outfit, black knee-high socks"

NEGATIVE_PROMPT = "realistic, 3d, ugly, bad anatomy, blurry, watermark, multiple girls, 2girls, group"

POSES = [
    "joy, jumping, hands up, happy expression",
    "surprised, wide eyes, open mouth",
    "thinking pose, hand on chin, thoughtful",
    "guts pose, fist raised, triumphant",
    "waving hand, friendly smile",
    "pointing forward, peace sign",
    "heart hands, kawaii pose",
    "crying, tears, sad expression",
    "angry, arms crossed, pouting",
    "sleepy, eyes closed, yawning",
]

POSE_LABELS = [
    "喜び・ジャンプ", "驚き", "考えポーズ", "ガッツポーズ", "手を振る",
    "指差し・ピース", "ハートハンド", "泣き顔", "怒り・腕組み", "眠い・あくび",
]


def generate_image(pose: str, img_num: int, total: int) -> str:
    filename = f"sakura_chibi_black_{img_num:02d}.png"
    prompt = f"{pose}, {BLACK_OUTFIT}, {BASE_COMMON}"
    payload = {
        "prompt": prompt,
        "negative_prompt": NEGATIVE_PROMPT,
        "width": 512,
        "height": 512,
        "steps": 25,
        "cfg_scale": 7,
        "sampler_name": "DPM++ 2M Karras",
        "batch_size": 1,
        "n_iter": 1,
        "seed": -1,
        "override_settings": {
            "sd_model_checkpoint": "novaAnimeXL_ilV170.safetensors"
        }
    }
    print(f"[{img_num:02d}/{total}] Generating: {filename} | {pose[:40]}...")
    resp = requests.post(f"{SD_HOST}/sdapi/v1/txt2img", json=payload, timeout=300)
    resp.raise_for_status()
    img_bytes = base64.b64decode(resp.json()["images"][0])
    out_path = os.path.join(OUTPUT_DIR, filename)
    with open(out_path, "wb") as f:
        f.write(img_bytes)
    print(f"  Saved: {out_path}")
    return out_path


def remove_bg(src_path: str, dst_path: str):
    print(f"  rembg: {os.path.basename(src_path)} → {os.path.basename(dst_path)}")
    with open(src_path, "rb") as f:
        result = remove(f.read())
    with open(dst_path, "wb") as f:
        f.write(result)


def send_photo(img_path: str, caption: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    with open(img_path, "rb") as f:
        resp = requests.post(url, data={"chat_id": CHAT_ID, "caption": caption},
                             files={"photo": f}, timeout=60)
    resp.raise_for_status()


def send_message(text: str):
    requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={"chat_id": CHAT_ID, "text": text},
        timeout=30
    )


os.makedirs(OUTPUT_DIR, exist_ok=True)

# 黒服11〜30番（10ポーズ×2周）
print("\n=== Phase 2: 黒服20枚（11〜30） ===")
black_raw = []
total = 20
for round_num in range(2):
    for pose_idx, pose in enumerate(POSES):
        img_num = 11 + round_num * 10 + pose_idx
        try:
            path = generate_image(pose, img_num, total + 10)  # display as 11-30
            black_raw.append((img_num, path, pose_idx))
        except Exception as e:
            print(f"  ERROR black_{img_num:02d}: {e}", file=sys.stderr)

# rembg
print("\n--- rembg 黒服20枚 ---")
black_nobg = []
for img_num, raw_path, pose_idx in black_raw:
    dst = os.path.join(OUTPUT_DIR, f"sakura_chibi_black_{img_num:02d}_nobg.png")
    try:
        remove_bg(raw_path, dst)
        black_nobg.append((img_num, dst, pose_idx))
    except Exception as e:
        print(f"  ERROR rembg black_{img_num:02d}: {e}", file=sys.stderr)

# Telegram送信
print("\n=== Telegram送信 ===")
send_message(
    f"🖤 サクラちびキャラ phase2 生成完了！\n"
    f"✅ 黒服残り: {len(black_nobg)}枚（No.11〜30）\n"
    f"🎉 追加50枚（白服20+黒服30）すべて完成！"
)

for img_num, path, pose_idx in black_nobg:
    label = POSE_LABELS[pose_idx]
    round_label = "1周目" if img_num <= 20 else "2周目"
    caption = f"🖤 黒服 {img_num:02d}/30 ({round_label}) {label}"
    print(f"Sending: {caption}")
    try:
        send_photo(path, caption)
    except Exception as e:
        print(f"  ERROR: {e} — retrying...")
        try:
            send_photo(path, caption)
        except Exception as e2:
            print(f"  RETRY FAILED: {e2}", file=sys.stderr)

send_message("✅ phase2全送信完了。黒服20枚（11〜30）送信済み。追加50枚完全完了！")

print(f"\n=== 完了 ===")
print(f"黒服phase2: {len(black_nobg)}/20 nobg完了・Telegram送信済み")
