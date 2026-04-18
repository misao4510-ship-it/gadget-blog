#!/usr/bin/env python3
"""3Dプリンター記事 batch2 用サクラ挿絵・OG画像を生成するスクリプト"""
import json, base64, random, time
from pathlib import Path
import requests

API_URL = "http://172.18.208.1:7860"

SAKURA_BASE = (
    "masterpiece, best quality, beautiful face, beautiful detailed eyes, "
    "beautiful hairstyle, beautiful skin, perfect body, "
    "1girl, solo, teenager, small breasts, cowboy shot, "
    "semi-long hair, pink hair, light blue inner color hair, "
    "light blue eyes, round eyes, "
    "futuristic playsuit, white outfit, "
    "<lora:kaina_v1:0.70>"
)

NEGATIVE = (
    "worst quality, low quality, blurry, bad anatomy, bad hands, extra fingers, "
    "missing fingers, watermark, text, signature, deformed, ugly, 3d, realistic, "
    "cropped head, head out of frame, cut off head, "
    "nsfw, nude, naked"
)

OUTPUT_SD = Path("/mnt/c/tools/multi-agent-shogun/output_sd")
BLOG_IMAGES = Path("/home/misao/gadget-blog/public/images/posts")
OG_DIR = Path("/home/misao/gadget-blog/public/images/og")

ARTICLES = [
    {
        "slug": "creality-k1c-review",
        "og_prompt": f"{SAKURA_BASE}, holding high-tech gadget, excited expression, technology background, carbon fiber theme",
        "sections": {
            "spec": f"{SAKURA_BASE}, holding gadget, presenting, showing, excited expression, pointing",
            "merit": f"{SAKURA_BASE}, thumbs up, happy, satisfied, grin, one eye closed",
            "demerit": f"{SAKURA_BASE}, thinking, hand on chin, pondering, thoughtful, closed mouth, tilted head",
            "summary": f"{SAKURA_BASE}, heart hands, recommending, gentle smile, waving",
        }
    },
    {
        "slug": "elegoo-neptune4-pro-review",
        "og_prompt": f"{SAKURA_BASE}, holding tablet with graph, presenting, professional look, technology background, blue theme",
        "sections": {
            "spec": f"{SAKURA_BASE}, holding gadget, presenting, showing, excited expression, pointing",
            "merit": f"{SAKURA_BASE}, clapping hands, very happy, excited, joyful, smile",
            "demerit": f"{SAKURA_BASE}, thinking, hand on chin, pondering, thoughtful, closed mouth, tilted head",
            "summary": f"{SAKURA_BASE}, peace sign, recommending, cheerful smile, waving",
        }
    },
]

def generate_image(prompt: str, width: int, height: int) -> str | None:
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
            "sd_model_checkpoint": "novaAnimeXL_ilV170.safetensors"
        },
    }
    try:
        r = requests.post(f"{API_URL}/sdapi/v1/txt2img", json=payload, timeout=180)
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
    total = len(ARTICLES) * 5
    done = 0

    for article in ARTICLES:
        slug = article["slug"]
        print(f"\n=== {slug} ===")
        post_dir = BLOG_IMAGES / slug

        og_path = OG_DIR / f"{slug}.png"
        if og_path.exists():
            print(f"  OG already exists, skipping")
        else:
            print(f"  Generating OG (1200x624)...")
            b64 = generate_image(article["og_prompt"], 1200, 624)
            if b64:
                save_image(b64, og_path)
                save_image(b64, OUTPUT_SD / f"og_{slug}.png")
        done += 1

        for section, prompt in article["sections"].items():
            img_path = post_dir / f"{section}.png"
            if img_path.exists():
                print(f"  {section} already exists, skipping")
                done += 1
                continue
            print(f"  Generating {section} (1024x1024)...")
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
