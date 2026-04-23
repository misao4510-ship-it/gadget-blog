#!/usr/bin/env python3
"""cmd_226 全画像novaAnimeXL差し替えスクリプト (batch2 OG + batch3+ 挿絵)
使い方:
  python3 scripts/regen_nova_full.py --target og              # OG残12枚(batch2)
  python3 scripts/regen_nova_full.py --target illust          # 挿絵166枚(batch3+, 30件/セッション)
  python3 scripts/regen_nova_full.py --target illust --batch 30 --offset 0   # batch3
  python3 scripts/regen_nova_full.py --target illust --batch 30 --offset 30  # batch4
  python3 scripts/regen_nova_full.py --target og --dry-run
  python3 scripts/regen_nova_full.py --target illust --reset  # STATE_FILEリセット(挿絵用)
"""
import sys, json, base64, random, time, io, argparse, atexit
from pathlib import Path
import requests
from PIL import Image

API_URL    = "http://172.18.208.1:7860"
NOVA_MODEL = "novaAnimeXL_ilV170.safetensors"
WAI_MODEL  = "waiIllustriousSDXL_v160.safetensors"

SAKURA_BASE = (
    "kurokawa style, masterpiece, best quality, amazing quality, absurdres, "
    "soft lineart, thin outlines, digital painting, smooth shading, gradient shading, "
    "soft shadows, soft lighting, beautiful face, beautiful detailed eyes, detailed iris, "
    "eye reflection, colorful eyes, beautiful hairstyle, beautiful skin, perfect body, "
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
    "spec":    "holding gadget, presenting, showing, excited expression, pointing",
    "merit":   "thumbs up, happy, satisfied, grin, one eye closed",
    "demerit": "thinking, hand on chin, pondering, thoughtful, closed mouth, tilted head",
    "matome":  "heart hands, recommending, gentle smile, waving",
    "summary": "heart hands, recommending, gentle smile, waving",
}

OUTPUT_SD  = Path("/mnt/c/tools/multi-agent-shogun/output_sd")
OG_DIR     = Path("/home/misao/gadget-blog/public/images/og")
POSTS_DIR  = Path("/home/misao/gadget-blog/public/images/posts")
STATE_FILE = Path("/tmp/nova_full_state.json")

# batch1(subtask_226a)で処理済みのOGスラッグ
BATCH1_DONE = {
    "100w-usb-charger-comparison-2026", "3d-printer-comparison-2026",
    "amazon-basics-aa-battery-review", "amazon-basics-monitor-arm-review",
    "amazon-disaster-kit-b0ct7zx2ch-review", "amazon-sale-guide-2026",
    "anker-317-charger-100w-review", "anker-nano-charger-100w-review",
    "anker-powerbank-25000-builtin-cable-review", "anker-prime-charger-100w-review",
    "anker-soundcore-liberty5-review", "anycubic-kobra3-combo-review",
    "apple-airpods-pro2-review", "bambu-lab-a1-mini-review",
    "ciniffo-electric-air-duster-review", "cio-novaport-quad2-100w-review",
    "creality-ender3-v3-se-review", "creality-k1c-review",
    "deoway-card-case-review", "elecom-dpa-ss02bk-monitor-arm-review",
    "elegoo-neptune4-pro-review", "ergotron-lx-monitor-arm-review",
    "fedour-aquarium-air-pump-review", "final-ze500-asmr-3d-review",
    "greeshow-gs297-radio-review", "gummy-supplement-review",
    "huanuo-monitor-arm-review", "imuraya-eiyokan-review",
    "monitor-arm-single-gas-comparison-2026", "pykes-peak-toilet-120-review",
}


def get_all_slugs() -> list[str]:
    """公開記事スラッグ一覧を取得（.md有りのみ、孤児除外）"""
    posts_md = Path("/home/misao/gadget-blog/src/content/posts")
    return sorted(p.stem for p in posts_md.glob("*.md"))


def get_og_scene_prompt(slug: str) -> str:
    if any(x in slug for x in ["charger", "usb", "gan", "novaport", "cio"]):
        return "holding charger, presenting product, smile, cheerful"
    elif any(x in slug for x in ["3d-printer", "anycubic", "bambu", "creality", "elegoo"]):
        return "gesturing toward device, excited, showing off gadget, smile"
    elif any(x in slug for x in ["airpods", "earphone", "liberty", "final-ze", "soundcore", "tws", "technics", "sony-wf", "samsung"]):
        return "wearing earphones, listening to music, slight smile, content"
    elif any(x in slug for x in ["battery", "powerbank"]):
        return "holding battery pack, smile, presenting product"
    elif any(x in slug for x in ["monitor-arm", "ergotron", "elecom", "huanuo", "sanwa"]):
        return "pointing at monitor arm, presenting, smile"
    elif any(x in slug for x in ["disaster", "emergency"]):
        return "holding emergency kit, reliable expression, determined"
    elif any(x in slug for x in ["supplement", "gummy"]):
        return "holding supplement bottle, smile, healthy"
    elif any(x in slug for x in ["toilet", "pykes"]):
        return "presenting cleaning product, smile, thumbs up"
    elif any(x in slug for x in ["aquarium", "fedour"]):
        return "holding aquarium equipment, curious expression, smile"
    elif any(x in slug for x in ["radio", "greeshow"]):
        return "holding radio device, curious expression, smile"
    elif any(x in slug for x in ["card-case", "deoway"]):
        return "holding card case, presenting, smile"
    elif any(x in slug for x in ["eiyokan", "imuraya", "bath-brush", "yamazaki"]):
        return "holding product, happy expression, smile"
    elif any(x in slug for x in ["sale", "comparison", "calendar", "hub", "qi2", "magsafe", "threekey", "rakuten", "yahoo"]):
        return "presenting multiple products, excited, thumbs up, smile"
    elif any(x in slug for x in ["buds", "samsung-galaxy"]):
        return "wearing earphones, listening to music, slight smile, content"
    else:
        return "holding gadget, presenting product, smile, cheerful"


def switch_model(model_name: str):
    print(f"  Switching model → {model_name} ...")
    r = requests.post(
        f"{API_URL}/sdapi/v1/options",
        json={"sd_model_checkpoint": model_name},
        timeout=120,
    )
    r.raise_for_status()
    time.sleep(5)
    print(f"  Model switched OK")


def txt2img(prompt: str, seed: int, width=1024, height=1024) -> str | None:
    payload = {
        "prompt": prompt,
        "negative_prompt": NEGATIVE,
        "seed": seed,
        "steps": 28,
        "cfg_scale": 7,
        "width": width,
        "height": height,
        "sampler_name": "DPM++ 2M SDE Karras",
    }
    try:
        r = requests.post(f"{API_URL}/sdapi/v1/txt2img", json=payload, timeout=180)
        r.raise_for_status()
        return r.json()["images"][0]
    except Exception as e:
        print(f"  ERROR txt2img: {e}")
        return None


def img2img_detail_up(b64_src: str, prompt: str, seed: int) -> str | None:
    payload = {
        "init_images": [b64_src],
        "prompt": prompt,
        "negative_prompt": NEGATIVE,
        "seed": seed,
        "denoising_strength": 0.30,
        "steps": 35,
        "cfg_scale": 7,
        "width": 1024,
        "height": 1024,
        "sampler_name": "DPM++ 2M SDE Karras",
    }
    try:
        r = requests.post(f"{API_URL}/sdapi/v1/img2img", json=payload, timeout=180)
        r.raise_for_status()
        return r.json()["images"][0]
    except Exception as e:
        print(f"  ERROR img2img: {e}")
        return None


def center_crop_to_og(b64_img: str) -> bytes:
    """1024x1024 → 中央クロップ1200x624"""
    img_data = base64.b64decode(b64_img)
    img = Image.open(io.BytesIO(img_data))
    w, h = img.size
    crop_top = (h - 624) // 2
    cropped = img.crop((0, crop_top, w, crop_top + 624))
    resized = cropped.resize((1200, 624), Image.LANCZOS)
    buf = io.BytesIO()
    resized.save(buf, format="PNG")
    return buf.getvalue()


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {"done": [], "results": []}


def save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2))


def restore_model_atexit():
    """atexit でも必ずwaiに戻す"""
    try:
        r = requests.post(
            f"{API_URL}/sdapi/v1/options",
            json={"sd_model_checkpoint": WAI_MODEL},
            timeout=60,
        )
        r.raise_for_status()
        print(f"\n[atexit] Model restored to {WAI_MODEL}")
    except Exception as e:
        print(f"\n[atexit] WARNING: Failed to restore model: {e}")


def run_og(args):
    """batch2: OG残12枚生成"""
    all_slugs = get_all_slugs()
    batch2_slugs = [s for s in all_slugs if s not in BATCH1_DONE]
    print(f"=== cmd_226 OG batch2 再生成 (novaAnimeXL) ===")
    print(f"対象: {len(batch2_slugs)} slugs")

    if args.dry_run:
        for s in batch2_slugs:
            print(f"  [dry-run] {s} → {OG_DIR / (s + '.png')}")
        return

    state = load_state()
    done_set = set(state.get("done", []))
    pending = [s for s in batch2_slugs if s not in done_set]
    if not pending:
        print("全OGスラッグ処理済み。完了。")
        return
    print(f"  処理対象: {len(pending)} slugs | スキップ済み: {len(done_set)}")

    og_base = SAKURA_BASE.replace("cowboy shot", "upper body, portrait, looking at viewer, centered")
    detail_extra = "skin texture, detailed skin, high detail"

    atexit.register(restore_model_atexit)
    switch_model(NOVA_MODEL)

    results = state.get("results", [])
    success = sum(1 for r in results if r.get("status") == "ok")
    fail    = sum(1 for r in results if r.get("status") == "fail")

    try:
        for i, slug in enumerate(pending, 1):
            print(f"\n[{i}/{len(pending)}] {slug}")
            og_path     = OG_DIR / f"{slug}.png"
            backup_path = OUTPUT_SD / f"og_nova_{slug}.png"

            scene  = get_og_scene_prompt(slug)
            prompt = f"{og_base}, {scene}"
            seed   = random.randint(0, 2147483647)
            print(f"  Scene: {scene} | Seed: {seed}")

            print(f"  txt2img 1024x1024 ...")
            b64_t2i = txt2img(prompt, seed)
            if not b64_t2i:
                print(f"  FAILED (txt2img): {slug}")
                fail += 1
                results.append({"slug": slug, "status": "fail", "step": "txt2img", "seed": seed, "type": "og"})
                state["done"].append(slug)
                state["results"] = results
                save_state(state)
                continue

            print(f"  img2img detail-up ...")
            b64_i2i = img2img_detail_up(b64_t2i, f"{prompt}, {detail_extra}", seed + 1)
            b64_final = b64_i2i if b64_i2i else b64_t2i

            print(f"  Cropping to 1200x624 ...")
            png_data = center_crop_to_og(b64_final)

            og_path.parent.mkdir(parents=True, exist_ok=True)
            og_path.write_bytes(png_data)
            print(f"  Saved OG: {og_path}")

            OUTPUT_SD.mkdir(parents=True, exist_ok=True)
            backup_path.write_bytes(png_data)
            print(f"  Backup:   {backup_path}")

            success += 1
            results.append({"slug": slug, "status": "ok", "seed": seed,
                            "og_path": str(og_path), "backup": str(backup_path), "type": "og"})
            state["done"].append(slug)
            state["results"] = results
            save_state(state)

            time.sleep(0.5)

    finally:
        print(f"\nRestoring model → {WAI_MODEL} ...")
        try:
            switch_model(WAI_MODEL)
            print("Model restored OK")
        except Exception as e:
            print(f"WARNING: Failed to restore model: {e}")

    total = len(batch2_slugs)
    print(f"\n=== OG batch2 完了 ===")
    print(f"成功: {success} / {total}, 失敗: {fail}")
    for r in results:
        if r.get("status") == "ok" and r.get("type") == "og":
            print(f"  [{r['slug']}] seed={r['seed']} → {r['og_path']}")


def run_illust(args):
    """batch3+: 挿絵166枚生成 (30件/バッチ)"""
    all_slugs = get_all_slugs()

    # 全挿絵タスク一覧: (slug, section)
    all_tasks = []
    for slug in all_slugs:
        post_dir = POSTS_DIR / slug
        if not post_dir.exists():
            continue
        for section in ["spec", "merit", "demerit", "matome", "summary"]:
            img_path = post_dir / f"{section}.png"
            if img_path.exists():
                all_tasks.append((slug, section))

    print(f"=== cmd_226 挿絵再生成 (novaAnimeXL) ===")
    print(f"対象総数: {len(all_tasks)} 枚")

    if args.dry_run:
        for slug, section in all_tasks:
            print(f"  [dry-run] {slug}/{section}.png")
        return

    # STATE_FILEで処理済みスキップ
    state = load_state()
    done_set = set(state.get("done", []))
    pending_all = [(s, sec) for s, sec in all_tasks if f"{s}/{sec}" not in done_set]

    # --batch / --offset でバッチ制御
    offset = args.offset
    batch_size = args.batch
    pending = pending_all[offset:offset + batch_size]

    print(f"  全未処理: {len(pending_all)} 枚 | offset={offset} batch={batch_size} → 今回: {len(pending)} 枚")

    if not pending:
        print("このバッチの対象なし（全処理済みか offset 超過）。完了。")
        return

    detail_extra = "skin texture, detailed skin, high detail"
    illust_base = SAKURA_BASE  # cowboy shot そのまま

    atexit.register(restore_model_atexit)
    switch_model(NOVA_MODEL)

    results = state.get("results", [])
    success = sum(1 for r in results if r.get("status") == "ok" and r.get("type") == "illust")
    fail    = sum(1 for r in results if r.get("status") == "fail" and r.get("type") == "illust")

    try:
        for i, (slug, section) in enumerate(pending, 1):
            key = f"{slug}/{section}"
            img_path    = POSTS_DIR / slug / f"{section}.png"
            backup_path = OUTPUT_SD / f"illust_nova_{slug}_{section}.png"

            pose   = POSES.get(section, "holding gadget, smile")
            prompt = f"{illust_base}, {pose}"
            seed   = random.randint(0, 2147483647)
            print(f"\n[{i}/{len(pending)}] {key} | Seed: {seed}")

            print(f"  txt2img 1024x1024 ...")
            b64_t2i = txt2img(prompt, seed)
            if not b64_t2i:
                print(f"  FAILED (txt2img): {key}")
                fail += 1
                results.append({"key": key, "status": "fail", "step": "txt2img", "seed": seed, "type": "illust"})
                state["done"].append(key)
                state["results"] = results
                save_state(state)
                continue

            print(f"  img2img detail-up ...")
            b64_i2i = img2img_detail_up(b64_t2i, f"{prompt}, {detail_extra}", seed + 1)
            b64_final = b64_i2i if b64_i2i else b64_t2i

            png_data = base64.b64decode(b64_final)

            img_path.parent.mkdir(parents=True, exist_ok=True)
            img_path.write_bytes(png_data)
            print(f"  Saved: {img_path}")

            OUTPUT_SD.mkdir(parents=True, exist_ok=True)
            backup_path.write_bytes(png_data)
            print(f"  Backup: {backup_path}")

            success += 1
            results.append({"key": key, "status": "ok", "seed": seed,
                            "path": str(img_path), "backup": str(backup_path), "type": "illust"})
            state["done"].append(key)
            state["results"] = results
            save_state(state)

            time.sleep(0.5)

    finally:
        print(f"\nRestoring model → {WAI_MODEL} ...")
        try:
            switch_model(WAI_MODEL)
            print("Model restored OK")
        except Exception as e:
            print(f"WARNING: Failed to restore model: {e}")

    total_done = sum(1 for r in results if r.get("status") == "ok" and r.get("type") == "illust")
    print(f"\n=== 挿絵バッチ完了 ===")
    print(f"このバッチ: 成功={success}, 失敗={fail}")
    print(f"累計成功: {total_done} / {len(all_tasks)}")

    remaining = len(pending_all) - len(pending)
    if remaining > 0:
        next_offset = offset + batch_size
        print(f"\n次バッチ: --target illust --batch {batch_size} --offset {next_offset} ({remaining}枚残り)")
    else:
        print("\n全挿絵処理完了！")


def main():
    parser = argparse.ArgumentParser(description="cmd_226 全画像novaAnimeXL差し替え")
    parser.add_argument("--target", choices=["og", "illust"], required=True)
    parser.add_argument("--batch", type=int, default=30, help="挿絵バッチサイズ (default: 30)")
    parser.add_argument("--offset", type=int, default=0, help="挿絵バッチ開始オフセット")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--reset", action="store_true", help="STATE_FILEをリセット")
    args = parser.parse_args()

    if args.reset and STATE_FILE.exists():
        STATE_FILE.unlink()
        print(f"STATE_FILE reset: {STATE_FILE}")

    if args.target == "og":
        run_og(args)
    else:
        run_illust(args)


if __name__ == "__main__":
    main()
