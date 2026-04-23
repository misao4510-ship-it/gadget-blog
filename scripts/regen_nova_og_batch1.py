#!/usr/bin/env python3
"""OGサムネbatch1(30枚)をnovaAnimeXL_ilV170で再生成するスクリプト。subtask_226a用
手順:
  1. novaAnimeXL_ilV170にモデル切替
  2. 30スラッグをtxt2img(1024x1024) + img2img detail-up(denoising 0.30)
  3. Pillow中央クロップで1200x624
  4. public/images/og/ 上書き + output_sd バックアップ
  5. waiIllustriousSDXL_v160に戻す
"""
import sys, json, base64, random, time, io
from pathlib import Path
import requests
from PIL import Image

API_URL = "http://172.18.208.1:7860"
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

OUTPUT_SD   = Path("/mnt/c/tools/multi-agent-shogun/output_sd")
OG_DIR      = Path("/home/misao/gadget-blog/public/images/og")
STATE_FILE  = Path("/tmp/nova_og_batch1_state.json")   # 処理済みslugスキップ用

# batch1: 30スラッグ (アルファベット順・孤児除外済み)
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
    "gummy-supplement-review",
    "huanuo-monitor-arm-review",
    "imuraya-eiyokan-review",
    "monitor-arm-single-gas-comparison-2026",
    "pykes-peak-toilet-120-review",
]


def switch_model(model_name: str):
    """SD Forgeのモデルを切り替える"""
    print(f"  Switching model → {model_name} ...")
    r = requests.post(
        f"{API_URL}/sdapi/v1/options",
        json={"sd_model_checkpoint": model_name},
        timeout=120,
    )
    r.raise_for_status()
    # モデル読込を待つ
    time.sleep(5)
    print(f"  Model switched OK")


def txt2img(prompt: str, seed: int) -> str | None:
    """txt2imgで1024x1024生成。base64を返す"""
    payload = {
        "prompt": prompt,
        "negative_prompt": NEGATIVE,
        "seed": seed,
        "steps": 28,
        "cfg_scale": 7,
        "width": 1024,
        "height": 1024,
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
    """img2imgでディテールアップ(denoising 0.30)"""
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
    """1024x1024 → 中央クロップで1200x624
    - 横は全幅(1024)から中央1024を使用(変化なし)
    - 縦の中央から624px抽出して横を1200にリサイズ
    """
    img_data = base64.b64decode(b64_img)
    img = Image.open(io.BytesIO(img_data))  # 1024x1024
    w, h = img.size  # 1024, 1024

    # 縦: 中央から624px (上から (1024-624)//2 = 200)
    crop_top = (h - 624) // 2
    cropped = img.crop((0, crop_top, w, crop_top + 624))  # 1024x624
    # 横を1024→1200に拡大
    resized = cropped.resize((1200, 624), Image.LANCZOS)

    buf = io.BytesIO()
    resized.save(buf, format="PNG")
    return buf.getvalue()


def get_scene_prompt(slug: str) -> str:
    """スラッグからシーンプロンプトを決定"""
    if any(x in slug for x in ["charger", "usb", "gan", "novaport", "cio"]):
        return "holding charger, presenting product, smile, cheerful"
    elif any(x in slug for x in ["3d-printer", "anycubic", "bambu", "creality", "elegoo"]):
        return "gesturing toward device, excited, showing off gadget, smile"
    elif any(x in slug for x in ["airpods", "earphone", "liberty", "final-ze", "soundcore"]):
        return "wearing earphones, listening to music, slight smile, content"
    elif any(x in slug for x in ["battery", "powerbank"]):
        return "holding battery pack, smile, presenting product"
    elif any(x in slug for x in ["monitor-arm", "ergotron", "elecom", "huanuo"]):
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
    elif any(x in slug for x in ["eiyokan", "imuraya"]):
        return "holding snack, happy expression, smile"
    elif any(x in slug for x in ["sale", "comparison"]):
        return "presenting multiple products, excited, thumbs up, smile"
    else:
        return "holding gadget, presenting product, smile, cheerful"


def load_state() -> dict:
    """処理済みslug一覧をSTATE_FILEから読み込む"""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {"done": [], "results": []}


def save_state(state: dict):
    """処理済み状態をSTATE_FILEに保存（クラッシュ復旧用）"""
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2))


def main():
    test_mode    = "--test" in sys.argv
    dry_run      = "--dry-run" in sys.argv
    reset_state  = "--reset" in sys.argv

    if reset_state and STATE_FILE.exists():
        STATE_FILE.unlink()
        print("State reset.")

    slugs = BATCH1_SLUGS[:1] if test_mode else BATCH1_SLUGS
    print(f"=== cmd_226 OG batch1 再生成 (novaAnimeXL) ===")
    print(f"対象: {len(slugs)} slugs | test={test_mode} | dry_run={dry_run}")

    if dry_run:
        for s in slugs:
            print(f"  [dry-run] {s} → {OG_DIR / (s + '.png')}")
        return

    # 処理済みslugスキップ機構（SD落ち対策）
    state = load_state()
    done_slugs = set(state.get("done", []))
    if done_slugs:
        print(f"  [Resume] スキップ済み: {len(done_slugs)} slugs")

    pending = [s for s in slugs if s not in done_slugs]
    if not pending:
        print("全スラッグ処理済み。完了。")
        return

    print(f"  処理対象: {len(pending)} slugs")

    # OGプロンプトベース: cowboy shot → upper body portrait
    og_base = SAKURA_BASE.replace("cowboy shot", "upper body, portrait, looking at viewer, centered")
    # ディテールアップ用追加プロンプト
    detail_extra = "skin texture, detailed skin, high detail"

    # 1. モデルをnovaに切替 (try/finallyで必ずwaiに戻す)
    switch_model(NOVA_MODEL)

    results = state.get("results", [])
    success = sum(1 for r in results if r.get("status") == "ok")
    fail    = sum(1 for r in results if r.get("status") == "fail")

    try:
        for i, slug in enumerate(pending, 1):
            print(f"\n[{i}/{len(pending)}] {slug}")
            og_path     = OG_DIR / f"{slug}.png"
            backup_path = OUTPUT_SD / f"og_nova_{slug}.png"

            scene  = get_scene_prompt(slug)
            prompt = f"{og_base}, {scene}"
            seed   = random.randint(0, 2147483647)
            print(f"  Scene: {scene} | Seed: {seed}")

            # txt2img
            print(f"  txt2img 1024x1024 ...")
            b64_t2i = txt2img(prompt, seed)
            if not b64_t2i:
                print(f"  FAILED (txt2img): {slug}")
                fail += 1
                results.append({"slug": slug, "status": "fail", "step": "txt2img", "seed": seed})
                state["done"].append(slug)   # 失敗もスキップ対象に（再試行はリセット後）
                state["results"] = results
                save_state(state)
                continue

            # img2img detail-up
            print(f"  img2img detail-up (denoising=0.30, steps=35) ...")
            detail_prompt = f"{prompt}, {detail_extra}"
            b64_i2i = img2img_detail_up(b64_t2i, detail_prompt, seed + 1)
            if not b64_i2i:
                print(f"  WARN: img2img failed, using txt2img result for {slug}")
                b64_final = b64_t2i
            else:
                b64_final = b64_i2i

            # クロップ & 保存
            print(f"  Cropping to 1200x624 ...")
            png_data = center_crop_to_og(b64_final)

            og_path.parent.mkdir(parents=True, exist_ok=True)
            og_path.write_bytes(png_data)
            print(f"  Saved OG: {og_path}")

            OUTPUT_SD.mkdir(parents=True, exist_ok=True)
            backup_path.write_bytes(png_data)
            print(f"  Backup:   {backup_path}")

            success += 1
            results.append({
                "slug": slug,
                "status": "ok",
                "seed": seed,
                "og_path": str(og_path),
                "backup": str(backup_path),
            })

            # 処理済みを即座に保存（クラッシュ時の復旧用）
            state["done"].append(slug)
            state["results"] = results
            save_state(state)

            if i < len(pending):
                time.sleep(1)

    finally:
        # try/finally で必ずwaiに戻す（異常終了対策）
        print(f"\nRestoring model → {WAI_MODEL} ...")
        try:
            switch_model(WAI_MODEL)
            print("Model restored OK")
        except Exception as e:
            print(f"WARNING: Failed to restore model: {e}")

    # 結果出力
    total = len(slugs)
    print(f"\n=== 完了 ===")
    print(f"成功: {success} / {total}, 失敗: {fail}")

    result_file = Path("/tmp/nova_og_batch1_results.json")
    result_file.write_text(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"詳細結果: {result_file}")

    # QC観点サマリ出力 (kurokawa_v1×nova画風・顔見切れ・複数人)
    print("\n=== QC確認観点 ===")
    print("重点チェック項目:")
    print("  1. kurokawa_v1 LoRA × novaAnimeXL 画風相性（透明感・線の細さ・色調）")
    print("  2. 顔見切れ（上部クロップで額が切れていないか）")
    print("  3. 複数人（2girls等の複数サクラ混入）")
    print("出力パス一覧:")
    for r in results:
        if r.get("status") == "ok":
            print(f"  [{r['slug']}] seed={r['seed']} → {r['og_path']}")

    if fail > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
