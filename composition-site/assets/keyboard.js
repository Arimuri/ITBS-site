/* 鍵盤ウィジェット（composition-src/build.py が生成）
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
  const DIATONIC = [['Imaj7', 'maj7'], ['IIm7', 'm7'], ['IIIm7', 'm7'], ['IVmaj7', 'maj7'], ['V7', '7'], ['VIm7', 'm7'], ['VIIm7-5', 'm7-5']];
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
          // 色分けは tier1 のダイアトニックだけ。Imaj7→I、IIm7→IIm、VIIm7-5→VIIm-5 のように7thを外して照らす
          const triad = name.replace(/m7-5$|maj7$|M7$|7$/, s => (s === 'm7-5' ? 'm-5' : ''));
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
    const PM = ['Imaj7', 'IIm7', 'IIIm7', 'IVmaj7', 'V7', 'VIm7', 'VIIm7-5'];
    const init = (root.dataset.prog || 'IVmaj7-IIIm7-IIm7-Imaj7').split('-').map(x => x.replace(/M7$/, 'maj7'));
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

  // 進行の再生（中級編の {{play}}）。data-progs="ラベル=IIm7 V7 Imaj7|IIm7 ♭II7 Imaj7"
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
