#!/usr/bin/env python3
"""
note_generate_illustrations.py: SD WebUI APIでサクラの挿絵5枚を生成

使用法: python3 scripts/note_generate_illustrations.py --slug <slug>
出力先: /tmp/note_illustrations/<slug>/{intro,features,merit,demerit,summary}.png
"""
import requests
import base64
import time
import argparse
import sys
import random
from pathlib import Path

DEFAULT_API_URL = "http://172.18.208.1:7860"

# サクラテンプレート（殿が2026-04-15にプロンプトビルダーから指定）
SAKURA_BASE = (
    "masterpiece, best quality, amazing quality, absurdres, beautiful face, beautiful detailed eyes, "
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

ILLUSTRATIONS = [
    {
        "name": "intro",
        "prompt": f"{SAKURA_BASE}, smile, waving hand, greeting, cheerful, open mouth",
        "seed": 42,
    },
    {
        "name": "features",
        "prompt": f"{SAKURA_BASE}, holding, presenting, showing, excited expression, pointing",
        "seed": 123,
    },
    {
        "name": "merit",
        "prompt": f"{SAKURA_BASE}, thumbs up, happy, satisfied, grin, one eye closed",
        "seed": 456,
    },
    {
        "name": "demerit",
        "prompt": f"{SAKURA_BASE}, thinking, hand on chin, pondering, thoughtful, closed mouth, tilted head",
        "seed": 789,
    },
    {
        "name": "summary",
        "prompt": f"{SAKURA_BASE}, heart hands, recommending, gentle smile",
        "seed": 1024,
    },
]


def generate_image(name: str, config: dict, output_dir: Path, api_url: str) -> str:
    """1枚生成。成功時はパスを返す。失敗時は空文字を返す（graceful）"""
    payload = {
        "prompt": config["prompt"],
        "negative_prompt": NEGATIVE,
        "seed": random.randint(0, 2147483647),
        "steps": 28,
        "cfg_scale": 7,
        "width": 768,
        "height": 768,
        "sampler_name": "DPM++ 2M SDE",
        "scheduler": "Karras",
        "batch_size": 1,
        "n_iter": 1,
    }
    print(f"[{name}] 生成中...")
    try:
        resp = requests.post(f"{api_url}/sdapi/v1/txt2img", json=payload, timeout=120)
        resp.raise_for_status()
    except requests.exceptions.ConnectionError:
        print(f"  SKIP: SD WebUI API ({api_url}) に接続できません")
        return ""
    except requests.exceptions.Timeout:
        print(f"  TIMEOUT: {name}")
        return ""
    except Exception as e:
        print(f"  ERROR: {e}")
        return ""

    data = resp.json()
    if not data.get("images"):
        print(f"  ERROR: 画像データなし")
        return ""

    img_data = base64.b64decode(data["images"][0])
    path = output_dir / f"{name}.png"
    path.write_bytes(img_data)
    print(f"  完了: {path}")
    return str(path)


def main():
    parser = argparse.ArgumentParser(description="SD WebUI APIでサクラの挿絵5枚を生成")
    parser.add_argument("--slug", required=True, help="記事スラッグ（出力ディレクトリ名）")
    parser.add_argument("--api-url", default=DEFAULT_API_URL,
                        help=f"SD WebUI API URL (default: {DEFAULT_API_URL})")
    parser.add_argument("--output-dir",
                        help="出力ディレクトリ（省略時: /tmp/note_illustrations/<slug>）")
    args = parser.parse_args()

    output_dir = (
        Path(args.output_dir)
        if args.output_dir
        else Path(f"/tmp/note_illustrations/{args.slug}")
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"挿絵生成開始: {args.slug}")
    print(f"出力先: {output_dir}")

    success_count = 0
    for illust in ILLUSTRATIONS:
        path = generate_image(illust["name"], illust, output_dir, args.api_url)
        if path:
            success_count += 1
        time.sleep(1)

    print(f"\n生成完了: {success_count}/{len(ILLUSTRATIONS)}枚")
    if success_count == 0:
        print("WARNING: 挿絵が1枚も生成されませんでした（SD API未接続の可能性）")
        sys.exit(1)


if __name__ == "__main__":
    main()
