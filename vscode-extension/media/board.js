// Raspberry Pi 5 board view: draws the board, wires peripherals to ports, shows live state.
(function () {
  const vscode = acquireVsCodeApi();
  const NS = 'http://www.w3.org/2000/svg';
  const svg = document.getElementById('board');
  const statusEl = document.getElementById('status');

  // Port positions in board coordinates (viewBox 560x470, board at 20,20 520x340).
  // `name` disambiguates ports that share a printed label in the search results.
  const PORTS = {
    gpio_header: { x: 58, y: 26, w: 306, h: 34, label: 'GPIO J8' },
    usb2_0: { x: 470, y: 40, w: 78, h: 40, label: 'USB 2.0', name: 'USB 2.0 (top)' },
    usb2_1: { x: 470, y: 82, w: 78, h: 40, label: 'USB 2.0', name: 'USB 2.0 (bottom)' },
    usb3_0: { x: 470, y: 132, w: 78, h: 40, label: 'USB 3.0', name: 'USB 3.0 (top)' },
    usb3_1: { x: 470, y: 174, w: 78, h: 40, label: 'USB 3.0', name: 'USB 3.0 (bottom)' },
    eth: { x: 462, y: 232, w: 86, h: 88, label: 'RJ45' },
    cam1: { x: 322, y: 268, w: 16, h: 86, label: 'CAM/DISP 1' },
    cam0: { x: 352, y: 268, w: 16, h: 86, label: 'CAM/DISP 0' },
    pcie: { x: 22, y: 120, w: 16, h: 110, label: 'PCIe' },
    usbc: { x: 56, y: 330, w: 44, h: 34, label: 'USB-C' },
    hdmi0: { x: 160, y: 334, w: 40, h: 28, label: 'HDMI0' },
    hdmi1: { x: 254, y: 334, w: 40, h: 28, label: 'HDMI1' },
    uart: { x: 214, y: 336, w: 24, h: 16, label: 'UART' },
    fan: { x: 378, y: 28, w: 18, h: 22, label: 'FAN' },
  };
  const PIN_COLORS = { power: '#e8344e', ground: '#222', SDA1: '#2f6fe0', SCL1: '#2f6fe0', TXD0: '#8a4fe0', RXD0: '#8a4fe0', ID_SD: '#7a7f88', ID_SC: '#7a7f88', PWM0: '#c9a227', PWM1: '#c9a227' };
  const pinColor = (name, fn) => name === '3V3' ? '#f08a24' : PIN_COLORS[fn] || (fn.startsWith('SPI') ? '#e04fb0' : fn.startsWith('PCM') ? '#1aa8a8' : fn === 'GPCLK0' ? '#2fbf71' : '#2fbf71');

  let state = { links: {}, gpio: {}, running: false, peripherals: {}, j8: {} };
  let local = (vscode.getState() || {}).links || {};
  // Extra words each component can be found by.
  const KEYWORDS = {
    pirate_audio: 'mic microphone audio hat screen display buttons pimoroni',
    usb_speaker: 'speaker sound audio usb output',
    imx519: 'camera cam arducam imx519 16mp autofocus csi mipi picamera',
  };
  const portName = (port) => PORTS[port].name || PORTS[port].label;

  const el = (tag, attrs, parent) => {
    const e = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs || {})) e.setAttribute(k, v);
    if (parent) parent.appendChild(e);
    return e;
  };
  const text = (x, y, s, cls, parent) => { const t = el('text', { x, y, class: cls }, parent); t.textContent = s; return t; };
  const setStatus = (msg, kind) => { statusEl.textContent = msg; statusEl.className = 'status ' + (kind || ''); };

  function draw() {
    svg.textContent = '';
    // PCB
    el('rect', { x: 20, y: 20, width: 520, height: 340, rx: 16, fill: 'var(--pcb)', stroke: 'var(--pcb-edge)', 'stroke-width': 3 }, svg);
    for (const [x, y] of [[44, 44], [394, 44], [44, 336], [394, 336]]) {
      el('circle', { cx: x, cy: y, r: 9, fill: '#e9e2c8' }, svg);
      el('circle', { cx: x, cy: y, r: 5, fill: 'var(--vscode-sideBar-background, #1e1e1e)' }, svg);
    }
    // Chips
    const chip = (x, y, w, h, fill, lines) => {
      el('rect', { x, y, width: w, height: h, rx: 3, fill }, svg);
      lines.forEach((l, i) => {
        const t = text(x + w / 2, y + h / 2 + (i - (lines.length - 1) / 2) * 11, l, 'chip-label', svg);
        t.setAttribute('text-anchor', 'middle');
        if (fill === 'var(--metal)') t.setAttribute('fill', '#2a2d33'); // dark text on metal shields
      });
    };
    chip(70, 70, 70, 50, 'var(--metal)', ['Wi-Fi/BT']);
    chip(185, 95, 95, 70, 'var(--chip)', ['LPDDR4X', '16 GB']);
    chip(205, 190, 80, 80, 'var(--metal)', ['BCM2712']);
    chip(310, 120, 70, 70, 'var(--chip)', ['RP1']);
    chip(390, 210, 34, 30, 'var(--chip)', ['PHY']);
    chip(110, 230, 46, 46, 'var(--chip)', ['PMIC']);
    // Connector bodies
    const body = (p, fill) => el('rect', { x: p.x, y: p.y, width: p.w, height: p.h, rx: 2, fill }, svg);
    ['usb2_0', 'usb2_1', 'usb3_0', 'usb3_1', 'eth'].forEach((k) => body(PORTS[k], 'var(--metal)'));
    ['usb2_0', 'usb2_1'].forEach((k) => el('rect', { x: PORTS[k].x + 10, y: PORTS[k].y + 16, width: 58, height: 8, fill: '#111' }, svg));
    ['usb3_0', 'usb3_1'].forEach((k) => el('rect', { x: PORTS[k].x + 10, y: PORTS[k].y + 16, width: 58, height: 8, fill: '#2f6fe0' }, svg));
    ['cam0', 'cam1', 'pcie'].forEach((k) => body(PORTS[k], '#d9b45a'));
    ['usbc', 'hdmi0', 'hdmi1'].forEach((k) => body(PORTS[k], 'var(--metal)'));
    body(PORTS.uart, '#f1f1f1');
    body(PORTS.fan, '#f1f1f1');
    el('rect', { x: 400, y: 280, width: 26, height: 26, rx: 2, fill: '#111' }, svg); // PoE header
    for (const k of ['usb2_0', 'usb3_0', 'eth', 'cam1', 'cam0', 'pcie', 'usbc', 'hdmi0', 'hdmi1', 'fan']) {
      const p = PORTS[k];
      const vertical = p.h > p.w * 2.5;
      const t = text(p.x + p.w / 2, vertical ? p.y + p.h / 2 : p.y - 3, p.label, 'label', svg);
      t.setAttribute('text-anchor', 'middle');
      if (vertical) t.setAttribute('transform', `rotate(-90 ${p.x + p.w / 2} ${p.y + p.h / 2})`);
    }
    // LEDs
    el('circle', { cx: 40, cy: 298, r: 4, fill: '#ff3b3b' }, svg);
    el('circle', { cx: 40, cy: 312, r: 4, fill: '#174d2c', class: 'led-act' + (state.running ? ' on' : '') , id: 'act' }, svg);
    text(50, 301, 'PWR', 'label', svg);
    text(50, 315, 'ACT', 'label', svg);
    // GPIO pins: odd pins on the inner row, pin 1 at the left
    for (const [num, [name, fn]] of Object.entries(state.j8)) {
      const n = Number(num);
      const col = Math.floor((n - 1) / 2);
      const cx = 66 + col * 15;
      const cy = n % 2 ? 51 : 36;
      const gpio = name.startsWith('GPIO') ? state.gpio[name.slice(4)] : null;
      const shape = n === 1 ? el('rect', { x: cx - 5, y: cy - 5, width: 10, height: 10 }, svg) : el('circle', { cx, cy, r: 5 }, svg);
      shape.setAttribute('fill', pinColor(name, fn));
      shape.setAttribute('class', 'pin' + (gpio && gpio.level ? ' high' : ''));
      const title = el('title', {}, shape);
      title.textContent = `Pin ${n} · ${name}${fn && fn !== 'power' && fn !== 'ground' ? ' (' + fn + ')' : ''}${gpio ? ' · ' + (gpio.mode === 'op' ? 'output ' : 'input ') + (gpio.level ? 'high' : 'low') : ''}`;
    }
    drawAttached();
  }

  function drawAttached() {
    const links = state.links;
    if (links.pirate_audio) {
      el('rect', { x: 54, y: 22, width: 200, height: 150, rx: 6, fill: 'rgba(20,20,20,.82)', stroke: '#888' }, svg);
      el('rect', { x: 110, y: 70, width: 80, height: 80, fill: '#000', stroke: '#444' }, svg);
      text(154, 64, 'Pirate Audio', 'label', svg).setAttribute('text-anchor', 'middle');
    }
    if (links.usb_speaker) {
      const p = PORTS[links.usb_speaker];
      el('rect', { x: p.x + p.w - 6, y: p.y + 10, width: 12, height: 20, fill: '#333' }, svg);
      text(p.x + p.w - 30, p.y + 36, 'Speaker', 'label', svg);
    }
    if (links.imx519) {
      const p = PORTS[links.imx519];
      const mx = p.x + p.w / 2;
      el('rect', { x: mx - 7, y: p.y + p.h - 6, width: 14, height: 70, fill: '#f0a020', opacity: .95 }, svg);
      el('rect', { x: mx - 32, y: 410, width: 64, height: 56, rx: 4, fill: '#1f9a55' }, svg);
      el('rect', { x: mx - 14, y: 418, width: 28, height: 28, fill: '#b8bcc4' }, svg);
      el('circle', { cx: mx, cy: 432, r: 10, fill: '#111' }, svg);
      el('circle', { cx: mx - 3, cy: 429, r: 3, fill: '#3a5a7a' }, svg);
      text(mx + 36, 440, 'IMX519', 'label', svg).setAttribute('fill', 'var(--vscode-foreground)');
    }
  }

  const canPlug = (periph, port) => periph && (state.peripherals[periph] || [null, []])[1].includes(port) && !Object.entries(state.links).some(([k, v]) => v === port && k !== periph);

  function plug(periph, port) {
    sendWiring({ ...local, [periph]: port });
    setStatus(`${state.peripherals[periph][0]} connected to ${portName(port)}.`, 'ok');
  }

  function sendWiring(links) {
    local = links;
    vscode.setState({ links });
    vscode.postMessage({ t: 'wiring', links });
  }

  // ---------- search bar: one result per (component, free compatible port) ----------
  const search = document.getElementById('search');
  const results = document.getElementById('results');
  let matches = [];
  let active = 0;

  function findMatches(query) {
    const words = query.toLowerCase().split(/\s+/).filter(Boolean);
    const out = [];
    for (const [id, [name, ports]] of Object.entries(state.peripherals)) {
      if (state.links[id]) continue; // already connected: unplug it first
      for (const port of ports) {
        if (!canPlug(id, port)) continue;
        const hay = `${name} ${KEYWORDS[id] || ''} ${portName(port)}`.toLowerCase();
        if (words.every((w) => hay.includes(w))) out.push({ id, port, name });
      }
    }
    return out;
  }

  function renderResults() {
    matches = findMatches(search.value);
    active = Math.min(active, Math.max(0, matches.length - 1));
    results.textContent = '';
    const open = document.activeElement === search;
    results.hidden = !open;
    search.setAttribute('aria-expanded', String(open));
    if (!open) return;
    if (!matches.length) {
      const li = document.createElement('li');
      li.className = 'empty';
      li.textContent = Object.values(state.links).every(Boolean) ? 'Everything is connected.' : 'No matching component or free port.';
      results.appendChild(li);
      return;
    }
    matches.forEach((m, i) => {
      const li = document.createElement('li');
      li.id = `result-${i}`;
      li.setAttribute('role', 'option');
      li.setAttribute('aria-selected', String(i === active));
      li.innerHTML = '<span class="r-name"></span><span class="r-port"></span>';
      li.firstChild.textContent = m.name;
      li.lastChild.textContent = `→ ${portName(m.port)}`;
      li.addEventListener('mousedown', (e) => { e.preventDefault(); choose(i); }); // before the input blurs
      li.addEventListener('mousemove', () => { if (active !== i) { active = i; renderResults(); } });
      results.appendChild(li);
    });
    search.setAttribute('aria-activedescendant', `result-${active}`);
  }

  function choose(i) {
    const m = matches[i];
    if (!m) return;
    plug(m.id, m.port);
    search.value = '';
    active = 0;
    search.blur();
    renderResults();
  }

  search.addEventListener('input', () => { active = 0; renderResults(); });
  search.addEventListener('focus', renderResults);
  search.addEventListener('blur', renderResults);
  search.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      if (matches.length) active = (active + (e.key === 'ArrowDown' ? 1 : matches.length - 1)) % matches.length;
      renderResults();
    } else if (e.key === 'Enter') {
      e.preventDefault();
      choose(active);
    } else if (e.key === 'Escape') {
      search.value = '';
      search.blur();
    }
  });

  function renderAttached() {
    const box = document.getElementById('attached');
    box.textContent = '';
    for (const [id, port] of Object.entries(state.links)) {
      if (!port) continue;
      const row = document.createElement('div');
      row.className = 'attached-row';
      row.textContent = `${state.peripherals[id][0]} → ${portName(port)}`;
      const b = document.createElement('button');
      b.className = 'secondary';
      b.textContent = 'Unplug';
      b.addEventListener('click', () => { sendWiring({ ...local, [id]: null }); setStatus(''); });
      row.appendChild(b);
      box.appendChild(row);
    }
    document.getElementById('pirate').hidden = !state.links.pirate_audio;
    document.getElementById('camera').hidden = !state.links.imx519;
  }

  // Pirate Audio buttons: hold to press
  document.querySelectorAll('[data-btn]').forEach((b) => {
    const send = (down) => { b.classList.toggle('down', down); vscode.postMessage({ t: 'button', btn: b.dataset.btn, down }); };
    b.addEventListener('pointerdown', () => send(true));
    b.addEventListener('pointerup', () => send(false));
    b.addEventListener('pointerleave', () => b.classList.contains('down') && send(false));
    b.addEventListener('keydown', (e) => { if (e.key === ' ' || e.key === 'Enter') send(true); });
    b.addEventListener('keyup', (e) => { if (e.key === ' ' || e.key === 'Enter') send(false); });
  });
  document.getElementById('open-terminal').addEventListener('click', () => vscode.postMessage({ t: 'openTerminal' }));

  window.addEventListener('message', ({ data: msg }) => {
    if (msg.t === 'state') {
      state = msg;
      renderResults();
      renderAttached();
      draw();
    } else if (msg.t === 'started') {
      // A fresh backend: restore this view's wiring.
      if (Object.values(local).some(Boolean)) vscode.postMessage({ t: 'wiring', links: local });
      vscode.postMessage({ t: 'hello' });
    } else if (msg.t === 'screen') {
      const s = document.getElementById('pa-screen');
      s.textContent = msg.text;
      s.style.color = msg.color;
    } else if (msg.t === 'frame') {
      const img = document.getElementById('cam-img');
      img.src = 'data:image/jpeg;base64,' + msg.jpg;
      img.hidden = false;
      const af = ['idle', 'scanning', 'focused'][msg.af] || '';
      document.getElementById('cam-info').textContent = `Source: ${msg.source} · lens ${msg.lens} · AF ${af}`;
    } else if (msg.t === 'exit') {
      setStatus('Simulator stopped. Open the terminal to start it again.', 'bad');
    }
  });

  setInterval(() => { const a = document.getElementById('act'); if (a && state.running) a.classList.toggle('on'); }, 250);
  vscode.postMessage({ t: 'hello' });
})();
