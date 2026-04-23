#!/usr/bin/env python3
"""subtask_217d: NG挿絵6枚を新seedで再生成"""
import json, base64, random, time
from pathlib import Path
import requests

API_URL = "http://172.18.208.1:7860"

SAKURA_BASE = (
    "kurokawa style, masterpiece, best quality, amazing quality, absurdres, soft lineart, thin outlines, digital painting, smooth shading, gradient shading, soft shadows, soft lighting, beautiful face, beautiful detailed eyes, "
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

POSES = {
    "spec": "holding gadget, presenting, showing, excited expression, pointing",
    "merit": "thumbs up, happy, satisfied, grin, one eye closed",
    "demerit": "thinking, hand on chin, pondering, thoughtful, closed mouth, tilted head",
    "matome": "heart hands, recommending, gentle smile, waving",
    "summary": "heart hands, recommending, gentle smile, waving",
}

NG_LIST = [
    ("100w-usb-charger-comparison-2026", "demerit"),
    ("bambu-lab-a1-mini-review", "demerit"),
    ("ciniffo-electric-air-duster-review", "demerit"),
    ("cio-novaport-quad2-100w-review", "demerit"),
    ("creality-ender3-v3-se-review", "merit"),
    ("huanuo-monitor-arm-review", "summary"),
]

BLOG_IMAGES = Path("/home/misao/gadget-blog/public/images/posts")
OUTPUT_SD = Path("/mnt/c/tools/multi-agent-shogun/output_sd")


def generate_image(prompt: str, width: int, height: int, seed: int):
    payload = {
        "prompt": prompt,
        "negative_prompt": NEGATIVE,
        "seed": seed,
        "steps": 28,
        "cfg_scale": 7,
        "width": width,
        "height": height,
        "sampler_name": "DPM++ 2M SDE Karras",
        "override_settings": {
            "sd_model_checkpoint": "waiIllustriousSDXL_v160.safetensors"
        },
    }
    r = requests.post(f"{API_URL}/sdapi/v1/txt2img", json=payload, timeout=120)
    r.raise_for_status()
    return r.json()["images"][0]


def save_image(b64: str, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = base64.b64decode(b64)
    with open(path, "wb") as f:
        f.write(data)
    print(f"  Saved: {path}")


def main():
    print(f"NG再生成: {len(NG_LIST)}枚")
    for i, (slug, section) in enumerate(NG_LIST, 1):
        seed = random.randint(100000, 2147483647)
        pose = POSES.get(section, "smiling, gentle pose, looking at viewer")
        prompt = f"{SAKURA_BASE}, {pose}"

        blog_path = BLOG_IMAGES / slug / f"{section}.png"
        sd_path = OUTPUT_SD / f"ng_regen_{slug}_{section}.png"

        print(f"\n[{i}/{len(NG_LIST)}] {slug}/{section}.png (seed={seed})")
        try:
            b64 = generate_image(prompt, 1024, 1024, seed)
            save_image(b64, blog_path)
            save_image(b64, sd_path)
            print(f"  OK")
        except Exception as e:
            print(f"  ERROR: {e}")
            continue

        time.sleep(1)

    print("\n全NG再生成完了。")


if __name__ == "__main__":
    main()
