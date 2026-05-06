#!/usr/bin/env python3
"""
cmd_359-C: YouTube動画説明欄から商品情報を抽出してアフィリリンク生成
"""
import re
import os
import sys
import requests
import yaml
from pathlib import Path
from dotenv import load_dotenv
from urllib.parse import quote

BLOG_DIR = Path(__file__).parent.parent
TODAY_FILE = BLOG_DIR / 'data' / 'youtube_today.yaml'

load_dotenv(BLOG_DIR / 'config' / 'rakuten_auth.env')
load_dotenv(BLOG_DIR / 'config' / 'moshimo_auth.env')

RAKUTEN_APP_ID = os.environ.get('RAKUTEN_APPLICATION_ID', '')
RAKUTEN_AFFILIATE = os.environ.get('RAKUTEN_AFFILIATE_ID', '')
MOSHIMO_A_ID = os.environ.get('MOSHIMO_AMAZON_A_ID', '')
MOSHIMO_A_P_ID = os.environ.get('MOSHIMO_AMAZON_P_ID', '')
MOSHIMO_A_PC_ID = os.environ.get('MOSHIMO_AMAZON_PC_ID', '185')
MOSHIMO_A_PL_ID = os.environ.get('MOSHIMO_AMAZON_PL_ID', '4072')

# Amazon URL パターン
AMAZON_URL_PATTERNS = [
    r'amazon\.co\.jp/(?:dp|gp/product)/([A-Z0-9]{10})',
    r'amazon\.co\.jp/exec/obidos/ASIN/([A-Z0-9]{10})',
    r'amzn\.to/([A-Za-z0-9]+)',
    r'a\.co/([A-Za-z0-9]+)',
]
RAKUTEN_URL_PATTERN = r'(https?://item\.rakuten\.co\.jp/[^\s\)\]>]+)'


def extract_amazon_entries(text: str) -> list[dict]:
    """説明欄からAmazon URLまたはASINを抽出して返す"""
    entries = []
    seen_asins = set()
    seen_short = set()
    for pattern in AMAZON_URL_PATTERNS:
        for m in re.finditer(pattern, text):
            token = m.group(1)
            if len(token) == 10 and token.isupper():  # ASIN
                if token not in seen_asins:
                    seen_asins.add(token)
                    entries.append({'type': 'asin', 'asin': token,
                                    'amazon_url': f'https://www.amazon.co.jp/dp/{token}'})
            else:  # 短縮URL
                if token not in seen_short:
                    seen_short.add(token)
                    entries.append({'type': 'short', 'token': token,
                                    'amazon_url': f'https://amzn.to/{token}'})
    return entries


def extract_rakuten_urls(text: str) -> list[str]:
    return list(dict.fromkeys(re.findall(RAKUTEN_URL_PATTERN, text)))


def to_moshimo_amazon(amazon_url: str) -> str:
    """Amazon URLをもしも経由アフィリリンクに変換"""
    m = re.search(r'/dp/([A-Z0-9]{10})', amazon_url)
    asin = m.group(1) if m else ''
    if not asin or not MOSHIMO_A_ID:
        return amazon_url
    encoded_url = quote(f'https://www.amazon.co.jp/dp/{asin}', safe='')
    return (f'https://af.moshimo.com/af/c/click?a_id={MOSHIMO_A_ID}'
            f'&p_id={MOSHIMO_A_P_ID}&pc_id={MOSHIMO_A_PC_ID}&pl_id={MOSHIMO_A_PL_ID}'
            f'&url={encoded_url}')


def to_moshimo_rakuten(rakuten_url: str) -> str:
    """楽天URLをもしも経由に変換"""
    a_id = os.environ.get('MOSHIMO_RAKUTEN_A_ID', '5471111')
    p_id = os.environ.get('MOSHIMO_RAKUTEN_P_ID', '54')
    pc_id = os.environ.get('MOSHIMO_RAKUTEN_PC_ID', '54')
    pl_id = os.environ.get('MOSHIMO_RAKUTEN_PL_ID', '616')
    encoded_url = quote(rakuten_url, safe='')
    return (f'https://af.moshimo.com/af/c/click?a_id={a_id}'
            f'&p_id={p_id}&pc_id={pc_id}&pl_id={pl_id}&url={encoded_url}')


def search_rakuten(query: str, hits: int = 3) -> list[dict]:
    """商品名で楽天検索して上位商品を返す"""
    if not RAKUTEN_APP_ID:
        print(f'[WARN] RAKUTEN_APPLICATION_ID未設定', file=sys.stderr)
        return []
    try:
        resp = requests.get(
            'https://app.rakuten.co.jp/services/api/IchibaItem/Search/20220601',
            params={
                'applicationId': RAKUTEN_APP_ID,
                'affiliateId': RAKUTEN_AFFILIATE,
                'keyword': query,
                'hits': hits,
                'format': 'json',
            },
            timeout=10,
        )
        items = resp.json().get('Items', [])
        results = []
        for it in items:
            item = it['Item']
            url = item.get('affiliateUrl') or item.get('itemUrl', '')
            results.append({
                'name': item['itemName'],
                'price': item['itemPrice'],
                'url': url,
                'image_url': (item['mediumImageUrls'][0]['imageUrl']
                              if item.get('mediumImageUrls') else ''),
            })
        return results
    except Exception as e:
        print(f'[WARN] 楽天検索失敗 ({query}): {e}', file=sys.stderr)
        return []


def extract_product_name_from_title(title: str) -> str:
    """動画タイトルから商品名候補を抽出"""
    patterns = [
        r'【(.+?)】',
        r'「(.+?)」',
        r'^\[(.+?)\]',
        r'^(.+?)(?:を|が|は|の|レビュー|紹介|使って|買って|開封)',
    ]
    for p in patterns:
        m = re.search(p, title)
        if m and len(m.group(1)) > 3:
            return m.group(1).strip()
    return title[:30]


def process_video(video: dict) -> list[dict]:
    """1動画から商品情報を抽出してリストで返す"""
    title = video.get('title', '')
    desc = video.get('description', '')
    combined = desc + ' ' + title
    products = []

    # 1. Amazon URL抽出 → もしも変換
    for entry in extract_amazon_entries(combined):
        url = entry['amazon_url']
        affiliate = to_moshimo_amazon(url) if entry['type'] == 'asin' else url
        products.append({
            'source': 'amazon_url',
            'amazon_url': url,
            'amazon_affiliate': affiliate,
        })

    # 2. 楽天URL抽出 → もしも変換
    for url in extract_rakuten_urls(desc):
        products.append({
            'source': 'rakuten_url',
            'rakuten_url': url,
            'rakuten_affiliate': to_moshimo_rakuten(url),
        })

    # 3. タイトルから商品名で楽天検索（URL抽出できなかった場合）
    if not products:
        query = extract_product_name_from_title(title)
        results = search_rakuten(query, hits=2)
        for r in results:
            rakuten_affiliate = to_moshimo_rakuten(r['url']) if r['url'] else ''
            products.append({
                'source': 'rakuten_search',
                'query': query,
                'name': r['name'],
                'price': r['price'],
                'rakuten_url': r['url'],
                'rakuten_affiliate': rakuten_affiliate,
                'image_url': r['image_url'],
            })

    return products[:3]


def main():
    if not TODAY_FILE.exists():
        print(f'[ERROR] {TODAY_FILE} が見つかりません', file=sys.stderr)
        sys.exit(1)

    with open(TODAY_FILE) as f:
        data = yaml.safe_load(f)

    if not data:
        print('[ERROR] youtube_today.yaml が空です', file=sys.stderr)
        sys.exit(1)

    videos = data.get('new_videos', [])
    if not videos:
        print('[INFO] new_videos が空です。処理対象なし。')
        return

    for video in videos:
        products = process_video(video)
        video['products'] = products
        print(f"  [{video.get('channel_name', '?')}] {video.get('title', '')[:40]}: {len(products)}商品")

    data['products_extracted'] = True
    with open(TODAY_FILE, 'w') as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False)

    print(f'[extractor] {len(videos)}動画の商品抽出完了 → {TODAY_FILE}')


if __name__ == '__main__':
    main()
