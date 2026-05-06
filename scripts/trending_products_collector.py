#!/usr/bin/env python3
"""
gadget-blog 売れ筋ガジェット検出daemon (cmd_358-A)
毎朝6:30にcronで実行。楽天Search APIの標準順位から前日比急上昇TOP5を抽出。

注意: 楽天Ranking APIは openapi.rakuten.co.jp では非公開のため、
IchibaItem/Search の sort=standard（人気順）で代替している。
"""
import os, sys, time, urllib.request, urllib.parse, json, yaml
from datetime import datetime, date, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
BLOG_DIR = SCRIPT_DIR.parent
DATA_DIR = BLOG_DIR / 'data'
DATA_DIR.mkdir(exist_ok=True)

HISTORY_FILE = DATA_DIR / 'trending_history.yaml'
TODAY_FILE   = DATA_DIR / 'trending_today.yaml'

CONFIG_FILE = BLOG_DIR / 'config' / 'rakuten_auth.env'

BASE_URL = 'https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20220601'

# ガジェット系カテゴリ（genreId or keyword）
CATEGORIES = {
    '家電': {'genreId': '100026'},
    'スマホ・周辺機器': {'genreId': '564500'},
    'ノートPC・タブレット': {'keyword': 'ノートパソコン'},
    'TV・カメラ': {'keyword': 'テレビ'},
}

HITS_PER_CATEGORY = 30


def load_config():
    config = {}
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, _, value = line.partition('=')
                    config[key.strip()] = value.strip()
    return config


def fetch_popular_items(app_id: str, access_key: str, origin: str,
                        category_params: dict, hits: int = 30) -> list[dict]:
    params_dict = {
        'applicationId': app_id,
        'accessKey': access_key,
        'hits': hits,
        'sort': 'standard',
        'format': 'json',
        **category_params,
    }
    params = urllib.parse.urlencode(params_dict)
    req = urllib.request.Request(f'{BASE_URL}?{params}')
    req.add_header('Origin', origin)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            items = data.get('Items', [])
            result = []
            for i, item_w in enumerate(items):
                item = item_w['Item']
                image_url = ''
                if item.get('mediumImageUrls'):
                    image_url = item['mediumImageUrls'][0].get('imageUrl', '')
                result.append({
                    'rank': i + 1,
                    'item_code': item['itemCode'],
                    'name': item['itemName'],
                    'price': item['itemPrice'],
                    'url': item.get('itemUrl', ''),
                    'image_url': image_url,
                    'shop': item.get('shopName', ''),
                    'review_count': item.get('reviewCount', 0),
                })
            return result
    except urllib.error.HTTPError as e:
        print(f'[WARN] fetch failed ({e.code}): {category_params}', file=sys.stderr)
        return []
    except Exception as e:
        print(f'[WARN] fetch error: {e}', file=sys.stderr)
        return []


def load_history() -> dict:
    if HISTORY_FILE.exists():
        with open(HISTORY_FILE) as f:
            return yaml.safe_load(f) or {}
    return {}


def save_history(history: dict):
    with open(HISTORY_FILE, 'w') as f:
        yaml.dump(history, f, allow_unicode=True, default_flow_style=False)


def calc_top5(today_data: dict, history: dict) -> list[dict]:
    yesterday_str = (date.today() - timedelta(days=1)).isoformat()
    yesterday = history.get(yesterday_str, {})

    candidates = []
    for genre, items in today_data.items():
        for item in items:
            code = item['item_code']
            prev_data = yesterday.get(genre, {}).get(code, {})
            prev_rank = prev_data.get('rank', 999)
            rank_change = prev_rank - item['rank']  # 正=上昇
            score = rank_change * 2 + (HITS_PER_CATEGORY - item['rank'])
            candidates.append({
                **item,
                'category': genre,
                'prev_rank': prev_rank,
                'rank_change': rank_change,
                'score': score,
            })

    top5 = sorted(candidates, key=lambda x: x['score'], reverse=True)[:5]
    return top5


def main():
    config = load_config()
    app_id = config.get('RAKUTEN_APPLICATION_ID', '')
    access_key = config.get('RAKUTEN_ACCESS_KEY', '')
    origin = config.get('RAKUTEN_ORIGIN', 'https://gadget-blog-dxq.pages.dev')

    if not app_id or not access_key:
        print('[ERROR] RAKUTEN_APPLICATION_ID / RAKUTEN_ACCESS_KEY が未設定', file=sys.stderr)
        sys.exit(1)

    today_str = date.today().isoformat()
    print(f'[trending_collector] {today_str} 実行開始')

    today_data = {}
    for genre_name, category_params in CATEGORIES.items():
        items = fetch_popular_items(app_id, access_key, origin, category_params, HITS_PER_CATEGORY)
        today_data[genre_name] = items
        print(f'  {genre_name}: {len(items)}件取得')
        time.sleep(1.0)  # レート制限対応

    history = load_history()
    history[today_str] = {
        genre: {item['item_code']: {'rank': item['rank'], 'price': item['price']}
                for item in items}
        for genre, items in today_data.items()
    }
    # 30日超の古い履歴を削除
    cutoff = (date.today() - timedelta(days=30)).isoformat()
    history = {k: v for k, v in history.items() if k >= cutoff}
    save_history(history)

    top5 = calc_top5(today_data, history)

    output = {
        'date': today_str,
        'generated_at': datetime.now().isoformat(),
        'top5': top5,
    }
    with open(TODAY_FILE, 'w') as f:
        yaml.dump(output, f, allow_unicode=True, default_flow_style=False)

    print(f'[trending_collector] TOP5:')
    for i, item in enumerate(top5, 1):
        print(f'  {i}. {item["name"][:40]} (rank_change: +{item["rank_change"]})')
    print(f'[trending_collector] → {TODAY_FILE}')


if __name__ == '__main__':
    main()
