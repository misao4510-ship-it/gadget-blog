#!/usr/bin/env bash
# daily_rebuild.sh — 毎日空コミットでCloudflare Pagesのリビルドをトリガーする
# cron: 0 0 * * * bash /home/misao/gadget-blog/scripts/daily_rebuild.sh

set -e

cd /home/misao/gadget-blog

# gitユーザー設定
git config user.email "misao_4510@yahoo.co.jp" 2>/dev/null || true
git config user.name "misao" 2>/dev/null || true

TODAY=$(date '+%Y-%m-%d')

# 空コミットでリビルドトリガー
git commit --allow-empty -m "chore: daily rebuild trigger ${TODAY}"
git push origin main

echo "[$(date)] daily_rebuild.sh: push completed for ${TODAY}"
