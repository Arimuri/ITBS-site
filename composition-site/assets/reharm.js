/* リハモ（コード進行ジェネレータのメロ固定版。composition-src/reharm.js → assets/reharm.js）
   <div class="reharm" data-notes data-heads data-key data-high data-bars data-store data-name> を中身で埋める。
   ・ダイアトニックコード（T/SD/D）を小節にドラッグして並べ、固定のメロと一緒に鳴らす。1小節に2つまで（2拍ずつ）
   ・小節0は弱起の小節（コードなし）。本編は data-bars 小節（既定16）で、8小節ずつのレーンに分ける
   ・各レーン＝コード欄8小節＋ピアノロール（弱起の小節＋8小節）。2本目以降のロールの頭は、前の小節の弱起ぶんだけ見せる
   ・音の頭に「キー度数/コード度数」。コードの音の短9度上（半音上）でぶつかる音は赤
   ・キーを変えると、メロもロールの音域も同じ量だけ動く（数字は変わらない） */
(() => {
  'use strict';
  const STEPS = 8, LANE = 8, ROWS = 25;
  const MAJOR = [0, 2, 4, 5, 7, 9, 11];
  const KEYDEG = ['1', '♭2', '2', '♭3', '3', '4', '#4', '5', '♭6', '6', '♭7', '7'];
  const KEYS = ['C', 'D♭', 'D', 'E♭', 'E', 'F', 'G♭', 'G', 'A♭', 'A', 'B♭', 'B'];
  const FILE_KEYS = ['C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'B'];
  const BPMS = [60, 70, 80, 90, 100, 110, 120], DEFAULT_BPM = 80;
  const SCHED_AHEAD = 0.12, TICK_MS = 25;
  // ドリル4「ダイアトニックコードを3つに分ける：T/SD/D」の並び。色は tips/ のグループ分けと同じ
  const GROUPS = [
    { label: 'T', g: 1, names: ['I', 'IM7', 'IIIm', 'IIIm7', 'VIm', 'VIm7'] },
    { label: 'SD', g: 2, names: ['IIm', 'IIm7', 'IV', 'IVM7'] },
    { label: 'D', g: 3, names: ['V', 'V7', 'VIIm-5', 'VIIm7-5'] }
  ];
  const chipClass = name => {
    const G = GROUPS.find(x => x.names.indexOf(name) >= 0);
    return 'cw-chip t1' + (G ? ' g' + G.g : '');
  };

  // ---- 音を出す（各回ページのロールと同じシンセ） ----------------------------------
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
      default: return n7 === 11 ? '7' : 'M7';
    }
  }

  const els = document.querySelectorAll('.reharm');
  for (let i = 0; i < els.length; i++) setup(els[i]);

  function setup(root) {
    const mk = (tag, cls, text) => { const el = document.createElement(tag); if (cls) el.className = cls; if (text !== undefined) el.textContent = text; return el; };
    const BODY = Math.max(1, +root.dataset.bars || 16), LANES = Math.ceil(BODY / LANE);
    const TOTAL = (BODY + 1) * STEPS;                // 弱起の小節（0）＋本編
    const baseKey = (+root.dataset.key || 0) % 12, baseHigh = +root.dataset.high || 72;
    const baseSet = new Set((root.dataset.notes || '').split(/\s+/).filter(Boolean));
    const baseHeads = new Set((root.dataset.heads || '').split(/\s+/).filter(Boolean));
    const storeKey = root.dataset.store || 'reharm';
    const fileName = root.dataset.name || 'reharm';
    // 弱起の長さ＝小節0の最初の音から小節の終わりまで（2本目以降のロールの頭で、前の小節のここだけ見せる）
    let firstCol = STEPS;
    baseSet.forEach(k => { const c = +k.split(',')[1]; if (c < firstCol) firstCol = c; });
    const PICK = Math.max(1, STEPS - firstCol);

    // ---- 状態：slots[i] ＝ 本編 i+1 小節目のコード（0〜2個。2個なら2拍ずつ） ----
    let slots = Array.from({ length: BODY }, () => []);
    let tonicPc = baseKey, bpm = DEFAULT_BPM, picked = null;
    try {
      const o = JSON.parse(localStorage.getItem(storeKey) || 'null');
      if (o) {
        if (Array.isArray(o.s) && o.s.length === BODY) slots = o.s.map(b => (Array.isArray(b) ? b : []).filter(n => typeof n === 'string' && window.Voicing.parse(n)).slice(0, 2));
        if (typeof o.k === 'number' && o.k >= 0 && o.k < 12) tonicPc = o.k;
        if (BPMS.indexOf(o.b) >= 0) bpm = o.b;
      }
    } catch (e) {}
    const save = () => { try { localStorage.setItem(storeKey, JSON.stringify({ s: slots, k: tonicPc, b: bpm })); } catch (e) {} };

    // キーを変えたら、メロもロールの音域もまとめて同じ量だけ動かす
    const keyOffset = pc => ((pc + 6) % 12) - 6;
    const shift = () => keyOffset(tonicPc) - keyOffset(baseKey);
    const HIGH = () => baseHigh + shift();
    const noteAt = (m, g) => baseSet.has((m - shift()) + ',' + g);
    const cutAt = (m, g) => g > 0 && noteAt(m, g - 1) && baseHeads.has((m - shift()) + ',' + g);   // 同じ高さの音の切れ目
    const isStart = (m, g) => noteAt(m, g) && !(g > 0 && noteAt(m, g - 1) && !cutAt(m, g));
    const noteLen = (m, g) => { let l = 1; while (g + l < TOTAL && noteAt(m, g + l) && !cutAt(m, g + l)) l++; return l; };

    // 本編のコードを「コード名・開始マス・長さ」の並びに（再生・MIDI・ラベルで共用）
    function segments() {
      const seq = [];
      slots.forEach((bar, i) => {
        const each = STEPS / bar.length;
        bar.forEach((nm, s) => seq.push({ name: nm, start: (i + 1) * STEPS + s * each, len: each, bar: i, sub: s }));
      });
      return seq;
    }
    function segAt(g) {
      const b = Math.floor(g / STEPS) - 1;
      if (b < 0 || b >= BODY || !slots[b].length) return null;
      const sub = slots[b].length === 1 ? 0 : ((g % STEPS) < STEPS / 2 ? 0 : 1);
      return { name: slots[b][sub], bar: b, sub: sub };
    }
    function chordPcs(name) {
      const ch = window.Voicing.parse(name);
      return { ch: ch, rootPc: (tonicPc + ch.root) % 12, pcs: ch.ivs.map(iv => (tonicPc + ch.root + iv) % 12) };
    }
    function labelFor(m, g) {
      const kd = KEYDEG[((m - tonicPc) % 12 + 12) % 12];
      const sg = segAt(g);
      if (!sg) return kd;
      const c = chordPcs(sg.name);
      return kd + '/' + chordDeg(((m - c.rootPc) % 12 + 12) % 12, c.ch);
    }
    // 短9度：コードの音ではなく、コードの音の半音上にある（Tの上の4、Dの上の1 など）
    function clashes(m, g) {
      const sg = segAt(g);
      if (!sg) return false;
      const pcs = chordPcs(sg.name).pcs, pc = ((m % 12) + 12) % 12;
      return pcs.indexOf(pc) < 0 && pcs.indexOf((pc + 11) % 12) >= 0;
    }
    function playOne(name, at, dur, out) {
      const v = window.Voicing.voice([name], tonicPc)[0];
      tone(v.bass, at || 0, dur || 1.1, 0.19, out); tone(v.bass + 12, at || 0, dur || 1.1, 0.095, out);
      v.upper.forEach(n => tone(n, at || 0, dur || 1.1, 0.14, out));
    }

    // ---- パレット ----------------------------------------------------------------
    const status = mk('p', 'rh-status');
    const HINT = 'コードを小節にドラッグ。押してから小節を押してもいい。';
    const say = t => { status.textContent = t; };
    const panel = mk('div', 'panel rh-palette'), grid = mk('div', 'cw-grid');
    const chips = [];
    GROUPS.forEach(G => {
      grid.appendChild(mk('div', 'cw-tier', G.label));
      const groupsEl = mk('div', 'cw-groups'), groupEl = mk('div', 'cw-group');
      G.names.forEach(name => {
        const chip = mk('button', chipClass(name), name);
        chip.type = 'button';
        chip.draggable = true;
        chip.addEventListener('click', () => {
          playOne(name);
          picked = picked === name ? null : name;
          chips.forEach(c => c.classList.toggle('picked', c.textContent === picked));
          say(picked ? name + ' を選択中。小節を押すと入る。' : HINT);
        });
        chip.addEventListener('dragstart', e => {
          e.dataTransfer.setData('text/plain', JSON.stringify({ name: name }));
          e.dataTransfer.effectAllowed = 'copy';
        });
        chips.push(chip);
        groupEl.appendChild(chip);
      });
      groupsEl.appendChild(groupEl);
      grid.appendChild(groupsEl);
    });
    panel.appendChild(grid);

    // ---- ボタン類 -----------------------------------------------------------------
    const btns = mk('div', 'rh-btns');
    const playBtn = mk('button', 'pri', '鳴らす'); playBtn.type = 'button';
    const keySel = mk('select'); keySel.setAttribute('aria-label', 'キー');
    KEYS.forEach((k, i) => { const o = mk('option', '', k + ' キー'); o.value = String(i); keySel.appendChild(o); });
    const bpmSel = mk('select'); bpmSel.setAttribute('aria-label', 'テンポ');
    BPMS.forEach(b => { const o = mk('option', '', b + ' BPM'); o.value = String(b); bpmSel.appendChild(o); });
    const clearBtn = mk('button', '', 'コードを消す'); clearBtn.type = 'button';
    const dlBtn = mk('button', '', 'MIDIをダウンロード'); dlBtn.type = 'button';
    [playBtn, keySel, bpmSel, clearBtn, dlBtn].forEach(el => btns.appendChild(el));
    const namesBox = mk('div', 'rh-names'), namesOut = mk('output'), copyBtn = mk('button', '', 'コピー');
    copyBtn.type = 'button';
    namesBox.appendChild(mk('span', 'k', '実音')); namesBox.appendChild(namesOut); namesBox.appendChild(copyBtn);

    root.appendChild(panel);
    root.appendChild(btns);
    root.appendChild(namesBox);
    root.appendChild(status);

    // ---- レーン：コード欄8小節＋ロール（弱起の小節＋8小節） ---------------------------
    const slotEls = [], cellEls = [];
    const lanes = [];
    function readDrag(e) {
      try {
        const d = JSON.parse(e.dataTransfer.getData('text/plain'));
        if (d && typeof d.name === 'string' && window.Voicing.parse(d.name)) return d;
      } catch (err) {}
      return null;
    }
    function dropTarget(el, bar, sub) {
      el.addEventListener('dragover', e => { e.preventDefault(); e.stopPropagation(); el.classList.add('over'); });
      el.addEventListener('dragleave', () => el.classList.remove('over'));
      el.addEventListener('drop', e => {
        e.preventDefault(); e.stopPropagation();
        el.classList.remove('over');
        const d = readDrag(e);
        if (d) put(bar, sub, d.name, d.from || null);
      });
    }
    function dragChip(chip, name, bar, sub) {
      chip.draggable = true;
      chip.addEventListener('dragstart', e => {
        e.dataTransfer.setData('text/plain', JSON.stringify({ name: name, from: { bar: bar, sub: sub, w: storeKey } }));
        e.dataTransfer.effectAllowed = 'move';
      });
    }
    // 置く・入れ替える。from は null（パレット）か {bar, sub}
    function put(bar, sub, name, from) {
      if (from && (from.w !== storeKey || !(slots[from.bar] && slots[from.bar][from.sub] === name))) from = null;
      if (sub === 'add') {
        if (slots[bar].length !== 1) return;
        slots[bar].push(name);
        if (from && from.bar !== bar) slots[from.bar].splice(from.sub, 1);
      } else if (slots[bar].length === 0) {
        slots[bar] = [name];
        if (from) slots[from.bar].splice(from.sub, 1);
      } else {
        const displaced = slots[bar][sub];
        slots[bar][sub] = name;
        if (from && !(from.bar === bar && from.sub === sub)) slots[from.bar][from.sub] = displaced;
      }
      picked = null;
      chips.forEach(c => c.classList.remove('picked'));
      render();
    }
    function removeAt(bar, sub) { slots[bar].splice(sub, 1); render(); }

    for (let L = 0; L < LANES; L++) {
      const barsEl = mk('div', 'rh-bars');
      root.appendChild(barsEl);
      for (let i = L * LANE; i < Math.min(BODY, (L + 1) * LANE); i++) {
        const slot = mk('div', 'rh-slot');
        slot.addEventListener('click', e => {
          if (e.target.closest('.x, .add, .half')) return;
          if (picked) { put(i, 0, picked); playOne(slots[i][0]); return; }
          if (slots[i].length === 1) { playOne(slots[i][0]); return; }
          if (!slots[i].length) say('先にコードを押して選ぶか、ドラッグで置く。');
        });
        dropTarget(slot, i, 0);
        slotEls[i] = slot;
        barsEl.appendChild(slot);
      }
      // ロール：ビュー列 v ↔ 全体の列 g。L≥1 の頭の小節は前の小節の弱起ぶんだけ見せる
      const VBARS = Math.min(LANE, BODY - L * LANE) + 1, VCOLS = VBARS * STEPS, OFF = L * LANE * STEPS;
      const scroll = mk('div', 'roll-scroll'), rg = mk('div', 'roll-grid');
      const head = mk('div', 'roll-bars'), gutEl = mk('div', 'roll-gutter'), cellsEl = mk('div', 'roll-cells');
      rg.style.minWidth = (VBARS * 150) + 'px';
      head.style.gridTemplateColumns = 'repeat(' + VBARS + ',1fr)';
      cellsEl.style.gridTemplateColumns = 'repeat(' + VCOLS + ',1fr)';
      [mk('div', 'roll-corner'), head, gutEl, cellsEl].forEach(el => rg.appendChild(el));
      scroll.appendChild(rg);
      root.appendChild(scroll);
      const heads = [], gut = [], cells = [], byCol = [];
      for (let b = 0; b < VBARS; b++) { const d = mk('div', 'roll-bar split'); head.appendChild(d); heads.push(d); }
      for (let v = 0; v < VCOLS; v++) byCol.push([]);
      for (let r = 0; r < ROWS; r++) {
        const gd = mk('div', 'roll-deg'); gutEl.appendChild(gd); gut.push(gd);
        const row = [];
        for (let v = 0; v < VCOLS; v++) {
          const el = mk('div', 'rc' + (v % STEPS === 0 && v ? ' barstart' : ''));
          cellsEl.appendChild(el); row.push(el); byCol[v].push(el);
        }
        cells.push(row);
      }
      const visible = v => L === 0 || v >= STEPS - PICK;
      lanes.push({ OFF: OFF, VBARS: VBARS, VCOLS: VCOLS, heads: heads, gut: gut, cells: cells, byCol: byCol, visible: visible });
    }
    const legend = mk('p', 'roll-note', '音の頭の数字＝キー度数/コード度数。赤い音＝コードの音と短9度でぶつかっている（Tの上の4、Dの上の1 など）。太線＝小節、点線＝コードの切り替わり。');
    root.appendChild(legend);

    function renderSlots() {
      slotEls.forEach((slot, i) => {
        slot.innerHTML = '';
        slot.appendChild(mk('span', 'no', String(i + 1)));
        const bar = slots[i];
        slot.classList.toggle('filled', bar.length > 0);
        slot.classList.toggle('single', bar.length === 1);
        if (!bar.length) {
          slot.appendChild(mk('span', 'empty', '＋'));
          cellEls[i] = [slot];
        } else if (bar.length === 1) {
          const chip = mk('span', chipClass(bar[0]), bar[0]);
          dragChip(chip, bar[0], i, 0);
          const x = mk('button', 'x', '×'); x.type = 'button';
          x.setAttribute('aria-label', (i + 1) + '小節目を消す');
          x.addEventListener('click', () => removeAt(i, 0));
          const add = mk('span', 'add', '＋');
          add.title = '3拍目にコードを足す';
          add.addEventListener('click', () => { const nm = picked || bar[0]; put(i, 'add', nm); if (picked) playOne(nm); });
          dropTarget(add, i, 'add');
          slot.appendChild(chip); slot.appendChild(x); slot.appendChild(add);
          cellEls[i] = [slot];
        } else {
          const halves = mk('div', 'halves');
          cellEls[i] = [];
          bar.forEach((nm, s) => {
            const half = mk('div', 'half');
            const chip = mk('span', chipClass(nm), nm);
            dragChip(chip, nm, i, s);
            const x = mk('button', 'x', '×'); x.type = 'button';
            x.setAttribute('aria-label', (i + 1) + '小節目の' + (s === 0 ? '前半' : '後半') + 'を消す');
            x.addEventListener('click', () => removeAt(i, s));
            half.addEventListener('click', e => {
              if (e.target.closest('.x')) return;
              if (picked) { put(i, s, picked); playOne(slots[i][s]); return; }
              playOne(slots[i][s]);
            });
            dropTarget(half, i, s);
            half.appendChild(chip); half.appendChild(x);
            halves.appendChild(half);
            cellEls[i].push(half);
          });
          slot.appendChild(halves);
        }
      });
    }

    function paint() {
      const top = HIGH();
      lanes.forEach(ln => {
        // ヘッダ：見えている範囲のコードを、置いたコード（小節・前後半）ごとのまとまりで出す
        for (let b = 0; b < ln.VBARS; b++) {
          const runs = [];
          for (let k = 0; k < STEPS; k++) {
            const v = b * STEPS + k, sg = ln.visible(v) ? segAt(v + ln.OFF) : null;
            const id = sg ? sg.bar + ':' + sg.sub : '-';
            if (runs.length && runs[runs.length - 1].id === id) runs[runs.length - 1].len++;
            else runs.push({ id: id, name: sg ? sg.name : null, len: 1, start: k });
          }
          ln.heads[b].innerHTML = '';
          runs.forEach(rn => { const sp = mk('span', '', rn.name || '—'); sp.style.flex = String(rn.len); ln.heads[b].appendChild(sp); });
          ln.heads[b].dataset.cuts = runs.filter(rn => rn.start).map(rn => b * STEPS + rn.start).join(',');
        }
        const cuts = new Set();
        ln.heads.forEach(h => (h.dataset.cuts || '').split(',').filter(Boolean).forEach(c => cuts.add(+c)));
        for (let r = 0; r < ROWS; r++) {
          const m = top - r, iv = ((m - tonicPc) % 12 + 12) % 12, d = MAJOR.indexOf(iv);
          ln.gut[r].textContent = d >= 0 ? String(d + 1) : '';
          ln.gut[r].className = 'roll-deg' + (d >= 0 ? ' scale' : '');
          for (let v = 0; v < ln.VCOLS; v++) {
            const el = ln.cells[r][v], g = v + ln.OFF, vis = ln.visible(v);
            const on = vis && noteAt(m, g);
            el.classList.toggle('hide', !vis);
            el.classList.toggle('scale', vis && d >= 0);
            el.classList.toggle('oct', iv === 0);
            el.classList.toggle('halfstart', cuts.has(v));
            el.classList.toggle('on', on);
            el.classList.toggle('split', on && cutAt(m, g));
            el.classList.toggle('clash', on && clashes(m, g));
            el.textContent = on && isStart(m, g) ? labelFor(m, g) : '';
          }
        }
      });
    }

    function render() {
      renderSlots();
      paint();
      updateNames();
      clearBtn.disabled = !slots.some(b => b.length);
      save();
    }

    // ---- 再生（8分音符ごとに先読み予約） ----------------------------------------------
    const stepSec = () => 60 / bpm / 2;
    let bus = null, timer = null, raf = null, startAt = 0, lastCol = -1, voiced = null, voicedFor = '';
    function voicing(seq) {
      const key = seq.map(s => s.name).join('-') + '@' + tonicPc;
      if (key !== voicedFor) { voiced = seq.length ? window.Voicing.voice(seq.map(s => s.name), tonicPc) : []; voicedFor = key; }
      return voiced;
    }
    function scheduleStep(n, at, out) {
      const rel = at - audio().currentTime, g = n % TOTAL;
      const seq = segments(), v = voicing(seq);
      seq.forEach((s, k) => {
        if (s.start !== g) return;
        const dur = s.len * stepSec() * 0.95;
        v[k].upper.forEach(x => tone(x, rel, dur, 0.075, out));
        tone(v[k].bass, rel, dur, 0.13, out);
        tone(v[k].bass + 12, rel, dur, 0.065, out);
      });
      const top = HIGH();
      for (let m = top - ROWS + 1; m <= top; m++) if (isStart(m, g)) tone(m, rel, noteLen(m, g) * stepSec() * 0.95, 0.2, out);
    }
    function markCol(g) {
      if (g === lastCol) return;
      lanes.forEach(ln => ln.byCol.forEach(col => col.forEach(el => el.classList.remove('now'))));
      cellEls.forEach(cs => (cs || []).forEach(el => el.classList.remove('now')));
      if (g >= 0) {
        lanes.forEach(ln => { const v = g - ln.OFF; if (v >= 0 && v < ln.VCOLS && ln.visible(v)) ln.byCol[v].forEach(el => el.classList.add('now')); });
        const sg = segAt(g);
        if (sg) { const cs = cellEls[sg.bar] || []; const el = cs.length > 1 ? cs[sg.sub] : cs[0]; if (el) el.classList.add('now'); }
      }
      lastCol = g;
    }
    function stop() {
      if (timer) { clearTimeout(timer); timer = null; }
      if (raf) { cancelAnimationFrame(raf); raf = null; }
      if (bus) {
        const b = bus; bus = null;
        try { b.gain.cancelScheduledValues(ac.currentTime); b.gain.setTargetAtTime(0, ac.currentTime, 0.02); } catch (e) {}
        setTimeout(() => { try { b.disconnect(); } catch (e) {} }, 400);
      }
      markCol(-1);
      playBtn.textContent = '鳴らす';
    }
    function start() {
      stop();
      const c = audio(), b = c.createGain();
      b.gain.value = 1; b.connect(c.destination); bus = b;
      startAt = c.currentTime + 0.08;
      let next = 0;
      (function tick() {
        if (bus !== b) return;
        const step = stepSec(), horizon = c.currentTime + SCHED_AHEAD;
        while (startAt + next * step < horizon) {
          const at = startAt + next * step;
          if (at >= c.currentTime - 0.02) scheduleStep(next, at, b);
          next++;
        }
        timer = setTimeout(tick, TICK_MS);
      })();
      (function follow() {
        if (bus !== b) return;
        const el = c.currentTime - startAt;
        markCol(el < 0 ? -1 : Math.floor((el % (TOTAL * stepSec())) / stepSec()));
        raf = requestAnimationFrame(follow);
      })();
      playBtn.textContent = '止める';
    }
    playBtn.addEventListener('click', () => (bus ? stop() : start()));

    keySel.value = String(tonicPc);
    bpmSel.value = String(bpm);
    keySel.addEventListener('change', () => { tonicPc = +keySel.value; render(); });
    bpmSel.addEventListener('change', () => { bpm = +bpmSel.value; save(); if (bus) start(); });
    clearBtn.addEventListener('click', () => { slots = Array.from({ length: BODY }, () => []); render(); say('コードを消した。'); });

    // ---- 実音のコードネーム（Logic のコード入力用。prog/ と同じ表記） ---------------------
    const LETTERS = 'CDEFGAB', NAT = [0, 2, 4, 5, 7, 9, 11];
    const ROMAN = { I: 0, II: 1, III: 2, IV: 3, V: 4, VI: 5, VII: 6 };
    const NUMERAL_RE = /^([#♭]?)(VII|VI|V|IV|III|II|I)(.*)$/;
    const FLAT_KEYS = [1, 3, 5, 6, 8, 10];
    const SHARP_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];
    const FLAT_NAMES = ['C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'B'];
    const LOGIC_QUALITY = { 'M7': 'maj7', 'm7-5': 'm7b5', 'm-5': 'dim' };
    function spell(deg, acc) {
      const li = (LETTERS.indexOf(KEYS[tonicPc][0]) + deg) % 7;
      const pc = (tonicPc + MAJOR[deg] + acc + 12) % 12;
      const d = (((pc - NAT[li]) % 12) + 18) % 12 - 6;
      const nm = LETTERS[li] + (d > 0 ? '#'.repeat(d) : 'b'.repeat(-d));
      if (Math.abs(d) <= 1 && ['Cb', 'E#', 'B#', 'Fb'].indexOf(nm) < 0) return nm;
      return (FLAT_KEYS.indexOf(tonicPc) >= 0 ? FLAT_NAMES : SHARP_NAMES)[pc];
    }
    function realName(name) {
      const m = NUMERAL_RE.exec(name);
      if (!m) return name;
      return spell(ROMAN[m[2]], m[1] === '#' ? 1 : m[1] === '♭' ? -1 : 0) + (m[3] in LOGIC_QUALITY ? LOGIC_QUALITY[m[3]] : m[3]);
    }
    function namesText() {
      let last = BODY - 1;
      while (last >= 0 && !slots[last].length) last--;
      return slots.slice(0, last + 1).map(bar => (bar.length ? bar.map(realName).join(' ') : 'N.C.')).join(' | ');
    }
    function updateNames() {
      const t = namesText();
      namesOut.textContent = t;
      copyBtn.disabled = !t;
    }
    copyBtn.addEventListener('click', () => {
      const t = namesText();
      if (!t) return;
      const done = () => { copyBtn.textContent = 'コピーした'; setTimeout(() => { copyBtn.textContent = 'コピー'; }, 1200); };
      const fallback = () => {
        const r = document.createRange(); r.selectNodeContents(namesOut);
        const sel = getSelection(); sel.removeAllRanges(); sel.addRange(r);
        try { document.execCommand('copy'); } catch (err) {}
        done();
      };
      try { navigator.clipboard.writeText(t).then(done, fallback); } catch (e) { fallback(); }
    });

    // ---- MIDI（format 1・480分解能・コードとメロの2トラック。弱起の小節から） ---------------
    function vlq(n) {
      const out = [n & 127];
      n = Math.floor(n / 128);
      while (n > 0) { out.unshift((n & 127) | 128); n = Math.floor(n / 128); }
      return out;
    }
    const TPQ = 480, STEP_T = TPQ / 2, GAP = 20;
    function track(head, ev) {
      ev.sort((a, b) => a.t - b.t);
      const bytes = [];
      let last = 0;
      const push = (t, b) => { bytes.push.apply(bytes, vlq(t - last).concat(b)); last = t; };
      head.forEach(h => push(0, h));
      ev.forEach(e => push(e.t, e.b));
      push(TOTAL * STEP_T, [0xFF, 0x2F, 0x00]);
      const len = bytes.length;
      return [0x4D, 0x54, 0x72, 0x6B, (len >> 24) & 255, (len >> 16) & 255, (len >> 8) & 255, len & 255].concat(bytes);
    }
    const nameMeta = s => [0xFF, 0x03, s.length].concat(Array.from(s, ch => ch.charCodeAt(0)));
    function midiBytes() {
      const us = Math.round(60000000 / bpm);
      const seq = segments(), v = voicing(seq), cev = [], mev = [];
      seq.forEach((s, k) => {
        const t0 = s.start * STEP_T, len = s.len * STEP_T, list = [v[k].bass].concat(v[k].upper);
        list.forEach(n => cev.push({ t: t0, b: [0x90, n, n === v[k].bass ? 92 : 78] }));
        list.forEach(n => cev.push({ t: t0 + len - GAP, b: [0x80, n, 0] }));
      });
      const top = HIGH();
      for (let m = top - ROWS + 1; m <= top; m++) for (let g = 0; g < TOTAL; g++) {
        if (!isStart(m, g)) continue;
        mev.push({ t: g * STEP_T, b: [0x91, m, 96] });
        mev.push({ t: (g + noteLen(m, g)) * STEP_T - GAP, b: [0x81, m, 0] });
      }
      const t0 = track([[0xFF, 0x51, 0x03, (us >> 16) & 255, (us >> 8) & 255, us & 255], [0xFF, 0x58, 0x04, 4, 2, 24, 8], nameMeta('Chords')], cev);
      const t1 = track([nameMeta('Melody')], mev);
      return new Uint8Array([0x4D, 0x54, 0x68, 0x64, 0, 0, 0, 6, 0, 1, 0, 2, (TPQ >> 8) & 255, TPQ & 255].concat(t0, t1));
    }
    dlBtn.addEventListener('click', () => {
      const a = document.createElement('a');
      a.href = URL.createObjectURL(new Blob([midiBytes()], { type: 'audio/midi' }));
      a.download = fileName + '_' + FILE_KEYS[tonicPc] + '_' + bpm + 'bpm.mid';
      a.click();
      setTimeout(() => URL.revokeObjectURL(a.href), 1000);
      say('ダウンロードした。DAWのトラックにドラッグ。');
    });

    say(HINT);
    render();
  }
})();
