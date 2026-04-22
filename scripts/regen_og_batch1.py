#!/usr/bin/env python3
"""OGサムネbatch1（25枚）を強制再生成するスクリプト。subtask_217a3用"""
import sys
sys.path.insert(0, '/home/misao/gadget-blog/scripts')

# generate_article_illustrations モジュールの設定を上書き
import json, base64, random, time, io
from pathlib import Path
import requests
from PIL import Image

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

OUTPUT_SD = Path("/mnt/c/tools/multi-agent-shogun/output_sd")
OG_DIR = Path("/home/misao/gadget-blog/public/images/og")

# batch1: 25スラッグ
BATCH1_SLUGS = [
    "100w-usb-charger-comparison-2026",
    "3d-printer-comparison-2026",
    "amazon-basics-aa-battery-review",
    "amazon-basics-monitor-arm-review",
    "amazon-disaster-kit-b0ct7zx2ch-review",
    "amazon-sale-guide-2026",
    "anker-317-charger-100w-review",
    "anker-nano-charger-100w-review",
    "anker-powerbank-25000-builtin-cable-review",
    "anker-prime-charger-100w-review",
    "anker-soundcore-liberty5-review",
    "anycubic-kobra3-combo-review",
    "apple-airpods-pro2-review",
    "bambu-lab-a1-mini-review",
    "ciniffo-electric-air-duster-review",
    "cio-novaport-quad2-100w-review",
    "creality-ender3-v3-se-review",
    "creality-k1c-review",
    "deoway-card-case-review",
    "elecom-dpa-ss02bk-monitor-arm-review",
    "elegoo-neptune4-pro-review",
    "ergotron-lx-monitor-arm-review",
    "fedour-aquarium-air-pump-review",
    "final-ze500-asmr-3d-review",
    "greeshow-gs297-radio-review",
]

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

def crop_to_og(b64_img: str) -> str:
    """1024x1024画像 → 1024x624クロップ → 1200x624リサイズ → base64"""
    img_data = base64.b64decode(b64_img)
    img = Image.open(io.BytesIO(img_data))
    # 縦の上寄り(y=200)から624pxを抽出。顔と上半身を保持
    crop_y = 200
    cropped = img.crop((0, crop_y, 1024, crop_y + 624))
    # 横を1024→1200に拡大（縦は変えない）
    resized = cropped.resize((1200, 624), Image.LANCZOS)
    buf = io.BytesIO()
    resized.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()

def save_image(b64: str, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        f.write(base64.b64decode(b64))
    print(f"  Saved: {path}")

def get_scene_prompt(slug: str) -> str:
    """スラッグからシーンプロンプトを選択"""
    if any(x in slug for x in ["charger", "usb", "gan", "novaport"]):
        return "holding charger, presenting product, smile, cheerful"
    elif any(x in slug for x in ["3d-printer", "anycubic", "bambu", "creality", "elegoo"]):
        return "gesturing toward device, excited, showing off gadget, smile"
    elif any(x in slug for x in ["airpods", "earphone", "liberty", "final-ze"]):
        return "wearing earphones, listening to music, eyes closed, content smile"
    elif any(x in slug for x in ["battery", "powerbank"]):
        return "holding batteries, smile, presenting product"
    elif any(x in slug for x in ["monitor-arm"]):
        return "pointing at monitor arm, presenting, smile"
    elif any(x in slug for x in ["disaster", "emergency"]):
        return "holding emergency kit, serious expression, reliable"
    else:
        return "holding gadget, presenting product, smile, cheerful"

def main():
    test_only = "--test" in sys.argv
    slugs = BATCH1_SLUGS[:1] if test_only else BATCH1_SLUGS

    print(f"Generating OG images for {len(slugs)} slugs...")
    if test_only:
        print("(TEST MODE: 1 slug only)")

    # SAKURA_BASEのcowboy shotをupper bodyに置換
    og_base = SAKURA_BASE.replace("cowboy shot", "upper body, portrait, looking at viewer, centered")

    success = 0
    fail = 0

    for i, slug in enumerate(slugs, 1):
        print(f"\n[{i}/{len(slugs)}] {slug}")
        og_path = OG_DIR / f"{slug}.png"

        scene = get_scene_prompt(slug)
        prompt = f"{og_base}, {scene}"
        print(f"  Scene: {scene}")
        print(f"  Generating 1024x1024...")

        b64 = generate_image(prompt, 1024, 1024)
        if b64:
            print(f"  Cropping to 1200x624...")
            b64_og = crop_to_og(b64)
            save_image(b64_og, og_path)
            save_image(b64_og, OUTPUT_SD / f"og_{slug}.png")
            success += 1
        else:
            fail += 1
            print(f"  FAILED: {slug}")

        if i < len(slugs):
            time.sleep(2)

    print(f"\n=== 完了 ===")
    print(f"成功: {success}, 失敗: {fail}")

if __name__ == "__main__":
    main()
