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
  function tone(midi, at, dur, vol) {
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
    g.connect(lp).connect(c.destination);
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
    return { top, sel, kb, keys, status, rows, state, hl, flash, tonic: () => LOW + state.tonicPc };
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
      [0, 4, 7].forEach(iv => tone(w.tonic() - 12 + iv, 0, 1.4, 0.09));
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

  const els = document.querySelectorAll('[data-widget]');
  for (let i = 0; i < els.length; i++) {
    const kind = els[i].dataset.widget;
    if (kind === 'interval') setupInterval(els[i]);
    else if (kind === 'scale') setupScale(els[i]);
  }
})();
