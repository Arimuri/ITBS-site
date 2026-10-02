/* 4小節ピアノロール（composition-src/build.py が生成）
   各回のページの <div class="roll" data-prog data-degrees data-lesson> を中身で埋める。
   ・行は半音ごと。選んだキーのメジャースケールの行だけ色を濃くし、1〜7の番号を振る
   ・その回までに解禁された度数の行は、さらに濃く＋番号を強調する
   ・キーを変えるとメロも一緒に移調する（数字は変わらず高さだけ変わる、を体感させる） */
(() => {
  'use strict';
  const LOW = 48, HIGH = 72, ROWS = HIGH - LOW + 1;
  const BARS = 4, STEPS = 8, COLS = BARS * STEPS;
  const MAJOR = [0, 2, 4, 5, 7, 9, 11];
  const KEYDEG = ['1', '♭2', '2', '♭3', '3', '4', '#4', '5', '♭6', '6', '♭7', '7'];
  const KEYS = ['C', 'D♭', 'D', 'E♭', 'E', 'F', 'G♭', 'G', 'A♭', 'A', 'B♭', 'B'];
  const FILE_KEYS = ['C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'B'];
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
    // data-steps：1小節のマス数（既定8＝8分音符。16にすると16分音符のマスで、付点8分＋16分などが書ける）
    const STEPS = +root.dataset.steps === 16 ? 16 : 8;
    const BARS = Math.max(1, +root.dataset.bars || 4), COLS = BARS * STEPS;
    // data-high：ロールの一番上の音（MIDI、既定72＝C5）。下はその2オクターブ下まで。見本のメロが高いときに使う
    const HIGH = +root.dataset.high || 72, LOW = HIGH - 24, ROWS = HIGH - LOW + 1;
    // data-progs：「|」区切りの進行。「Step 1:IVmaj7-V7-Imaj7-Imaj7」のように「名前:」を付けるとプルダウンにその名前が出る
    const progLabels = {};
    const progs = (root.dataset.progs || 'I-VIm-IV-V').split('|').map(v => {
      const i = v.indexOf(':');
      if (i < 0) return v;
      progLabels[v.slice(i + 1)] = v.slice(0, i);
      return v.slice(i + 1);
    });
    let prog = progs[0].split('-');
    // data-group：同じ名前のロールどうしは、進行のプルダウンをまとめて切り替える（同じ曲を4小節ずつ並べたとき用）
    const group = root.dataset.group || '';
    const open = new Set((root.dataset.degrees || '').split(',').filter(Boolean));
    const notes = new Set();                      // "midi,col"
    // data-notes：最初から置いておく音（見本のメロ）。data-nosave：保存しない（開き直すと見本に戻る）
    const nosave = root.dataset.nosave === '1';
    (root.dataset.notes || '').split(/\s+/).filter(Boolean).forEach(k => notes.add(k));
    // data-heads：同じ高さの音が続くとき、ここで音を切る（「ミミミー」を1本の長い音にしない）
    const heads = new Set((root.dataset.heads || '').split(/\s+/).filter(Boolean));
    const isHead = (m, c) => c > 0 && notes.has(m + ',' + (c - 1)) && heads.has(m + ',' + c);
    let tonicPc = (+root.dataset.key || 0) % 12, bpm = DEFAULT_BPM, dragging = false, drawMode = 'draw', warn = '';   // data-key：最初のキー（0=C）
    const stepSec = () => 60 / bpm / (STEPS / 4);  // 横1マス＝8分音符（steps=16 なら16分音符）
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
    if (BARS !== 4 || STEPS !== 8) {                    // CSS は4小節・8分前提なので、それ以外は幅と列数を上書き
      grid.style.minWidth = (BARS * 150 * STEPS / 8) + 'px';
      barsEl.style.gridTemplateColumns = 'repeat(' + BARS + ',1fr)';
      cellsEl.style.gridTemplateColumns = 'repeat(' + COLS + ',1fr)';
    }
    if (BARS < 4) scroll.style.maxWidth = 'calc(36px + (100% - 36px) * ' + BARS / 4 + ')';   // 1〜3小節は横に引き伸ばさず、1小節の幅を4小節のロールにそろえる
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
      const shown = v.indexOf('+') >= 0 || v.indexOf('*') >= 0 ? v.split('-').map(b => b.replace(/\*\d+/g, '').replace(/\+/g, ' ')).join('｜') : v;   // 2コードの小節がある進行は「IV Vsus4｜I VIm7」と見せる
      o.value = v; o.textContent = progLabels[v] ? progLabels[v] + '：' + shown : shown;
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
          const on = notes.has(m + ',' + c);
          el.classList.toggle('on', on);
          el.classList.toggle('split', on && isHead(m, c));
          const ck = on ? clashKind(m, c) : '';
          el.classList.toggle('clash', ck === 'clash');
          el.classList.toggle('mild', ck === 'mild');
          // 音の頭にだけ「キー度数/コード度数」（伸ばしている途中のマスには出さない）
          const lab = on && !(c > 0 && notes.has(m + ',' + (c - 1)) && !isHead(m, c)) ? labelFor(m, c) : '';
          if (el.dataset.lab !== lab) {
            el.dataset.lab = lab;
            el.textContent = '';
            if (lab) { const sp = document.createElement('span'); sp.className = 'lbl'; sp.textContent = lab; el.appendChild(sp); }
          }
        }
      }
      warnEl.textContent = warn;
      noteEl.textContent = '音の頭の数字＝キー度数/コード度数。赤い音＝短9度（Tの上の4、Dの上の1）、黄色い音＝IIIm7の上の1（軽め）。黄色い行＝今回使う音、濃い行＝スケール。横1マス＝' + (STEPS === 16 ? '16分' : '8分') + '音符、太線＝小節。';
    }
    // コード度数は curriculum の書き方（そのコードが本来持つ3rd・5th・7thを3・5・7と呼ぶ）。prog/ と同じ
    function chordDeg(iv, ch) {
      const has = x => ch.ivs.indexOf(x) >= 0;
      const t3 = has(4) ? 4 : has(3) ? 3 : null;
      const n5 = has(6) ? 6 : has(8) ? 8 : 7;
      const n7 = has(11) ? 11 : has(10) ? 10 : has(9) ? 9 : (t3 === 4 || has(8)) ? 11 : 10;
      switch (iv) {
        case 0: return 'R';
        case 1: return '♭9';
        case 2: return '9';
        case 3: return t3 === 3 ? '3' : '♭3';
        case 4: return t3 === 3 ? '#3' : '3';
        case 5: return '4';
        case 6: return n5 === 6 ? '♭5' : '#4';
        case 7: return '5';
        case 8: return n5 === 8 ? '#5' : '♭6';
        case 9: return n7 === 9 ? '7' : '6';
        case 10: return n7 === 10 ? '7' : '♭7';
        default: return n7 === 11 ? '7' : 'maj7';
      }
    }
    function chordNameAt(c) {
      const inBar = c % STEPS;
      const seg = barSegs(Math.floor(c / STEPS)).find(x => inBar >= x.start && inBar < x.start + x.len);
      return seg && seg.name ? seg.name : null;
    }
    function labelFor(m, c) {
      const kd = KEYDEG[((m - tonicPc) % 12 + 12) % 12];
      const nm = chordNameAt(c), ch = nm ? window.Voicing.parse(nm) : null;
      if (!ch) return kd;
      return kd + '/' + chordDeg(((m - (tonicPc + ch.root)) % 12 + 12) % 12, ch);
    }
    // 授業で教える短9度：Tの上の4、Dの上の1 は赤。IIIm7 の上の1は軽め（黄色）。
    // その音がコードの音なら色を付けない（Vsus4 の上の1など）。ダイアトニック以外のコードは判定しない
    const FUNC = { I: 'T', Imaj7: 'T', IM7: 'T', IIIm: 'T', IIIm7: 'T', VIm: 'T', VIm7: 'T',
      IIm: 'SD', IIm7: 'SD', IV: 'SD', IVmaj7: 'SD', IVM7: 'SD', V: 'D', V7: 'D', 'VIIm-5': 'D', 'VIIm7-5': 'D' };
    function clashKind(m, c) {
      const nm = chordNameAt(c), f = nm && FUNC[nm];
      if (!f) return '';
      const ch = window.Voicing.parse(nm), kd = ((m - tonicPc) % 12 + 12) % 12;
      if (ch.ivs.some(iv => (ch.root + iv) % 12 === kd)) return '';
      if ((f === 'T' && kd === 5) || (f === 'D' && kd === 0)) return 'clash';
      if ((nm === 'IIIm7' || nm === 'IIIm') && kd === 0) return 'mild';
      return '';
    }

    // ---- 打ち込み ----
    function apply(el) {
      const m = midiOf(+el.dataset.r), key = m + ',' + el.dataset.c;
      if (drawMode === 'draw') {
        if (!notes.has(key)) { notes.add(key); tone(m, 0, 0.35, 0.2, null); }
      } else if (notes.has(key)) { notes.delete(key); heads.delete(key); }
      paint();                                      // 前後の音のラベル（音の頭）も変わるので描き直す
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
    // data-store があればその名前で保存（同じ回に練習用ロールが2本あるとき）
    const storeKey = 'roll:' + (root.dataset.store || lesson + (BARS !== 4 ? '@' + BARS : ''));
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
    // ---- data-dl：ロールの下に「コード進行のMIDIをダウンロード」（選んでいる進行・キー・テンポのまま。Logic に読み込む用） ----
    // format 0・480分解能・1トラック。ボイシングは再生と同じ（ベース＋上3〜4音）
    function vlq(n) {
      const out = [n & 127];
      n = Math.floor(n / 128);
      while (n > 0) { out.unshift((n & 127) | 128); n = Math.floor(n / 128); }
      return out;
    }
    function chordMidi() {
      const TPQ = 480, STEP_T = TPQ * 4 / STEPS, GAP = 20, ev = [];
      voicing().forEach((segs, b) => segs.forEach(s => {
        const t0 = (b * STEPS + s.start) * STEP_T, t1 = t0 + s.len * STEP_T - GAP;
        [s.v.bass].concat(s.v.upper).forEach((n, i) => {
          ev.push({ t: t0, b: [0x90, n, i ? 78 : 92] });
          ev.push({ t: t1, b: [0x80, n, 0] });
        });
      }));
      ev.sort((x, y) => x.t - y.t);
      const us = Math.round(60000000 / bpm), bytes = [];
      let last = 0;
      const push = (t, b) => { bytes.push.apply(bytes, vlq(t - last).concat(b)); last = t; };
      push(0, [0xFF, 0x51, 0x03, (us >> 16) & 255, (us >> 8) & 255, us & 255]);
      push(0, [0xFF, 0x58, 0x04, 4, 2, 24, 8]);
      push(0, [0xFF, 0x03, 6].concat(Array.from('Chords', ch => ch.charCodeAt(0))));
      ev.forEach(e => push(e.t, e.b));
      push(COLS * STEP_T, [0xFF, 0x2F, 0x00]);
      const len = bytes.length;
      return new Uint8Array([0x4D, 0x54, 0x68, 0x64, 0, 0, 0, 6, 0, 0, 0, 1, (TPQ >> 8) & 255, TPQ & 255,
        0x4D, 0x54, 0x72, 0x6B, (len >> 24) & 255, (len >> 16) & 255, (len >> 8) & 255, len & 255].concat(bytes));
    }
    if (root.dataset.dl === '1') {
      const row = mk('div', 'rh-btns'), msg = mk('p', 'rh-status');
      const dlBtn = mk('button', '', 'コード進行のMIDIをダウンロード');
      dlBtn.type = 'button';
      dlBtn.addEventListener('click', () => {
        const name = progLabels[prog.join('-')];
        const a = document.createElement('a');
        a.href = URL.createObjectURL(new Blob([chordMidi()], { type: 'audio/midi' }));
        a.download = (name ? name + '_' : '') + 'chords_' + FILE_KEYS[tonicPc] + '_' + bpm + 'bpm.mid';
        a.click();
        setTimeout(() => URL.revokeObjectURL(a.href), 1000);
        msg.textContent = 'ダウンロードした。Logicのトラックにドラッグ。';
      });
      row.appendChild(dlBtn);
      root.appendChild(row);
      root.appendChild(msg);
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
    function applyProg() {
      prog = progSel.value.split('-');
      updateBars();
      paint();                                      // コードが変わるとコード度数も変わる
      save();
    }
    progSel.addEventListener('change', () => {
      applyProg();
      if (group) document.dispatchEvent(new CustomEvent('roll-group', { detail: { group: group, index: progSel.selectedIndex, from: root } }));
    });
    document.addEventListener('roll-group', e => {
      const d = e.detail;
      if (!group || d.group !== group || d.from === root || d.index >= progSel.options.length) return;
      progSel.selectedIndex = d.index;
      applyProg();
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
