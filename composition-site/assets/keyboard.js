/* 鍵盤ウィジェット（composition-src/build.py が生成）
   原稿に書いた {{interval}} / {{scale}} の置き場（<div data-widget="…">）を中身で埋める。
   - interval（段階2）：選んだキーの1度からオク上までの13鍵に度数名。押すと1度→その音
   - scale（段階3）：選んだキーのメジャースケール7音に番号。押すと主和音の上でその音
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
  function build(root) {
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
    for (let m = LOW; m <= HIGH; m++) if (WHITE.indexOf(m % 12) >= 0) nWhite++;
    const w = 100 / nWhite;
    let wi = 0;
    for (let m = LOW; m <= HIGH; m++) {
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
    // 中心（主和音）を鳴らしたまま、その音を重ねる。キャラは中心があって初めて聴こえる
    w.kb.addEventListener('pointerdown', e => {
      const el = e.target.closest('.iv-key');
      if (!el) return;
      const m = +el.dataset.midi, d = degOf(m);
      if (d < 0) return;
      e.preventDefault();
      // 主和音（C2｜E3 G3 C4 をキーの分だけ上げる）を鳴らしてから、その音。
      // キーごとに組み直すと、度数と和音の当たり方がキーで変わる（Cキーだと4が3とぶつからない）
      const s = w.state.tonicPc, I0 = window.Voicing.voice(['I'], 0, { lo: 50, hi: 62, center: 56 })[0];
      tone(I0.bass + s, 0, 1.4, 0.1);
      I0.upper.forEach(n => tone(n + s, 0, 1.4, 0.06));
      tone(m, 0.15, 1.1, 0.22);
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
  // 段階4：ダイアトニックコード（4和音）。キーを選ぶとボタンの下に実音のコード名。押すと鳴って、鍵盤のコードトーンが光る
  const DIATONIC = [['IM7', 'M7'], ['IIm7', 'm7'], ['IIIm7', 'm7'], ['IVM7', 'M7'], ['V7', '7'], ['VIm7', 'm7'], ['VIIm7-5', 'm7-5']];
  const LETTERS = 'CDEFGAB', NAT = [0, 2, 4, 5, 7, 9, 11];
  // キーの i 番目（0＝1度）の音名。キー名の文字から順に数えるので、E♭キーの4は A♭、Bキーの7は A#
  function noteName(k, i) {
    const li = (LETTERS.indexOf(KEYS[k][0]) + i) % 7;
    const d = (((k + MAJOR[i] - NAT[li]) % 12) + 18) % 12 - 6;
    return LETTERS[li] + (d > 0 ? '#'.repeat(d) : '♭'.repeat(-d));
  }
  function setupDiatonic(root) {
    const w = build(root);
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
    // コードトーンは、ルートを下のオクターブに置いて積む（どのキーでも鍵盤に収まる）
    function light() {
      const k = w.state.tonicPc;
      const lit = {};
      let rootM = -1;
      if (cur !== null) {
        rootM = LOW + (k + MAJOR[cur]) % 12;
        [0, 2, 4, 6].forEach(s => { lit[rootM + MAJOR[(cur + s) % 7] - MAJOR[cur] + (cur + s >= 7 ? 12 : 0)] = true; });
      }
      w.keys.forEach(el => {
        const m = +el.dataset.midi;
        el.classList.toggle('lit', !!lit[m]);
        el.classList.toggle('croot', m === rootM);
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

  const els = document.querySelectorAll('[data-widget]');
  for (let i = 0; i < els.length; i++) {
    const kind = els[i].dataset.widget;
    if (kind === 'interval') setupInterval(els[i]);
    else if (kind === 'scale') setupScale(els[i]);
    else if (kind === 'chords') setupChords(els[i]);
    else if (kind === 'diatonic') setupDiatonic(els[i]);
  }
})();
