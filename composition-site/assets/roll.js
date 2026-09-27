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
    trLabel.appendChild(mk('span', '', ' メロも移調'));
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
      noteEl.textContent = '濃い行＝スケール、番号が濃い行＝解禁音。横1マス＝8分音符、太線＝小節。';
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
    // 伴奏のボイシングは、進行かキーが変わったときだけ組み直す。
    // Cキーで組んだものをメロと同じ量（keyOffset）だけ平行移動する。
    // キーごとに組み直すと転回形が変わり、「数字は同じで高さだけ変わる」が音で崩れる
    let voiced = null, voicedFor = '';
    function voicing() {
      const key = prog.join('-') + '@' + tonicPc;
      if (key !== voicedFor) {
        const o = keyOffset(tonicPc);
        voiced = window.Voicing.voice(prog, 0).map(v => ({ bass: v.bass + o, upper: v.upper.map(m => m + o) }));
        voicedFor = key;
      }
      return voiced;
    }
    // 通し番号 n のステップ（8分音符1つ）を、時刻 at に予約する。
    // 予約の直前に notes を見るので、その時点で置いてある音がそのまま鳴る。
    function scheduleStep(n, at, out) {
      const c = audio(), rel = at - c.currentTime;
      const col = ((n % COLS) + COLS) % COLS;
      if (col % STEPS === 0) {                       // 小節のあたま：コードとベース
        const v = voicing()[(col / STEPS) % prog.length];
        const dur = STEPS * stepSec() * 0.96;
        v.upper.forEach(m => tone(m, rel, dur, 0.075, out));
        tone(v.bass, rel, dur, 0.13, out);
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
          warn = '音域が広すぎてこのキーに収まらない。狭めるか「メロも移調」を外す。';
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
