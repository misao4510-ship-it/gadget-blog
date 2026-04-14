#!/bin/bash
# note.com転載ワンコマンド実行スクリプト
# 使用法: bash scripts/note_publish.sh <slug>
# 例: bash scripts/note_publish.sh amazon-basics-aa-battery-review

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BLOG_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SLUG="$1"

if [ -z "$SLUG" ]; then
    echo "使用法: $0 <slug>"
    exit 1
fi

echo "📝 note転載開始: $SLUG"

# Step 1: 挿絵生成
echo "🎨 挿絵生成中..."
python3 "$SCRIPT_DIR/note_generate_illustrations.py" --slug "$SLUG" || {
    echo "⚠️  挿絵生成失敗（SD API未起動の可能性）。挿絵なしで続行します。"
}

# Step 2: note投稿（サクラ音声変換+挿絵+Telegram通知）
echo "📤 note投稿中..."
python3 "$SCRIPT_DIR/note_post.py" \
    --slug "$SLUG" \
    --sakura-voice \
    --with-illustrations \
    --telegram-notify

echo "✅ note転載完了: $SLUG"
