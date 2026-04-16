#!/usr/bin/env bash
# note.com 自動転載スクリプト (cmd_174)
# cronで毎朝8:00に実行され、未転載の新記事を自動投稿する
#
# Usage:
#   bash scripts/note_auto_post.sh           # 通常実行
#   bash scripts/note_auto_post.sh --dry-run # ドライラン（投稿しない）
#
# 動作:
#   1. gadget-blog/src/content/posts/ の全記事 vs config/note_posted.yaml を比較
#   2. 未転載記事をnote.comに投稿（サクラ口調そのまま、ブログ画像流用）
#   3. Telegram通知

set -euo pipefail

BLOG_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG_FILE="/tmp/note_auto_post.log"
DRY_RUN=""

if [[ "${1:-}" == "--dry-run" ]]; then
    DRY_RUN="--dry-run"
fi

echo "$(date '+%Y-%m-%d %H:%M:%S') note自動転載 開始" | tee -a "$LOG_FILE"

cd "$BLOG_ROOT"

python3 scripts/note_post.py \
    --all-new \
    --no-sakura-voice \
    --blog-images \
    --limit 3 \
    --telegram-notify \
    ${DRY_RUN} \
    2>&1 | tee -a "$LOG_FILE"

echo "$(date '+%Y-%m-%d %H:%M:%S') note自動転載 完了" | tee -a "$LOG_FILE"
