#!/usr/bin/env python3
"""
もしもアフィリエイト バッチ記事更新スクリプト (cmd_181)

既存記事のAmazonリンクをもしもアフィリエイト経由の3ショップリンクに差し替える。
バッチ処理プロトコルに従い、batch1(5件)でQCゲートを通過してから残りを処理する。

Usage:
    python3 scripts/moshimo_batch_update.py --batch 1 --dry-run
    python3 scripts/moshimo_batch_update.py --batch 1
    python3 scripts/moshimo_batch_update.py --slug anker-powerbank-25000-builtin-cable-review
"""

import argparse
import re
import sys
import urllib.parse
from pathlib import Path

BLOG_ROOT = Path(__file__).parent.parent.resolve()
POSTS_DIR = BLOG_ROOT / "src" / "content" / "posts"

# もしもアフィリエイト ID
MOSHIMO_AMAZON_AID = "5471177"
MOSHIMO_AMAZON_PID = "170"
MOSHIMO_AMAZON_PCID = "185"
MOSHIMO_AMAZON_PLID = "4072"

MOSHIMO_RAKUTEN_AID = "5471111"
MOSHIMO_RAKUTEN_PID = "54"
MOSHIMO_RAKUTEN_PCID = "54"
MOSHIMO_RAKUTEN_PLID = "616"

MOSHIMO_YAHOO_AID = "5494175"
MOSHIMO_YAHOO_PID = "1225"
MOSHIMO_YAHOO_PCID = "1925"
MOSHIMO_YAHOO_PLID = "19165"

IMPRESSION_TAGS = (
    f'<img src="https://i.moshimo.com/af/i/impression?a_id={MOSHIMO_AMAZON_AID}&p_id={MOSHIMO_AMAZON_PID}" '
    f'width="1" height="1" style="display:none" />\n'
    f'<img src="https://i.moshimo.com/af/i/impression?a_id={MOSHIMO_RAKUTEN_AID}&p_id={MOSHIMO_RAKUTEN_PID}" '
    f'width="1" height="1" style="display:none" />\n'
    f'<img src="https://i.moshimo.com/af/i/impression?a_id={MOSHIMO_YAHOO_AID}&p_id={MOSHIMO_YAHOO_PID}" '
    f'width="1" height="1" style="display:none" />'
)


# バッチ定義: {slug: {amazon_url, keyword}}
BATCH_DATA = {
    1: [
        {
            "slug": "anker-powerbank-25000-builtin-cable-review",
            "amazon_url": "https://amzn.to/4sCrvzW",
            "keyword": "Anker Power Bank 25000mAh ケーブル内蔵",
        },
        {
            "slug": "fedour-aquarium-air-pump-review",
            "amazon_url": "https://amzn.to/4tIpJ12",
            "keyword": "FEDOUR 水槽 エアーポンプ",
        },
        {
            "slug": "final-ze500-asmr-3d-review",
            "amazon_url": "https://amzn.to/4vmCbVY",
            "keyword": "final ZE500 イヤホン",
        },
        {
            "slug": "ciniffo-electric-air-duster-review",
            "amazon_url": "https://amzn.to/4mtSwUP",
            "keyword": "CINIFFO 電動エアダスター",
        },
        {
            "slug": "deoway-card-case-review",
            "amazon_url": "https://amzn.to/4eorbkN",
            "keyword": "DEOWAY 名刺入れ カードケース",
        },
    ],
    2: [
        {"slug": "amazon-basics-aa-battery-review", "amazon_url": "https://amzn.to/47JsGpU", "keyword": "Amazon ベーシック 単三電池 乾電池"},
        {"slug": "bambu-lab-a1-mini-review", "amazon_url": "https://amzn.to/41jLYyj", "keyword": "Bambu Lab A1 mini 3Dプリンター"},
        {"slug": "greeshow-gs297-radio-review", "amazon_url": "https://www.amazon.co.jp/dp/B0DNQLLD6S?tag=misao4510-22", "keyword": "Greeshow GS-297 防災ラジオ"},
        {"slug": "gummy-supplement-review", "amazon_url": "", "keyword": "グミサプリ"},
        {"slug": "imuraya-eiyokan-review", "amazon_url": "", "keyword": "井村屋 えいようかん"},
    ],
    3: [
        {"slug": "keyboard-comparison", "amazon_url": "", "keyword": "キーボード ワイヤレス"},
        {"slug": "mobile-battery-recommendation", "amazon_url": "", "keyword": "モバイルバッテリー おすすめ"},
        {"slug": "pc-monitor-guide", "amazon_url": "", "keyword": "PCモニター"},
        {"slug": "portable-ssd-comparison", "amazon_url": "", "keyword": "ポータブルSSD"},
        {"slug": "tfal-kettle-review", "amazon_url": "", "keyword": "T-fal ケトル"},
    ],
}


def make_moshimo_url(shop: str, product_url: str) -> str:
    if shop == "amazon":
        params = {"a_id": MOSHIMO_AMAZON_AID, "p_id": MOSHIMO_AMAZON_PID,
                  "pc_id": MOSHIMO_AMAZON_PCID, "pl_id": MOSHIMO_AMAZON_PLID, "url": product_url}
    elif shop == "rakuten":
        params = {"a_id": MOSHIMO_RAKUTEN_AID, "p_id": MOSHIMO_RAKUTEN_PID,
                  "pc_id": MOSHIMO_RAKUTEN_PCID, "pl_id": MOSHIMO_RAKUTEN_PLID, "url": product_url}
    elif shop == "yahoo":
        params = {"a_id": MOSHIMO_YAHOO_AID, "p_id": MOSHIMO_YAHOO_PID,
                  "pc_id": MOSHIMO_YAHOO_PCID, "pl_id": MOSHIMO_YAHOO_PLID, "url": product_url}
    return "https://af.moshimo.com/af/c/click?" + urllib.parse.urlencode(params)


def make_shop_links_html(amazon_url: str, keyword: str) -> str:
    """3ショップボタンHTMLを生成（楽天/Yahoo!は検索URL）"""
    amazon_moshimo = make_moshimo_url("amazon", amazon_url)
    rakuten_search = f"https://search.rakuten.co.jp/search/mall/{urllib.parse.quote(keyword)}/"
    yahoo_search = f"https://shopping.yahoo.co.jp/search?p={urllib.parse.quote(keyword)}"
    rakuten_moshimo = make_moshimo_url("rakuten", rakuten_search)
    yahoo_moshimo = make_moshimo_url("yahoo", yahoo_search)

    return (
        '<div class="shop-links-wrap">\n'
        f'  <a href="{amazon_moshimo}" class="btn-amazon" target="_blank" rel="noopener nofollow">🛒 Amazonで見る</a>\n'
        f'  <a href="{rakuten_moshimo}" class="btn-rakuten" target="_blank" rel="noopener nofollow">🛒 楽天で見る</a>\n'
        f'  <a href="{yahoo_moshimo}" class="btn-yahoo" target="_blank" rel="noopener nofollow">🛒 Yahoo!で見る</a>\n'
        '</div>'
    )


def process_article(slug: str, amazon_url: str, keyword: str, dry_run: bool = False) -> bool:
    """1記事を処理。Amazonリンクを3ショップボタンに差し替える。"""
    path = POSTS_DIR / f"{slug}.md"
    if not path.exists():
        print(f"  ❌ ファイルなし: {path}")
        return False

    content = path.read_text(encoding="utf-8")
    original = content

    if not amazon_url:
        print(f"  ⏭️  Amazon URLなし、スキップ: {slug}")
        return True

    shop_html = make_shop_links_html(amazon_url, keyword)
    impression_added = False

    def replace_btn_amazon(m):
        """<div class="btn-wrap"><a href="URL" class="btn-amazon"...>TEXT</a></div> を差し替え"""
        nonlocal impression_added
        result = shop_html
        if not impression_added:
            result += "\n" + IMPRESSION_TAGS
            impression_added = True
        return result

    # パターン1: <div class="btn-wrap"><a href="AMZN" class="btn-amazon"...>...</a></div>
    pattern1 = r'<div class="btn-wrap"><a href="https?://(?:www\.)?(?:amazon\.co\.jp|amzn\.to)[^"]*" class="btn-amazon"[^>]*>.*?</a></div>'
    content, n1 = re.subn(pattern1, replace_btn_amazon, content)
    if n1:
        print(f"  ✅ btn-amazon div を差し替え: {n1}箇所")

    # パターン2: <a href="AMZN"...>Amazon...</a> インラインリンク
    def replace_inline_amazon(m):
        nonlocal impression_added
        result = shop_html
        if not impression_added:
            result += "\n" + IMPRESSION_TAGS
            impression_added = True
        return result

    pattern2 = r'<a href="https?://(?:www\.)?(?:amazon\.co\.jp|amzn\.to)[^"]*"[^>]*>(?:[^<]|<(?!/?a\b))*(?:Amazon|amazon)[^<]*</a>'
    content, n2 = re.subn(pattern2, replace_inline_amazon, content)
    if n2:
        print(f"  ✅ インラインAmazonリンクを差し替え: {n2}箇所")

    # パターン3: [text](AMZN_URL) Markdownリンク
    def replace_md_amazon(m):
        nonlocal impression_added
        result = "\n" + shop_html
        if not impression_added:
            result += "\n" + IMPRESSION_TAGS
            impression_added = True
        return result

    pattern3 = r'\[([^\]]*(?:Amazon|amazon|見る|確認|購入)[^\]]*)\]\((https?://(?:www\.)?(?:amazon\.co\.jp|amzn\.to)[^)]*)\)'
    content, n3 = re.subn(pattern3, replace_md_amazon, content)
    if n3:
        print(f"  ✅ MarkdownリンクAmazonを差し替え: {n3}箇所")

    total = n1 + n2 + n3
    if total == 0:
        print(f"  ⚠️  差し替え対象なし（Amazonリンクパターンが見つからない）: {slug}")
        # Amazonリンクが残っていないか確認
        remaining = re.findall(r'amzn\.to|amazon\.co\.jp', content)
        if remaining:
            print(f"     → 残存Amazonリンク({len(remaining)}個)は手動確認が必要")
        return True

    if content == original:
        print(f"  ⚠️  変更なし: {slug}")
        return True

    if dry_run:
        print(f"  [DRY RUN] 変更をプレビュー（書き込みなし）")
        # 差分を表示
        orig_lines = original.splitlines()
        new_lines = content.splitlines()
        for i, (ol, nl) in enumerate(zip(orig_lines, new_lines)):
            if ol != nl:
                print(f"    L{i+1} - {ol[:80]}")
                print(f"    L{i+1} + {nl[:80]}")
    else:
        path.write_text(content, encoding="utf-8")
        print(f"  ✅ 保存完了: {slug}")

    return True


def main():
    parser = argparse.ArgumentParser(description="もしもアフィリエイト バッチ記事更新")
    parser.add_argument("--batch", type=int, choices=[1, 2, 3], help="バッチ番号")
    parser.add_argument("--slug", type=str, help="特定記事のスラッグ（単体処理）")
    parser.add_argument("--dry-run", action="store_true", help="変更せずにプレビュー")
    args = parser.parse_args()

    if not args.batch and not args.slug:
        parser.error("--batch または --slug のどちらかを指定してください")

    if args.slug:
        # 全バッチからスラッグを検索
        target = None
        for batch_items in BATCH_DATA.values():
            for item in batch_items:
                if item["slug"] == args.slug:
                    target = item
                    break
        if not target:
            print(f"スラッグが見つかりません: {args.slug}")
            sys.exit(1)
        items = [target]
    else:
        items = BATCH_DATA.get(args.batch, [])

    print(f"処理対象: {len(items)}記事")
    results = []
    for item in items:
        slug = item["slug"]
        print(f"\n[{slug}]")
        ok = process_article(
            slug=slug,
            amazon_url=item["amazon_url"],
            keyword=item["keyword"],
            dry_run=args.dry_run,
        )
        results.append((slug, ok))

    print(f"\n=== 結果 ===")
    for slug, ok in results:
        status = "✅" if ok else "❌"
        print(f"  {status} {slug}")

    failed = [s for s, ok in results if not ok]
    if failed:
        print(f"\n❌ 失敗: {len(failed)}件")
        sys.exit(1)
    else:
        print(f"\n✅ 全{len(results)}件 完了")


if __name__ == "__main__":
    main()
