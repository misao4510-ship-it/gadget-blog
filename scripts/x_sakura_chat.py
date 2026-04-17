#!/usr/bin/env python3
"""
サクラ雑談ツイートスクリプト (cmd_179 / cmd_171 施策⑥)

記事紹介以外の「サクラキャラとしての雑談ツイート」をサクラ画像付きで投稿する。
data/x_chat_templates.json から未使用（または7日以上経過）のテンプレートを
ランダム選択して投稿。

Usage:
    python3 scripts/x_sakura_chat.py              # 通常投稿（10:00/15:00/18:00 cron）
    python3 scripts/x_sakura_chat.py --dry-run    # ログのみ（投稿しない）
    python3 scripts/x_sakura_chat.py --category 豆知識  # カテゴリ指定
    python3 scripts/x_sakura_chat.py --no-image   # テキストのみ投稿（画像生成なし）
    python3 scripts/x_sakura_chat.py --list       # テンプレート一覧表示
"""

import argparse
import base64
import json
import logging
import random
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

BLOG_ROOT = Path(__file__).parent.parent.resolve()
TEMPLATES_FILE = BLOG_ROOT / "data" / "x_chat_templates.json"
TELEGRAM_AUTH = Path("/mnt/c/tools/multi-agent-shogun/config/telegram_auth.env")
SD_FORGE_API = "http://172.18.208.1:7860"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# 7日以上経過したテンプレートは再利用可能とみなす
REUSE_DAYS = 7

# サクラテンプレート（殿確定 2026-04-15）
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
    "cropped head, head out of frame, cut off head, nsfw, nude, naked"
)

# カテゴリ別のポーズ指定
CATEGORY_POSES = {
    "豆知識":     f"{SAKURA_BASE}, holding book, explaining, finger raised, didactic pose, cheerful expression",
    "季節ネタ":   f"{SAKURA_BASE}, seasonal background, bright smile, cheerful, waving hand, greeting",
    "テック小話": f"{SAKURA_BASE}, holding gadget, excited expression, pointing, showing, presentation",
    "日常サクラ": f"{SAKURA_BASE}, casual pose, gentle smile, relaxed, friendly, heart hands",
    "おすすめ小ネタ": f"{SAKURA_BASE}, thumbs up, winking, happy, grin, one eye closed, recommending",
    "防災・備蓄": f"{SAKURA_BASE}, serious expression, holding emergency kit, cautious, informative pose",
}
DEFAULT_POSE = f"{SAKURA_BASE}, smile, cheerful, waving hand, greeting"


def load_env(path: Path) -> dict:
    env = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip()
    return env


def send_telegram(text: str):
    import requests
    env = load_env(TELEGRAM_AUTH)
    bot_token = env.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = env.get("TELEGRAM_CHAT_ID", "")
    if bot_token and chat_id:
        try:
            requests.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={"chat_id": chat_id, "text": text},
                timeout=30,
            )
        except Exception as e:
            logger.warning(f"Telegram通知失敗: {e}")


def load_templates() -> dict:
    if not TEMPLATES_FILE.exists():
        logger.error(f"テンプレートファイルが見つかりません: {TEMPLATES_FILE}")
        sys.exit(1)
    return json.loads(TEMPLATES_FILE.read_text(encoding="utf-8"))


def save_templates(data: dict):
    TEMPLATES_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def is_available(tmpl: dict) -> bool:
    """テンプレートが使用可能か判定"""
    if not tmpl.get("used", False):
        return True
    last_used = tmpl.get("last_used")
    if not last_used:
        return True
    try:
        last_dt = datetime.fromisoformat(last_used)
        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        return (now - last_dt) >= timedelta(days=REUSE_DAYS)
    except Exception:
        return True


def pick_template(templates: list, category: str = None) -> dict:
    """
    未使用（または7日以上経過）のテンプレートからランダム選択。
    全て使用済みの場合は最も古いものを選択。
    """
    candidates = [t for t in templates if is_available(t)]
    if category:
        cat_candidates = [t for t in candidates if t.get("category") == category]
        if cat_candidates:
            candidates = cat_candidates
        else:
            logger.warning(f"カテゴリ '{category}' に利用可能なテンプレートがありません。全テンプレートから選択します。")

    if candidates:
        return random.choice(candidates)

    # 全て使用済み → 最も古いものを選択
    logger.info("全テンプレート使用済み。最も古いものを再利用します。")
    fallback = templates
    if category:
        cat_fallback = [t for t in templates if t.get("category") == category]
        if cat_fallback:
            fallback = cat_fallback

    def last_used_key(t):
        lu = t.get("last_used")
        if not lu:
            return "0000-01-01T00:00:00+00:00"
        return lu

    return min(fallback, key=last_used_key)


def mark_used(data: dict, tmpl_id: int):
    """テンプレートを使用済みとしてマーク"""
    now_str = datetime.now(timezone.utc).isoformat()
    for t in data["templates"]:
        if t["id"] == tmpl_id:
            t["used"] = True
            t["last_used"] = now_str
            break


def generate_sakura_image(category: str, output_path: Path) -> bool:
    """SD Forge APIでサクラ画像を生成 (1024×1536)"""
    import requests as req

    prompt = CATEGORY_POSES.get(category, DEFAULT_POSE)
    payload = {
        "prompt": prompt,
        "negative_prompt": NEGATIVE,
        "seed": random.randint(0, 2147483647),
        "steps": 28,
        "cfg_scale": 7,
        "width": 1024,
        "height": 1536,
        "sampler_name": "DPM++ 2M SDE",
        "scheduler": "Karras",
        "batch_size": 1,
        "n_iter": 1,
        "override_settings": {
            "sd_model_checkpoint": "novaAnimeXL_ilV170.safetensors",
        },
    }
    logger.info(f"SD Forge APIでサクラ画像生成中: {category}")
    try:
        resp = req.post(f"{SD_FORGE_API}/sdapi/v1/txt2img", json=payload, timeout=120)
        resp.raise_for_status()
        result = resp.json()
        img_b64 = result["images"][0]
        img_bytes = base64.b64decode(img_b64)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(img_bytes)
        logger.info(f"画像生成完了: {output_path}")
        return True
    except req.exceptions.ConnectionError:
        logger.warning(f"SD Forge API ({SD_FORGE_API}) に接続できません。テキストのみで投稿します。")
        return False
    except Exception as e:
        logger.warning(f"画像生成失敗: {e}。テキストのみで投稿します。")
        return False


def main():
    parser = argparse.ArgumentParser(description="サクラ雑談ツイート投稿スクリプト")
    parser.add_argument("--dry-run", action="store_true", help="実際に投稿せずログのみ表示")
    parser.add_argument("--category", type=str,
                        help="指定カテゴリから選択 (豆知識/季節ネタ/テック小話/日常サクラ/おすすめ小ネタ/防災・備蓄)")
    parser.add_argument("--no-image", action="store_true", help="テキストのみ投稿（画像生成スキップ）")
    parser.add_argument("--list", action="store_true", help="テンプレート一覧を表示して終了")
    args = parser.parse_args()

    data = load_templates()
    templates = data.get("templates", [])

    if args.list:
        for t in templates:
            avail = "✓" if is_available(t) else "✗"
            print(f"[{avail}] id={t['id']} [{t['category']}] {t['text'][:60]}...")
        return

    tmpl = pick_template(templates, args.category)
    tweet_text = tmpl["text"]
    tmpl_id = tmpl["id"]
    category = tmpl.get("category", "")

    logger.info(f"選択テンプレート: id={tmpl_id} [{category}]")
    logger.info(f"ツイート内容:\n{tweet_text}")

    if args.dry_run:
        logger.info("[DRY RUN] 投稿スキップ。")
        return

    # サクラ画像生成
    image_path = None
    if not args.no_image:
        now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        img_file = Path(f"/tmp/sakura_chat_{now_str}.png")
        if generate_sakura_image(category, img_file):
            image_path = str(img_file)

    # x_scheduled_post.py の post_to_x 関数で画像付き投稿
    try:
        sys.path.insert(0, str(BLOG_ROOT / "scripts"))
        from x_scheduled_post import post_to_x
        success = post_to_x(tweet_text, image_path)

        if success:
            # 使用済みマーク + 保存
            mark_used(data, tmpl_id)
            save_templates(data)
            logger.info("テンプレート使用状態を更新しました。")
            img_info = "🖼️画像付き" if image_path else "テキストのみ"
            send_telegram(f"🌸 サクラ雑談ツイート投稿完了 ({img_info})\n[{category}]\n{tweet_text[:80]}...")
            logger.info("Telegram通知済み。")
        else:
            logger.error("投稿失敗（post_to_x がFalseを返した）")
            send_telegram(f"❌ サクラ雑談ツイート失敗\n[{category}]\n投稿処理エラー")
            sys.exit(1)
    except Exception as e:
        logger.error(f"投稿失敗: {e}")
        send_telegram(f"❌ サクラ雑談ツイート失敗\n{e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
