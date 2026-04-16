#!/usr/bin/env python3
"""
note.com向けMarkdown変換モジュール

ブログ記事のMarkdown（Astro frontmatter付き）をnote向けに変換する。
"""

import re
import yaml
from pathlib import Path
from datetime import datetime


class NoteConverter:
    """Markdown→note向け変換クラス"""

    def __init__(self, config: dict):
        self.config = config

    def convert(self, md_content: str, slug: str) -> dict:
        """
        Markdown→note向け変換

        Returns:
            {
                "title": str,
                "body": str,
                "hashtags": list[str],
                "canonical_url": str,
            }
        """
        # frontmatter抽出
        meta, body = self._split_frontmatter(md_content)

        title = meta.get("title", slug)
        canonical_url = self._build_canonical_url(slug)

        # body変換
        body = self._remove_svg_images(body)
        body = self._remove_inline_images(body)
        body = self._remove_html_blocks(body)
        body = self._remove_amazon_links(body)
        body = self._convert_markdown_links(body)
        body = self._convert_tables(body)
        body = self._convert_headers(body)
        body = body.strip()

        # 末尾に元記事URL付与
        if self.config.get("add_canonical_footer", True):
            template = self.config.get(
                "canonical_template", "\n\n---\n▶ 元記事はこちら: {url}\n"
            )
            body += template.format(url=canonical_url)

        # ハッシュタグ
        hashtags = list(self.config.get("note_hashtags", []))
        category = meta.get("category", "")
        if category and category not in hashtags:
            hashtags.append(category)

        return {
            "title": title,
            "body": body,
            "hashtags": hashtags,
            "canonical_url": canonical_url,
            "meta": meta,
        }

    def _split_frontmatter(self, content: str) -> tuple[dict, str]:
        """frontmatterを分離してメタデータとbodyを返す"""
        match = re.match(r"^---\s*\n(.*?)\n---\s*\n?", content, re.DOTALL)
        if not match:
            return {}, content
        try:
            meta = yaml.safe_load(match.group(1)) or {}
        except yaml.YAMLError:
            meta = {}
        body = content[match.end():]
        return meta, body

    def _remove_svg_images(self, content: str) -> str:
        """SVG画像参照を除去（noteはSVG非対応）"""
        # Markdown画像記法 ![alt](xxx.svg) を除去
        content = re.sub(r'!\[.*?\]\([^)]*\.svg[^)]*\)', '', content)
        # HTML imgタグでSVGを参照しているものを除去
        content = re.sub(r'<img[^>]+src="[^"]*\.svg[^"]*"[^>]*/?>', '', content)
        return content

    def _remove_inline_images(self, content: str) -> str:
        """ブログのインライン画像タグを除去（note転載時はillustration systemで別途挿入）"""
        # ![alt](path.png) 等のMarkdown画像記法を除去（alt文字列が残らないよう ! ごと削除）
        content = re.sub(r'!\[.*?\]\([^)]*\.(png|jpe?g|gif|webp)[^)]*\)', '', content)
        # HTML imgタグ（PNG/JPG等）を除去
        content = re.sub(r'<img[^>]+src="[^"]*\.(png|jpe?g|gif|webp)[^"]*"[^>]*/?>', '', content)
        return content

    def _remove_html_blocks(self, content: str) -> str:
        """HTMLブロック（divタグ、aタグ等）を除去"""
        # <div>...</div> ブロックを除去（Amazonボタン等）
        content = re.sub(r'<div[^>]*>.*?</div>', '', content, flags=re.DOTALL)
        # 残りのHTMLタグを除去
        content = re.sub(r'<[^>]+>', '', content)
        return content

    def _remove_amazon_links(self, content: str) -> str:
        """Amazonアフィリエイトリンクを保持（URLはプレーンテキストとして残す）"""
        # [テキスト](Amazon URL) → テキスト（Amazon URL）
        content = re.sub(
            r'\[([^\]]+)\]\((https?://(?:www\.)?(?:amazon\.co\.jp|amazon\.com|amzn\.to|amzn\.asia)[^\)]*)\)',
            r'\1（\2）', content
        )
        # 裸のAmazon URLはそのまま残す（削除しない）
        return content

    def _convert_markdown_links(self, content: str) -> str:
        """残りのMarkdownリンクをテキスト化（note.comはプレーンテキスト入力のため）"""
        # [テキスト](URL) → テキスト
        content = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', content)
        return content

    def _convert_tables(self, content: str) -> str:
        """Markdownテーブルを見やすいテキスト形式に変換"""
        def _replace_table(match):
            table_text = match.group(0)
            lines = [l.strip() for l in table_text.strip().split('\n') if l.strip()]
            rows = []
            for line in lines:
                cells = [c.strip() for c in line.strip('|').split('|')]
                if all(re.match(r'^[-:]+$', c) for c in cells):
                    continue
                rows.append(cells)
            if len(rows) < 2:
                return table_text
            header = rows[0]
            data_rows = rows[1:]
            if len(header) == 2:
                # 2列: key：value のリスト形式
                result = f"【{header[0]}／{header[1]}】\n"
                for row in data_rows:
                    result += f"・{row[0]}：{row[1]}\n"
            else:
                # 3列以上: ヘッダー付きリスト形式
                result = ""
                for row in data_rows:
                    parts = [f"{header[i]}:{row[i]}" for i in range(len(header)) if i < len(row)]
                    result += "▸ " + "／".join(parts) + "\n"
            return result.rstrip('\n')

        # Markdownテーブル検出（|で始まる連続行）
        content = re.sub(
            r'(?:^\|.+\|[ ]*\n)+',
            _replace_table,
            content,
            flags=re.MULTILINE,
        )
        return content

    def _convert_headers(self, content: str) -> str:
        """ヘッダーレベルを調整（h1→h2、全体的に一段下げ）"""
        # noteでは本文内のh1は不自然なのでh2に変換
        content = re.sub(r'^# (.+)$', r'## \1', content, flags=re.MULTILINE)
        return content

    def _build_canonical_url(self, slug: str) -> str:
        """スラッグからcanonical URLを生成"""
        base_url = self.config.get("blog_base_url", "").rstrip("/")
        return f"{base_url}/{slug}/"
