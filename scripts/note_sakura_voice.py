#!/usr/bin/env python3
"""
note_sakura_voice.py: ブログ記事テキストをサクラ口調に変換（ルールベース実装）
使用法: python3 note_sakura_voice.py input.md [--output output.md]
"""
import re
import sys
import argparse
from pathlib import Path


INTRO = "こんにちは、サクラです！"
OUTRO = "\n\nサクラでした！またお会いしましょうね🌸"


def convert_to_sakura_voice(text: str) -> str:
    """テキストをサクラ口調に変換する（ルールベース）"""

    # 区切り線（---）を除去
    text = re.sub(r'\n\s*---\s*\n', '\n\n', text)
    text = re.sub(r'^\s*---\s*\n', '', text)
    text = re.sub(r'\n\s*---\s*$', '', text.rstrip())

    # 連続空行を2行（=1空行）に圧縮
    text = re.sub(r'\n{3,}', '\n\n', text)

    # 文末変換ルール（句点・感嘆符・改行の前に適用）
    # 「〜します」→「〜しますよ」
    text = re.sub(r'します([。！\n])', r'しますよ\1', text)
    # 「〜ました」→「〜ましたよ」
    text = re.sub(r'ました([。！\n])', r'ましたよ\1', text)
    # 「〜です」→「〜ですよ」（文末のみ）
    text = re.sub(r'です([。！\n])', r'ですよ\1', text)
    # 「〜でしょう」→「〜でしょうね」
    text = re.sub(r'でしょう([。！\n])', r'でしょうね\1', text)
    # 「〜ください」→「〜くださいね」
    text = re.sub(r'ください([。！\n])', r'くださいね\1', text)

    # 冒頭に「こんにちは、サクラです！」を追加（まだない場合）
    if not text.startswith(INTRO):
        text = INTRO + "\n\n" + text.lstrip()

    # 末尾に追加（まだない場合）
    if "またお会いしましょうね" not in text:
        text = text.rstrip() + OUTRO

    return text


def main():
    parser = argparse.ArgumentParser(description="ブログ記事テキストをサクラ口調に変換")
    parser.add_argument("input", help="入力ファイル（Markdown）")
    parser.add_argument("--output", "-o", help="出力ファイル（省略時は標準出力）")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"ERROR: ファイルが見つかりません: {input_path}", file=sys.stderr)
        sys.exit(1)

    text = input_path.read_text(encoding="utf-8")
    result = convert_to_sakura_voice(text)

    if args.output:
        Path(args.output).write_text(result, encoding="utf-8")
        print(f"変換完了: {args.output}")
    else:
        print(result)


if __name__ == "__main__":
    main()
