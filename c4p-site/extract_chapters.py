#!/usr/bin/env python3
"""Extract chapters from C4P_Book.md into chapters.js for the website."""
import json
import re
import sys

BOOK_PATH = "../book/C4P_Book.md"

# Chapters to exclude from random display
SPECIAL = {"用語の定義：C4Q / C4P", "はじめに", "おわりに", "数理モデル"}

# Part mapping
PART_MAP = {
    "いいのができたら": ("第一部", "いいのができたら"),
    "サイズはどうしますか": ("第一部", "いいのができたら"),
    "余計なお世話": ("第一部", "いいのができたら"),
    "早くおわんないかな": ("第一部", "いいのができたら"),
    "完成宣言": ("第一部", "いいのができたら"),
    "目的は手段です": ("第一部", "いいのができたら"),
    "人間と作品": ("第一部", "いいのができたら"),
    "しかしなにもおこらない": ("第一部", "いいのができたら"),
    "そして非合理へ": ("第一部", "いいのができたら"),
    "自主制作のススメ": ("第一部", "いいのができたら"),
    "馴れ合いしようや": ("第二部", "馴れ合いしようや"),
    "Be 玄人(前編)": ("第二部", "馴れ合いしようや"),
    "Be 玄人(中編)": ("第二部", "馴れ合いしようや"),
    "Be 玄人(後編)": ("第二部", "馴れ合いしようや"),
    "Be 玄人（前編）": ("第二部", "馴れ合いしようや"),
    "Be 玄人（中編）": ("第二部", "馴れ合いしようや"),
    "Be 玄人（後編）": ("第二部", "馴れ合いしようや"),
    "プロトC4P": ("第二部", "馴れ合いしようや"),
    "郊外のブルース": ("第二部", "馴れ合いしようや"),
    "創作の苦しみ？": ("第二部", "馴れ合いしようや"),
    "名無しさん": ("第三部", "名無しさん"),
    "あいつ、音楽やりそう": ("第三部", "名無しさん"),
    "ディグ・ダグ": ("第三部", "名無しさん"),
    "任意のタイミングで": ("第三部", "名無しさん"),
    "心のエジプト": ("第三部", "名無しさん"),
    "ベースの音ってどれですか": ("第三部", "名無しさん"),
    "脱凡庸": ("第三部", "名無しさん"),
    "Rage Against the AI": ("第三部", "名無しさん"),
    "チーティング": ("第三部", "名無しさん"),
    "へぼさの民主化": ("第四部", "へぼさの民主化"),
    "まねっこ": ("第四部", "へぼさの民主化"),
    "アンチセオリー": ("第四部", "へぼさの民主化"),
    "変な人": ("第四部", "へぼさの民主化"),
    "犬と猫は何が違う": ("第四部", "へぼさの民主化"),
    "スペシャル(for me)": ("第四部", "へぼさの民主化"),
    "スペシャル（for me）": ("第四部", "へぼさの民主化"),
    "見当はずれ": ("第五部", "見当はずれ"),
    "楽しみ力": ("第五部", "見当はずれ"),
    "ちょうどよさ": ("第五部", "見当はずれ"),
    "阪神ファン": ("第五部", "見当はずれ"),
    "無限の彼方へ": ("第五部", "見当はずれ"),
    "スワイプ&スワイプ": ("第五部", "見当はずれ"),
    "あれなんだっけ？": ("第五部", "見当はずれ"),
    "じゃあお前がやってみろよ": ("第五部", "見当はずれ"),
    "不運な人": ("第六部", "不運な人"),
    "アウトオブスコープ": ("第六部", "不運な人"),
    "去るもの追わず": ("第六部", "不運な人"),
}

def extract_chapters(path):
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    # Split by ## headings
    parts = re.split(r'^## ', text, flags=re.MULTILINE)

    hajimeni = ""
    chapters = []

    for part in parts[1:]:  # skip the # title
        lines = part.split("\n", 1)
        title = lines[0].strip()
        body = lines[1].strip() if len(lines) > 1 else ""

        # Remove LaTeX math references like （付属の数理モデルでは...）
        body = re.sub(r'（付属の数理モデルでは.*?参照。）', '', body, flags=re.DOTALL)
        body = body.strip()

        if title == "はじめに":
            hajimeni = body
        elif title not in SPECIAL:
            part_info = PART_MAP.get(title, ("", ""))
            # Get first paragraph as excerpt
            paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]
            excerpt = paragraphs[0][:200] + "……" if paragraphs and len(paragraphs[0]) > 200 else (paragraphs[0] if paragraphs else "")
            chapters.append({
                "title": title,
                "part": part_info[0],
                "body": body,
                "excerpt": excerpt,
            })

    return hajimeni, chapters

def main():
    hajimeni, chapters = extract_chapters(BOOK_PATH)

    # Write chapters.js
    output = f"var HAJIMENI = {json.dumps(hajimeni, ensure_ascii=False, indent=2)};\n\n"
    output += f"var CHAPTERS = {json.dumps(chapters, ensure_ascii=False, indent=2)};\n"

    with open("chapters.js", "w", encoding="utf-8") as f:
        f.write(output)

    print(f"Extracted {len(chapters)} chapters + はじめに")
    print(f"はじめに: {len(hajimeni)} chars")
    for i, ch in enumerate(chapters):
        print(f"  {i+1}. [{ch['part']}] {ch['title']} ({len(ch['body'])} chars)")

if __name__ == "__main__":
    main()
