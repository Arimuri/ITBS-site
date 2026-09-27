#!/usr/bin/env python3
"""応用実習1,2：作曲 特設サイト（intheblueshirt.com/composition/）のジェネレータ。

curriculum.md を唯一の原稿として読み、composition-site/ に静的HTMLを書き出す。
手書きページ（ear/ と .htaccess）には触らない。

    python3 composition-src/build.py
"""

import html
import re
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent
OUT = SRC.parent / "composition-site"
BASE = "https://intheblueshirt.com/composition/"
SITE_TITLE = "応用実習1,2：作曲"
SITE_DESC = "京都精華大学メディア表現学部「応用実習1,2：作曲」（火曜・有村担当）全14回のカリキュラム。メロディの全ての音を移動ドの「キー度数/コード度数」で捉えて作曲する。"

# ---------------------------------------------------------------- markdown 周り

def inline(s):
    """インライン記法だけを HTML に変換する。"""
    s = html.escape(s, quote=False)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(https?://[^\s<（）()、。]+)", r'<a href="\1">\1</a>', s)
    return s


def split_sections(lines, prefix):
    """指定レベルの見出しで分割し [(見出し, 本文行)] を返す。"""
    out, cur = [], None
    for ln in lines:
        if ln.startswith(prefix) and not ln[len(prefix) - 1 :].startswith("##"):
            cur = (ln[len(prefix) :].strip(), [])
            out.append(cur)
        elif cur is not None:
            cur[1].append(ln)
    return out


def parse_table(block):
    rows = [[c.strip() for c in ln.strip().strip("|").split("|")] for ln in block]
    return rows[0], rows[2:]


def render_table(header, body, cls=""):
    th = "".join(f"<th>{inline(c)}</th>" for c in header)
    trs = []
    for row in body:
        tds = "".join(f"<td>{inline(c)}</td>" for c in row)
        trs.append(f"<tr>{tds}</tr>")
    c = f' class="{cls}"' if cls else ""
    return (
        f'<div class="tablebox"><table{c}><thead><tr>{th}</tr></thead>'
        f'<tbody>{"".join(trs)}</tbody></table></div>'
    )


def render_list(block):
    """4スペース字下げのネストに対応した箇条書き。"""
    items = [
        ((len(l) - len(l.lstrip(" "))) // 4, l.strip()[2:].strip()) for l in block
    ]

    def build(i, depth):
        out = ["<ul>"]
        while i < len(items) and items[i][0] >= depth:
            d, text = items[i]
            if d > depth:  # 先頭が深い異常ケース
                sub, i = build(i, depth + 1)
                out.append(sub)
                continue
            i += 1
            li = "<li>" + inline(text)
            if i < len(items) and items[i][0] > depth:
                sub, i = build(i, depth + 1)
                li += sub
            out.append(li + "</li>")
        out.append("</ul>")
        return "".join(out), i

    return build(0, 0)[0]


BOLD_ONLY = re.compile(r"\*\*(.+?)\*\*$")


def is_bullet(ln):
    return ln.lstrip(" ").startswith("- ")


def render_blocks(lines):
    """段落・太字見出し・表・箇条書きからなる本文をまとめて変換する。"""
    out, i = [], 0
    while i < len(lines):
        ln = lines[i].rstrip()
        if not ln.strip():
            i += 1
            continue
        if ln.startswith("|"):
            blk = []
            while i < len(lines) and lines[i].startswith("|"):
                blk.append(lines[i])
                i += 1
            out.append(render_table(*parse_table(blk)))
            continue
        if is_bullet(ln):
            blk = []
            while i < len(lines) and is_bullet(lines[i]):
                blk.append(lines[i].rstrip())
                i += 1
            out.append(render_list(blk))
            continue
        m = BOLD_ONLY.fullmatch(ln.strip())
        if m:
            out.append(f'<h3>{inline(m.group(1))}</h3>')
            i += 1
            continue
        para = []
        while i < len(lines):
            cand = lines[i].rstrip()
            if (
                not cand.strip()
                or cand.startswith(("|", "#"))
                or is_bullet(cand)
                or BOLD_ONLY.fullmatch(cand.strip())
            ):
                break
            para.append(cand.strip())
            i += 1
        out.append("<p>" + inline("".join(para)) + "</p>")
    return "\n".join(out)


# ------------------------------------------------------------------ 解禁音の集合

DEG_ALL = ["1", "2", "3", "4", "5", "6", "7"]


def degree_set(raw, prev_deg, prev_flat):
    """「使える音」の記述から、その回までに解禁された音を求める。"""
    r = raw.replace("＋", "+").strip()
    if "全て" in r:
        return set(DEG_ALL), {"♭3", "♭7"}
    cumulative = r.startswith("+")
    deg = set(prev_deg) if cumulative else set()
    flat = set(prev_flat) if cumulative else set()
    if "全7音" in r:
        deg |= set(DEG_ALL)
    for tok in re.findall(r"♭\d|\d", r):
        (flat if tok.startswith("♭") else deg).add(tok)
    return deg, flat


# ピアノロールに出す4小節ぶんのコード。原稿の「伴奏進行」から拾えるときは拾い、
# 「自由」など拾えない回だけ、この既定値を使う。授業に合わせて変えてよい。
FALLBACK_PROGS = {
    4: "I-VIm-IV-V",
    5: "I-VIm-IV-V",
    6: "I-IV-V-I",        # T-S-D-T の型そのもの
    7: "I-IV-V-VIm",      # 偽終止を聴かせる
    9: "I-IV-V7-I",
    10: "I-VIm-IIm7-V",
    11: "I-VIm-IV-IV/V",  # 4on5 を種明かしする回
    12: "I-VIm-IV-V",
    13: "I-VIm-IV-V",
    14: "I-VIm-IV-V",
}
DEFAULT_PROG = "I-VIm-IV-V"

# ピアノロールのコード進行プルダウンに出す候補。
# 右の数字は「その進行を出してよい最初の回」。授業の解禁順に合わせてある。
# 回をまとめたり順番を変えたりしたら、ここも合わせて直すこと。
ROLL_PROG_CHOICES = [
    ("I-IV-VIm-IV", 1),
    ("I-VIm-IIm7-IV", 1),
    ("I-VIm-IV-V", 1),      # V は第1回から使う（Vの上は1が11th、2が5th）
    ("I-IIIm-IV-V", 2),
    ("IIm7-V-I-I", 3),
    ("I-IV-V-I", 6),        # 機能を習う回から
    ("I-IV-V-VIm", 7),      # 偽終止
    ("I-VIm-IIm7-V", 7),
    ("IV-I-IV-V", 8),
    ("I-IV-V7-I", 9),
    ("I-VIm-IV-IV/V", 11),  # 4on5 は第11回で種明かしする
]


def roll_prog_choices(no, raw):
    """その回で選べる進行の一覧。先頭がその回の既定。"""
    own = "-".join(roll_prog(no, raw))
    out = [own]
    for name, first in ROLL_PROG_CHOICES:
        if first <= no and name not in out:
            out.append(name)
    return out

_NUM = r"(?:VII|VI|V|IV|III|II|I)"   # 長いものから並べないと IV が I+V に割れる
_CHORD = rf"{_NUM}(?:maj7|m7|m|7|sus4)?(?:/{_NUM})?"
_RUN = re.compile(rf"{_CHORD}(?:-{_CHORD})+")


def roll_prog(no, raw):
    """伴奏進行の記述から、ピアノロール用に4和音を作る。"""
    m = _RUN.search(raw or "")
    found = m.group(0).split("-") if m else []
    if not found:
        found = FALLBACK_PROGS.get(no, DEFAULT_PROG).split("-")
    return [found[i % len(found)] for i in range(4)]


def degree_chips(deg, flat):
    chips = [
        f'<span class="deg{" on" if d in deg else ""}">{d}</span>' for d in DEG_ALL
    ]
    for f in ("♭3", "♭7"):
        if f in flat:
            chips.append(f'<span class="deg flat on">{f}</span>')
    return f'<div class="degs">{"".join(chips)}</div>'


# -------------------------------------------------------------------- 原稿を読む

def load():
    md = (SRC / "curriculum.md").read_text(encoding="utf-8").splitlines()
    secs = dict(split_sections(md, "## "))

    def find(keyword):
        for k in secs:
            if keyword in k:
                return k, secs[k]
        raise SystemExit(f"curriculum.md に「{keyword}」の節が見つからない")

    data = {}

    # 授業の狙いと前提：先頭の段落をリードに、残りを本文に
    _, body = find("狙いと前提")
    lead, rest = "", list(body)
    for n, ln in enumerate(rest):
        if ln.strip():
            lead = ln.strip()
            rest = rest[n + 1 :]
            break
    data["lead"] = lead
    data["about_html"] = render_blocks(rest)

    title, body = find("標準の流れ")
    data["flow_title"] = title
    data["flow_html"] = render_blocks(body)

    # 全14回一覧
    _, body = find("全14回一覧")
    note = next((l.strip() for l in body if l.strip() and not l.startswith("|")), "")
    tbl = [l for l in body if l.startswith("|")]
    header, rows = parse_table(tbl)
    col = {name: idx for idx, name in enumerate(header)}
    lessons, prev_deg, prev_flat = {}, set(), set()
    for row in rows:
        no = int(row[col["回"]])
        deg, flat = degree_set(row[col["使える音"]], prev_deg, prev_flat)
        prev_deg, prev_flat = deg, flat
        lessons[no] = {
            "no": no,
            "phase": row[col["Phase"]],
            "theme": row[col["テーマ"]],
            "sounds_raw": row[col["使える音"]],
            "prog": row[col["伴奏進行"]],
            "deg": deg,
            "flat": flat,
            "items": [],
        }
    data["lessons_note"] = note
    data["lessons"] = lessons

    # 各回の詳細：Phase ごと → 第N回 ごと
    _, body = find("各回の詳細")
    data["phases"] = []
    for phase_title, phase_body in split_sections(body, "### "):
        nos = []
        for head, bullets in split_sections(phase_body, "#### "):
            m = re.match(r"第(\d+)回[　\s]*(.*)", head)
            if not m:
                continue
            no = int(m.group(1))
            lesson = lessons[no]
            lesson["title"] = m.group(2).strip() or lesson["theme"]
            lesson["phase_title"] = phase_title
            for ln in bullets:
                b = re.match(r"^- \*\*(.+?)\*\*：(.*)$", ln.strip())
                if b:
                    lesson["items"].append((b.group(1), b.group(2).strip()))
            nos.append(no)
        data["phases"].append({"title": phase_title, "nos": nos})

    # 音楽理論ロードマップ
    _, body = find("音楽理論ロードマップ")
    lead, rest = "", list(body)
    for n, ln in enumerate(rest):
        if ln.strip():
            lead, rest = ln.strip(), rest[n + 1 :]
            break
    head_at = next((i for i, ln in enumerate(rest) if ln.startswith("### ")), len(rest))
    data["roadmap_lead"] = lead
    data["roadmap_intro"] = render_blocks(rest[:head_at])
    data["roadmap"] = []
    for idx, (head, bullets) in enumerate(split_sections(rest[head_at:], "### ")):
        items, others = [], []
        for ln in bullets:
            m = re.match(r"^- \*\*(.+?)\*\*：(.*)$", ln.strip())
            if m:
                items.append((m.group(1), m.group(2).strip()))
            else:
                others.append(ln)
        data["roadmap"].append(
            {
                "title": head,
                "slug": f"s{idx + 1}",
                "items": items,
                "extra": render_blocks(others),   # 表などは行の後ろにまとめて出す
            }
        )

    # ポップスのコツ
    _, body = find("ポップスのコツ")
    data["tips_note"] = next(
        (l.strip() for l in body if l.strip() and not l.startswith("|")), ""
    )
    header, rows = parse_table([l for l in body if l.startswith("|")])
    col = {name: idx for idx, name in enumerate(header)}
    tips = []
    for row in rows:
        intro = row[col["導入回"]]
        tips.append(
            {
                "view": row[col["観点"]],
                "tip": row[col["コツ"]],
                "why": row[col["例・理由"]],
                "intro": intro,
                "nos": [int(n) for n in re.findall(r"\d+", intro)],
            }
        )
    data["tips"] = tips

    title, body = find("評価とワークシート")
    data["eval_title"] = title
    data["eval_html"] = render_blocks(body)

    for no, lesson in lessons.items():
        lesson.setdefault("title", lesson["theme"])
        lesson.setdefault("phase_title", lesson["phase"])
    return data


# ------------------------------------------------------------------------- CSS

CSS = """/* 応用実習1,2：作曲 特設サイト 共通スタイル（composition-src/build.py が生成） */
/* 授業で投影するので、OSのダークモードでも反転させず常に薄い水色で出す */
:root{
  --page:#e6f4fc;--surface:#f9fcff;--ink:#0c1522;--ink2:#46596c;--muted:#596b7d;
  --grid:#c6dff0;--ring:rgba(12,21,34,.12);--acc:#1f6fc4;--acc-soft:#d4e8f8;
  --acc-ink:#175a9f; /* --acc-soft のような色地に文字を載せるとき用 */
  --ng-ink:#ad3a28;  /* 誤答など、否定を表す文字色 */
  --row-scale:#dcecf8;--row-open:#c9e2f5; /* ピアノロールの行（スケール／解禁済み） */
}
html{background:var(--page);color-scheme:light}
*{box-sizing:border-box}
body{margin:0;background:var(--page);color:var(--ink);
  font-family:system-ui,-apple-system,"Hiragino Sans","Noto Sans JP",sans-serif;
  line-height:1.8;font-size:15px;-webkit-text-size-adjust:100%}
.wrap{max-width:860px;margin:0 auto;padding:40px 16px 72px}
.wrap.narrow{max-width:720px}
a{color:var(--acc)}
h1{font-size:clamp(23px,4.6vw,32px);line-height:1.34;letter-spacing:-.01em;margin:0 0 8px;text-wrap:balance}
h2{font-size:18px;margin:44px 0 12px;letter-spacing:-.01em;padding-bottom:7px;border-bottom:1px solid var(--grid)}
h3{font-size:14px;margin:26px 0 8px;color:var(--ink2);letter-spacing:.01em}
p{margin:9px 0}
ul{margin:9px 0;padding-left:1.35em}
li{margin:4px 0}
ul ul{margin:3px 0}
.eyebrow{font-size:11px;letter-spacing:.16em;color:var(--muted);margin:0 0 9px}
.meta{color:var(--ink2);font-size:13.5px;margin:0 0 6px}
.lead{color:var(--ink2);font-size:14.5px;margin:18px 0 0}
.foot{color:var(--muted);font-size:11.5px;margin:56px 0 0;padding-top:18px;border-top:1px solid var(--grid)}
/* ナビ */
.topnav{font-size:12.5px;margin:0 0 24px;display:flex;flex-wrap:wrap;gap:6px 14px}
.topnav a{color:var(--ink2);text-decoration:none}
.topnav a:hover{color:var(--acc)}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin:22px 0 0}
.chips a{display:inline-block;background:var(--surface);border:1px solid var(--ring);
  border-radius:999px;padding:7px 15px;font-size:13px;text-decoration:none;color:var(--ink)}
.chips a:hover{border-color:var(--acc);color:var(--acc)}
/* カード */
.cards{display:grid;gap:10px;grid-template-columns:repeat(auto-fill,minmax(232px,1fr));margin:14px 0 0}
a.card{display:block;background:var(--surface);border:1px solid var(--ring);border-radius:13px;
  padding:14px 16px;color:inherit;text-decoration:none}
a.card:hover{border-color:var(--acc)}
.card .no{font-size:10.5px;letter-spacing:.13em;color:var(--muted)}
.card .th{font-size:15px;font-weight:700;margin:3px 0 9px;line-height:1.45}
.card .sub{font-size:11.5px;color:var(--ink2);margin:8px 0 0}
/* 解禁音チップ */
.degs{display:flex;gap:5px;flex-wrap:wrap}
/* .degs の内側に限定する。限定しないと ear/ のピアノ鍵盤が付ける同名クラスに当たり、
   1度を決めた瞬間に白鍵の高さが30pxに潰れる */
.degs .deg{min-width:30px;height:30px;padding:0 4px;border-radius:8px;display:grid;place-items:center;
  font-weight:700;font-size:14px;border:1px solid var(--ring);background:var(--page);color:var(--muted)}
.degs .deg.on{background:var(--acc);border-color:var(--acc);color:#fff}
.degs .deg.flat{font-size:12px;padding:0 8px}
.degs.lg .deg{min-width:38px;height:38px;font-size:16px;border-radius:10px}
/* パネル */
.panel{background:var(--surface);border:1px solid var(--ring);border-radius:14px;padding:16px 18px;margin:20px 0}
.panel .k{font-size:10.5px;letter-spacing:.14em;color:var(--muted);margin:0 0 9px}
.panel .v{font-size:15px;margin:0}
.panel .v code{font-size:14px}
.panel .note{font-size:11.5px;color:var(--ink2);margin:9px 0 0}
.grid2{display:grid;gap:12px;grid-template-columns:1fr 1fr}
@media (max-width:560px){.grid2{grid-template-columns:1fr}}
/* 定義行 */
.rows{margin:24px 0 0}
.row{display:grid;grid-template-columns:78px 1fr;gap:16px;padding:13px 0;border-top:1px solid var(--grid)}
.row:last-child{border-bottom:1px solid var(--grid)}
.row .lbl{font-size:12px;font-weight:700;color:var(--acc);letter-spacing:.02em;padding-top:4px}
.row .val{margin:0}
.why{color:var(--ink2);font-size:13.5px}
/* ポップスのコツ：授業と切り離して読める資料として、コツ本文を主役にする */
.tips{counter-reset:tip;list-style:none;margin:14px 0 0;padding:0;display:grid;gap:10px}
.tip{position:relative;background:var(--surface);border:1px solid var(--ring);border-radius:13px;
  padding:15px 17px 14px 54px}
.tip::before{counter-increment:tip;content:counter(tip);position:absolute;left:16px;top:16px;
  width:26px;height:26px;border-radius:8px;background:var(--acc-soft);color:var(--acc-ink);
  font-size:12.5px;font-weight:700;display:grid;place-items:center}
.tip .t{margin:0;font-size:16px;font-weight:700;line-height:1.5;letter-spacing:-.01em}
.tip .d{margin:7px 0 0;font-size:13.5px;color:var(--ink2)}
.tip .src{margin:10px 0 0;font-size:11.5px;color:var(--muted)}
.tip .src a{color:var(--muted)}
.index{display:flex;flex-wrap:wrap;gap:8px;margin:18px 0 0}
.index a{display:inline-block;background:var(--surface);border:1px solid var(--ring);border-radius:999px;
  padding:6px 14px;font-size:12.5px;text-decoration:none;color:var(--ink)}
.index a:hover{border-color:var(--acc);color:var(--acc)}
.index a span{color:var(--muted);margin-left:5px}
.tight{margin-top:8px}
.more{font-size:12.5px}
.stage-src{font-size:11.5px;color:var(--muted);margin:10px 0 0}
.stage-src a{color:var(--muted)}
@media (max-width:520px){.row{grid-template-columns:1fr;gap:3px}.row .lbl{padding-top:0}}
/* 表 */
.tablebox{overflow-x:auto;margin:12px 0}
table{border-collapse:collapse;width:100%;font-size:13px}
th,td{padding:7px 10px;text-align:left;border-bottom:1px solid var(--grid);vertical-align:top}
th{font-size:10.5px;color:var(--muted);letter-spacing:.07em;white-space:nowrap}
code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.92em}
/* ページ送り */
.pager{display:flex;justify-content:space-between;gap:10px;margin:40px 0 0;font-size:13px}
.pager a{display:inline-block;background:var(--surface);border:1px solid var(--ring);border-radius:10px;
  padding:9px 14px;text-decoration:none;color:var(--ink)}
.pager a:hover{border-color:var(--acc);color:var(--acc)}
.pager .sp{flex:1}
/* 4小節ピアノロール。中身は assets/roll.js が作る */
.roll{margin:16px 0 0}
.roll-top{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:0 0 10px}
.roll-top select,.roll-top button{font:inherit;font-size:13px;border:1px solid var(--ring);
  border-radius:9px;padding:7px 12px;background:var(--surface);color:var(--ink);cursor:pointer}
.roll-top button:hover{border-color:var(--acc);color:var(--acc)}
.roll-top button.pri{background:var(--acc);border-color:var(--acc);color:#fff;font-weight:700}
.roll-top button.pri:hover{color:#fff;opacity:.9}
.roll-top label{display:flex;align-items:center;gap:6px;font-size:12px;color:var(--ink2);cursor:pointer}
.roll-scroll{overflow-x:auto;border:1px solid var(--ring);border-radius:12px;background:var(--surface)}
.roll-grid{--rh:15px;min-width:600px;display:grid;grid-template-columns:34px 1fr;grid-template-rows:auto 1fr}
.roll-corner{border-bottom:1px solid var(--grid);border-right:1px solid var(--grid)}
.roll-bars{display:grid;grid-template-columns:repeat(4,1fr);border-bottom:1px solid var(--grid)}
.roll-bar{padding:7px 0;text-align:center;font-size:12.5px;font-weight:700;color:var(--acc-ink);
  border-right:1px solid var(--grid)}
.roll-bar:last-child{border-right:none}
.roll-bar.now{background:var(--acc-soft)}
.roll-gutter{display:grid;grid-auto-rows:var(--rh);border-right:1px solid var(--grid)}
.roll-deg{display:grid;place-items:center;font-size:10px;line-height:1;color:transparent}
.roll-deg.scale{color:var(--ink2)}
.roll-deg.open{color:var(--acc-ink);font-weight:700}
.roll-cells{display:grid;grid-template-columns:repeat(32,1fr);grid-auto-rows:var(--rh);
  touch-action:none;user-select:none}
.rc{border-right:1px solid var(--grid);cursor:pointer}
.rc.scale{background:var(--row-scale)}
.rc.open{background:var(--row-open)}
.rc.oct{border-bottom:1px solid var(--grid)}
.rc.barstart{border-left:2px solid var(--muted)}
.rc.now{background-image:linear-gradient(rgba(31,111,196,.14),rgba(31,111,196,.14))}
.rc.on{background:var(--acc);border-right-color:var(--acc)}
.roll-note{font-size:12px;color:var(--ink2);margin:10px 0 0}
.roll-warn{font-size:12.5px;color:var(--ng-ink);font-weight:700;margin:10px 0 0}
.roll-warn:empty{display:none}
@media print{
  :root{--page:#fff;--surface:#fff;--ink:#000;--ink2:#333;--muted:#666;--grid:#bbb;--ring:#bbb;--acc:#0a4a8a}
  .topnav,.pager,.chips,.roll-top{display:none}
  .wrap{padding:0;max-width:none}
  a{text-decoration:none}
}
"""

ROLL_JS = r"""/* 4小節ピアノロール（composition-src/build.py が生成）
   各回のページの <div class="roll" data-prog data-degrees data-lesson> を中身で埋める。
   ・行は半音ごと。選んだキーのメジャースケールの行だけ色を濃くし、1〜7の番号を振る
   ・その回までに解禁された度数の行は、さらに濃く＋番号を強調する
   ・キーを変えるとメロも一緒に移調する（数字は変わらず高さだけ変わる、を体感させる） */
(() => {
  'use strict';
  const LOW = 48, HIGH = 72, ROWS = HIGH - LOW + 1;
  const BARS = 4, STEPS = 8, COLS = BARS * STEPS;
  const MAJOR = [0, 2, 4, 5, 7, 9, 11];
  const KEYS = ['C', 'D♭', 'D', 'E♭', 'E', 'F', 'G♭', 'G', 'A♭', 'A', 'B♭', 'B'];
  const CHORDS = {
    'I': [0, 4, 7], 'IIm': [2, 5, 9], 'IIm7': [2, 5, 9, 12], 'IIIm': [4, 7, 11],
    'IV': [5, 9, 12], 'V': [7, 11, 14], 'V7': [7, 11, 14, 17], 'VIm': [9, 12, 16],
    'VIIm-5': [11, 14, 17], 'IV/V': [5, 9, 12], 'Isus4': [0, 5, 7]
  };
  const BASS = { 'IV/V': 7 };
  const BPMS = [70, 80, 90, 100, 110, 120, 130, 140], DEFAULT_BPM = 100;
  // 1周ぶんをまとめて予約すると、置いた音が次の周まで鳴らない。
  // 8分音符ごとに SCHED_AHEAD 秒だけ先を予約することで、置いた音がその周のうちに鳴る。
  const SCHED_AHEAD = 0.12, TICK_MS = 25;

  let ac = null;
  function audio() {
    if (!ac) ac = new (window.AudioContext || window.webkitAudioContext)();
    if (ac.state === 'suspended') ac.resume();
    return ac;
  }
  function tone(midi, at, dur, vol, out) {
    const c = audio(), t0 = c.currentTime + Math.max(at, 0), f = 440 * Math.pow(2, (midi - 69) / 12);
    const g = c.createGain(), lp = c.createBiquadFilter();
    lp.type = 'lowpass'; lp.frequency.value = 2600;
    g.gain.setValueAtTime(0, t0);
    g.gain.linearRampToValueAtTime(vol, t0 + 0.015);
    g.gain.exponentialRampToValueAtTime(Math.max(vol * 0.35, 0.0002), t0 + dur * 0.5);
    g.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
    [['sine', 1], ['triangle', 0.3]].forEach(pair => {
      const o = c.createOscillator(), og = c.createGain();
      o.type = pair[0]; o.frequency.value = f; og.gain.value = pair[1];
      o.connect(og).connect(g); o.start(t0); o.stop(t0 + dur + 0.05);
    });
    g.connect(lp).connect(out || c.destination);
  }

  const els = document.querySelectorAll('.roll');
  for (let i = 0; i < els.length; i++) setup(els[i]);

  function setup(root) {
    const lesson = root.dataset.lesson || '0';
    const progs = (root.dataset.progs || 'I-VIm-IV-V').split('|');
    let prog = progs[0].split('-');
    const open = new Set((root.dataset.degrees || '').split(',').filter(Boolean));
    const notes = new Set();                      // "midi,col"
    let tonicPc = 0, bpm = DEFAULT_BPM, dragging = false, drawMode = 'draw', warn = '';
    const stepSec = () => 60 / bpm / 2;           // 横1マス＝8分音符
    const cycleLen = () => COLS * stepSec();      // 4小節1周
    let bus = null, timer = null, raf = null, startAt = 0, lastCol = -1;

    // ---- 目に見える部品を組む ----
    const mk = (tag, cls, text) => {
      const el = document.createElement(tag);
      if (cls) el.className = cls;
      if (text !== undefined) el.textContent = text;
      return el;
    };
    const top = mk('div', 'roll-top');
    const progSel = mk('select', 'roll-prog');
    progSel.setAttribute('aria-label', 'コード進行');
    const sel = mk('select', 'roll-key');
    sel.setAttribute('aria-label', 'キー');
    const bpmSel = mk('select', 'roll-bpm');
    bpmSel.setAttribute('aria-label', 'テンポ');
    const playBtn = mk('button', 'roll-play pri', '再生');
    const clearBtn = mk('button', 'roll-clear', '消す');
    const trLabel = mk('label');
    const trBox = mk('input', 'roll-tr');
    trBox.type = 'checkbox';
    trBox.checked = true;
    trLabel.appendChild(trBox);
    trLabel.appendChild(mk('span', '', ' キーを変えたらメロも移調'));
    [progSel, sel, bpmSel, playBtn, clearBtn, trLabel].forEach(el => top.appendChild(el));

    const scroll = mk('div', 'roll-scroll');
    const grid = mk('div', 'roll-grid');
    const barsEl = mk('div', 'roll-bars');
    const gutEl = mk('div', 'roll-gutter');
    const cellsEl = mk('div', 'roll-cells');
    [mk('div', 'roll-corner'), barsEl, gutEl, cellsEl].forEach(el => grid.appendChild(el));
    scroll.appendChild(grid);
    const noteEl = mk('p', 'roll-note');
    const warnEl = mk('p', 'roll-warn');
    [top, scroll, warnEl, noteEl].forEach(el => root.appendChild(el));

    for (let k = 0; k < 12; k++) {
      const o = document.createElement('option');
      o.value = String(k); o.textContent = KEYS[k] + ' キー';
      sel.appendChild(o);
    }
    BPMS.forEach(v => {
      const o = document.createElement('option');
      o.value = String(v); o.textContent = v + ' BPM';
      bpmSel.appendChild(o);
    });
    progs.forEach(v => {
      const o = document.createElement('option');
      o.value = v; o.textContent = v;
      progSel.appendChild(o);
    });
    const bars = [];
    for (let b = 0; b < BARS; b++) {
      const d = mk('div', 'roll-bar');
      barsEl.appendChild(d); bars.push(d);
    }
    function updateBars() {
      for (let b = 0; b < BARS; b++) bars[b].textContent = prog[b % prog.length];
    }
    const gut = [], cells = [], byCol = [];
    for (let c = 0; c < COLS; c++) byCol.push([]);
    for (let r = 0; r < ROWS; r++) {
      const g = document.createElement('div');
      g.className = 'roll-deg'; gutEl.appendChild(g); gut.push(g);
      const row = [];
      for (let c = 0; c < COLS; c++) {
        const el = document.createElement('div');
        el.className = 'rc' + (c % STEPS === 0 && c ? ' barstart' : '');
        el.dataset.r = String(r); el.dataset.c = String(c);
        cellsEl.appendChild(el); row.push(el); byCol[c].push(el);
      }
      cells.push(row);
    }

    const midiOf = r => HIGH - r;
    // キーの移動量は必ず ±6 半音に正規化する。伴奏の基準音もメロもこの同じ量で動かすので、
    // どのキーにしてもメロとコードの上下関係（＝コード度数の聴こえ方）が変わらない。
    // LOW + tonicPc（0〜+11）だと、伴奏だけが最大1オクターブ上がってメロが埋もれる。
    const keyOffset = pc => ((pc + 6) % 12) - 6;
    const tonicMidi = () => LOW + keyOffset(tonicPc);

    function paint() {
      for (let r = 0; r < ROWS; r++) {
        const m = midiOf(r);
        const iv = ((m - tonicPc) % 12 + 12) % 12;
        const d = MAJOR.indexOf(iv);
        const isScale = d >= 0, isOpen = isScale && open.has(String(d + 1));
        gut[r].textContent = isScale ? String(d + 1) : '';
        gut[r].className = 'roll-deg' + (isScale ? ' scale' : '') + (isOpen ? ' open' : '');
        for (let c = 0; c < COLS; c++) {
          const el = cells[r][c];
          el.classList.toggle('scale', isScale);
          el.classList.toggle('open', isOpen);
          el.classList.toggle('oct', iv === 0);
          el.classList.toggle('on', notes.has(m + ',' + c));
        }
      }
      warnEl.textContent = warn;
      const total = open.size ? open.size : 7;
      noteEl.textContent =
        '色の濃い行が ' + KEYS[tonicPc] + ' キーのメジャースケール。' +
        '番号が濃い行がこの回までに解禁された ' + total +
        'つの音。マスを押すと音が置け、横になぞると伸びる。' +
        '横1マスが8分音符、太い線が小節の切れ目。';
    }

    // ---- 打ち込み ----
    function apply(el) {
      const m = midiOf(+el.dataset.r), key = m + ',' + el.dataset.c;
      if (drawMode === 'draw') {
        if (!notes.has(key)) { notes.add(key); el.classList.add('on'); tone(m, 0, 0.35, 0.2, null); }
      } else if (notes.has(key)) { notes.delete(key); el.classList.remove('on'); }
      save();
    }
    cellsEl.addEventListener('pointerdown', e => {
      const el = e.target.closest('.rc');
      if (!el) return;
      e.preventDefault();
      const m = midiOf(+el.dataset.r);
      drawMode = notes.has(m + ',' + el.dataset.c) ? 'erase' : 'draw';
      dragging = true;
      try { cellsEl.setPointerCapture(e.pointerId); } catch (err) {}
      apply(el);
    });
    cellsEl.addEventListener('pointermove', e => {
      if (!dragging) return;
      const el = document.elementFromPoint(e.clientX, e.clientY);
      const cell = el && el.closest && el.closest('.rc');
      if (cell && cellsEl.contains(cell)) apply(cell);
    });
    window.addEventListener('pointerup', () => { dragging = false; });

    // ---- 保存 ----
    function save() {
      try {
        localStorage.setItem('roll:' + lesson, JSON.stringify({ k: tonicPc, b: bpm, p: prog.join('-'), n: Array.from(notes) }));
      } catch (err) {}
    }
    function load() {
      try {
        const raw = localStorage.getItem('roll:' + lesson);
        if (!raw) return;
        const o = JSON.parse(raw);
        if (typeof o.k === 'number' && o.k >= 0 && o.k < 12) tonicPc = o.k;
        if (BPMS.indexOf(o.b) >= 0) bpm = o.b;
        if (progs.indexOf(o.p) >= 0) prog = o.p.split('-');
        (o.n || []).forEach(k => notes.add(k));
      } catch (err) {}
    }

    // ---- 再生（止めるまでループ） ----
    // 通し番号 n のステップ（8分音符1つ）を、時刻 at に予約する。
    // 予約の直前に notes を見るので、その時点で置いてある音がそのまま鳴る。
    function scheduleStep(n, at, out) {
      const c = audio(), rel = at - c.currentTime;
      const col = ((n % COLS) + COLS) % COLS;
      if (col % STEPS === 0) {                       // 小節のあたま：コードとベース
        const name = prog[(col / STEPS) % prog.length];
        const off = CHORDS[name] || CHORDS.I;
        const dur = STEPS * stepSec() * 0.96;
        off.forEach(iv => tone(tonicMidi() + iv, rel, dur, 0.075, out));
        const rootIv = BASS[name] !== undefined ? BASS[name] : off[0];
        tone(tonicMidi() + rootIv - 12, rel, dur, 0.13, out);
      }
      for (let m = LOW; m <= HIGH; m++) {
        if (!notes.has(m + ',' + col)) continue;
        if (col > 0 && notes.has(m + ',' + (col - 1))) continue;   // 伸ばしている途中なので鳴らし直さない
        let len = 1;
        while (col + len < COLS && notes.has(m + ',' + (col + len))) len++;
        tone(m, rel, len * stepSec() * 0.95, 0.2, out);
      }
    }
    function markCol(col) {
      if (col === lastCol) return;
      if (lastCol >= 0) byCol[lastCol].forEach(el => el.classList.remove('now'));
      if (lastCol >= 0) bars[Math.floor(lastCol / STEPS)].classList.remove('now');
      if (col >= 0) {
        byCol[col].forEach(el => el.classList.add('now'));
        bars[Math.floor(col / STEPS)].classList.add('now');
      }
      lastCol = col;
    }
    function stop() {
      if (timer) { clearTimeout(timer); timer = null; }
      if (raf) { cancelAnimationFrame(raf); raf = null; }
      if (bus) {
        const b = bus; bus = null;
        try {
          b.gain.cancelScheduledValues(ac.currentTime);
          b.gain.setTargetAtTime(0, ac.currentTime, 0.02);
        } catch (err) {}
        setTimeout(() => { try { b.disconnect(); } catch (err) {} }, 400);
      }
      markCol(-1);
      playBtn.textContent = '再生';
      playBtn.classList.add('pri');
    }
    function play() {
      stop();
      const c = audio();
      const b = c.createGain();
      b.gain.value = 1; b.connect(c.destination); bus = b;
      startAt = c.currentTime + 0.08;
      let nextStep = 0;
      (function tick() {
        if (bus !== b) return;
        const step = stepSec(), horizon = c.currentTime + SCHED_AHEAD;
        while (startAt + nextStep * step < horizon) {
          const at = startAt + nextStep * step;
          // タブが裏にいた等で遅れた分は、まとめて鳴らさずに捨てる
          if (at >= c.currentTime - 0.02) scheduleStep(nextStep, at, b);
          nextStep++;
        }
        timer = setTimeout(tick, TICK_MS);
      })();
      (function follow() {
        if (bus !== b) return;
        const el = c.currentTime - startAt;
        markCol(el < 0 ? -1 : Math.floor((el % cycleLen()) / stepSec()));
        raf = requestAnimationFrame(follow);
      })();
      playBtn.textContent = '止める';
      playBtn.classList.remove('pri');
    }

    playBtn.addEventListener('click', () => (bus ? stop() : play()));
    clearBtn.addEventListener('click', () => {
      notes.clear(); paint(); save();
    });
    sel.addEventListener('change', () => {
      const next = +sel.value;
      const delta = keyOffset(next) - keyOffset(tonicPc);
      warn = '';
      if (trBox.checked && delta && notes.size) {
        // メロは必ず全体を同じ量だけ動かす。音ごとにオクターブ折り返しすると、
        // (1) メロの形が壊れ (2) 同じマスに重なった音が消え (3) キーを戻しても元に戻らない。
        // 盤面から出るときは、全体をまとめてオクターブ単位でずらして収める。
        let lo = Infinity, hi = -Infinity;
        notes.forEach(k => {
          const m = +k.split(',')[0];
          if (m < lo) lo = m;
          if (m > hi) hi = m;
        });
        // 伴奏と「同じ量」を最優先する。移動量の小ささで選ぶと、
        // 伴奏が下がったのにメロだけ上がって1オクターブずれる。
        // 盤面に収まらないときだけ、オクターブ単位でずらした候補に落とす。
        const cands = [delta, delta - 12, delta + 12, delta - 24, delta + 24];
        let d = null;
        for (let i = 0; i < cands.length; i++) {
          if (lo + cands[i] >= LOW && hi + cands[i] <= HIGH) { d = cands[i]; break; }
        }
        if (d === null) {
          warn = 'このメロは音域が広すぎて、このキーには収まらない。音域を狭めるか、移調のチェックを外す。';
        } else {
          const moved = [];
          notes.forEach(k => { const q = k.split(','); moved.push((+q[0] + d) + ',' + q[1]); });
          notes.clear();
          moved.forEach(k => notes.add(k));
        }
      }
      tonicPc = next;
      paint(); save();
      if (bus) play();
    });

    // 予約は8分音符ごとなので、鳴らしたまま変えても次の小節から新しい進行になる
    progSel.addEventListener('change', () => {
      prog = progSel.value.split('-');
      updateBars();
      save();
    });
    bpmSel.addEventListener('change', () => {
      bpm = +bpmSel.value;
      save();
      if (bus) play();
    });

    load();
    sel.value = String(tonicPc);
    bpmSel.value = String(bpm);
    progSel.value = prog.join('-');
    updateBars();
    paint();
  }
})();
"""

# -------------------------------------------------------------------- テンプレート

def page(title, desc, url, body, css_extra="", depth=1):
    up = "../" * depth
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="icon" type="image/png" href="/favicon.png">
<title>{html.escape(title)}</title>
<meta name="description" content="{html.escape(desc)}">
<link rel="canonical" href="{url}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="in the blue shirt">
<meta property="og:title" content="{html.escape(title)}">
<meta property="og:description" content="{html.escape(desc)}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{BASE}og.png">
<meta name="twitter:card" content="summary_large_image">
<link rel="stylesheet" href="{up}assets/base.css">{css_extra}
</head>
<body>
{body}
</body>
</html>
"""


FOOT = (
    '<p class="foot">京都精華大学 メディア表現学部「応用実習1,2：作曲」（火曜・全14回／各3時間＝90分×2コマ）<br>'
    '担当：有村崚（<a href="https://intheblueshirt.com/">in the blue shirt</a>）</p>'
)


def nav(depth, current=""):
    up = "../" * depth
    links = [
        (f"{up}", "← 授業トップ"),
        (f"{up}roadmap/", "理論ロードマップ"),
        (f"{up}tips/", "ポップスのコツ"),
        (f"{up}ear/", "1度当て練習"),
    ]
    out = []
    for href, label in links:
        if label.endswith(current) and current:
            continue
        out.append(f'<a href="{href}">{label}</a>')
    return f'<p class="topnav">{"".join(out)}</p>'


# ------------------------------------------------------------------- ページ生成

def build_index(d):
    parts = [
        '<div class="wrap">',
        '<p class="eyebrow">京都精華大学 メディア表現学部</p>',
        "<h1>応用実習1,2：作曲</h1>",
        '<p class="meta">火曜・全14回／各3時間（90分×2コマ）｜担当：有村崚（in the blue shirt）</p>',
        f'<p class="lead">{inline(d["lead"])}</p>',
        '<div class="chips">'
        '<a href="#lessons">全14回</a>'
        '<a href="roadmap/">理論ロードマップ</a>'
        '<a href="tips/">ポップスのコツ</a>'
        '<a href="ear/">1度当て練習</a>'
        '<a href="#flow">1回の流れ</a>'
        '<a href="#eval">評価と提出物</a>'
        "</div>",
        '<h2 id="lessons">全14回</h2>',
        f'<p>{inline(d["lessons_note"])}</p>',
    ]
    for phase in d["phases"]:
        parts.append(f'<h3>{inline(phase["title"])}</h3>')
        cards = []
        for no in phase["nos"]:
            ls = d["lessons"][no]
            cards.append(
                f'<a class="card" href="{no:02d}/">'
                f'<div class="no">第{no}回</div>'
                f'<div class="th">{inline(ls["title"])}</div>'
                f'{degree_chips(ls["deg"], ls["flat"])}'
                + (
                    f'<div class="sub">伴奏：{inline(ls["prog"])}</div>'
                    if ls["prog"].strip() not in ("", "—", "-")
                    else ""
                )
                + "</a>"
            )
        parts.append(f'<div class="cards">{"".join(cards)}</div>')
    parts += [
        f'<h2 id="flow">{inline(d["flow_title"])}</h2>',
        d["flow_html"],
        "<h2>授業の狙いと表記ルール</h2>",
        d["about_html"],
        f'<h2 id="eval">{inline(d["eval_title"])}</h2>',
        d["eval_html"],
        FOOT,
        "</div>",
    ]
    return page(
        f"{SITE_TITLE}｜京都精華大学 メディア表現学部",
        SITE_DESC,
        BASE,
        "\n".join(parts),
        depth=0,
    )


def build_lesson(d, no):
    ls = d["lessons"][no]
    tips = [t for t in d["tips"] if no in t["nos"]]
    prog = dict(ls["items"]).get("伴奏", ls["prog"]).strip()
    chords = "-".join(roll_prog(no, prog))
    # 「伴奏」欄に進行以外の説明が書いてあるときは、パネルはコード名だけにして
    # 説明のほうは本文の行に残す
    prog_has_note = prog.replace("。", "").strip() != chords
    sounds = (
        '<div class="panel"><p class="k">使える音（キー度数）</p>'
        + degree_chips(ls["deg"], ls["flat"]).replace('class="degs"', 'class="degs lg"')
        + f'<p class="note">今回の解禁：{inline(ls["sounds_raw"])}</p></div>'
    )
    parts = [
        '<div class="wrap narrow">',
        nav(1),
        f'<p class="eyebrow">{inline(ls["phase_title"])}</p>',
        f'<h1>第{no}回　{inline(ls["title"])}</h1>',
    ]
    if prog in ("", "—", "-"):
        parts.append(sounds)
    else:
        parts += [
            '<div class="grid2">',
            sounds,
            '<div class="panel"><p class="k">伴奏進行</p>'
            f'<p class="v"><code>{inline(chords)}</code></p></div>',
            "</div>",
        ]
    rows = []
    for label, text in ls["items"]:
        if label == "伴奏" and not prog_has_note:
            continue
        rows.append(
            f'<div class="row"><div class="lbl">{inline(label)}</div>'
            f'<p class="val">{inline(text)}</p></div>'
        )
    parts.append(f'<div class="rows">{"".join(rows)}</div>')

    degrees = ",".join(x for x in DEG_ALL if x in ls["deg"])
    parts += [
        "<h2>4小節つくってみる</h2>",
        "<p>マスを押してメロを置く。色の濃い行が、選んだキーのメジャースケール。"
        "コード進行はプルダウンで差し替えられる（鳴らしたまま変えると次の小節から切り替わる）。"
        "キーを変えると、メロごと移調して高さだけが変わる（数字は変わらない）。</p>",
        f'<div class="roll" data-lesson="{no:02d}" '
        f'data-progs="{"|".join(roll_prog_choices(no, prog))}" '
        f'data-degrees="{degrees}"></div>',
    ]

    if tips:
        parts.append("<h2>この回で教えるコツ</h2>")
        items = "".join(
            f'<li><strong>{inline(t["tip"])}</strong>（{inline(t["view"])}）<br>'
            f'<span class="why">{inline(t["why"])}</span></li>'
            for t in tips
        )
        parts.append(f"<ul>{items}</ul>")
        parts.append('<p class="more"><a href="../tips/">コツの一覧を見る →</a></p>')

    prev_l = f'<a href="../{no-1:02d}/">← 第{no-1}回</a>' if no > 1 else ""
    next_l = f'<a href="../{no+1:02d}/">第{no+1}回 →</a>' if no < 14 else ""
    parts.append(f'<div class="pager">{prev_l}<div class="sp"></div>{next_l}</div>')
    parts.append(FOOT)
    parts.append("</div>")
    parts.append('<script src="../assets/roll.js" defer></script>')

    desc = f'第{no}回「{ls["title"]}」。使える音：{ls["sounds_raw"]}／伴奏進行：{ls["prog"]}。'
    aim = dict(ls["items"]).get("狙い", "")
    if aim:
        desc += aim
    return page(
        f'第{no}回 {ls["title"]}｜{SITE_TITLE}',
        desc[:140],
        f"{BASE}{no:02d}/",
        "\n".join(parts),
    )


VIEW_SLUG = {"音選び": "note", "形": "shape", "リズム": "rhythm", "構成": "form"}


def build_tips(d):
    views = []
    for t in d["tips"]:
        if t["view"] not in views:
            views.append(t["view"])
    slug = {v: VIEW_SLUG.get(v, f"view{i+1}") for i, v in enumerate(views)}

    parts = [
        '<div class="wrap narrow">',
        nav(1, "ポップスのコツ"),
        '<p class="eyebrow">応用実習1,2：作曲</p>',
        "<h1>ポップスのコツ</h1>",
        f'<p class="lead">{inline(d["tips_note"])}</p>',
    ]
    counts = {v: sum(1 for t in d["tips"] if t["view"] == v) for v in views}
    parts.append(
        '<div class="index">'
        + "".join(
            f'<a href="#{slug[v]}">{inline(v)}<span>{counts[v]}</span></a>' for v in views
        )
        + "</div>"
    )

    for view in views:
        parts.append(f'<h2 id="{slug[view]}">{inline(view)}</h2>')
        items = []
        for t in d["tips"]:
            if t["view"] != view:
                continue
            # 授業との対応はおまけなので、小さく末尾に添えるだけにする
            src = ""
            if t["nos"]:
                links = "・".join(f'<a href="../{n:02d}/">第{n}回</a>' for n in t["nos"])
                src = f'<p class="src">授業では{links}で導入</p>'
            items.append(
                f'<li class="tip"><p class="t">{inline(t["tip"])}</p>'
                f'<p class="d">{inline(t["why"])}</p>{src}</li>'
            )
        parts.append(f'<ol class="tips">{"".join(items)}</ol>')

    parts += [FOOT, "</div>"]
    return page(
        f"ポップスのコツ｜{SITE_TITLE}",
        "メロディを作るときの鉄則16個を、音選び・形・リズム・構成の4つの観点で整理した資料。",
        f"{BASE}tips/",
        "\n".join(parts),
    )


def build_roadmap(d):
    parts = [
        '<div class="wrap narrow">',
        nav(1, "理論ロードマップ"),
        '<p class="eyebrow">応用実習1,2：作曲</p>',
        "<h1>何もわからない人のための音楽理論ロードマップ</h1>",
        f'<p class="lead">{inline(d["roadmap_lead"])}</p>',
        '<div class="index">'
        + "".join(
            f'<a href="#{st["slug"]}">{inline(st["title"].split("　")[0])}'
            f'<span>{inline(st["title"].split("　")[-1])}</span></a>'
            for st in d["roadmap"]
        )
        + "</div>",
        d["roadmap_intro"],
    ]
    for st in d["roadmap"]:
        parts.append(f'<h2 id="{st["slug"]}">{inline(st["title"])}</h2>')
        rows, src = [], ""
        for label, text in st["items"]:
            if label == "対応回":
                nos = [int(n) for n in re.findall(r"\d+", text)]
                links = "・".join(f'<a href="../{n:02d}/">第{n}回</a>' for n in nos)
                src = f'<p class="stage-src">授業では{links}で扱う</p>' if links else ""
                continue
            rows.append(
                f'<div class="row"><div class="lbl">{inline(label)}</div>'
                f'<p class="val">{inline(text)}</p></div>'
            )
        if rows:  # 地の文だけで書いた段階は行を出さない
            parts.append(f'<div class="rows tight">{"".join(rows)}</div>')
        if st.get("extra"):
            parts.append(st["extra"])
        if src:
            parts.append(src)
    parts += [FOOT, "</div>"]
    return page(
        "何もわからない人のための音楽理論ロードマップ｜" + SITE_TITLE,
        "音楽理論＝いいかんじの音楽あるある。中心からの距離で安定/不安定をコントロールする体系として、何も知らない状態からダイアトニックコードまでを4段階で辿る資料。",
        f"{BASE}roadmap/",
        "\n".join(parts),
    )


def main():
    d = load()
    (OUT / "assets").mkdir(parents=True, exist_ok=True)
    written = []

    def write(rel, text):
        path = OUT / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        written.append(rel)

    write("assets/base.css", CSS)
    write("assets/roll.js", ROLL_JS)
    write("index.html", build_index(d))
    for no in sorted(d["lessons"]):
        write(f"{no:02d}/index.html", build_lesson(d, no))
    write("tips/index.html", build_tips(d))
    write("roadmap/index.html", build_roadmap(d))

    print(f"{len(written)} ファイルを書き出した → {OUT}")
    for rel in written:
        print("  ", rel)
    missing = [n for n, l in d["lessons"].items() if not l["items"]]
    if missing:
        print("注意：詳細が空の回 →", missing, file=sys.stderr)


if __name__ == "__main__":
    main()
