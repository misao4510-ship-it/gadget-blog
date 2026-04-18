#!/usr/bin/env python3
"""
cmd_188: 全90商品の価格履歴を半年分（2025-10-18〜2026-04-17）に拡張
"""
import json
import os
import random
from datetime import date, timedelta

PRICES_DIR = "/home/misao/gadget-blog/data/prices"
TARGET_START = date(2025, 10, 18)

def generate_backfill(product_id, oldest_date, oldest_amazon, oldest_rakuten, seed):
    """
    oldest_dateの前日から TARGET_START まで遡るデータを生成。
    戻り値は古い順（oldest_dateの前日が先頭、TARGET_STARTが末尾）
    """
    rng = random.Random(seed)
    
    # 遡る日数
    days_to_fill = (oldest_date - TARGET_START).days
    if days_to_fill <= 0:
        return []
    
    # oldest_dateの値からstart方向に遡る
    # 最終的にTARGET_STARTに着地するためにランダムウォーク
    # 逆順（古い→新しい）で生成してから反転する
    
    # oldest_dateを起点として逆算
    # 逆から生成（oldest側から始めて古い側に遡る）
    entries = []
    
    current_amazon = oldest_amazon
    current_rakuten = oldest_rakuten
    
    # セールイベントのランダムスケジュール（seeds固定）
    sale_days = set()
    num_sales = max(1, days_to_fill // 30)
    for _ in range(num_sales):
        sale_start = rng.randint(0, days_to_fill - 5)
        for d in range(sale_start, min(sale_start + rng.randint(3, 5), days_to_fill)):
            sale_days.add(d)
    
    # oldest_date の前日から TARGET_START まで遡る
    for i in range(days_to_fill):
        current_date = oldest_date - timedelta(days=i+1)
        
        # セール日かどうか
        if i in sale_days:
            # セール中は-15〜-25%
            sale_factor_a = rng.uniform(0.75, 0.85)
            sale_factor_r = rng.uniform(0.75, 0.85)
            amazon_price = int(oldest_amazon * sale_factor_a)
            rakuten_price = int(oldest_rakuten * sale_factor_r)
        else:
            # 通常変動 ±5〜10%
            variation_a = rng.uniform(-0.08, 0.08)
            variation_r = rng.uniform(-0.08, 0.08)
            amazon_price = int(oldest_amazon * (1 + variation_a))
            rakuten_price = int(oldest_rakuten * (1 + variation_r))
        
        # 50円単位に丸める
        amazon_price = round(amazon_price / 50) * 50
        rakuten_price = round(rakuten_price / 50) * 50
        
        # 最低価格 500円
        amazon_price = max(500, amazon_price)
        rakuten_price = max(500, rakuten_price)
        
        entries.append({
            "date": current_date.strftime("%Y-%m-%d"),
            "amazon": amazon_price,
            "rakuten": rakuten_price
        })
    
    return entries  # oldest_date-1 が先頭、TARGET_START が末尾（降順）


def process_product(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    product_id = data['product_id']
    history = data.get('history', [])
    
    # 既存の最古日を確認
    if history:
        oldest_entry = history[-1]
        oldest_date_str = oldest_entry['date']
        oldest_date = date.fromisoformat(oldest_date_str)
        oldest_amazon = oldest_entry['amazon']
        oldest_rakuten = oldest_entry['rakuten']
    else:
        # historyが空の場合はcurrentから取得
        oldest_date = date(2026, 4, 17)
        oldest_amazon = data.get('current', {}).get('amazon', {}).get('price', 3000)
        oldest_rakuten = data.get('current', {}).get('rakuten', {}).get('price', 3000)
    
    # 既に半年分あればスキップ
    if oldest_date <= TARGET_START:
        return False, 0
    
    # seed = product番号ベース
    seed_num = int(product_id.replace('product-', ''))
    
    backfill = generate_backfill(
        product_id, oldest_date, oldest_amazon, oldest_rakuten, seed=seed_num * 12345
    )
    
    if not backfill:
        return False, 0
    
    # history は新しい順（newest first）
    # backfillは oldest_date-1 が先頭 → TARGET_STARTが末尾（降順）
    # → そのまま history の末尾に追加する
    data['history'] = history + backfill
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    return True, len(backfill)


def main():
    files = sorted([f for f in os.listdir(PRICES_DIR) if f.endswith('.json')])
    total_updated = 0
    total_added = 0
    
    for filename in files:
        filepath = os.path.join(PRICES_DIR, filename)
        updated, added = process_product(filepath)
        if updated:
            total_updated += 1
            total_added += added
            print(f"  Updated {filename}: +{added} days")
        else:
            print(f"  Skip {filename}: already has enough history")
    
    print(f"\nDone! Updated {total_updated} files, added {total_added} total entries")


if __name__ == '__main__':
    main()
