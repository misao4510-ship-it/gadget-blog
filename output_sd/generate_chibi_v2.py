#!/usr/bin/env python3
"""Generate Sakura chibi v2 images via SD Forge API (long hair, blue inner color, solo)"""

import requests
import base64
import json
import os
import sys

SD_HOST = "http://172.18.208.1:7860"
OUTPUT_DIR = "/home/misao/gadget-blog/output_sd"

BASE_PROMPT = (
    "chibi, super deformed, 2-3 head tall, cute girl, solo, 1girl, "
    "long hair, pink hair, blue inner color hair, "
    "blue eyes, white futuristic outfit, knee-high socks, "
    "<lora:kaina_v1:0.7>, masterpiece, best quality, simple background, white background"
)

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

def generate_image(pose: str, index: int) -> str:
    prompt = f"{pose}, {BASE_PROMPT}"
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

    print(f"[{index:02d}/10] Generating: {pose[:50]}...")
    resp = requests.post(f"{SD_HOST}/sdapi/v1/txt2img", json=payload, timeout=300)
    resp.raise_for_status()

    data = resp.json()
    img_data = data["images"][0]
    img_bytes = base64.b64decode(img_data)

    out_path = os.path.join(OUTPUT_DIR, f"sakura_chibi_v2_{index:02d}.png")
    with open(out_path, "wb") as f:
        f.write(img_bytes)
    print(f"  Saved: {out_path}")
    return out_path

if __name__ == "__main__":
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    generated = []
    for i, pose in enumerate(POSES, start=1):
        try:
            path = generate_image(pose, i)
            generated.append(path)
        except Exception as e:
            print(f"  ERROR on pose {i}: {e}", file=sys.stderr)
    print(f"\nGenerated {len(generated)}/10 images.")
