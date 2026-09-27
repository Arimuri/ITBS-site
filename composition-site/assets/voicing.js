/* 和音のボイシング（composition-src/build.py が生成）
   サイトで鳴る和音は全部ここを通す（コードtier・ピアノロール・スケール鍵盤・1度当て）。
   ・ベースはルート（分数コードは分母）を C2〜C3 に置く
   ・上の3声は密集の転回形で F3〜A4 に収める。4和音はルートをベースに任せ、上は3・5・7
   ・進行は、ループの継ぎ目も含めて上の声部とベースの動きが一番小さくなる組み合わせを選ぶ */
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
  const RANGE = { lo: 53, hi: 69, center: 61, blo: 36, bhi: 48, bcenter: 41 };
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
  function move(a, b) {
    if (a.length === b.length) return a.reduce((s, x, i) => s + Math.abs(x - b[i]), 0);
    const near = (x, v) => Math.min.apply(null, v.map(y => Math.abs(x - y)));
    return a.reduce((s, x) => s + near(x, b), 0) + b.reduce((s, y) => s + near(y, a), 0);
  }
  // 候補の並びから、点（single）とつなぎ（link）の合計が最小になる選び方を返す。loop なら最後→最初も数える
  function best(cands, single, link, loop) {
    const n = cands.length;
    let top = Infinity, path = null;
    const starts = loop && n > 1 ? cands[0].map((_, k) => k) : [-1];
    starts.forEach(k0 => {
      let row = cands[0].map((c, k) => (k0 < 0 || k === k0 ? { s: single(c), p: [k] } : null));
      for (let i = 1; i < n; i++) {
        const prev = row;
        row = cands[i].map((c, k) => {
          let b = null;
          prev.forEach((q, j) => {
            if (!q) return;
            const s = q.s + link(cands[i - 1][j], c);
            if (!b || s < b.s) b = { s: s, p: q.p };
          });
          return b && { s: b.s + single(c), p: b.p.concat(k) };
        });
      }
      row.forEach((q, k) => {
        if (!q) return;
        const s = q.s + (k0 >= 0 ? link(cands[n - 1][k], cands[0][k0]) : 0);
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
    const ups = best(chords.map(ch => uppers(upperPcs(ch, tonicPc), r)),
      v => W_CENTER * Math.abs(mean(v) - r.center), move, loop);
    const bs = best(chords.map(ch => basses((tonicPc + ch.bass) % 12, r)),
      b => W_BCENTER * Math.abs(b - r.bcenter), (a, b) => Math.abs(a - b), loop);
    return chords.map((ch, i) => ({ bass: bs[i], upper: ups[i] }));
  }
  window.Voicing = { parse: parse, voice: voice };
})();
