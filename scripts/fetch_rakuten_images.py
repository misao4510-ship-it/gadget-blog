#!/usr/bin/env python3
"""
楽天API商品画像取得スクリプト
使い方: .venv/bin/python3 scripts/fetch_rakuten_images.py

処理内容:
1. data/products.json を読み込む
2. 各商品の name で楽天IchibaItem/Search APIを検索（hits=1）
3. 1件目の商品画像URL（mediumImageUrls[0].imageUrl）を取得
4. image_url が未設定の商品のみ処理（既設定はスキップ）
5. products.json の各商品に image_url フィールドを追加して上書き保存
6. 取得できなかった商品は image_url を null のままにする
7. APIレート制限対応: 1リクエストごとに0.5秒sleep
"""

import json
import time
import urllib.request
import urllib.parse
import os
from pathlib import Path

# 設定読み込み
SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
CONFIG_FILE = PROJECT_DIR / "config" / "rakuten_auth.env"
PRODUCTS_FILE = PROJECT_DIR / "data" / "products.json"

def load_config():
    """config/rakuten_auth.env から認証情報を読み込む"""
    config = {}
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    config[key.strip()] = value.strip()
    return config

config = load_config()
APP_ID = config.get("RAKUTEN_APPLICATION_ID", "")
ACCESS_KEY = config.get("RAKUTEN_ACCESS_KEY", "")
ORIGIN = config.get("RAKUTEN_ORIGIN", "https://gadget-blog-dxq.pages.dev")
BASE_URL = "https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20220601"


def search_product(name):
    """楽天APIで商品検索し、画像URLを返す。取得失敗時はNoneを返す。"""
    params = urllib.parse.urlencode({
        "applicationId": APP_ID,
        "accessKey": ACCESS_KEY,
        "keyword": name,
        "hits": 1,
        "format": "json"
    })
    url = f"{BASE_URL}?{params}"
    try:
        req = urllib.request.Request(url)
        req.add_header("Origin", ORIGIN)
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.load(r)

        if "error" in data:
            raise ValueError(f"API error: {data.get('error')} - {data.get('error_description')}")

        items = data.get("Items", [])
        if items:
            imgs = items[0]["Item"].get("mediumImageUrls", [])
            if imgs:
                return imgs[0]["imageUrl"]
    except ValueError:
        raise
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        try:
            err_data = json.loads(body)
            raise ValueError(f"HTTP {e.code}: {err_data.get('error')} - {err_data.get('error_description')}")
        except (json.JSONDecodeError, KeyError):
            raise ValueError(f"HTTP {e.code}: {body[:200]}")
    except Exception as e:
        print(f"  Warning: {e}")
    return None


def main():
    print(f"楽天API画像取得スクリプト開始 (applicationId={APP_ID})")
    print(f"Products file: {PRODUCTS_FILE}")

    with open(PRODUCTS_FILE, encoding="utf-8") as f:
        data = json.load(f)

    products = data["products"]
    total = len(products)
    print(f"総商品数: {total}")

    # まず1件テスト
    test_product = products[0]
    print(f"\n--- APIテスト (商品: {test_product['name']}) ---")
    try:
        test_url = search_product(test_product["name"])
        if test_url:
            print(f"APIテスト成功: {test_url}")
        else:
            print("APIテスト: 画像URLなし（エラーではない）")
    except ValueError as e:
        print(f"APIテスト失敗: {e}")
        print("\n【エラー】applicationIdが無効です。")
        print("楽天デベロッパーポータル（https://webservice.rakuten.co.jp/）で")
        print("applicationIdを確認・取得してください。")
        print(f"config/rakuten_auth.env の RAKUTEN_APPLICATION_ID を更新してください。")
        return False

    # 全商品処理
    success_count = 0
    fail_count = 0
    skip_count = 0

    for i, product in enumerate(products):
        if product.get("image_url") is not None:
            skip_count += 1
            continue

        name = product.get("rakuten_keyword") or product.get("name")
        print(f"[{i+1}/{total}] {name} ... ", end="", flush=True)

        try:
            image_url = search_product(name)
            product["image_url"] = image_url
            if image_url:
                print(f"OK: {image_url[:60]}...")
                success_count += 1
            else:
                print("画像なし")
                fail_count += 1
        except ValueError as e:
            print(f"エラー: {e}")
            product["image_url"] = None
            fail_count += 1

        time.sleep(0.5)

    # 保存
    with open(PRODUCTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n完了: 成功={success_count}, 失敗={fail_count}, スキップ={skip_count}")
    print(f"products.json を更新しました。")
    return True


if __name__ == "__main__":
    main()
