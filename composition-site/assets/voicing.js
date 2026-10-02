/* 和音のボイシング（composition-src/build.py が生成）
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
  // 「IIm7」「IV/V」「♭VImaj7」などを { root, bass, ivs }（root・bass はキーの1度からの半音）にする
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
