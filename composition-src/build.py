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
SITE_DESC = "京都精華大学メディア表現学部「応用実習1,2：作曲」（火曜・有村担当）全14回。メロの音は全部、移動ドの「キー度数/コード度数」で捉える。"

# ---------------------------------------------------------------- markdown 周り

def inline(s):
    """インライン記法だけを HTML に変換する。"""
    s = html.escape(s, quote=False)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)   # リズムの型（x..x..x.）など、等幅で見せたいもの
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    # [テキスト](URL) を先に。裸URLの自動リンクは、その href の中を二重に拾わないようにする
    s = re.sub(r"\[([^\]]+)\]\(((?:https?://|\.{1,2}/|/)[^)\s]+)\)", r'<a href="\2">\1</a>', s)
    s = re.sub(r'(?<!href=")(https?://[^\s<（）()、。"]+)', r'<a href="\1">\1</a>', s)
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
    """4スペース字下げのネストに対応した箇条書き。「1. 」始まりの並びは番号付き（<ol>）で出す。"""
    items = []
    for l in block:
        depth = (len(l) - len(l.lstrip(" "))) // 4
        s = l.strip()
        m = re.match(r"^(\d+)\.\s+(.*)$", s)
        if m:
            items.append((depth, "ol", m.group(2).strip()))
        else:
            items.append((depth, "ul", s[2:].strip()))

    def build(i, depth):
        tag = items[i][1]
        out = [f"<{tag}>"]
        while i < len(items) and items[i][0] >= depth:
            d, _, text = items[i]
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
        out.append(f"</{tag}>")
        return "".join(out), i

    return build(0, 0)[0]


BOLD_ONLY = re.compile(r"\*\*(.+?)\*\*$")


def is_bullet(ln):
    s = ln.lstrip(" ")
    return s.startswith("- ") or bool(re.match(r"^\d+\.\s", s))


def render_blocks(lines):
    """段落・太字見出し・表・箇条書きからなる本文をまとめて変換する。"""
    out, i = [], 0
    while i < len(lines):
        ln = lines[i].rstrip()
        if not ln.strip():
            i += 1
            continue
        w = re.fullmatch(r"\{\{([a-z][a-z0-9-]*)\}\}", ln.strip())
        if w:  # {{interval}} など。中身は assets/ の JS が作る
            out.append(f'<div data-widget="{w.group(1)}"></div>')
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
    5: "I-IV-V-I",        # T-S-D-T の型そのもの
    6: "I-VIm-IV-V",
    7: "I-IV-V-VIm",      # 偽終止を聴かせる
    9: "I-IV-V7-I",
    10: "I-VIm-IIm7-V",
    12: "I-VIm-IV-IV/V",  # 4on5 を種明かしする回
    13: "I-IV-♭VIM7-♭VII7",
    14: "I-VIm-IV-V",
    15: "I-VIm-IV-V",
}
DEFAULT_PROG = "I-VIm-IV-V"

# ピアノロールのコード進行プルダウンに出す候補。
# 右の数字は「その進行を出してよい最初のドリル」。授業の解禁順に合わせてある。
# 回をまとめたり順番を変えたりしたら、ここも合わせて直すこと。
ROLL_PROG_CHOICES = [
    ("IVM7-IIIm7-IIm7-I", 1),  # Phase 1 の進行（IIIm7 の上で1が♭6、2が7）
    ("I-IV-VIm-IV", 1),
    ("I-VIm-IIm7-IV", 1),
    ("I-VIm-IV-V", 1),      # Phase 1 の代わりの候補（V入り。Vの上は1が11th、2が5th）
    ("I-IIIm-IV-V", 2),
    ("IIm7-V-I-I", 3),
    ("I-IV-V-I", 5),        # 機能を習うドリルから
    ("I-IV-V-VIm", 7),      # 偽終止
    ("I-VIm-IIm7-V", 7),
    ("IV-I-IV-V", 8),
    ("IV-IVm7-I-I", 8),     # ここから tier表のダイアトニック外コード
    ("I-IV-V7-I", 9),
    ("IV-V-III7-VIm", 9),
    ("I-VI7-IIm7-V", 11),
    ("I-#Idim7-IIm7-V", 11),
    ("IV-V-#Vdim7-VIm", 11),
    ("I-Vm7-I7-IV", 11),
    ("I-VIm-IV-IV/V", 12),  # 4on5 はドリル12で種明かしする
    ("IIm7-♭II7-I-I", 12),
    ("I-IV-♭VIM7-♭VII7", 13),
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
_CHORD = rf"[#♭]?{_NUM}(?:maj7|M7|m7|m|dim7|7|sus4|aug)?(?:/[#♭]?{_NUM})?"
_BAR = rf"{_CHORD}(?:\+{_CHORD})?"     # 1小節。「IV+Vsus4」は小節の真ん中で切り替え
_RUN = re.compile(rf"{_BAR}(?:-{_BAR})+")


def roll_prog(no, raw):
    """伴奏進行の記述から、ピアノロール用の小節ごとのコードを作る。
    4小節に満たなければ繰り返して4小節に、5小節以上（8小節など）はそのまま"""
    m = _RUN.search(raw or "")
    found = m.group(0).split("-") if m else []
    if not found:
        found = FALLBACK_PROGS.get(no, DEFAULT_PROG).split("-")
    return [found[i % len(found)] for i in range(max(4, len(found)))]


def prog_label(chords):
    """「IV+Vsus4-I+VIm7」→「IV Vsus4｜I VIm7」。2コードの小節がない進行はそのまま（I-VIm-IV-V）"""
    if "+" not in chords:
        return chords
    return "｜".join(b.replace("+", " ") for b in chords.split("-"))


TOTAL_SESSIONS = 14   # 授業の回数。ドリルを割り当てていない回は「未定」と出す
QUARTERS = [("3Q", 1, 7), ("4Q", 8, 14)]   # 1クオーター7コマ


def session_label(d, ls):
    """カードとドリルのページ上部に出す「授業1回目 10/6」（課題日なら「・3Q末課題」も）。"""
    m = re.match(r"\d+", ls.get("session") or "")
    if not m:
        return ""
    n = int(m.group(0))
    date = next((dt for s, dt, _ in d.get("schedule", []) if s == n and dt), "")
    ev = d.get("events", {}).get(n)
    return f"授業{n}回目" + (f" {date}" if date else "") + (f"・{inline(ev)}" if ev else "")


def session_table(d):
    """カードの下に出す、授業の回ごとの表（授業｜日付｜ドリル｜Phase｜テーマ｜新コード）。
    一覧表の「授業」列と、その下の「授業｜日付｜予定」の表から組む。授業のない火曜も日付順に1行で出す。"""
    by = {}
    for no in sorted(d["lessons"]):
        ls = d["lessons"][no]
        m = re.match(r"\d+", ls.get("session") or "")
        if m:
            by.setdefault(int(m.group(0)), []).append(ls)
    if not by:
        return ""
    last = max(TOTAL_SESSIONS, max(by))
    sched = list(d.get("schedule") or [])
    have = {s for s, _, _ in sched if s}
    sched += [(s, "", "") for s in range(1, last + 1) if s not in have]
    dates = {s: dt for s, dt, _ in sched if s and dt}
    rows = []
    for s, dt, label in sched:
        if not s:                       # 授業のない日
            rows.append(f'<tr class="off"><td></td><td>{inline(dt)}</td><td></td><td></td><td>{inline(label)}</td><td></td></tr>')
            continue
        for q, a, z in QUARTERS:
            if s == a:
                span = f"・{dates[a]}〜{dates[z]}" if a in dates and z in dates else ""
                rows.append(f'<tr class="qh"><td colspan="6">{q}（授業{a}〜{z}{span}）</td></tr>')
        lss = by.get(s)
        ev = f'<b>{inline(label)}</b>' if label else ""
        date = inline(dt)
        if not lss:                     # ドリルを割り当てていない回（課題日か未定）
            cls = "qend" if ev else "tbd"
            rows.append(f'<tr class="{cls}"><td>{s}</td><td>{date}</td><td>—</td><td></td><td>{ev or "未定"}</td><td>—</td></tr>')
            continue
        drills = "・".join(f'<a href="{ls["no"]:02d}/">{ls["no"]}</a>' for ls in lss)
        phases = "・".join(dict.fromkeys(ls["phase"] for ls in lss))
        themes = "／".join(inline(ls["title"]) for ls in lss)
        if ev:
            themes = f"{ev}　{themes}"
        news = "・".join(n for n in (new_chords(ls) for ls in lss) if n) or "—"
        tr = '<tr class="qend">' if ev else "<tr>"
        rows.append(f"{tr}<td>{s}</td><td>{date}</td><td>{drills}</td><td>{inline(phases)}</td><td>{themes}</td><td>{inline(news)}</td></tr>")
    return (
        f'<h2 id="plan">全{last}回の予定</h2>'
        '<div class="tablebox"><table><thead><tr><th>授業</th><th>日付</th><th>ドリル</th><th>Phase</th><th>テーマ</th><th>新コード</th></tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table></div>'
    )


def new_chords(ls):
    """「新コード」の行から、コード名だけ（最初の（ や 。の手前まで）を取り出す。"""
    text = dict(ls["items"]).get("新コード", "")
    return re.split(r"[（。]", text)[0].strip()


def degree_chips(deg, flat):
    chips = [
        f'<span class="deg{" on" if d in deg else ""}">{d}</span>' for d in DEG_ALL
    ]
    for f in ("♭3", "♭7"):
        if f in flat:
            chips.append(f'<span class="deg flat on">{f}</span>')
    return f'<div class="degs">{"".join(chips)}</div>'


# -------------------------------------------------------------------- 原稿を読む

def _table_blocks(lines):
    """表の行だけを、表ごとに空行で区切って取り出す。"""
    out, prev = [], False
    for l in lines:
        is_t = l.startswith("|")
        if is_t and not prev and out:
            out.append("")
        if is_t:
            out.append(l)
        prev = is_t
    return out


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
    # 「**到達目標**」の塊だけ抜き出して、トップの一番上（リードの下）に出す
    g0 = next((i for i, ln in enumerate(rest) if ln.strip() == "**到達目標**"), None)
    goals = []
    if g0 is not None:
        g1 = next((i for i in range(g0 + 1, len(rest)) if re.fullmatch(r"\*\*[^*]+\*\*", rest[i].strip())), len(rest))
        goals, rest = rest[g0 + 1 : g1], rest[:g0] + rest[g1:]
    data["goals_html"] = render_blocks(goals)
    data["about_html"] = render_blocks(rest)

    # 標準の流れ（1回の時間配分）は節があれば出す。無ければトップに出さない（2026-09-30に節ごと削除）
    flow = next(((k, secs[k]) for k in secs if "標準の流れ" in k), None)
    data["flow_title"] = flow[0] if flow else ""
    data["flow_html"] = render_blocks(flow[1]) if flow else ""

    # 全14回一覧
    _, body = find("全14回一覧")
    note = next((l.strip() for l in body if l.strip() and not l.startswith("|") and not l.startswith("**")), "")
    # 表は空行で分かれて2つある：ドリルの表（ドリル｜授業｜…）と、授業の予定の表（授業｜予定）
    tables, cur = [], []
    for l in body + [""]:
        if l.startswith("|"):
            cur.append(l)
        elif cur:
            tables.append(cur); cur = []
    tbl = next(t for t in tables if "ドリル" in t[0])
    # 授業の日程：授業｜日付｜予定。授業が「—」の行は授業のない日（補講日など）
    data["events"], data["schedule"] = {}, []
    for t in tables:
        if "予定" in t[0]:
            eh, er = parse_table(t)
            ec = {name: idx for idx, name in enumerate(eh)}
            for r in er:
                m = re.match(r"\d+", r[ec["授業"]])
                no = int(m.group(0)) if m else None
                date = r[ec["日付"]] if "日付" in ec else ""
                label = r[ec["予定"]]
                data["schedule"].append((no, date, label))
                if no and label:
                    data["events"][no] = label
    header, rows = parse_table(tbl)
    col = {name: idx for idx, name in enumerate(header)}
    lessons, prev_deg, prev_flat = {}, set(), set()
    for row in rows:
        no = int(row[col["ドリル"]])
        deg, flat = degree_set(row[col["使える音"]], prev_deg, prev_flat)
        prev_deg, prev_flat = deg, flat
        lessons[no] = {
            "no": no,
            "phase": row[col["Phase"]],
            "theme": row[col["テーマ"]],
            "sounds_raw": row[col["使える音"]],
            "prog": row[col["伴奏進行"]],
            "session": row[col["授業"]] if "授業" in col else "",
            "deg": deg,
            "flat": flat,
            "items": [],
        }
    data["lessons_note"] = note
    data["lessons"] = lessons

    # 各回の詳細：Phase ごと → ドリルN ごと
    _, body = find("各回の詳細")
    data["phases"] = []
    for phase_title, phase_body in split_sections(body, "### "):
        nos = []
        for head, bullets in split_sections(phase_body, "#### "):
            m = re.match(r"ドリル(\d+)[　\s]*(.*)", head)
            if not m:
                continue
            no = int(m.group(1))
            lesson = lessons[no]
            lesson["title"] = m.group(2).strip() or lesson["theme"]
            lesson["phase_title"] = phase_title
            # 「##### 見出し」から下は授業の流れ（ページの上から順に投影して進める）。
            # それより上の「- **ラベル**：本文」が、これまでどおりの設計メモの行
            lesson["flow"] = []
            step = None
            for ln in bullets:
                if ln.startswith("##### "):
                    step = (ln[6:].strip(), [])
                    lesson["flow"].append(step)
                    continue
                if step is not None:
                    step[1].append(ln)
                    continue
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
                "extra": render_blocks([l for l in others if not l.startswith("|")]),
                "tables": render_blocks(_table_blocks(others)),   # PCでは右に並べる
            }
        )

    # ざっくり音楽理論史（節が無ければページも作らない）
    data["history"] = None
    hist_key = next((k for k in secs if "理論史" in k), None)
    if hist_key:
        body = secs[hist_key]
        lead, rest = "", list(body)
        for n, ln in enumerate(rest):
            if ln.strip():
                # 節の頭が箇条書きなら、リードにせず本文（intro）として出す
                if not is_bullet(ln):
                    lead, rest = ln.strip(), rest[n + 1 :]
                break
        head_at = next((i for i, ln in enumerate(rest) if ln.startswith("### ")), len(rest))
        sections = []
        for head, bullets in split_sections(rest[head_at:], "### "):
            items, others = [], []
            for ln in bullets:
                m = re.match(r"^- \*\*(.+?)\*\*：(.*)$", ln.strip())
                if m:
                    items.append((m.group(1), m.group(2).strip()))
                else:
                    others.append(ln)
            # ラベルの頭が年代（数字・世紀）ならタイムライン、そうでなければ行（つながりの節）
            timeline = sum(1 for l, _ in items if re.search(r"[0-9０-９]|世紀", l.split("　")[0])) > len(items) / 2
            sections.append({"title": head, "items": items, "timeline": timeline, "extra": render_blocks(others)})
        data["history"] = {
            "title": hist_key,
            "lead": lead,
            "intro": render_blocks(rest[:head_at]),
            "sections": sections,
        }

    # ポップスのコツ
    _, body = find("ポップスのコツ")
    data["tips_note"] = next(
        (l.strip() for l in body if l.strip() and not l.startswith("|")), ""
    )
    # コツの一覧は「| 観点」で始まる表。
    # 冒頭文とその表の間に「**観点：見出し**」の塊を置くと、その観点の節ごとページの一番上に出す
    # （例：コードの tier 表）。表の後ろに置いた塊は、その観点の節の下に出す。
    ni = next(i for i, l in enumerate(body) if l.strip() and not l.startswith("|"))
    t0 = next(i for i, l in enumerate(body) if l.startswith("| 観点"))
    t1 = t0
    while t1 < len(body) and body[t1].startswith("|"):
        t1 += 1
    header, rows = parse_table(body[t0:t1])

    def split_blocks(lines):
        pre, out, cur, buf = [], [], None, []
        for ln in lines + ["**__end__：__end__**"]:
            m = re.fullmatch(r"\*\*(.+?)：(.+?)\*\*", ln.strip())
            if m:
                if cur:
                    out.append((cur[0], cur[1], render_blocks(buf)))
                cur, buf = (m.group(1), m.group(2)), []
            elif cur:
                buf.append(ln)
            else:
                pre.append(ln)
        return pre, out

    pre, top_blocks = split_blocks(body[ni + 1 : t0])
    _, after_blocks = split_blocks(body[t1:])
    data["tips_top"] = render_blocks(pre)
    data["tips_top_views"] = []
    extra = {}
    for view, title, h in top_blocks:
        extra.setdefault(view, []).append((title, h))
        if view not in data["tips_top_views"]:
            data["tips_top_views"].append(view)
    for view, title, h in after_blocks:
        extra.setdefault(view, []).append((title, h))
    data["tips_extra"] = extra
    col = {name: idx for idx, name in enumerate(header)}
    tips = []
    for row in rows:
        intro = row[col["導入ドリル"]]
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

    title, body = find("評価")
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
  --row-scale:#dcecf8;--row-open:#fbe3a6; /* ピアノロールの行（スケール／今回使う音＝黄色で目立たせる） */
}
html{background:var(--page);color-scheme:light}
*{box-sizing:border-box}
body{margin:0;background:var(--page);color:var(--ink);
  font-family:system-ui,-apple-system,"Hiragino Sans","Noto Sans JP",sans-serif;
  line-height:1.8;font-size:15px;-webkit-text-size-adjust:100%}
.wrap{max-width:1400px;margin:0 auto;padding:40px 16px 72px}
.wrap.narrow{max-width:1400px}
.wrap.tool{max-width:1100px}
a{color:var(--acc)}
h1{font-size:clamp(23px,4.6vw,32px);line-height:1.34;letter-spacing:-.01em;margin:0 0 8px;text-wrap:balance}
h2{font-size:18px;margin:44px 0 12px;letter-spacing:-.01em;padding-bottom:7px;border-bottom:1px solid var(--grid)}
h3{font-size:14px;margin:26px 0 8px;color:var(--ink2);letter-spacing:.01em}
p{margin:9px 0}
ul,ol{margin:9px 0;padding-left:1.35em}
li{margin:4px 0}
ul ul,ul ol,ol ul,ol ol{margin:3px 0}
.nw{white-space:nowrap}
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
.card .sess{margin-left:.8em;letter-spacing:.06em}
.card .sub.new{color:var(--acc-ink);font-weight:700}
.tablebox tr.tbd td{color:var(--muted)}
.tablebox tr.qh td{font-weight:800;color:var(--acc-ink);background:var(--acc-soft)}
.tablebox tr.qend td{background:var(--surface)}
.tablebox tr.off td{color:var(--muted);font-size:.9em}
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
/* ざっくり音楽理論史（history/）：kammerkonzert/ensemble/ の振り子年表の簡易版。
   縦＝時間。クラシックは左トラック、バークリーは右トラック、最後に中央で合流。
   ノード・カードは build.py が絶対配置で吐き、折れ線は SVG（xは%・yはpx、non-scaling-stroke） */
.histwrap{max-width:860px;margin:26px auto 0}
.histbox{position:relative}
.histbox svg{position:absolute;inset:0;width:100%;height:100%;pointer-events:none;z-index:1}
.histbox .vline{position:absolute;width:1px;background:var(--grid)}
.hnode{position:absolute;transform:translate(-50%,-50%);width:16px;height:16px;border-radius:50%;
  background:var(--hc,var(--acc));border:2px solid var(--page);box-shadow:0 0 0 1px var(--ring);z-index:3}
.hnode.merge{width:26px;height:26px;box-shadow:0 0 0 3px var(--page),0 0 0 4.5px var(--hc,var(--acc-ink))}
.hcard{position:absolute;transform:translateY(-50%);max-width:min(70%,460px);background:var(--surface);
  border:1px solid var(--ring);border-radius:11px;padding:10px 14px;z-index:2}
.hcard h3{margin:0;font-size:14px;line-height:1.45;letter-spacing:-.01em}
.hcard h3 .cy{color:var(--muted);font-weight:400;font-size:11.5px;margin-left:8px;white-space:nowrap;font-variant-numeric:tabular-nums}
.hcard p{margin:5px 0 0;font-size:12.5px;color:var(--ink2);line-height:1.75}
.hcard.mergecard{transform:translateX(-50%);left:50%;max-width:min(86%,480px)}
.hlabel{position:absolute;left:0;right:0;transform:translateY(-50%);z-index:2;text-align:center}
.hlabel span{display:inline-block;background:var(--page);padding:2px 12px;font-size:13.5px;font-weight:700;color:var(--hc,var(--acc-ink))}
@media (max-width:620px){.hcard{max-width:76%}.hcard p{font-size:11.5px;line-height:1.65}}
/* スクロールで出現。JSが動かないときは常に見せる */
html.js .hrv{opacity:0;transition:opacity .6s ease}
html.js .hrv.show{opacity:1}
@media (prefers-reduced-motion:reduce){html.js .hrv{opacity:1;transition:none}}
/* 表 */
.tablebox{overflow-x:auto;margin:12px 0}
/* 評価の表：2列しかないので幅を内容に合わせ、比重は右揃え */
.eval table{width:auto;min-width:min(100%,360px)}
.eval th:last-child,.eval td:last-child{text-align:right;font-variant-numeric:tabular-nums}
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
.roll .roll-deg.open{background:var(--row-open);color:#7a4f00}
.roll-cells{display:grid;grid-template-columns:repeat(32,1fr);grid-auto-rows:var(--rh);
  touch-action:none;user-select:none}
.rc{border-right:1px solid var(--grid);cursor:pointer}
.rc.scale{background:var(--row-scale)}
.rc.open{background:var(--row-open)}
.rc.oct{border-bottom:1px solid var(--grid)}
.rc.barstart{border-left:2px solid var(--muted)}
.rc.now{background-image:linear-gradient(rgba(31,111,196,.14),rgba(31,111,196,.14))}
.rc.on{background:var(--acc);border-right-color:var(--acc)}
.rc.on.split{box-shadow:inset 2px 0 0 var(--surface)}   /* 同じ高さの音の切れ目 */
.rc.halfstart{border-left:1px dashed var(--muted)}          /* 小節の途中でコードが変わる */
.roll-bar.split{display:flex;padding:0}
.roll-bar.split span{flex:1;padding:7px 0;min-width:0;overflow:hidden;text-overflow:ellipsis}
.roll-bar.split span+span{border-left:1px dashed var(--grid)}
/* インターバル鍵盤。中身は assets/interval.js が作る */
.iv-top{display:flex;gap:8px;align-items:center;margin:14px 0 10px}
.iv-top select{font:inherit;font-size:13px;border:1px solid var(--ring);border-radius:9px;padding:7px 12px;
  background:var(--surface);color:var(--ink);cursor:pointer}
.iv-scroll{overflow-x:auto;padding:2px 0 6px}
.iv-kb{position:relative;height:150px;min-width:560px;user-select:none;touch-action:manipulation}
.iv-kb.wide{min-width:780px}
.iv-whites{display:flex;height:100%}
.iv-key{display:flex;align-items:flex-end;justify-content:center;cursor:pointer;font-weight:700}
.iv-key.w{flex:1;background:#fbfdff;border:1px solid #b9cddd;border-top:none;border-radius:0 0 7px 7px;
  margin-right:-1px;padding-bottom:9px;font-size:11.5px;color:var(--acc-ink)}
.iv-key.b{position:absolute;top:0;height:60%;background:#1a2634;border:1px solid #0d141c;border-top:none;
  border-radius:0 0 6px 6px;z-index:2;padding-bottom:6px;font-size:10px;color:#cfe0ee}
.iv-key.off{cursor:default}
.iv-key.w.off{background:#edf2f6;color:transparent}
.iv-key.b.off{background:#56626f}
.iv-key.w.root,.iv-key.b.root{background:var(--acc);border-color:var(--acc);color:#fff}
.iv-key.w.hit{background:var(--acc-soft)}
.iv-key.b.hit{background:#31506f}
.iv-key.out{cursor:default}
.iv-key.w.out{background:#e9eef3;color:transparent}
.iv-key.b.out{background:#46525f}
.iv-top .iv-play{font:inherit;font-size:13px;border:1px solid var(--acc);border-radius:9px;padding:7px 14px;
  background:var(--acc);color:#fff;font-weight:700;cursor:pointer}
/* 覚えるべきコード（鳴らせる tier 表） */
/* 観点の鉄則（コツのページ）。でかく出す */
.motto{margin:4px 0 18px;padding:20px 24px;border-left:6px solid var(--acc);border-radius:10px;background:var(--surface)}
.motto p{margin:0;font-size:clamp(20px,2.3vw,30px);font-weight:800;line-height:1.45;letter-spacing:-.01em;color:var(--ink)}
.cw-top{margin:6px 0 14px}
.cw-top select{font:inherit;font-size:13px;border:1px solid var(--ring);border-radius:9px;padding:7px 12px;
  background:var(--surface);color:var(--ink);cursor:pointer}
.cw-grid{display:grid;grid-template-columns:64px 1fr;gap:14px 18px;align-items:start}
.cw-tier{font-size:12px;font-weight:700;color:var(--muted);letter-spacing:.06em;padding-top:10px}
.cw-groups{display:flex;flex-wrap:wrap;gap:10px 26px}
.cw-group{display:flex;flex-wrap:wrap;align-items:center;gap:7px}
.cw-group.labeled{flex-basis:100%}
.cw-glabel{font-size:11.5px;color:var(--muted);min-width:4.5em}
.cw-chip{font:inherit;font-size:15px;font-weight:700;border-radius:10px;padding:7px 13px;cursor:pointer;
  border:1px solid var(--ring);background:var(--surface);color:var(--ink);line-height:1.3}
.cw-chip .to{font-weight:400;font-size:12.5px;color:var(--ink2);margin-left:6px}
.cw-chip.g1{background:#d4e8f8;border-color:#d4e8f8;color:#175a9f}
.cw-chip.g2{background:#d6f0de;border-color:#d6f0de;color:#1d6a3a}
.cw-chip.g3{background:#fbe2d4;border-color:#fbe2d4;color:#9a3a12}
.cw-chip.t2{border-color:var(--acc);color:var(--acc-ink)}
.cw-chip:hover{border-color:var(--acc)}
.cw-chip.hit{background:var(--acc);border-color:var(--acc);color:#fff}
.cw-chip.hit .to{color:#fff}
.cw-chip .to.hit{color:var(--acc-ink);font-weight:700}
.iv-status{font-size:13px;color:var(--ink2);margin:6px 0 0;min-height:1.6em}
.dg-chords{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:8px;margin:0 0 12px}
.dg-chip{font:inherit;display:flex;flex-direction:column;align-items:center;gap:3px;padding:8px 4px;cursor:pointer;
  border:1px solid var(--ring);border-radius:10px;background:var(--surface);color:var(--ink)}
.dg-chip:hover{border-color:var(--acc)}
.dg-num{font-size:15px;font-weight:800}
.dg-name{font-size:12.5px;color:var(--ink2)}
.dg-chip.on{background:var(--acc);border-color:var(--acc);color:#fff}
.dg-chip.on .dg-name{color:#fff}
.iv-key.w.lit,.iv-key.b.lit{background:var(--acc);border-color:var(--acc);color:#fff}
.iv-key.w.croot,.iv-key.b.croot{background:var(--acc-ink);border-color:var(--acc-ink)}
.iv-key.w.lit{font-size:10.5px;letter-spacing:-.02em}   /* 「6/3」の併記が収まるように */
.iv-key.b.lit{font-size:9px;letter-spacing:-.02em}
@media (max-width:560px){.dg-chords{grid-template-columns:repeat(4,minmax(0,1fr))}}
.tablebox tr.iv-hl td{background:var(--acc-soft)}
.roll-note{font-size:12px;color:var(--ink2);margin:10px 0 0}
/* ドリルの授業の流れ：上から順に投影してスクロールで進める。文字は大きめ */
.flow{counter-reset:step;margin:8px 0 0}
.step{padding:34px 0 38px;border-top:1px solid var(--grid)}
.step:first-child{border-top:none;padding-top:18px}
.step>h2{counter-increment:step;display:flex;align-items:center;gap:14px;margin:0 0 18px;
  font-size:clamp(24px,2.8vw,36px);letter-spacing:-.01em}
.step>h2::before{content:counter(step);flex:none;width:40px;height:40px;border-radius:11px;
  background:var(--acc);color:#fff;font-size:20px;display:grid;place-items:center}
.step>ul,.step>ol{font-size:clamp(18px,2vw,26px);line-height:1.65;font-weight:700}
.step>ul ul{font-size:.85em;font-weight:400;color:var(--ink2)}
.step>p{font-size:clamp(16px,1.7vw,20px)}
/* 節の中の小見出し（例：曲名）。箇条書きより一段大きく、左に色の線 */
.step>h3{font-size:clamp(20px,2.3vw,30px);margin:40px 0 14px;padding-left:14px;border-left:5px solid var(--acc);line-height:1.35}
.step>h2+h3{margin-top:8px}
/* 簡易コード進行ジェネレータ（keyboard.js の progmini） */
.pm-row{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:18px 0 0}
.pm-chord{font:inherit;font-size:clamp(16px,1.8vw,22px);font-weight:700;color:var(--acc-ink);text-align:center;
  border:1px solid var(--ring);border-radius:11px;padding:14px 8px;background:var(--surface);cursor:pointer}
.pm-chord.now{border-color:var(--acc);background:var(--acc-soft);box-shadow:inset 0 0 0 1px var(--acc)}
.pm-top{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0 18px}
.pm-top select,.pm-top button{font:inherit;font-size:14px;border:1px solid var(--ring);border-radius:9px;
  padding:8px 14px;background:var(--surface);color:var(--ink);cursor:pointer}
.pm-top .pm-play{background:var(--acc);border-color:var(--acc);color:#fff;font-weight:700}
@media (max-width:560px){.pm-row{grid-template-columns:repeat(2,1fr)}}
/* 進行の再生（keyboard.js の play。中級編）：行ごとに再生ボタンと小節のチップ */
.pl-top{margin:14px 0 6px}
.pl-top select{font:inherit;font-size:13px;border:1px solid var(--ring);border-radius:9px;padding:7px 12px;
  background:var(--surface);color:var(--ink)}
.pl-row{display:flex;gap:12px;align-items:flex-start;padding:10px 0;border-top:1px solid var(--grid)}
.pl-row:last-child{border-bottom:1px solid var(--grid);margin-bottom:6px}
.pl-play{flex:none;min-width:5.2em;font:inherit;font-size:13px;border:1px solid var(--ring);border-radius:9px;
  padding:7px 12px;background:var(--surface);color:var(--ink);cursor:pointer}
.pl-play.pri{background:var(--acc);border-color:var(--acc);color:#fff;font-weight:700}
.pl-body{min-width:0}
.pl-label{font-size:12px;color:var(--muted);margin:0 0 4px}
.pl-bars{display:flex;flex-wrap:wrap;gap:6px}
.pl-bar{font-weight:700;font-size:14px;color:var(--acc-ink);border:1px solid var(--ring);border-radius:8px;
  padding:3px 10px;background:var(--surface)}
.pl-bar.now{background:var(--acc-soft);border-color:var(--acc)}
.pl-body{flex:1}
.pl-roll{display:block;width:100%;height:auto;margin:8px 0 2px;border:1px solid var(--ring);border-radius:8px;
  background:var(--surface);cursor:pointer}
.pl-roll .cr-row{fill:var(--surface)}
.pl-roll .cr-row.scale{fill:var(--row-scale)}
.pl-roll .cr-row.tonic{fill:#c6def2}
.pl-roll .cr-deg{font-size:5.6px;font-weight:700;fill:var(--ink2)}
.pl-roll .cr-deg.tonic{fill:var(--acc-ink)}
.pl-roll .cr-hl{fill:transparent}
.pl-roll .cr-hl.now{fill:rgba(31,111,196,.14)}
.pl-roll .cr-bar{stroke:var(--muted);stroke-width:.8}
.pl-roll .cr-half{stroke:var(--muted);stroke-width:.5;stroke-dasharray:1.5 1.5}
.pl-roll .cr-sep{stroke:var(--muted);stroke-width:.5;stroke-dasharray:2 2}
.pl-roll .cr-note{fill:var(--acc)}
.pl-roll .cr-bass{fill:var(--acc-ink)}
.flow-end{margin-top:40px;padding-top:28px;border-top:3px solid var(--grid);color:var(--ink2);font-size:18px}
.roll-warn{font-size:12.5px;color:var(--ng-ink);font-weight:700;margin:10px 0 0}
.roll-warn:empty{display:none}
/* PC（16:9）前提の横長レイアウト。1100px 未満では1段に戻る */
.lesson-main .grid2{display:flex;flex-wrap:wrap;gap:12px}
.lesson-main .grid2 .panel{flex:1 1 auto;margin:0}
.lesson-main .grid2 + .rows{margin-top:24px}
@media (min-width:1100px){
  body{font-size:17px}
  .wrap{padding:44px 48px 80px}
  h1{font-size:38px}
  h2{font-size:21px}
  .lead{font-size:17px}
  .cards{grid-template-columns:repeat(auto-fill,minmax(250px,1fr))}
  .lesson-grid{display:grid;grid-template-columns:minmax(0,5fr) minmax(0,7fr);gap:56px;align-items:start;margin-top:20px}
  .lesson-side{position:sticky;top:24px}
  .lesson-side h2:first-child{margin-top:0}
  .lesson-main h2{margin-top:36px}
  .cols{display:grid;grid-template-columns:repeat(var(--n),minmax(0,1fr));gap:48px;align-items:start}
  .stage-grid{display:grid;grid-template-columns:minmax(0,7fr) minmax(0,5fr);gap:48px;align-items:start}
  .stage-grid .tablebox{margin-top:0}
  .tips{grid-template-columns:repeat(auto-fill,minmax(340px,1fr))}
  .row{grid-template-columns:96px 1fr}
  table{font-size:14.5px}
  .roll-grid{--rh:18px}
  .phases{display:grid;grid-template-columns:repeat(var(--n),minmax(0,1fr));gap:18px;align-items:start}
  .phases h3{font-size:13px;margin:6px 0 10px;min-height:3.1em;line-height:1.45}
  .phases .cards{grid-template-columns:1fr;gap:10px;margin:0}
  .phases a.card{padding:12px 14px}
  .phases .card .th{font-size:14.5px}
  .phases .degs{gap:4px}
  .phases .degs .deg{min-width:24px;height:24px;font-size:12px;border-radius:6px;padding:0 3px}
}
@media print{
  :root{--page:#fff;--surface:#fff;--ink:#000;--ink2:#333;--muted:#666;--grid:#bbb;--ring:#bbb;--acc:#0a4a8a}
  .topnav,.pager,.chips,.roll-top{display:none}
  .wrap{padding:0;max-width:none}
  a{text-decoration:none}
}
"""

VOICING_JS = r"""/* 和音のボイシング（composition-src/build.py が生成）
   サイトで鳴る和音は全部ここを通す（コードtier・ピアノロール・段階4の鍵盤・1度当て・進行ジェネレータ）。
   ・ベースはルート（分数コードは分母）を C2〜D#3 に置く。鳴らす側でオクターブ上も半分の音量で重ねる
     （正弦波の低音は小さいスピーカーでほぼ聞こえず、ルート抜きの4和音が別のコードに聞こえるため）
   ・上の3声は密集の転回形で F3〜A#4 に収める。4和音はルートをベースに任せ、上は3・5・7
   ・上の一番下はベースから5度以上離す。重ねたオクターブと半音でぶつかる配置も選ばない（maj7 の7thがベースの長7度上に来る形など）
   ・進行のつなぎは、ループの継ぎ目も含めてコストの合計が最小になる組み合わせを選ぶ。
     コストは Emocute Studio の chord_gen（_vl_pair_cost）を移植した簡易版：
     共通音の保持ボーナス／移動距離の段階コスト（順次は安く跳躍は高い）／トップノートの旋律化／
     ガイドトーン（3rd・7th）の連結ボーナス（ルートモーション別）／並行5度・8度ペナルティ／
     外声の反行ボーナス／ベースとの短9度ペナルティ */
(function () {
  'use strict';
  const NUMERAL = /^([#♭]?)(VII|VI|V|IV|III|II|I)(.*)$/;
  const DEG = { I: 0, II: 2, III: 4, IV: 5, V: 7, VI: 9, VII: 11 };
  const QUALITY = {
    '': [0, 4, 7], 'm': [0, 3, 7], '7': [0, 4, 7, 10], 'M7': [0, 4, 7, 11], 'maj7': [0, 4, 7, 11],
    'm7': [0, 3, 7, 10], 'm7-5': [0, 3, 6, 10], 'm-5': [0, 3, 6], 'dim': [0, 3, 6, 9], 'dim7': [0, 3, 6, 9],
    'sus4': [0, 5, 7], 'aug': [0, 4, 8]
  };
  // lo〜hi：上の声部の音域／center：単独で鳴らすときに寄せる高さ／blo〜bhi・bcenter：ベース
  const RANGE = { lo: 53, hi: 70, center: 61, blo: 36, bhi: 51, bcenter: 41 };
  const W_CENTER = 0.35, W_BCENTER = 0.3;

  const stepOf = m => (((DEG[m[2]] + (m[1] === '#' ? 1 : m[1] === '♭' ? -1 : 0)) % 12) + 12) % 12;
  // 「IIm7」「IV/V」「♭VIM7」などを { root, bass, ivs }（root・bass はキーの1度からの半音）にする
  function parse(name) {
    const parts = String(name).trim().split('/');
    const m = NUMERAL.exec(parts[0]);
    if (!m || !(m[3] in QUALITY) || parts.length > 2) return null;
    const root = stepOf(m);
    let bass = root;
    if (parts.length === 2) {
      const b = NUMERAL.exec(parts[1]);
      if (!b || b[3]) return null;
      bass = stepOf(b);
    }
    return { root: root, bass: bass, ivs: QUALITY[m[3]] };
  }
  function upperPcs(ch, tonicPc) {
    const drop = ch.ivs.length >= 4 && ch.bass === ch.root;   // 4和音：ルートはベースに任せる
    return (drop ? ch.ivs.slice(1) : ch.ivs).map(iv => (tonicPc + ch.root + iv) % 12);
  }
  // 上の声部の候補：どれか1音を一番下に置き、残りをその上に密集で積む。音域に収まるものを全部
  function uppers(pcs, r) {
    const out = [];
    for (let n = r.lo; n <= r.hi; n++) {
      if (pcs.indexOf(n % 12) < 0) continue;
      const v = [n];
      pcs.forEach(p => { if (p !== n % 12) v.push(n + (((p - n) % 12) + 12) % 12); });
      v.sort((a, b) => a - b);
      if (v[v.length - 1] <= r.hi) out.push(v);
    }
    return out;
  }
  function basses(pc, r) {
    const out = [];
    for (let n = r.blo; n <= r.bhi; n++) if (n % 12 === pc) out.push(n);
    return out;
  }
  const mean = v => v.reduce((s, x) => s + x, 0) / v.length;

  // 並行5度・8度（Emocute準拠：出発も到達も同じ完全音程なら5、外声なら+3、到達だけなら2）
  function parallels(vf, vt) {
    let pen = 0;
    const n = Math.min(vf.length, vt.length);
    for (let i = 0; i < n; i++) for (let j = i + 1; j < n; j++) {
      const di = vt[i] - vf[i], dj = vt[j] - vf[j];
      if (di === 0 || dj === 0 || (di > 0) !== (dj > 0)) continue;
      const to = Math.abs(vt[i] - vt[j]) % 12;
      if (to !== 0 && to !== 7) continue;
      if (Math.abs(vf[i] - vf[j]) % 12 === to) { pen += 5; if (i === 0 && j === n - 1) pen += 3; }
      else pen += 2;
    }
    return pen;
  }
  // ガイドトーン＝3rdと7th（susの4th、6thは代理）。コードのキャラを決める音
  function guidePcs(ch, tonicPc) {
    let third = null, seventh = null, sus = null, sixth = null;
    ch.ivs.forEach(iv => {
      const m = iv % 12;
      if (m === 3 || m === 4) third = m;
      else if (m === 10 || m === 11) seventh = m;
      else if (m === 5 || m === 2) sus = m;
      else if (m === 9) sixth = m;
    });
    if (third === null) third = sus;
    if (seventh === null) seventh = sixth;
    return [third, seventh].filter(x => x !== null).map(iv => (tonicPc + ch.root + iv) % 12);
  }
  // ルートモーション別のガイドトーン連結ボーナス（4度・5度進行の3rd↔7th交換が最強）
  function gtWeights(from, to) {
    const iv = ((to.root - from.root) % 12 + 12) % 12;
    if (iv === 0) return null;
    if (iv === 5 || iv === 7) return { res: -6, com: -4 };
    if (iv === 6) return { res: -5, com: -3 };
    if (iv <= 2 || iv >= 10) return { res: -5, com: -3.5 };
    return { res: -4, com: -4 };
  }

  // 候補の並びから、点（single）とつなぎ（link）の合計が最小になる選び方を返す。loop なら最後→最初も数える
  function best(cands, single, link, loop) {
    const n = cands.length;
    let top = Infinity, path = null;
    const starts = loop && n > 1 ? cands[0].map((_, k) => k) : [-1];
    starts.forEach(k0 => {
      let row = cands[0].map((c, k) => (k0 < 0 || k === k0 ? { s: single(c, 0), p: [k] } : null));
      for (let i = 1; i < n; i++) {
        const prev = row;
        row = cands[i].map((c, k) => {
          let b = null;
          prev.forEach((q, j) => {
            if (!q) return;
            const s = q.s + link(cands[i - 1][j], c, i - 1, i);
            if (!b || s < b.s) b = { s: s, p: q.p };
          });
          return b && { s: b.s + single(c, i), p: b.p.concat(k) };
        });
      }
      row.forEach((q, k) => {
        if (!q) return;
        const s = q.s + (k0 >= 0 ? link(cands[n - 1][k], cands[0][k0], n - 1, 0) : 0);
        if (s < top) { top = s; path = q.p; }
      });
    });
    return path.map((k, i) => cands[i][k]);
  }
  // names：コード名の配列（1つなら単独で鳴らす和音）。tonicPc：キーの1度（0=C）
  // 返り値：[{ bass: midi, upper: [midi, midi, midi] }, ...]
  function voice(names, tonicPc, opt) {
    const r = Object.assign({}, RANGE, opt || {});
    const loop = r.loop !== false;
    const chords = names.map(nm => parse(nm) || parse('I'));
    const gts = chords.map(ch => guidePcs(ch, tonicPc));
    // 上の一番下はベースから5度以上離す（近いと 1-3-5 の積み上げになって濁る）。ベースのオクターブ上と半音でもぶつけない
    const fits = (v, b) => v[0] - b >= 7 && v.every(u => Math.abs(u - (b + 12)) !== 1);
    const ucand = chords.map(ch => uppers(upperPcs(ch, tonicPc), r));
    const keep = (list, ok) => { const k = list.filter(ok); return k.length ? k : list; };
    // ベースは、上の3声がきれいに収まる高さだけを候補にしてから選ぶ
    const bs = best(chords.map((ch, i) => keep(basses((tonicPc + ch.bass) % 12, r), b => ucand[i].some(v => fits(v, b)))),
      b => W_BCENTER * Math.abs(b - r.bcenter), (a, b) => Math.abs(a - b), loop);

    // 上の3声：真ん中への引力＋半音密集・ベースとの短9度のペナルティ
    const upSingle = (v, i) => {
      let c = W_CENTER * Math.abs(mean(v) - r.center);
      for (let k = 0; k + 1 < v.length; k++) if (v[k + 1] - v[k] === 1) c += 6;
      v.forEach(u => { if ((u - bs[i]) % 12 === 1) c += 8; });
      return c;
    };
    // 上の3声のつなぎ：Emocute chord_gen の VL コストの簡易版
    const upLink = (a, b, i, j) => {
      let c = 0;
      for (let k = 0; k < a.length && k < b.length; k++) {   // 共通音はボーナス、順次は安く、跳躍ほど高く
        const d = Math.abs(b[k] - a[k]);
        c += d === 0 ? -2.5 : d <= 2 ? d * 0.8 : d <= 4 ? d * 1.2 : d * 2.0;
      }
      const td = Math.abs(b[b.length - 1] - a[a.length - 1]);   // トップノートは旋律。保持と順次を優遇
      c += td === 0 ? -2 : td <= 2 ? -1 : td >= 5 ? td * 2 : 0;
      c += parallels([bs[i]].concat(a), [bs[j]].concat(b)) * 0.9;
      const bd = bs[j] - bs[i], sd = b[b.length - 1] - a[a.length - 1];   // 外声の反行
      if (bd !== 0 && sd !== 0 && (bd > 0) !== (sd > 0)) c -= 2;
      const w = gtWeights(chords[i], chords[j]);   // ガイドトーン連結
      if (w) gts[i].forEach(pc => {
        const from = a.find(n => n % 12 === pc);
        if (from === undefined) return;
        let dMin = Infinity;
        gts[j].forEach(pc2 => b.forEach(n2 => { if (n2 % 12 === pc2) dMin = Math.min(dMin, Math.abs(n2 - from)); }));
        if (dMin === 0) c += w.com;
        else if (dMin <= 2) c += w.res;
      });
      return c;
    };
    const ups = best(ucand.map((list, i) => keep(list, v => fits(v, bs[i]))), upSingle, upLink, loop);
    return chords.map((ch, i) => ({ bass: bs[i], upper: ups[i] }));
  }
  window.Voicing = { parse: parse, voice: voice };
})();
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
    // data-bars：このロールの小節数（既定4）。見本で「弱起の小節＋8小節」などにする
    const BARS = Math.max(1, +root.dataset.bars || 4), COLS = BARS * STEPS;
    // data-high：ロールの一番上の音（MIDI、既定72＝C5）。下はその2オクターブ下まで。見本のメロが高いときに使う
    const HIGH = +root.dataset.high || 72, LOW = HIGH - 24, ROWS = HIGH - LOW + 1;
    const progs = (root.dataset.progs || 'I-VIm-IV-V').split('|');
    let prog = progs[0].split('-');
    const open = new Set((root.dataset.degrees || '').split(',').filter(Boolean));
    const notes = new Set();                      // "midi,col"
    // data-notes：最初から置いておく音（見本のメロ）。data-nosave：保存しない（開き直すと見本に戻る）
    const nosave = root.dataset.nosave === '1';
    (root.dataset.notes || '').split(/\s+/).filter(Boolean).forEach(k => notes.add(k));
    // data-heads：同じ高さの音が続くとき、ここで音を切る（「ミミミー」を1本の長い音にしない）
    const heads = new Set((root.dataset.heads || '').split(/\s+/).filter(Boolean));
    const isHead = (m, c) => c > 0 && notes.has(m + ',' + (c - 1)) && heads.has(m + ',' + c);
    let tonicPc = (+root.dataset.key || 0) % 12, bpm = DEFAULT_BPM, dragging = false, drawMode = 'draw', warn = '';   // data-key：最初のキー（0=C）
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
    trLabel.appendChild(mk('span', '', ' メロも移調'));
    [progSel, sel, bpmSel, playBtn, clearBtn, trLabel].forEach(el => top.appendChild(el));

    const scroll = mk('div', 'roll-scroll');
    const grid = mk('div', 'roll-grid');
    const barsEl = mk('div', 'roll-bars');
    const gutEl = mk('div', 'roll-gutter');
    const cellsEl = mk('div', 'roll-cells');
    [mk('div', 'roll-corner'), barsEl, gutEl, cellsEl].forEach(el => grid.appendChild(el));
    if (BARS !== 4) {                                   // CSS は4小節前提なので、それ以外は幅と列数を上書き
      grid.style.minWidth = (BARS * 150) + 'px';
      barsEl.style.gridTemplateColumns = 'repeat(' + BARS + ',1fr)';
      cellsEl.style.gridTemplateColumns = 'repeat(' + COLS + ',1fr)';
    }
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
      o.value = v; o.textContent = v.indexOf('+') >= 0 ? v.split('-').map(b => b.replace(/\+/g, ' ')).join('｜') : v;   // 2コードの小節がある進行は「IV Vsus4｜I VIm7」と見せる
      progSel.appendChild(o);
    });
    const bars = [];
    for (let b = 0; b < BARS; b++) {
      const d = mk('div', 'roll-bar');
      barsEl.appendChild(d); bars.push(d);
    }
    // 進行の1要素＝1小節。「I+IV」と書くと小節の真ん中でコードが変わる（2拍ずつ）。
    // 「V*3+I」のように *拍数 を付けるとその長さ（Vが3拍、Iが残りの1拍）。「NC」はコードなし（弱起の小節など）
    // 返り値：[{ name（NCならnull）, start（小節の中のマス）, len（マス数） }]
    function barSegs(b) {
      const parts = String(prog[b % prog.length]).split('+').map(x => {
        const m = /^(.*?)(?:\*(\d+))?$/.exec(x);
        return { name: m[1] === 'NC' ? null : m[1], beats: m[2] ? +m[2] : 0 };
      });
      const fixed = parts.reduce((t, x) => t + x.beats, 0), free = parts.filter(x => !x.beats).length;
      const each = free ? Math.max(0, 4 - fixed) / free : 0;
      let pos = 0;
      return parts.map(x => {
        const len = Math.round((x.beats || each) * STEPS / 4);
        const seg = { name: x.name, start: pos, len: Math.min(len, STEPS - pos) };
        pos += seg.len;
        return seg;
      }).filter(x => x.len > 0);
    }
    const barChords = b => barSegs(b).filter(x => x.name).map(x => x.name);
    function updateBars() {
      for (let b = 0; b < BARS; b++) {
        const segs = barSegs(b), named = segs.some(x => x.name);
        bars[b].innerHTML = '';
        bars[b].classList.toggle('split', named && segs.length > 1);
        (named ? segs : [{ name: null, len: STEPS }]).forEach(x => {
          const sp = document.createElement('span');
          sp.textContent = x.name || '—';
          sp.style.flex = String(x.len);                // 拍の長さに合わせた幅
          bars[b].appendChild(sp);
        });
      }
      const starts = [];
      for (let b = 0; b < BARS; b++) barSegs(b).forEach(x => { if (x.start) starts.push(b * STEPS + x.start); });
      for (let r = 0; r < ROWS; r++) for (let c = 0; c < COLS; c++)
        cells[r][c].classList.toggle('halfstart', starts.indexOf(c) >= 0);
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
          el.classList.toggle('split', notes.has(m + ',' + c) && isHead(m, c));
        }
      }
      warnEl.textContent = warn;
      noteEl.textContent = '黄色い行＝今回使う音、濃い行＝スケール。横1マス＝8分音符、太線＝小節。';
    }

    // ---- 打ち込み ----
    function apply(el) {
      const m = midiOf(+el.dataset.r), key = m + ',' + el.dataset.c;
      if (drawMode === 'draw') {
        if (!notes.has(key)) { notes.add(key); el.classList.add('on'); tone(m, 0, 0.35, 0.2, null); }
      } else if (notes.has(key)) { notes.delete(key); heads.delete(key); el.classList.remove('on'); }
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
    // 小節数が4以外のロールは保存先を分ける（4小節の頃の進行・メロを8小節のロールに読ませない）
    const storeKey = 'roll:' + lesson + (BARS !== 4 ? '@' + BARS : '');
    function save() {
      if (nosave) return;
      try {
        localStorage.setItem(storeKey, JSON.stringify({ k: tonicPc, b: bpm, p: prog.join('-'), n: Array.from(notes), h: Array.from(heads) }));
      } catch (err) {}
    }
    function load() {
      if (nosave) return;
      try {
        const raw = localStorage.getItem(storeKey);
        if (!raw) return;
        const o = JSON.parse(raw);
        notes.clear();                               // 保存があれば data-notes より優先
        if (typeof o.k === 'number' && o.k >= 0 && o.k < 12) tonicPc = o.k;
        if (BPMS.indexOf(o.b) >= 0) bpm = o.b;
        if (progs.indexOf(o.p) >= 0) prog = o.p.split('-');
        (o.n || []).forEach(k => notes.add(k));
        heads.clear(); (o.h || []).forEach(k => heads.add(k));
      } catch (err) {}
    }

    // ---- 再生（止めるまでループ） ----
    // 伴奏のボイシングは、進行かキーが変わったときだけ組み直す。
    // Cキーで組んだものをメロと同じ量（keyOffset）だけ平行移動する。
    // キーごとに組み直すと転回形が変わり、「数字は同じで高さだけ変わる」が音で崩れる
    let voiced = null, voicedFor = '';
    function voicing() {
      const key = prog.join('-') + '@' + tonicPc;
      if (key !== voicedFor) {
        const o = keyOffset(tonicPc);
        const flat = [];
        for (let b = 0; b < BARS; b++) barChords(b).forEach(c => flat.push(c));
        const vs = window.Voicing.voice(flat, 0).map(v => ({ bass: v.bass + o, upper: v.upper.map(m => m + o) }));
        voiced = [];                                  // voiced[小節] ＝ その小節のコード [{ start, len, v }]
        let k = 0;
        for (let b = 0; b < BARS; b++) voiced.push(barSegs(b).filter(x => x.name).map(x => ({ start: x.start, len: x.len, v: vs[k++] })));
        voicedFor = key;
      }
      return voiced;
    }
    // 通し番号 n のステップ（8分音符1つ）を、時刻 at に予約する。
    // 予約の直前に notes を見るので、その時点で置いてある音がそのまま鳴る。
    function scheduleStep(n, at, out) {
      const c = audio(), rel = at - c.currentTime;
      const col = ((n % COLS) + COLS) % COLS;
      const inBar = col % STEPS;
      const seg = voicing()[Math.floor(col / STEPS)].find(x => x.start === inBar);
      if (seg) {                                      // コードの頭：コードとベース
        const v = seg.v;
        const dur = seg.len * stepSec() * 0.96;
        v.upper.forEach(m => tone(m, rel, dur, 0.075, out));
        tone(v.bass, rel, dur, 0.13, out);
        tone(v.bass + 12, rel, dur, 0.065, out);
      }
      for (let m = LOW; m <= HIGH; m++) {
        if (!notes.has(m + ',' + col)) continue;
        if (col > 0 && notes.has(m + ',' + (col - 1)) && !isHead(m, col)) continue;   // 伸ばしている途中なので鳴らし直さない
        let len = 1;
        while (col + len < COLS && notes.has(m + ',' + (col + len)) && !isHead(m, col + len)) len++;
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
      notes.clear(); heads.clear(); paint(); save();
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
          warn = '音域が広すぎてこのキーに収まらない。狭めるか「メロも移調」を外す。';
        } else {
          const moved = [];
          notes.forEach(k => { const q = k.split(','); moved.push((+q[0] + d) + ',' + q[1]); });
          const movedHeads = Array.from(heads, k => { const q = k.split(','); return (+q[0] + d) + ',' + q[1]; });
          heads.clear(); movedHeads.forEach(k => heads.add(k));
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

KEYBOARD_JS = r"""/* 鍵盤ウィジェット（composition-src/build.py が生成）
   原稿に書いた {{interval}} / {{scale}} の置き場（<div data-widget="…">）を中身で埋める。
   - interval（段階2）：選んだキーの1度からオク上までの13鍵に度数名。押すと1度→その音
   - scale（段階3）：選んだキーのメジャースケール7音に番号。押すとその音だけ
   どちらも、押すと同じ段階（section）の中の表の該当行に印を付ける */
(() => {
  'use strict';
  const LOW = 48, HIGH = 71;                       // どのキーでも1度〜オク上が収まる
  const WHITE = [0, 2, 4, 5, 7, 9, 11];
  const MAJOR = [0, 2, 4, 5, 7, 9, 11];
  const KEYS = ['C', 'D♭', 'D', 'E♭', 'E', 'F', 'G♭', 'G', 'A♭', 'A', 'B♭', 'B'];
  const SHORT = ['1度', '短2', '長2', '短3', '長3', '完全4', '増4', '完全5', '短6', '長6', '短7', '長7', '8度'];
  const FULL = ['1度', '短2度', '長2度', '短3度', '長3度', '完全4度', '増4度／減5度', '完全5度',
    '増5度／短6度', '長6度', '短7度', '長7度', '完全8度（オク上）'];

  let ac = null;
  function audio() {
    if (!ac) ac = new (window.AudioContext || window.webkitAudioContext)();
    if (ac.state === 'suspended') ac.resume();
    return ac;
  }
  function tone(midi, at, dur, vol, out) {
    const c = audio(), t0 = c.currentTime + at, f = 440 * Math.pow(2, (midi - 69) / 12);
    const g = c.createGain(), lp = c.createBiquadFilter();
    lp.type = 'lowpass'; lp.frequency.value = 2600;
    g.gain.setValueAtTime(0, t0);
    g.gain.linearRampToValueAtTime(vol, t0 + 0.015);
    g.gain.exponentialRampToValueAtTime(vol * 0.35, t0 + dur * 0.5);
    g.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
    [['sine', 1], ['triangle', 0.3]].forEach(pair => {
      const o = c.createOscillator(), og = c.createGain();
      o.type = pair[0]; o.frequency.value = f; og.gain.value = pair[1];
      o.connect(og).connect(g); o.start(t0); o.stop(t0 + dur + 0.05);
    });
    g.connect(lp).connect(out || c.destination);
  }

  // キーのプルダウン・鍵盤・表示欄を組み、同じ段階の表の行を探しておく
  // lo〜hi：鍵盤の範囲（既定は C3〜B4。段階4はベースまで見せるので C2 から）
  function build(root, lo = LOW, hi = HIGH) {
    const mk = (tag, cls) => { const el = document.createElement(tag); if (cls) el.className = cls; return el; };
    const top = mk('div', 'iv-top');
    const sel = mk('select', 'iv-sel');
    sel.setAttribute('aria-label', 'キー');
    for (let k = 0; k < 12; k++) {
      const o = document.createElement('option');
      o.value = String(k); o.textContent = KEYS[k] + ' キー';
      sel.appendChild(o);
    }
    top.appendChild(sel);
    const scroll = mk('div', 'iv-scroll');
    const kb = mk('div', 'iv-kb');
    const whites = mk('div', 'iv-whites');
    kb.appendChild(whites); scroll.appendChild(kb);
    const status = mk('p', 'iv-status');
    [top, scroll, status].forEach(el => root.appendChild(el));

    const keys = [];
    let nWhite = 0;
    for (let m = lo; m <= hi; m++) if (WHITE.indexOf(m % 12) >= 0) nWhite++;
    const w = 100 / nWhite;
    let wi = 0;
    for (let m = lo; m <= hi; m++) {
      const white = WHITE.indexOf(m % 12) >= 0;
      const el = mk('div', 'iv-key ' + (white ? 'w' : 'b'));
      el.dataset.midi = String(m);
      if (white) { whites.appendChild(el); wi++; }
      else {
        el.style.left = 'calc(' + (wi * w) + '% - ' + (w * 0.28) + '%)';
        el.style.width = (w * 0.56) + '%';
        kb.appendChild(el);
      }
      keys.push(el);
    }

    let rows = [];
    const sec = root.closest ? root.closest('section') : null;
    const secTable = sec && sec.querySelector ? sec.querySelector('table') : null;
    if (secTable) rows = secTable.tBodies && secTable.tBodies[0] ? secTable.tBodies[0].rows : [];
    else for (let el = root.nextElementSibling; el; el = el.nextElementSibling) {
      if (el.tagName === 'H2') break;
      const t = el.tagName === 'TABLE' ? el : (el.querySelector ? el.querySelector('table') : null);
      if (t) { rows = t.tBodies && t.tBodies[0] ? t.tBodies[0].rows : []; break; }
    }
    const state = { tonicPc: 0 };
    const hl = i => { for (let r = 0; r < rows.length; r++) rows[r].classList.toggle('iv-hl', r === i); };
    const flash = el => { el.classList.add('hit'); setTimeout(() => el.classList.remove('hit'), 200); };
    return { top, sel, scroll, kb, keys, status, rows, state, hl, flash, tonic: () => LOW + state.tonicPc };
  }

  // 段階2：インターバル
  function setupInterval(root) {
    const w = build(root);
    function paint() {
      w.keys.forEach(el => {
        const iv = +el.dataset.midi - w.tonic();
        const inWin = iv >= 0 && iv <= 12;
        el.textContent = inWin ? SHORT[iv] : '';
        el.classList.toggle('off', !inWin);
        el.classList.toggle('root', iv === 0 || iv === 12);
      });
    }
    function mark(iv) {
      w.hl(iv);
      w.status.textContent = iv === null ? '' : (iv === 0 ? '1度' : FULL[iv] + '（半音' + iv + 'つ）');
    }
    w.kb.addEventListener('pointerdown', e => {
      const el = e.target.closest('.iv-key');
      if (!el) return;
      const m = +el.dataset.midi, iv = m - w.tonic();
      if (iv < 0 || iv > 12) return;
      e.preventDefault();
      tone(w.tonic(), 0, 0.55, 0.2);
      if (iv > 0) tone(m, 0.45, 0.75, 0.22);
      w.flash(el);
      mark(iv);
    });
    w.sel.addEventListener('change', () => { w.state.tonicPc = +w.sel.value; paint(); mark(null); });
    paint();
  }

  // 段階3：メジャースケール
  function setupScale(root) {
    const w = build(root);
    const btn = document.createElement('button');
    btn.className = 'iv-play'; btn.textContent = 'スケールを鳴らす';
    w.top.appendChild(btn);
    const degOf = m => {                      // 1度からの距離がスケールの何番目か。外なら -1
      const iv = m - w.tonic();
      if (iv < 0 || iv > 12) return -1;
      return MAJOR.indexOf(iv % 12);
    };
    function paint() {
      w.keys.forEach(el => {
        const m = +el.dataset.midi, iv = m - w.tonic(), d = degOf(m);
        const inWin = iv >= 0 && iv <= 12;
        el.textContent = d >= 0 ? String(d + 1) : '';
        el.classList.toggle('off', !inWin);
        el.classList.toggle('out', inWin && d < 0);
        el.classList.toggle('root', d === 0);
      });
    }
    function mark(d) {
      w.hl(d);
      if (d === null || !w.rows[d]) { w.status.textContent = ''; return; }
      const cells = w.rows[d].cells || [];
      const parts = [];
      for (let i = 0; i < cells.length; i++) if (cells[i].textContent.trim()) parts.push(cells[i].textContent.trim());
      w.status.textContent = parts.join('　');
    }
    // 押した音だけを鳴らす（主和音を重ねると、押した音が和音に混ざって別の和音に聞こえる）
    w.kb.addEventListener('pointerdown', e => {
      const el = e.target.closest('.iv-key');
      if (!el) return;
      const m = +el.dataset.midi, d = degOf(m);
      if (d < 0) return;
      e.preventDefault();
      tone(m, 0, 0.9, 0.22);
      w.flash(el);
      mark(d);
    });
    btn.addEventListener('click', () => {
      const t = w.tonic();
      [0, 2, 4, 5, 7, 9, 11, 12].forEach((iv, i) => {
        tone(t + iv, i * 0.34, 0.5, 0.22);
        const el = w.keys[t + iv - LOW];
        setTimeout(() => w.flash(el), i * 340);
      });
    });
    w.sel.addEventListener('change', () => { w.state.tonicPc = +w.sel.value; paint(); mark(null); });
    paint();
  }

  // 和音は同時に1つだけ。次を押したら、前の和音はすぐ（30ms で）消す
  let chordBus = null;
  function playChord(name, tonicPc, at, dur) {
    const c = audio();
    if (chordBus) {
      const old = chordBus;
      try {
        old.gain.cancelScheduledValues(c.currentTime);
        old.gain.setValueAtTime(old.gain.value, c.currentTime);
        old.gain.linearRampToValueAtTime(0, c.currentTime + 0.03);
      } catch (err) {}
      setTimeout(() => { try { old.disconnect(); } catch (err) {} }, 80);
    }
    const bus = c.createGain();
    bus.gain.value = 1;
    bus.connect(c.destination);
    chordBus = bus;
    const v = window.Voicing.voice([name], tonicPc)[0];
    tone(v.bass, at, dur, 0.13, bus);
    tone(v.bass + 12, at, dur, 0.065, bus);
    v.upper.forEach(m => tone(m, at, dur, 0.08, bus));
  }
  // 段階4：ダイアトニックコード（4和音）。キーを選ぶとボタンの下に実音のコード名。押すと鳴って、鍵盤のコードトーンが光る。
  // 光った鍵には「キー度数/コード度数」を併記（例：6/3）。コード度数は長短を問わず R・3・5・7（curriculum の表記ルールと同じ）
  const DIATONIC = [['IM7', 'M7'], ['IIm7', 'm7'], ['IIIm7', 'm7'], ['IVM7', 'M7'], ['V7', '7'], ['VIm7', 'm7'], ['VIIm7-5', 'm7-5']];
  const LETTERS = 'CDEFGAB', NAT = [0, 2, 4, 5, 7, 9, 11];
  // キーの i 番目（0＝1度）の音名。キー名の文字から順に数えるので、E♭キーの4は A♭、Bキーの7は A#
  function noteName(k, i) {
    const li = (LETTERS.indexOf(KEYS[k][0]) + i) % 7;
    const d = (((k + MAJOR[i] - NAT[li]) % 12) + 18) % 12 - 6;
    return LETTERS[li] + (d > 0 ? '#'.repeat(d) : '♭'.repeat(-d));
  }
  function setupDiatonic(root) {
    const w = build(root, 36, HIGH);
    w.kb.classList.add('wide');
    const box = document.createElement('div');
    box.className = 'dg-chords';
    root.insertBefore(box, w.scroll);
    let cur = null;                                   // 押されているコード（0〜6）
    const chips = DIATONIC.map((dc, i) => {
      const b = document.createElement('button');
      b.className = 'dg-chip';
      const num = document.createElement('span'); num.className = 'dg-num'; num.textContent = dc[0];
      const name = document.createElement('span'); name.className = 'dg-name';
      b.appendChild(num); b.appendChild(name);
      b.addEventListener('click', () => {
        cur = i;
        playChord(dc[0], w.state.tonicPc, 0, 1.4);
        light();
      });
      box.appendChild(b);
      return { b, name };
    });
    function paint() {
      const k = w.state.tonicPc;
      w.keys.forEach(el => {
        const d = MAJOR.indexOf((((+el.dataset.midi - k) % 12) + 12) % 12);
        el.textContent = d >= 0 ? String(d + 1) : '';
        el.classList.toggle('out', d < 0);
      });
      chips.forEach((c, i) => { c.name.textContent = noteName(k, i) + DIATONIC[i][1]; });
    }
    // 光らせるのは、実際に鳴らす音そのもの（playChord と同じボイシング：ベース・そのオクターブ上・上の3声）
    function light() {
      const k = w.state.tonicPc;
      const lit = {};                                 // midi → コード度数（R・3・5・7）
      let rootPc = -1;
      if (cur !== null) {
        const v = window.Voicing.voice([DIATONIC[cur][0]], k)[0];
        rootPc = (k + MAJOR[cur]) % 12;
        const cdeg = m => {
          const iv = (((m - rootPc) % 12) + 12) % 12;
          return iv === 0 ? 'R' : iv <= 4 ? '3' : iv <= 7 ? '5' : '7';
        };
        [v.bass, v.bass + 12].concat(v.upper).forEach(m => { lit[m] = cdeg(m); });
      }
      w.keys.forEach(el => {
        const m = +el.dataset.midi;
        el.classList.toggle('lit', m in lit);
        el.classList.toggle('croot', m in lit && m % 12 === rootPc);
        // 鳴っている鍵はキー度数にコード度数を併記する（キー度数/コード度数）
        const d = MAJOR.indexOf((((m - k) % 12) + 12) % 12);
        el.textContent = d >= 0 ? (m in lit ? (d + 1) + '/' + lit[m] : String(d + 1)) : '';
      });
      chips.forEach((c, i) => c.b.classList.toggle('on', i === cur));
      if (cur === null) { w.status.textContent = ''; return; }
      const idx = [0, 2, 4, 6].map(s => (cur + s) % 7);
      w.status.textContent = chips[cur].name.textContent + '＝' + idx.map(i => noteName(k, i)).join(' ') +
        '（' + idx.map(i => i + 1).join('・') + '）';
    }
    w.sel.addEventListener('change', () => { w.state.tonicPc = +w.sel.value; paint(); light(); });
    paint();
  }

  // コツ：覚えるべきコード。直後の表（tier | コード）を読んで、押すとそのコードだけが鳴るボタンに組み直す
  // セルの書き方：「I　IIm　IIIm」＝空白区切り。「／」でまとまりを分ける。「引っ張る：VI7」＝ラベル：コード
  // data-groups="I IIIm VIm|IIm IV|V" があれば、そのグループごとに色を分ける
  function setupChords(root) {
    let box = null;
    for (let el = root.nextElementSibling; el; el = el.nextElementSibling) {
      const t = el.tagName === 'TABLE' ? el : (el.querySelector ? el.querySelector('table') : null);
      if (t) { box = { wrap: el, table: t }; break; }
    }
    if (!box) return;
    const rows = box.table.tBodies && box.table.tBodies[0] ? box.table.tBodies[0].rows : [];
    const groupOf = {};
    (root.dataset.groups || '').split('|').forEach((g, gi) => g.split(/[\s　]+/).filter(Boolean).forEach(n => { groupOf[n] = gi + 1; }));
    const mk = (tag, cls, text) => { const el = document.createElement(tag); if (cls) el.className = cls; if (text !== undefined) el.textContent = text; return el; };
    let tonicPc = 0;
    const top = mk('div', 'cw-top');
    const sel = mk('select', 'cw-sel');
    sel.setAttribute('aria-label', 'キー');
    for (let k = 0; k < 12; k++) { const o = mk('option', '', KEYS[k] + ' キー'); o.value = String(k); sel.appendChild(o); }
    sel.addEventListener('change', () => { tonicPc = +sel.value; });
    top.appendChild(sel);
    const grid = mk('div', 'cw-grid');
    for (let r = 0; r < rows.length; r++) {
      const cells = rows[r].cells;
      const tier = cells[0].textContent.trim(), level = (tier.match(/\d+/) || ['3'])[0];
      grid.appendChild(mk('div', 'cw-tier', tier));
      const groupsEl = mk('div', 'cw-groups');
      cells[1].textContent.split('／').forEach(g => {
        let text = g.trim(), label = '';
        const lm = /^([^：]+)：(.*)$/.exec(text);
        if (lm) { label = lm[1].trim(); text = lm[2]; }
        const groupEl = mk('div', 'cw-group' + (label ? ' labeled' : ''));
        if (label) groupEl.appendChild(mk('span', 'cw-glabel', label));
        text.split(/[\s　]+/).filter(Boolean).forEach(tok => {
          const name = tok.split('→')[0], ch = window.Voicing.parse(name);
          // 色分けは tier1 のダイアトニックだけ。IM7→I、IIm7→IIm、VIIm7-5→VIIm-5 のように7thを外して照らす
          const triad = name.replace(/m7-5$|M7$|7$/, s => (s === 'm7-5' ? 'm-5' : ''));
          const g = level === '1' && name.indexOf('sus') < 0 ? groupOf[triad] : 0;
          const chip = mk('button', 'cw-chip t' + level + (g ? ' g' + g : ''), name);
          chip.addEventListener('click', () => {
            if (!ch) return;
            playChord(name, tonicPc, 0, 1.1);
            chip.classList.add('hit');
            setTimeout(() => chip.classList.remove('hit'), 500);
          });
          groupEl.appendChild(chip);
        });
        groupsEl.appendChild(groupEl);
      });
      grid.appendChild(groupsEl);
    }
    root.appendChild(top);
    root.appendChild(grid);
    box.wrap.style.display = 'none';            // 元の表はスクリプトが動かないとき用に残し、隠す
  }

  // 簡易コード進行ジェネレータ（ドリルの授業の流れ用）。4小節をダイアトニック7つから選んでループし、
  // 「1度を鳴らす」で中心を確かめる。Phase 1〜3 はダイアトニック外を出さない方針なので選択肢も7つだけ
  function setupProgmini(root) {
    const mk = (tag, cls, text) => { const el = document.createElement(tag); if (cls) el.className = cls; if (text !== undefined) el.textContent = text; return el; };
    const PM = ['IM7', 'IIm7', 'IIIm7', 'IVM7', 'V7', 'VIm7', 'VIIm7-5'];
    const init = (root.dataset.prog || 'IVM7-IIIm7-IIm7-IM7').split('-');
    const row = mk('div', 'pm-row');
    const sels = init.map(v => {
      const s = mk('select', 'pm-chord');
      PM.forEach(c => { const o = mk('option', '', c); o.value = c; s.appendChild(o); });
      s.value = PM.indexOf(v) >= 0 ? v : PM[0];
      row.appendChild(s);
      return s;
    });
    const top = mk('div', 'pm-top');
    const keySel = mk('select', 'pm-key');
    keySel.setAttribute('aria-label', 'キー');
    for (let k = 0; k < 12; k++) { const o = mk('option', '', KEYS[k] + ' キー'); o.value = String(k); keySel.appendChild(o); }
    const playBtn = mk('button', 'pm-play', '再生');
    const oneBtn = mk('button', 'pm-one', '1度を鳴らす');
    [keySel, playBtn, oneBtn].forEach(el => top.appendChild(el));
    root.appendChild(row); root.appendChild(top);
    let tonic = 0, bus = null, timer = null, hl = null;
    const BAR = 2.4, AHEAD = 2.5;                 // 1小節＝100BPMの4拍
    function stop() {
      if (timer) { clearTimeout(timer); timer = null; }
      if (hl) { clearInterval(hl); hl = null; }
      sels.forEach(s => s.classList.remove('now'));
      if (bus) {
        const b = bus; bus = null;
        try { b.gain.cancelScheduledValues(ac.currentTime); b.gain.setTargetAtTime(0, ac.currentTime, 0.02); } catch (e) {}
        setTimeout(() => { try { b.disconnect(); } catch (e) {} }, 400);
      }
      playBtn.textContent = '再生';
    }
    function start() {
      stop();
      const c = audio(), b = c.createGain();
      b.gain.value = 1; b.connect(c.destination); bus = b;
      let next = c.currentTime + 0.08;
      const anchor = next;
      (function tick() {
        if (bus !== b) return;
        while (next < c.currentTime + AHEAD) {
          const v = window.Voicing.voice(sels.map(s => s.value), tonic);
          v.forEach((x, i) => {
            const at = next - c.currentTime + i * BAR, dur = BAR * 0.95;
            tone(x.bass, at, dur, 0.13, b); tone(x.bass + 12, at, dur, 0.065, b);
            x.upper.forEach(m => tone(m, at, dur, 0.08, b));
          });
          next += BAR * sels.length;
        }
        timer = setTimeout(tick, 500);
      })();
      hl = setInterval(() => {
        const t = c.currentTime - anchor, cur = t < 0 ? -1 : Math.floor(t / BAR) % sels.length;
        sels.forEach((s, i) => s.classList.toggle('now', i === cur));
      }, 60);
      playBtn.textContent = '止める';
    }
    playBtn.addEventListener('click', () => (bus ? stop() : start()));
    // 変えたら頭から鳴らし直す（1周ぶん先に予約しているため）
    sels.forEach(s => s.addEventListener('change', () => { if (bus) start(); }));
    keySel.addEventListener('change', () => { tonic = +keySel.value; if (bus) start(); });
    oneBtn.addEventListener('click', () => tone(60 + ((tonic + 6) % 12) - 6, 0, 1.4, 0.24));
  }

  // 進行の再生（中級編の {{play}}）。data-progs="ラベル=IIm7 V7 IM7|IIm7 ♭II7 IM7"
  // 空白区切りの1要素＝1小節、「A+B」は小節の真ん中で変わる。行ごとに再生ボタンと、鳴る音のピアノロール。
  // キーは上のプルダウンで全行共通。ロールは voicing.js が組んだ音そのもの（上の3声とベース）を描く
  function setupPlay(root) {
    const mk = (tag, cls, text) => { const el = document.createElement(tag); if (cls) el.className = cls; if (text !== undefined) el.textContent = text; return el; };
    const NS = 'http://www.w3.org/2000/svg';
    const sv = (tag, attrs, cls) => { const el = document.createElementNS(NS, tag); for (const k in attrs) el.setAttribute(k, attrs[k]); if (cls) el.setAttribute('class', cls); return el; };
    const BAR = 2.4;                                  // 1小節＝100BPMの4拍
    const RH = 7, BW = 60, GW = 16, GAP = 5;          // ロールの行の高さ・1小節の幅・度数の欄・上の声部とベースの間
    const top = mk('div', 'pl-top');
    const keySel = mk('select', 'pl-key');
    keySel.setAttribute('aria-label', 'キー');
    for (let k = 0; k < 12; k++) { const o = mk('option', '', KEYS[k] + ' キー'); o.value = String(k); keySel.appendChild(o); }
    top.appendChild(keySel);
    root.appendChild(top);
    let tonic = 0, bus = null, timers = [], cur = null;
    const rows = [];
    // 今のキーでボイシングした音（小節ごとに [{ bass, upper }]）。キーが変わったときだけ組み直す
    function voiced(r) {
      if (r.vKey === tonic) return r.v;
      const flat = [];
      r.bars.forEach(x => x.split('+').forEach(n => flat.push(n)));
      const vs = window.Voicing.voice(flat, tonic, { loop: false });
      let k = 0;
      r.v = r.bars.map(x => x.split('+').map(() => vs[k++]));
      r.vKey = tonic;
      return r.v;
    }
    function mark(r, i) {
      r.cells.forEach((el, q) => el.classList.toggle('now', q === i));
      (r.hl || []).forEach((el, q) => el.classList.toggle('now', q === i));
    }
    // ピアノロール：行は半音。上の3声の帯とベースの帯に分け、キーのスケールの行に度数を振る
    function drawRoll(r) {
      const v = voiced(r), ups = [], bs = [];
      v.forEach(bar => bar.forEach(x => { x.upper.forEach(m => ups.push(m)); bs.push(x.bass); }));
      const band = (lo, hi) => { const out = []; for (let m = hi; m >= lo; m--) out.push(m); return out; };
      const hiBand = band(Math.min.apply(null, ups) - 1, Math.max.apply(null, ups) + 1);
      const loBand = band(Math.min.apply(null, bs) - 1, Math.max.apply(null, bs) + 1);
      const n = r.bars.length, W = GW + n * BW, H = (hiBand.length + loBand.length) * RH + GAP;
      const svg = sv('svg', { viewBox: '0 0 ' + W + ' ' + H, role: 'img', 'aria-label': 'ピアノロール' }, 'pl-roll');
      svg.style.maxWidth = Math.round(W * 1.4) + 'px';
      const y = {};
      hiBand.forEach((m, i) => { y[m] = i * RH; });
      loBand.forEach((m, i) => { y[m] = hiBand.length * RH + GAP + i * RH; });
      [hiBand, loBand].forEach(list => list.forEach(m => {
        const d = MAJOR.indexOf((((m - tonic) % 12) + 12) % 12);
        svg.appendChild(sv('rect', { x: GW, y: y[m], width: n * BW, height: RH }, 'cr-row' + (d >= 0 ? ' scale' : '') + (d === 0 ? ' tonic' : '')));
        if (d >= 0) {
          const t = sv('text', { x: GW - 3, y: y[m] + RH - 1.2, 'text-anchor': 'end' }, 'cr-deg' + (d === 0 ? ' tonic' : ''));
          t.textContent = String(d + 1);
          svg.appendChild(t);
        }
      }));
      r.hl = r.bars.map((x, i) => { const el = sv('rect', { x: GW + i * BW, y: 0, width: BW, height: H }, 'cr-hl'); svg.appendChild(el); return el; });
      for (let i = 0; i <= n; i++) svg.appendChild(sv('line', { x1: GW + i * BW, x2: GW + i * BW, y1: 0, y2: H }, 'cr-bar'));
      svg.appendChild(sv('line', { x1: GW, x2: W, y1: hiBand.length * RH + GAP / 2, y2: hiBand.length * RH + GAP / 2 }, 'cr-sep'));
      v.forEach((bar, i) => bar.forEach((x, j) => {
        const w = BW / bar.length, x0 = GW + i * BW + j * w;
        if (j > 0) svg.appendChild(sv('line', { x1: x0, x2: x0, y1: 0, y2: H }, 'cr-half'));
        x.upper.forEach(m => svg.appendChild(sv('rect', { x: x0 + 1.5, y: y[m] + 0.8, width: w - 3, height: RH - 1.6, rx: 1 }, 'cr-note')));
        svg.appendChild(sv('rect', { x: x0 + 1.5, y: y[x.bass] + 0.8, width: w - 3, height: RH - 1.6, rx: 1 }, 'cr-bass'));
      }));
      svg.addEventListener('click', () => (cur === r ? stop() : start(r)));
      if (r.roll) r.roll.replaceWith(svg); else r.body.appendChild(svg);
      r.roll = svg;
      if (cur === r) mark(r, -1);
    }
    function stop() {
      timers.forEach(t => clearTimeout(t)); timers = [];
      if (bus) {
        const b = bus; bus = null;
        try { b.gain.cancelScheduledValues(ac.currentTime); b.gain.setTargetAtTime(0, ac.currentTime, 0.02); } catch (e) {}
        setTimeout(() => { try { b.disconnect(); } catch (e) {} }, 400);
      }
      if (cur) {
        cur.btn.textContent = '再生'; cur.btn.classList.add('pri');
        mark(cur, -1);
        cur = null;
      }
    }
    function start(r) {
      stop();
      const c = audio(), b = c.createGain();
      b.gain.value = 1; b.connect(c.destination); bus = b; cur = r;
      voiced(r).forEach((bar, i) => {
        bar.forEach((x, j) => {
          const at = 0.08 + i * BAR + j * BAR / bar.length, dur = BAR / bar.length * 0.95;
          tone(x.bass, at, dur, 0.13, b); tone(x.bass + 12, at, dur, 0.065, b);
          x.upper.forEach(m => tone(m, at, dur, 0.08, b));
        });
        timers.push(setTimeout(() => mark(r, i), (0.08 + i * BAR) * 1000));
      });
      timers.push(setTimeout(stop, (0.08 + r.bars.length * BAR + 0.2) * 1000));
      r.btn.textContent = '止める'; r.btn.classList.remove('pri');
    }
    (root.dataset.progs || '').split('|').forEach(part => {
      const eq = part.lastIndexOf('=');
      const label = eq >= 0 ? part.slice(0, eq).trim() : '';
      const bars = (eq >= 0 ? part.slice(eq + 1) : part).trim().split(/\s+/).filter(Boolean);
      if (!bars.length) return;
      const row = mk('div', 'pl-row');
      const btn = mk('button', 'pl-play pri', '再生');
      const body = mk('div', 'pl-body');
      if (label) body.appendChild(mk('div', 'pl-label', label));
      const list = mk('div', 'pl-bars');
      const cells = bars.map(x => { const el = mk('span', 'pl-bar', x.replace(/\+/g, ' ')); list.appendChild(el); return el; });
      body.appendChild(list);
      row.appendChild(btn); row.appendChild(body);
      root.appendChild(row);
      const r = { bars: bars, cells: cells, btn: btn, body: body };
      btn.addEventListener('click', () => (cur === r ? stop() : start(r)));
      rows.push(r);
    });
    rows.forEach(drawRoll);
    keySel.addEventListener('change', () => {
      tonic = +keySel.value;
      const playing = cur;
      rows.forEach(drawRoll);
      if (playing) start(playing);
    });
  }

  const els = document.querySelectorAll('[data-widget]');
  for (let i = 0; i < els.length; i++) {
    const kind = els[i].dataset.widget;
    if (kind === 'interval') setupInterval(els[i]);
    else if (kind === 'scale') setupScale(els[i]);
    else if (kind === 'chords') setupChords(els[i]);
    else if (kind === 'diatonic') setupDiatonic(els[i]);
    else if (kind === 'progmini') setupProgmini(els[i]);
    else if (kind === 'play') setupPlay(els[i]);
  }
})();
"""

# ブラウザに古い JS/CSS が残らないよう、読み込み先に中身のハッシュを付ける（assets/roll.js?v=abcd1234）
def asset(name):
    import hashlib
    src = {"base.css": CSS, "voicing.js": VOICING_JS, "roll.js": ROLL_JS, "keyboard.js": KEYBOARD_JS}[name]
    return f"assets/{name}?v={hashlib.md5(src.encode('utf-8')).hexdigest()[:8]}"

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
<link rel="stylesheet" href="{up}{asset("base.css")}">{css_extra}
</head>
<body>
{body}
</body>
</html>
"""


FOOT = (
    '<p class="foot">京都精華大学 メディア表現学部「応用実習1,2：作曲」（火曜・全14回・90分×2コマ）<br>'
    '担当：有村崚（<a href="https://intheblueshirt.com/">in the blue shirt</a>）</p>'
)


def nav(depth, current=""):
    up = "../" * depth
    links = [
        (f"{up}", "← 授業トップ"),
        (f"{up}roadmap/", "理論ロードマップ"),
        (f"{up}history/", "理論の歴史"),
        (f"{up}tips/", "ポップスのコツ"),
        (f"{up}chukyu/", "理論 中級編"),
        (f"{up}toranomaki/", "虎の巻"),
        (f"{up}ear/", "1度当て練習"),
        (f"{up}prog/", "コード進行ジェネレータ"),
    ]
    out = []
    for href, label in links:
        if label.endswith(current) and current:
            continue
        out.append(f'<a href="{href}">{label}</a>')
    return f'<p class="topnav">{"".join(out)}</p>'


# ------------------------------------------------------------------- ページ生成

def columns(blocks_html):
    """<h3> ごとのまとまりを横に並べる（PCの横幅を使う）。前置きは上に、末尾の注記は下に出す。"""
    parts = re.split(r"(?=<h3>)", blocks_html)
    pre, groups = parts[0], [g for g in parts[1:] if g.strip()]
    if len(groups) < 2:
        return blocks_html
    tail = ""
    m = re.match(r"(.*?(?:</div>|</ul>))\s*((?:<p>.*?</p>\s*)+)$", groups[-1], re.S)
    if m:
        groups[-1], tail = m.group(1), m.group(2)
    cols = "".join(f"<div>{g}</div>" for g in groups)
    return f'{pre}<div class="cols" style="--n:{len(groups)}">{cols}</div>{tail}'


def build_index(d):
    parts = [
        '<div class="wrap">',
        '<p class="eyebrow">京都精華大学 メディア表現学部</p>',
        "<h1>応用実習1,2：作曲</h1>",
        '<p class="meta">火曜・全14回・90分×2コマ｜担当：有村崚（in the blue shirt）</p>',
        f'<p class="lead">{inline(d["lead"])}</p>',
        (f'<h2 id="goals">到達目標</h2><div class="goals">{d["goals_html"]}</div>' if d.get("goals_html") else ""),
        '<div class="chips">'
        '<a href="#lessons">全14回</a>'
        '<a href="roadmap/">理論ロードマップ</a>'
        '<a href="history/">理論の歴史</a>'
        '<a href="tips/">ポップスのコツ</a>'
        '<a href="chukyu/">理論 中級編</a>'
        '<a href="toranomaki/">虎の巻</a>'
        '<a href="ear/">1度当て練習</a>'
        '<a href="prog/">コード進行ジェネレータ</a>'
        + ('<a href="#flow">1回の流れ</a>' if d["flow_title"] else "")
        + '<a href="#eval">評価</a>'
        "</div>",
        '<h2 id="lessons">全14回</h2>',
        f'<p>{inline(d["lessons_note"])}</p>' if d["lessons_note"] else "",
    ]
    # PCでは Phase を横に5列並べ、各 Phase の回を縦に積む（全14回を1画面で見渡せる）
    parts.append(f'<div class="phases" style="--n:{len(d["phases"])}">')
    for phase in d["phases"]:
        parts.append('<div class="phase">')
        # 末尾の「（ドリル3〜4）」は途中で折り返さない
        head = re.sub(r"（[^（）]*）$", lambda m: f'<span class="nw">{m.group(0)}</span>', inline(phase["title"]))
        parts.append(f'<h3>{head}</h3>')
        cards = []
        for no in phase["nos"]:
            ls = d["lessons"][no]
            cards.append(
                f'<a class="card" href="{no:02d}/">'
                f'<div class="no">ドリル{no}'
                + (f'<span class="sess">{session_label(d, ls)}</span>' if ls.get("session") else "")
                + '</div>'
                f'<div class="th">{inline(ls["title"])}</div>'
                f'{degree_chips(ls["deg"], ls["flat"])}'
                + (
                    f'<div class="sub">伴奏：{inline(ls["prog"])}</div>'
                    if ls["prog"].strip() not in ("", "—", "-")
                    else ""
                )
                + (f'<div class="sub new">新コード：{inline(new_chords(ls))}</div>' if new_chords(ls) else "")
                + "</a>"
            )
        parts.append(f'<div class="cards">{"".join(cards)}</div>')
        parts.append("</div>")  # phase
    parts.append("</div>")  # phases
    parts.append(session_table(d))
    if d["flow_title"]:
        parts += [f'<h2 id="flow">{inline(d["flow_title"])}</h2>', columns(d["flow_html"])]
    parts += [
        "<h2>表記ルール</h2>" if "到達目標" not in d["about_html"] else "<h2>ゴールと表記ルール</h2>",
        columns(d["about_html"]),
        f'<h2 id="eval">{inline(d["eval_title"])}</h2>',
        f'<div class="eval">{columns(d["eval_html"])}</div>',
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


NOTE_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def demo_notes(spec):
    """「C4:0-1 B3:2-3 D4:18」→（ロールの "midi,col" の並び, 各音の頭）。マスは8分音符・0始まり、範囲は両端を含む。
    頭を渡すので、同じ高さの音を続けて書いても（E4:8-9 E4:10-11）別々の音として鳴る"""
    out, heads = [], []
    for tok in spec.split():
        m = re.fullmatch(r"([A-G])([#b♭]?)(-?\d):(\d+)(?:-(\d+))?", tok)
        if not m:
            raise SystemExit(f"roll-demo の書き方が変：{tok}（例 C4:0-1）")
        pc = NOTE_PC[m.group(1)] + (1 if m.group(2) == "#" else -1 if m.group(2) else 0)
        midi = (int(m.group(3)) + 1) * 12 + pc
        a = int(m.group(4))
        b = int(m.group(5)) if m.group(5) else a
        out += [f"{midi},{c}" for c in range(a, b + 1)]
        heads.append(f"{midi},{a}")
    return " ".join(out), " ".join(heads)


def demo_roll(spec, lesson, default_prog):
    """{{roll-demo …}} の中身から見本ロールの <div> を作る。
    「prog=I-I-I-V7」があればその伴奏、無ければ default_prog。bars= で小節数、key= で最初のキー（0=C）"""
    toks = spec.split()
    demo_prog = next((t[5:] for t in toks if t.startswith("prog=")), default_prog)
    demo_bars = next((t[5:] for t in toks if t.startswith("bars=")), "")
    demo_key = next((t[4:] for t in toks if t.startswith("key=")), "")
    demo_high = next((t[5:] for t in toks if t.startswith("high=")), "")
    notes = " ".join(t for t in toks if not re.match(r"^(prog|bars|key|high)=", t))
    cells, heads = demo_notes(notes)
    return (
        f'<div class="roll" data-lesson="{lesson}" data-progs="{html.escape(demo_prog)}" '
        + (f'data-bars="{int(demo_bars)}" ' if demo_bars else "")
        + (f'data-key="{int(demo_key)}" ' if demo_key else "")
        + (f'data-high="{int(demo_high)}" ' if demo_high else "")
        + f'data-degrees="" data-nosave="1" data-notes="{cells}" data-heads="{heads}"></div>'
    )


def render_flow(d, no, flow, practice_roll, chords):
    """授業の流れ：##### ごとに番号付きの大きい節にする。
    {{roll}}＝練習用ロール、{{roll-demo …}}＝見本のロール、
    {{from-roadmap 段階N}}＝ロードマップのその段階の鍵盤と表（原稿はロードマップ側の1か所だけ）。
    {{progmini}} など他の {{…}} は render_blocks が鍵盤ウィジェットの置き場にする"""
    out = ['<div class="flow">']
    for title, lines in flow:
        out.append(f'<section class="step"><h2>{inline(title)}</h2>')
        buf = []
        for ln in lines + ["{{__end__}}"]:
            s = ln.strip()
            m = re.fullmatch(r"\{\{(roll|roll-demo\s+(.+)|from-roadmap\s+(.+)|__end__)\}\}", s)
            if not m:
                buf.append(ln)
                continue
            if buf:
                out.append(render_blocks(buf))
                buf = []
            if m.group(1) == "roll":
                out.append(practice_roll)
            elif m.group(2):
                # 「prog=I-I-I-V7」があればその伴奏、無ければそのドリルの伴奏
                out.append(demo_roll(m.group(2), f"{no:02d}-demo", chords))
            elif m.group(3):
                st = next((x for x in d["roadmap"] if x["title"].startswith(m.group(3).strip())), None)
                if not st:
                    raise SystemExit(f"from-roadmap：ロードマップに「{m.group(3)}」が無い")
                widgets = "".join(re.findall(r'<div data-widget="[^"]+"></div>', st.get("extra", "")))
                out.append(f'<div class="stage-grid"><div>{widgets}</div><div>{st.get("tables", "")}</div></div>')
        out.append("</section>")
    out.append("</div>")
    return "\n".join(out)


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
        f'<p class="eyebrow">{inline(ls["phase_title"])}'
        + (f'｜{session_label(d, ls)}' if ls.get("session") else "")
        + '</p>',
        f'<h1>ドリル{no}　{inline(ls["title"])}</h1>',
    ]
    degrees = ",".join(x for x in DEG_ALL if x in ls["deg"])
    n_bars = len(chords.split("-"))
    practice_roll = (
        f'<div class="roll" data-lesson="{no:02d}" '
        f'data-progs="{"|".join(roll_prog_choices(no, prog))}" '
        + (f'data-bars="{n_bars}" ' if n_bars > 4 else "")
        + f'data-degrees="{degrees}"></div>'
    )
    flow = ls.get("flow") or []
    # 授業の流れがあるページは右カラムを出さない（練習用ロールは流れの {{roll}} の位置に置く）
    if flow:
        parts.append(render_flow(d, no, flow, practice_roll, chords))
        parts.append('<h2 class="flow-end">このドリルの設計</h2>')
    parts += [
        # PCでは左に講義と課題、右にピアノロール
        '<div class="lesson-grid">' if not flow else "<div>",
        '<div class="lesson-main">',
    ]
    if prog in ("", "—", "-"):
        parts.append(sounds)
    else:
        parts += [
            '<div class="grid2">',
            sounds,
            '<div class="panel"><p class="k">伴奏</p>'
            f'<p class="v"><code>{inline(prog_label(chords))}</code></p></div>',
            "</div>",
        ]
    rows = []
    for label, text in ls["items"]:
        if label == "伴奏" and not prog_has_note:
            continue
        if flow and label == "新コード":   # 流れの「新コード」の節に出ている
            continue
        rows.append(
            f'<div class="row"><div class="lbl">{inline(label)}</div>'
            f'<p class="val">{inline(text)}</p></div>'
        )
    if rows:
        parts.append(f'<div class="rows">{"".join(rows)}</div>')

    side = [] if flow else [
        '<div class="lesson-side">',
        "<h2>4小節つくる</h2>",
        "<p>キーを変えても、数字は変わらない。</p>",
        practice_roll,
        "</div>",
    ]

    if tips:
        parts.append("<h2>今回のコツ</h2>")
        items = "".join(
            f'<li><strong>{inline(t["tip"])}</strong>（{inline(t["view"])}）<br>'
            f'<span class="why">{inline(t["why"])}</span></li>'
            for t in tips
        )
        parts.append(f"<ul>{items}</ul>")
        parts.append('<p class="more"><a href="../tips/">コツ一覧 →</a></p>')
    parts.append("</div>")          # lesson-main
    parts += side
    parts.append("</div>")          # lesson-grid

    prev_l = f'<a href="../{no-1:02d}/">← ドリル{no-1}</a>' if no > 1 else ""
    next_l = f'<a href="../{no+1:02d}/">ドリル{no+1} →</a>' if no < max(d["lessons"]) else ""
    parts.append(f'<div class="pager">{prev_l}<div class="sp"></div>{next_l}</div>')
    parts.append(FOOT)
    parts.append("</div>")
    parts.append(f'<script src="../{asset("voicing.js")}" defer></script>')
    parts.append(f'<script src="../{asset("roll.js")}" defer></script>')
    if any('data-widget=' in p for p in parts):   # 流れに鍵盤・簡易ジェネレータがあるときだけ
        parts.append(f'<script src="../{asset("keyboard.js")}" defer></script>')

    desc = f'ドリル{no}「{ls["title"]}」。使える音は{ls["sounds_raw"]}、伴奏は{ls["prog"]}。'
    aim = dict(ls["items"]).get("狙い", "")
    if aim:
        desc += aim
    return page(
        f'ドリル{no} {ls["title"]}｜{SITE_TITLE}',
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
    top_views = [v for v in d.get("tips_top_views", []) if v in views]
    rest = [v for v in views if v not in top_views]

    def section(view):
        out = [f'<h2 id="{slug[view]}">{inline(view)}</h2>']
        extras = d.get("tips_extra", {}).get(view, [])
        for title, blocks in extras:
            if title == "鉄則":      # 観点の鉄則は、コツより上に大きく出す
                out.append(f'<div class="motto">{blocks}</div>')
        items = []
        for t in d["tips"]:
            if t["view"] != view:
                continue
            # 授業との対応はおまけなので、小さく末尾に添えるだけにする
            src = ""
            if t["nos"]:
                links = "・".join(f'<a href="../{n:02d}/">ドリル{n}</a>' for n in t["nos"])
                src = f'<p class="src">{links}で習う</p>'
            items.append(
                f'<li class="tip"><p class="t">{inline(t["tip"])}</p>'
                f'<p class="d">{inline(t["why"])}</p>{src}</li>'
            )
        out.append(f'<ol class="tips">{"".join(items)}</ol>')
        for title, blocks in extras:
            if title == "鉄則":
                continue
            out.append(f"<h3>{inline(title)}</h3>")
            out.append(blocks)
        return out

    parts = [
        '<div class="wrap narrow">',
        nav(1, "ポップスのコツ"),
        '<p class="eyebrow">応用実習1,2：作曲</p>',
        "<h1>ポップスのコツ</h1>",
        f'<p class="lead">{inline(d["tips_note"])}</p>',
    ]
    if d.get("tips_top"):
        # 冒頭文の下の「**鉄則**」＋1段落は、ページ全体の鉄則として大きく出す
        top = re.sub(r"<h3>鉄則</h3>\s*(<p>.*?</p>)", r'<div class="motto">\1</div>', d["tips_top"], flags=re.S)
        parts.append(top)
    # 覚えるべきコードの色分けは、コツ「…グループ分け…」の例・理由（I IIIm VIm ／ IIm IV ／ V）から取る
    grouping = next((t["why"] for t in d["tips"] if "グループ分け" in t["tip"]), "")
    groups_attr = "|".join(g.strip() for g in grouping.split("／") if g.strip())
    for view in top_views:          # 一番上に出す観点（コードの tier 表など）
        parts += section(view)
    if groups_attr:
        parts = [x.replace('<div data-widget="chords"></div>', f'<div data-widget="chords" data-groups="{html.escape(groups_attr)}"></div>') for x in parts]
    counts = {v: sum(1 for t in d["tips"] if t["view"] == v) for v in rest}
    if rest:
        parts.append(
            '<div class="index">'
            + "".join(f'<a href="#{slug[v]}">{inline(v)}<span>{counts[v]}</span></a>' for v in rest)
            + "</div>"
        )
    for view in rest:
        parts += section(view)

    parts.append(f'<script src="../{asset("voicing.js")}" defer></script>')
    parts.append(f'<script src="../{asset("keyboard.js")}" defer></script>')
    parts += [FOOT, "</div>"]
    return page(
        f"ポップスのコツ｜{SITE_TITLE}",
        f'ポップスの作曲コツ{len(d["tips"])}個（{"・".join(views)}）。あくまでコツであってルールではない。',
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
        parts.append('<section class="stage">')
        parts.append(f'<h2 id="{st["slug"]}">{inline(st["title"])}</h2>')
        rows, src = [], ""
        for label, text in st["items"]:
            if label == "対応ドリル":
                nos = [int(n) for n in re.findall(r"\d+", text)]
                links = "・".join(f'<a href="../{n:02d}/">ドリル{n}</a>' for n in nos)
                src = f'<p class="stage-src">{links}で習う</p>' if links else ""
                continue
            rows.append(
                f'<div class="row"><div class="lbl">{inline(label)}</div>'
                f'<p class="val">{inline(text)}</p></div>'
            )
        if rows:  # 地の文だけで書いた段階は行を出さない
            parts.append(f'<div class="rows tight">{"".join(rows)}</div>')
        if st.get("tables"):
            parts.append(f'<div class="stage-grid"><div>{st.get("extra", "")}</div><div>{st["tables"]}</div></div>')
        elif st.get("extra"):
            parts.append(st["extra"])
        if src:
            parts.append(src)
        parts.append("</section>")
    parts.append(f'<script src="../{asset("voicing.js")}" defer></script>')
    parts.append(f'<script src="../{asset("keyboard.js")}" defer></script>')
    parts += [FOOT, "</div>"]
    return page(
        "何もわからない人のための音楽理論ロードマップ｜" + SITE_TITLE,
        "音楽理論＝いいかんじの音楽あるある。トーナリティ→インターバル→メジャースケール→ダイアトニックコードの4段階。",
        f"{BASE}roadmap/",
        "\n".join(parts),
    )


def render_doc(lines):
    """### / #### 見出し入りの本文（虎の巻など、curriculum.md 以外の原稿用）。"""
    out, buf = [], []

    def flush():
        if buf:
            out.append(render_blocks(buf))
            del buf[:]

    for ln in lines:
        if ln.startswith("#### "):
            flush()
            out.append(f"<h4>{inline(ln[5:].strip())}</h4>")
        elif ln.startswith("### "):
            flush()
            out.append(f"<h3>{inline(ln[4:].strip())}</h3>")
        else:
            buf.append(ln)
    flush()
    return "\n".join(out)


# {{play …}} で鳴らせるコードの種類（assets/voicing.js の QUALITY と同じ）。それ以外はビルドで止める
PLAY_QUALITIES = {"", "m", "7", "M7", "maj7", "m7", "m7-5", "m-5", "dim", "dim7", "sus4", "aug"}
_PLAY_NAME = re.compile(rf"([#♭]?{_NUM})(.*?)(?:/[#♭]?{_NUM})?")


def play_widget(spec):
    """{{play ラベル=IIm7 V7 IM7 | IIm7 ♭II7 IM7}} → 進行の再生（assets/keyboard.js の play）。
    「|」で行を分け、「ラベル=」は省略できる。空白区切りの1要素＝1小節、「A+B」は小節の真ん中で変わる"""
    rows = []
    for part in spec.split("|"):
        label, _, prog = part.strip().rpartition("=")
        bars = prog.split()
        if not bars:
            raise SystemExit(f"play の行にコードが無い：{part.strip()}")
        for name in (n for b in bars for n in b.split("+")):
            m = _PLAY_NAME.fullmatch(name)
            if not m or m.group(2) not in PLAY_QUALITIES:
                raise SystemExit(f"play で鳴らせないコード名：{name}（種類は {sorted(PLAY_QUALITIES)} のどれか）")
        rows.append((f"{label.strip()}=" if label.strip() else "") + " ".join(bars))
    return f'<div data-widget="play" data-progs="{html.escape("|".join(rows))}"></div>'


def render_doc_widgets(lines, lesson):
    """render_doc に {{play …}}（進行の再生）と {{roll-demo …}}（見本ロール）を足したもの。中級編の本文用"""
    out, buf = [], []

    def flush():
        if buf:
            out.append(render_doc(buf))
            del buf[:]

    for ln in lines:
        s = ln.strip()
        pm = re.fullmatch(r"\{\{play\s+(.+)\}\}", s)
        rm = re.fullmatch(r"\{\{roll-demo\s+(.+)\}\}", s)
        if pm:
            flush()
            out.append(play_widget(pm.group(1)))
        elif rm:
            flush()
            out.append(demo_roll(rm.group(1), lesson, DEFAULT_PROG))
        else:
            buf.append(ln)
    flush()
    return "\n".join(out)


def build_chukyu():
    """composition-src/chukyu.md（正本）から作曲理論 中級編を生成する。無ければページも作らない。
    書式は虎の巻と同じ（# タイトル＋リード、## 節＝目次チップ、### / #### 小見出し）に、{{play}} と {{roll-demo}} を足したもの"""
    path = SRC / "chukyu.md"
    if not path.exists():
        return None
    md = path.read_text(encoding="utf-8").splitlines()
    title = next((l[2:].strip() for l in md if l.startswith("# ")), "作曲理論 中級編")
    head = []
    for l in md:
        if l.startswith("## "):
            break
        if not l.startswith("# "):
            head.append(l.strip())
    paras = [l for l in head if l]
    lead = paras[0] if paras else ""
    note = "　".join(paras[1:])
    secs = split_sections(md, "## ")
    body = [render_doc_widgets(b, "chukyu-demo") for _, b in secs]
    parts = [
        '<div class="wrap narrow">',
        nav(1, "中級編"),
        '<p class="eyebrow">応用実習1,2：作曲</p>',
        f"<h1>{inline(title)}</h1>",
        f'<p class="lead">{inline(lead)}</p>',
        '<div class="index">'
        + "".join(f'<a href="#c{i + 1}">{inline(t)}</a>' for i, (t, _) in enumerate(secs))
        + "</div>",
    ]
    for i, (t, _) in enumerate(secs):
        parts.append('<section class="stage">')
        parts.append(f'<h2 id="c{i + 1}">{inline(t)}</h2>')
        parts.append(body[i])
        parts.append("</section>")
    if note:
        parts.append(f'<p class="why">{inline(note)}</p>')
    parts += [FOOT, "</div>"]
    joined = "\n".join(body)
    if 'data-widget="play"' in joined or 'class="roll"' in joined:
        parts.append(f'<script src="../{asset("voicing.js")}" defer></script>')
    if 'class="roll"' in joined:
        parts.append(f'<script src="../{asset("roll.js")}" defer></script>')
    if 'data-widget="play"' in joined:
        parts.append(f'<script src="../{asset("keyboard.js")}" defer></script>')
    return page(
        f"{title}｜{SITE_TITLE}",
        "もうちょっと込み入ったコードの話",
        f"{BASE}chukyu/",
        "\n".join(parts),
    )


def build_toranomaki():
    """composition-src/toranomaki.md（正本）から生成。無ければページも作らない。
    原典は DTM初級虎の巻（Googleドキュメント）。文言はそちらから、階層の崩れだけ直して持ってきた。"""
    path = SRC / "toranomaki.md"
    if not path.exists():
        return None
    md = path.read_text(encoding="utf-8").splitlines()
    title = next((l[2:].strip() for l in md if l.startswith("# ")), "音楽制作虎の巻")
    head = []
    for l in md:
        if l.startswith("## "):
            break
        if not l.startswith("# "):
            head.append(l.strip())
    paras = [l for l in head if l]
    lead = paras[0] if paras else ""
    note = "　".join(paras[1:])
    secs = split_sections(md, "## ")
    parts = [
        '<div class="wrap narrow">',
        nav(1, "虎の巻"),
        '<p class="eyebrow">応用実習1,2：作曲</p>',
        f"<h1>{inline(title)}</h1>",
        f'<p class="lead">{inline(lead)}</p>',
        '<div class="index">'
        + "".join(f'<a href="#t{i + 1}">{inline(t)}</a>' for i, (t, _) in enumerate(secs))
        + "</div>",
    ]
    for i, (t, body) in enumerate(secs):
        parts.append('<section class="stage">')
        parts.append(f'<h2 id="t{i + 1}">{inline(t)}</h2>')
        parts.append(render_doc(body))
        parts.append("</section>")
    if note:
        parts.append(f'<p class="why">{inline(note)}</p>')
    parts += [FOOT, "</div>"]
    return page(
        f"{title}｜{SITE_TITLE}",
        "音楽制作を続けるための心構え・理論の学び方・機材・情報源。",
        f"{BASE}toranomaki/",
        "\n".join(parts),
    )


def build_history(d):
    """kammerkonzert/ensemble/ の振り子年表の簡易版。
    縦＝時間（行の高さは一定）。クラシックの系譜は左トラック、バークリーは右トラック。
    折れ線が全ノードを時系列につなぎ、最後は中央の「この授業」（つながりの節の同名の行）に合流する。"""
    h = d["history"]
    CL, BK = 16, 84            # トラックの横位置（%）
    ROW, HEAD = 168, 66        # 1項目・系譜見出しの縦の割り当て（px）
    els, pts = [], []
    y = 16
    for sec in h["sections"]:
        if not sec["timeline"]:
            continue
        berk = "バークリー" in sec["title"]
        x = BK if berk else CL
        node_c = "#1d6a3a" if berk else "var(--acc)"      # コツのtier表の緑と同じ系統
        ink_c = "#1d6a3a" if berk else "var(--acc-ink)"
        els.append(f'<div class="hlabel hrv" style="top:{y + HEAD // 2}px;--hc:{ink_c}"><span>{inline(sec["title"])}</span></div>')
        y += HEAD
        for label, text in sec["items"]:
            p = label.split("　")
            era, ttl = p[0], "　".join(p[1:]) or p[0]
            yc = y + ROW // 2
            els.append(f'<div class="hnode hrv" style="top:{yc}px;left:{x}%;--hc:{node_c}"></div>')
            side = f"left:calc({CL}% + 16px)" if not berk else f"right:calc({100 - BK}% + 16px)"
            els.append(
                f'<div class="hcard hrv" style="top:{yc}px;{side}">'
                f'<h3>{inline(ttl)}<span class="cy">{inline(era)}</span></h3>'
                f'<p>{inline(text)}</p></div>'
            )
            pts.append((x, yc))
            y += ROW
    track_end = y
    # 合流ノード：つながりの節の「この授業」の行。残りの行はチャートの下に定義行で出す
    merge, conn_title, conn_rows, conn_extra = None, "", [], ""
    for sec in h["sections"]:
        if sec["timeline"]:
            continue
        conn_title, conn_extra = sec["title"], sec.get("extra", "")
        for label, text in sec["items"]:
            if label == "この授業" and merge is None:
                merge = (label, text)
            else:
                conn_rows.append((label, text))
    if merge:
        yc = y + 44
        pts.append((50, yc))
        els.append(f'<div class="hnode merge hrv" style="top:{yc}px;left:50%"></div>')
        els.append(
            f'<div class="hcard mergecard hrv" style="top:{yc + 26}px">'
            f'<h3>{inline(merge[0])}</h3><p>{inline(merge[1])}</p></div>'
        )
        y = yc + 190
    total = y
    line = " ".join(f"{x},{yc}" for x, yc in pts)
    chart = (
        f'<div class="histwrap"><div class="histbox" style="height:{total}px">'
        f'<svg viewBox="0 0 100 {total}" preserveAspectRatio="none" aria-hidden="true">'
        f'<polyline points="{line}" fill="none" stroke="var(--muted)" stroke-width="2" opacity="0.4" vector-effect="non-scaling-stroke"/></svg>'
        f'<div class="vline" style="left:{CL}%;top:0;height:{track_end}px"></div>'
        f'<div class="vline" style="left:{BK}%;top:0;height:{track_end}px"></div>'
        + "".join(els) + "</div></div>"
    )
    parts = [
        '<div class="wrap narrow">',
        nav(1, "理論の歴史"),
        '<p class="eyebrow">応用実習1,2：作曲</p>',
        f"<h1>{inline(h['title'])}</h1>",
        # 節の頭の1行（箇条書きでなければ）は、コツの鉄則と同じくデカく出す
        (f'<div class="motto"><p>{inline(h["lead"])}</p></div>' if h["lead"] else ""),
        h["intro"],
        chart,
    ]
    if conn_rows:
        parts.append('<section class="stage">')
        parts.append(f"<h2>{inline(conn_title)}</h2>")
        rows = "".join(
            f'<div class="row"><div class="lbl">{inline(l)}</div><p class="val">{inline(t)}</p></div>'
            for l, t in conn_rows
        )
        parts.append(f'<div class="rows tight">{rows}</div>')
        if conn_extra:
            parts.append(conn_extra)
        parts.append("</section>")
    parts.append(
        "<script>document.documentElement.classList.add('js');"
        "const io=new IntersectionObserver(es=>es.forEach(e=>{if(e.isIntersecting){e.target.classList.add('show');io.unobserve(e.target)}}),{threshold:.15});"
        "document.querySelectorAll('.hrv').forEach(el=>io.observe(el));</script>"
    )
    parts += [FOOT, "</div>"]
    return page(
        f"{h['title']}｜{SITE_TITLE}",
        "クラシック理論とバークリー理論、2つの系譜を1本の年表で把握する。あくまで実践が先、理論があと。",
        f"{BASE}history/",
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
    write("assets/voicing.js", VOICING_JS)
    write("assets/roll.js", ROLL_JS)
    write("assets/keyboard.js", KEYBOARD_JS)
    write("index.html", build_index(d))
    for no in sorted(d["lessons"]):
        write(f"{no:02d}/index.html", build_lesson(d, no))
    write("tips/index.html", build_tips(d))
    write("roadmap/index.html", build_roadmap(d))
    if d["history"]:
        write("history/index.html", build_history(d))
    tora = build_toranomaki()
    if tora:
        write("toranomaki/index.html", tora)
    chukyu = build_chukyu()
    if chukyu:
        write("chukyu/index.html", chukyu)

    print(f"{len(written)} ファイルを書き出した → {OUT}")
    for rel in written:
        print("  ", rel)
    missing = [n for n, l in d["lessons"].items() if not l["items"] and not l.get("flow")]
    if missing:
        print("注意：詳細が空の回 →", missing, file=sys.stderr)


if __name__ == "__main__":
    main()
