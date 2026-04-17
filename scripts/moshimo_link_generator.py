#!/usr/bin/env python3
"""
もしもアフィリエイト 3ショップリンク生成スクリプト (cmd_181)

Amazon URL から もしもアフィリエイト経由の3ショップリンクを生成し、
記事内挿入用のHTMLを出力する。

Usage:
    python3 scripts/moshimo_link_generator.py --amazon-url https://amzn.to/XXXXX
    python3 scripts/moshimo_link_generator.py --amazon-url https://amzn.to/XXXXX --keyword "商品名"
    python3 scripts/moshimo_link_generator.py --amazon-url URL --rakuten-url URL --yahoo-url URL
    python3 scripts/moshimo_link_generator.py --html  # HTMLブロックのみ出力
"""

import argparse
import sys
import urllib.parse
from pathlib import Path

BLOG_ROOT = Path(__file__).parent.parent.resolve()

# もしもアフィリエイト ID設定
MOSHIMO = {
    "amazon": {
        "a_id": "5471177", "p_id": "170", "pc_id": "185", "pl_id": "4072",
        "base": "https://af.moshimo.com/af/c/click",
    },
    "rakuten": {
        "a_id": "5471111", "p_id": "54", "pc_id": "54", "pl_id": "616",
        "base": "https://af.moshimo.com/af/c/click",
    },
    "yahoo": {
        "a_id": "5494175", "p_id": "1225", "pc_id": "1925", "pl_id": "19165",
        "base": "https://af.moshimo.com/af/c/click",
    },
}


def make_moshimo_url(shop: str, product_url: str) -> str:
    """商品URLをもしもアフィリエイトリンクに変換"""
    m = MOSHIMO[shop]
    params = {
        "a_id": m["a_id"],
        "p_id": m["p_id"],
        "pc_id": m["pc_id"],
        "pl_id": m["pl_id"],
        "url": product_url,
    }
    return m["base"] + "?" + urllib.parse.urlencode(params)


def make_rakuten_search_url(keyword: str) -> str:
    """楽天商品検索URL（キーワード指定）"""
    encoded = urllib.parse.quote(keyword)
    return f"https://search.rakuten.co.jp/search/mall/{encoded}/"


def make_yahoo_search_url(keyword: str) -> str:
    """Yahoo!ショッピング商品検索URL（キーワード指定）"""
    return f"https://shopping.yahoo.co.jp/search?p={urllib.parse.quote(keyword)}"


def make_impression_tags() -> str:
    """もしもインプレッションタグ（各ショップ1x1 gif）"""
    tags = []
    for shop in ["amazon", "rakuten", "yahoo"]:
        m = MOSHIMO[shop]
        tags.append(
            f'<img src="https://i.moshimo.com/af/i/impression?a_id={m["a_id"]}&p_id={m["p_id"]}" '
            f'width="1" height="1" style="display:none" />'
        )
    return "\n".join(tags)


def generate_shop_links_html(
    amazon_url: str,
    rakuten_url: str = None,
    yahoo_url: str = None,
    with_impression: bool = True,
) -> str:
    """
    3ショップボタンのHTMLブロックを生成。

    Args:
        amazon_url: Amazon商品URL（amzn.to or amazon.co.jp）
        rakuten_url: 楽天商品URL（Noneの場合はボタンなし）
        yahoo_url: Yahoo!ショッピング商品URL（Noneの場合はボタンなし）
        with_impression: インプレッションタグを含めるか
    """
    amazon_moshimo = make_moshimo_url("amazon", amazon_url)
    lines = ['<div class="shop-links-wrap">']
    lines.append(
        f'  <a href="{amazon_moshimo}" class="btn-amazon" target="_blank" rel="noopener nofollow">'
        '🛒 Amazonで見る</a>'
    )
    if rakuten_url:
        rakuten_moshimo = make_moshimo_url("rakuten", rakuten_url)
        lines.append(
            f'  <a href="{rakuten_moshimo}" class="btn-rakuten" target="_blank" rel="noopener nofollow">'
            '🛒 楽天で見る</a>'
        )
    if yahoo_url:
        yahoo_moshimo = make_moshimo_url("yahoo", yahoo_url)
        lines.append(
            f'  <a href="{yahoo_moshimo}" class="btn-yahoo" target="_blank" rel="noopener nofollow">'
            '🛒 Yahoo!で見る</a>'
        )
    lines.append('</div>')
    if with_impression:
        lines.append(make_impression_tags())
    return "\n".join(lines)


def load_moshimo_env() -> dict:
    """config/moshimo_auth.env から設定を読み込み（ID確認用）"""
    env = {}
    env_file = BLOG_ROOT / "config" / "moshimo_auth.env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip()
    return env


def main():
    parser = argparse.ArgumentParser(description="もしもアフィリエイト 3ショップリンク生成")
    parser.add_argument("--amazon-url", required=True, help="Amazon商品URL (amzn.to or amazon.co.jp)")
    parser.add_argument("--rakuten-url", help="楽天商品URL（省略時は楽天ボタンなし）")
    parser.add_argument("--yahoo-url", help="Yahoo!ショッピング商品URL（省略時はYahoo!ボタンなし）")
    parser.add_argument("--keyword", help="楽天/Yahoo!検索キーワード（--rakuten-url/--yahoo-url省略時に使用）")
    parser.add_argument("--no-impression", action="store_true", help="インプレッションタグを除外")
    args = parser.parse_args()

    rakuten_url = args.rakuten_url
    yahoo_url = args.yahoo_url

    if args.keyword:
        if not rakuten_url:
            rakuten_url = make_rakuten_search_url(args.keyword)
            print(f"[楽天] 検索URL生成: {rakuten_url}", file=sys.stderr)
        if not yahoo_url:
            yahoo_url = make_yahoo_search_url(args.keyword)
            print(f"[Yahoo!] 検索URL生成: {yahoo_url}", file=sys.stderr)

    html = generate_shop_links_html(
        amazon_url=args.amazon_url,
        rakuten_url=rakuten_url,
        yahoo_url=yahoo_url,
        with_impression=not args.no_impression,
    )
    print(html)


if __name__ == "__main__":
    main()
