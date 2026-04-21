#!/usr/bin/env python3
"""記事用サクラ挿絵を一括生成するスクリプト"""
import json, base64, random, time, sys, os, shutil
from pathlib import Path
import requests

API_URL = "http://172.18.208.1:7860"

SAKURA_BASE = (
    "masterpiece, best quality, amazing quality, absurdres, beautiful face, beautiful detailed eyes, "
    "sparkling eyes, glowing eyes, detailed iris, eye reflection, colorful eyes, "
    "beautiful hairstyle, beautiful skin, perfect body, "
    "1girl, solo, teenager, small breasts, cowboy shot, "
    "semi-long hair, pink hair, light blue inner color hair, "
    "light blue eyes, round eyes, "
    "futuristic playsuit, white outfit, "
    "<lora:kaina_v1_ep100:0.70>"
)

NEGATIVE = (
    "worst quality, low quality, blurry, bad anatomy, bad hands, extra fingers, "
    "missing fingers, watermark, text, signature, deformed, ugly, 3d, realistic, "
    "cropped head, head out of frame, cut off head, "
    "nsfw, nude, naked"
)

# 各セクション用ポーズ
POSES = {
    "spec": "holding gadget, presenting, showing, excited expression, pointing",
    "merit": "thumbs up, happy, satisfied, grin, one eye closed",
    "demerit": "thinking, hand on chin, pondering, thoughtful, closed mouth, tilted head",
    "matome": "heart hands, recommending, gentle smile, waving",
}

# 生成対象の記事スラッグ一覧
ARTICLES = [
    "ugreen-nexode-65w-gan-charger-review",
    "100w-usb-charger-comparison-2026",
    "anker-317-charger-100w-review",
    "anker-nano-charger-100w-review",
    "anker-prime-charger-100w-review",
    "ugreen-nexode-pro-100w-review",
    "cio-novaport-quad2-100w-review",
]

OUTPUT_SD = Path("/mnt/c/tools/multi-agent-shogun/output_sd")
BLOG_IMAGES = Path("/home/misao/gadget-blog/public/images/posts")
OG_DIR = Path("/home/misao/gadget-blog/public/images/og")

def generate_image(prompt: str, width: int, height: int) -> str | None:
    """SD Forge APIで画像生成。base64を返す"""
    payload = {
        "prompt": prompt,
        "negative_prompt": NEGATIVE,
        "seed": random.randint(0, 2147483647),
        "steps": 28,
        "cfg_scale": 7,
        "width": width,
        "height": height,
        "sampler_name": "DPM++ 2M SDE Karras",
        "override_settings": {
            "sd_model_checkpoint": "waiIllustriousSDXL_v160.safetensors"
        },
    }
    try:
        r = requests.post(f"{API_URL}/sdapi/v1/txt2img", json=payload, timeout=120)
        r.raise_for_status()
        return r.json()["images"][0]
    except Exception as e:
        print(f"  ERROR: {e}")
        return None

def save_image(b64: str, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        f.write(base64.b64decode(b64))
    print(f"  Saved: {path}")

def main():
    total = len(ARTICLES) * 5  # 4 sections + 1 OG per article
    done = 0

    for slug in ARTICLES:
        print(f"\n=== {slug} ===")
        post_dir = BLOG_IMAGES / slug

        # OG画像 (1200x624)
        og_path = OG_DIR / f"{slug}.png"
        if og_path.exists():
            print(f"  OG already exists, skipping")
        else:
            print(f"  Generating OG (1200x624)...")
            prompt = f"{SAKURA_BASE}, holding charger, presenting product, smile, cheerful"
            b64 = generate_image(prompt, 1200, 624)
            if b64:
                save_image(b64, og_path)
                # output_sdにも保存
                save_image(b64, OUTPUT_SD / f"og_{slug}.png")
            time.sleep(1)
        done += 1

        # セクション挿絵 (1024x1024)
        for section, pose in POSES.items():
            img_path = post_dir / f"{section}.png"
            if img_path.exists():
                print(f"  {section} already exists, skipping")
                done += 1
                continue
            print(f"  Generating {section} (1024x1024)...")
            prompt = f"{SAKURA_BASE}, {pose}"
            b64 = generate_image(prompt, 1024, 1024)
            if b64:
                save_image(b64, img_path)
                save_image(b64, OUTPUT_SD / f"{slug}_{section}.png")
            done += 1
            time.sleep(1)

        print(f"  Progress: {done}/{total}")

    print(f"\nDone! Generated images for {len(ARTICLES)} articles.")

if __name__ == "__main__":
    main()
