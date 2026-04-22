#!/usr/bin/env python3
"""
Generate SD Forge images for earphone articles (cmd_192)
6 articles: tws-earphone-comparison-2026, anker-soundcore-liberty5-review,
sony-wf1000xm5-review, apple-airpods-pro2-review,
samsung-galaxy-buds3-pro-review, technics-eah-az80-review
"""

import requests
import base64
import os
import json
from pathlib import Path
import time

SD_API = "http://172.18.208.1:7860"
OUTPUT_SD = "/mnt/c/tools/multi-agent-shogun/output_sd"
BLOG_PUBLIC = "/home/misao/gadget-blog/public"

SAKURA_BASE = "kurokawa style, masterpiece, best quality, amazing quality, absurdres, soft lineart, thin outlines, digital painting, smooth shading, gradient shading, soft shadows, soft lighting, beautiful face, beautiful detailed eyes, beautiful hairstyle, beautiful skin, perfect body, 1girl, solo, teenager, small breasts, cowboy shot, semi-long hair, pink hair, light blue inner color hair, light blue eyes, round eyes, futuristic playsuit, white outfit, <lora:kurokawa_v1:0.70>"

NEGATIVE = "lowres, bad anatomy, bad hands, text, error, missing fingers, extra digit, fewer digits, cropped, worst quality, low quality, normal quality, jpeg artifacts, signature, watermark, username, blurry, oil painting, impasto"

MODEL = "waiIllustriousSDXL_v160.safetensors"
SAMPLER = "DPM++ 2M SDE Karras"
STEPS = 28

def generate_image(prompt, width, height, filename_hint):
    payload = {
        "prompt": f"{SAKURA_BASE}, {prompt}",
        "negative_prompt": NEGATIVE,
        "steps": STEPS,
        "sampler_name": SAMPLER,
        "width": width,
        "height": height,
        "cfg_scale": 7,
        "seed": -1,
        "override_settings": {
            "sd_model_checkpoint": MODEL
        }
    }

    print(f"  Generating: {filename_hint} ({width}x{height})...")
    resp = requests.post(f"{SD_API}/sdapi/v1/txt2img", json=payload, timeout=300)
    resp.raise_for_status()
    data = resp.json()
    img_b64 = data["images"][0]
    return base64.b64decode(img_b64)

def save_image(img_data, blog_path, sd_filename):
    # Save to blog
    os.makedirs(os.path.dirname(blog_path), exist_ok=True)
    with open(blog_path, "wb") as f:
        f.write(img_data)
    print(f"    Saved: {blog_path}")

    # Save to output_sd
    os.makedirs(OUTPUT_SD, exist_ok=True)
    sd_path = os.path.join(OUTPUT_SD, sd_filename)
    with open(sd_path, "wb") as f:
        f.write(img_data)
    print(f"    Saved: {sd_path}")

# Article image definitions
ARTICLES = [
    {
        "slug": "tws-earphone-comparison-2026",
        "og_prompt": "holding multiple wireless earphones, looking excited, comparison chart background, colorful, gadget review",
        "illustrations": [
            ("spec", "pointing at spec table, professional pose, tech review setting"),
            ("merit", "happy excited face, thumbs up, earphone in hand, review positive"),
            ("demerit", "thoughtful expression, pondering, finger on chin"),
            ("summary", "recommendation pose, smiling brightly, earphones displayed around"),
        ]
    },
    {
        "slug": "anker-soundcore-liberty5-review",
        "og_prompt": "holding Anker Soundcore Liberty 5 wireless earphone, teal color earphone, excited happy expression, gadget blog",
        "illustrations": [
            ("spec", "pointing at spec table, professional technical review setting"),
            ("merit", "happy excited face, thumbs up, earphone in hand, great value"),
            ("demerit", "thoughtful expression, pondering, considering downsides"),
            ("summary", "recommendation pose, smiling, earphone, great value gadget"),
        ]
    },
    {
        "slug": "sony-wf1000xm5-review",
        "og_prompt": "holding Sony WF-1000XM5 wireless earphone, dark premium earphone, impressed expression, flagship audio review",
        "illustrations": [
            ("spec", "pointing at specifications, premium product review background"),
            ("merit", "excited happy face, premium earphone, high quality audio"),
            ("demerit", "thoughtful considering expression, premium price point"),
            ("summary", "recommendation pose, Sony earphone, flagship quality"),
        ]
    },
    {
        "slug": "apple-airpods-pro2-review",
        "og_prompt": "holding Apple AirPods Pro 2 white earphone, white stem earbuds, delighted expression, Apple ecosystem review",
        "illustrations": [
            ("spec", "pointing at Apple specifications, clean white tech aesthetic"),
            ("merit", "happy excited face, white AirPods, Apple device ecosystem"),
            ("demerit", "thoughtful considering expression, price consideration"),
            ("summary", "recommendation pose, AirPods, Apple quality, smiling"),
        ]
    },
    {
        "slug": "samsung-galaxy-buds3-pro-review",
        "og_prompt": "holding Samsung Galaxy Buds3 Pro earphone, blue silver design, enthusiastic expression, Galaxy review",
        "illustrations": [
            ("spec", "pointing at Samsung specifications, Galaxy tech background"),
            ("merit", "excited happy face, Samsung earphones, Galaxy AI features"),
            ("demerit", "thoughtful expression, considering limitations"),
            ("summary", "recommendation pose, Galaxy earphone, Samsung ecosystem"),
        ]
    },
    {
        "slug": "technics-eah-az80-review",
        "og_prompt": "holding Technics EAH-AZ80 earphone, dark gray premium audio earphone, impressed audiophile expression, hi-res audio review",
        "illustrations": [
            ("spec", "pointing at audio specifications, premium audiophile setting"),
            ("merit", "excited happy face, high-fidelity audio, LDAC earphone"),
            ("demerit", "thoughtful considering expression, evaluating features"),
            ("summary", "recommendation pose, audiophile earphone, premium audio quality"),
        ]
    },
]

def main():
    print("=== Earphone Articles Image Generation ===")
    print(f"Articles: {len(ARTICLES)}, Total images: {len(ARTICLES) * 5}")

    for article in ARTICLES:
        slug = article["slug"]
        print(f"\n[{slug}]")

        # OG image (1200x624)
        og_img = generate_image(article["og_prompt"], 1200, 624, f"{slug}-og")
        save_image(
            og_img,
            f"{BLOG_PUBLIC}/images/og/{slug}.png",
            f"{slug}-og.png"
        )
        time.sleep(1)

        # Section illustrations (1024x1024)
        for section, prompt in article["illustrations"]:
            ill_img = generate_image(prompt, 1024, 1024, f"{slug}-{section}")
            save_image(
                ill_img,
                f"{BLOG_PUBLIC}/images/posts/{slug}/{section}.png",
                f"{slug}-{section}.png"
            )
            time.sleep(1)

    print("\n=== All images generated successfully! ===")

if __name__ == "__main__":
    main()
