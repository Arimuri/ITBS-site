#!/usr/bin/env python3
"""composition-site/og.png（1200×630）を生成する。

    python3 composition-src/make_og.py
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent.parent / "composition-site" / "og.png"
W, H = 1200, 630
PAGE = "#e6f4fc"
INK = "#0c1522"
INK2 = "#46596c"
MUTED = "#596b7d"
ACC = "#1f6fc4"
RING = "#c6dff0"
FONT = "/System/Library/Fonts/Hiragino Sans GB.ttc"


def font(size, bold=False):
    for index in ((1, 0) if bold else (0, 1)):
        try:
            return ImageFont.truetype(FONT, size, index=index)
        except Exception:
            continue
    return ImageFont.load_default()


img = Image.new("RGB", (W, H), PAGE)
d = ImageDraw.Draw(img)

# 左端のアクセント帯
d.rectangle([0, 0, 14, H], fill=ACC)

x = 92
d.text((x, 96), "京都精華大学 メディア表現学部", font=font(26), fill=MUTED)
d.text((x, 146), "応用実習1,2：作曲", font=font(86, bold=True), fill=INK)
d.text((x, 316), "メロディの全ての音を、キー度数／コード度数で捉える", font=font(34), fill=INK2)
d.text((x, 368), "火曜・全14回／各3時間（90分×2コマ）", font=font(30), fill=INK2)

# 解禁音のモチーフ：1〜7 のチップ（1・3・5 を塗る）
size, gap, top = 68, 14, 448
filled = {"1", "3", "5"}
f = font(34, bold=True)
for i, label in enumerate("1234567"):
    left = x + i * (size + gap)
    box = [left, top, left + size, top + size]
    on = label in filled
    d.rounded_rectangle(box, radius=16, fill=ACC if on else PAGE, outline=ACC if on else RING, width=2)
    tw = d.textbbox((0, 0), label, font=f)
    d.text(
        (left + (size - tw[2] + tw[0]) / 2, top + (size - tw[3] - tw[1]) / 2 - 2),
        label,
        font=f,
        fill="#ffffff" if on else MUTED,
    )

d.text((x, 556), "intheblueshirt.com/composition/", font=font(26), fill=ACC)

img.save(OUT, optimize=True)
print("wrote", OUT, img.size)
