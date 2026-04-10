#!/usr/bin/env python3
"""
cmd_069 phase1: 白服20枚 + 黒服10枚 = 30枚生成 → rembg → Telegram送信
subtask_069c
"""

import requests
import base64
import json
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

WHITE_OUTFIT = "white futuristic outfit, knee-high socks"
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


def generate_image(pose: str, outfit: str, index: int, total: int, out_filename: str) -> str:
    prompt = f"{pose}, {outfit}, {BASE_COMMON}"
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
    print(f"[{index:02d}/{total}] Generating: {out_filename} | {pose[:40]}...")
    resp = requests.post(f"{SD_HOST}/sdapi/v1/txt2img", json=payload, timeout=300)
    resp.raise_for_status()

    data = resp.json()
    img_bytes = base64.b64decode(data["images"][0])
    out_path = os.path.join(OUTPUT_DIR, out_filename)
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

# ─── Phase 1-A: 白服20枚（10ポーズ×2周）─────────────────────────────────
print("\n=== Phase 1-A: 白服20枚 ===")
white_raw = []
total_white = 20
for round_num in range(2):
    for pose_idx, pose in enumerate(POSES):
        img_num = round_num * 10 + pose_idx + 1
        filename = f"sakura_chibi_white_{img_num:02d}.png"
        try:
            path = generate_image(pose, WHITE_OUTFIT, img_num, total_white, filename)
            white_raw.append((img_num, path, pose_idx))
        except Exception as e:
            print(f"  ERROR white_{img_num:02d}: {e}", file=sys.stderr)

# rembg 白服
print("\n--- rembg 白服20枚 ---")
white_nobg = []
for img_num, raw_path, pose_idx in white_raw:
    dst = os.path.join(OUTPUT_DIR, f"sakura_chibi_white_{img_num:02d}_nobg.png")
    try:
        remove_bg(raw_path, dst)
        white_nobg.append((img_num, dst, pose_idx))
    except Exception as e:
        print(f"  ERROR rembg white_{img_num:02d}: {e}", file=sys.stderr)

# ─── Phase 1-B: 黒服10枚（10ポーズ×1周）─────────────────────────────────
print("\n=== Phase 1-B: 黒服10枚 ===")
black_raw = []
total_black = 10
for pose_idx, pose in enumerate(POSES):
    img_num = pose_idx + 1
    filename = f"sakura_chibi_black_{img_num:02d}.png"
    try:
        path = generate_image(pose, BLACK_OUTFIT, img_num, total_black, filename)
        black_raw.append((img_num, path, pose_idx))
    except Exception as e:
        print(f"  ERROR black_{img_num:02d}: {e}", file=sys.stderr)

# rembg 黒服
print("\n--- rembg 黒服10枚 ---")
black_nobg = []
for img_num, raw_path, pose_idx in black_raw:
    dst = os.path.join(OUTPUT_DIR, f"sakura_chibi_black_{img_num:02d}_nobg.png")
    try:
        remove_bg(raw_path, dst)
        black_nobg.append((img_num, dst, pose_idx))
    except Exception as e:
        print(f"  ERROR rembg black_{img_num:02d}: {e}", file=sys.stderr)

# ─── Telegram送信 ─────────────────────────────────────────────────────────
print("\n=== Telegram送信 ===")
send_message(
    f"🌸 サクラちびキャラ phase1 生成完了！\n"
    f"✅ 白服: {len(white_nobg)}枚\n"
    f"✅ 黒服: {len(black_nobg)}枚\n"
    f"計: {len(white_nobg)+len(black_nobg)}枚"
)

# 白服送信
for img_num, path, pose_idx in white_nobg:
    label = POSE_LABELS[pose_idx]
    round_label = "1周目" if img_num <= 10 else "2周目"
    caption = f"🤍 白服 {img_num:02d}/{total_white} ({round_label}) {label}"
    print(f"Sending: {caption}")
    try:
        send_photo(path, caption)
    except Exception as e:
        print(f"  ERROR: {e} — retrying...")
        try:
            send_photo(path, caption)
        except Exception as e2:
            print(f"  RETRY FAILED: {e2}", file=sys.stderr)

# 黒服送信
for img_num, path, pose_idx in black_nobg:
    label = POSE_LABELS[pose_idx]
    caption = f"🖤 黒服 {img_num:02d}/{total_black} {label}"
    print(f"Sending: {caption}")
    try:
        send_photo(path, caption)
    except Exception as e:
        print(f"  ERROR: {e} — retrying...")
        try:
            send_photo(path, caption)
        except Exception as e2:
            print(f"  RETRY FAILED: {e2}", file=sys.stderr)

send_message("✅ phase1 全送信完了。白服20枚・黒服10枚。")

print(f"\n=== 完了 ===")
print(f"白服: {len(white_nobg)}/20 nobg完了")
print(f"黒服: {len(black_nobg)}/10 nobg完了")
print(f"合計: {len(white_nobg)+len(black_nobg)}/30 Telegram送信済み")
