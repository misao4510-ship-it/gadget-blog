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

    def _convert_headers(self, content: str) -> str:
        """ヘッダーレベルを調整（h1→h2、全体的に一段下げ）"""
        # noteでは本文内のh1は不自然なのでh2に変換
        content = re.sub(r'^# (.+)$', r'## \1', content, flags=re.MULTILINE)
        return content

    def _build_canonical_url(self, slug: str) -> str:
        """スラッグからcanonical URLを生成"""
        base_url = self.config.get("blog_base_url", "").rstrip("/")
        return f"{base_url}/{slug}/"
