#!/usr/bin/env python3
"""チャットAI比較記事用サクラ画像生成"""
import json, base64, random, io
from pathlib import Path
import requests
from PIL import Image

API_URL = "http://172.18.208.1:7860"
SLUG = "chat-ai-comparison-2026"

SAKURA_BASE = (
    "kurokawa style, masterpiece, best quality, amazing quality, absurdres, "
    "soft lineart, thin outlines, digital painting, smooth shading, gradient shading, "
    "soft shadows, soft lighting, beautiful face, beautiful detailed eyes, "
    "beautiful hairstyle, beautiful skin, perfect body, "
    "1girl, solo, teenager, small breasts, cowboy shot, "
    "semi-long hair, pink hair, light blue inner color hair, "
    "light blue eyes, round eyes, "
    "futuristic playsuit, white outfit, "
    "<lora:kurokawa_v1:0.70>"
)

NEGATIVE = (
    "2girls, 3girls, multiple girls, multiple people, "
    "worst quality, low quality, blurry, bad anatomy, bad hands, extra fingers, "
    "missing fingers, watermark, text, signature, deformed, ugly, 3d, realistic, "
    "cropped head, head out of frame, cut off head, "
    "nsfw, nude, naked, oil painting, impasto"
)

ILLUSTRATIONS = [
    ("intro",       "smile, waving hand, greeting, cheerful, open mouth, peace sign"),
    ("chatgpt",     "holding tablet, excited expression, pointing, happy, bright smile"),
    ("claude",      "writing, notebook, pen in hand, gentle smile, thinking"),
    ("perplexity",  "looking at phone, searching, curious expression, tilted head"),
    ("comparison",  "presenting, showing, both hands open, explaining, confident"),
    ("matome",      "heart hands, thumbs up, happy, satisfied, recommending, waving"),
]

OUTPUT_SD = Path("/mnt/c/tools/multi-agent-shogun/output_sd")
BLOG_POSTS = Path("/home/misao/gadget-blog/public/images/posts") / SLUG
OG_DIR = Path("/home/misao/gadget-blog/public/images/og")

def generate_image(prompt, width, height):
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
    r = requests.post(f"{API_URL}/sdapi/v1/txt2img", json=payload, timeout=180)
    r.raise_for_status()
    return r.json()["images"][0]

def save_b64(b64, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = base64.b64decode(b64)
    with open(path, "wb") as f:
        f.write(data)
    print(f"  saved: {path}")

def crop_og(b64):
    data = base64.b64decode(b64)
    img = Image.open(io.BytesIO(data))
    w, h = img.size
    left = (w - 1200) // 2
    top = (h - 624) // 2
    img = img.crop((left, top, left + 1200, top + 624))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()

OUTPUT_SD.mkdir(parents=True, exist_ok=True)

# 挿絵生成 (1024x1024)
print("=== 挿絵生成 ===")
for name, pose in ILLUSTRATIONS:
    print(f"  {name}...")
    prompt = f"{SAKURA_BASE}, {pose}"
    b64 = generate_image(prompt, 1024, 1024)
    fname = f"{name}.png"
    save_b64(b64, BLOG_POSTS / fname)
    save_b64(b64, OUTPUT_SD / f"{SLUG}_{fname}")

# OG画像生成 (1216x832 → crop 1200x624)
print("=== OG画像生成 ===")
og_prompt = (
    f"{SAKURA_BASE.replace('cowboy shot', 'upper body, centered composition, looking at viewer')}, "
    "smile, holding laptop, technology, bright background, confident"
)
b64_raw = generate_image(og_prompt, 1216, 832)
b64_og = crop_og(b64_raw)
save_b64(b64_og, OG_DIR / f"{SLUG}.png")
save_b64(b64_og, OUTPUT_SD / f"og_{SLUG}.png")

print("=== 完了 ===")
