// ===== feature1.js =====
// Fully wired notifications + scan flow + device table actions

// ===== Config =====
const API_URL = 'http://127.0.0.1:5000/run-script'; // Flask endpoint

// ===== Tabs helper
function switchToDevices(){ 
  const el = document.getElementById('tab-devices');
  if (el) el.checked = true; 
}

// ===== Elements
const overlay = document.getElementById('matrixOverlay');
const canvas = document.getElementById('matrixCanvas');
const ctx = canvas ? canvas.getContext('2d') : null;
const textEl = document.getElementById('matrixText');
const scanOutput = document.getElementById('scanOutput'); // optional
const brandDiv = document.querySelector('.brand');

let columns = [], drops = [], rafId = null, running = false;
let pendingOutput = "Waiting for scan...";
let loadingInterval = null;

// ===== Notification (GLOBAL and reusable)
function _createScanNotificationEl(){
  // create a small toast element matching the visual style used in the HTML
  const note = document.createElement('div');
  note.id = 'scanNotification';
  note.style.cssText = [
    'display:none',
    'position:fixed',
    'top:28px',
    'right:32px',
    'z-index:10010',
    'background:#0f141b',
    'color:#00e5ff',
    'border-radius:10px',
    'box-shadow:0 2px 18px rgba(0,229,255,.13)',
    'padding:12px 18px',
    'font-weight:600',
    'font-size:14px',
    'max-width:320px',
    'word-break:break-word'
  ].join(';');
  document.body.appendChild(note);
  return note;
}

function showScanNotification(msg){
  let note = document.getElementById('scanNotification');
  if (!note){
    // body should exist by the time buttons are clicked; create element as a fallback
    note = _createScanNotificationEl();
  }
  note.textContent = msg;
  note.style.display = 'block';
  // clear any existing hide timer stored on the element
  if (note._hideTimer) clearTimeout(note._hideTimer);
  note._hideTimer = setTimeout(()=>{ note.style.display = 'none'; note._hideTimer = null; }, 4000);
}
window.showScanNotification = showScanNotification; // expose globally for console/other scripts

// ===== Shield status (top-left) =====
function _setShieldVisual(status){
  // status: 'green' | 'yellow' | 'red'
  const el = document.querySelector('.cube');
  if (!el) return;
  // base styles to tweak
  const styles = {
    green: { border: '1px solid rgba(8,247,111,.45)', boxShadow: '0 0 18px rgba(8,247,111,.25), inset 0 0 30px rgba(8,247,111,.10)', background: 'linear-gradient(135deg, rgba(8,247,111,.08), rgba(0,0,0,.12))' },
    yellow: { border: '1px solid rgba(255,193,77,.45)', boxShadow: '0 0 18px rgba(255,193,77,.18), inset 0 0 30px rgba(255,193,77,.06)', background: 'linear-gradient(135deg, rgba(255,193,77,.06), rgba(0,0,0,.12))' },
    red: { border: '1px solid rgba(255,73,118,.45)', boxShadow: '0 0 18px rgba(255,73,118,.22), inset 0 0 30px rgba(255,73,118,.06)', background: 'linear-gradient(135deg, rgba(255,73,118,.06), rgba(0,0,0,.12))' }
  };
  const s = styles[status] || styles.yellow;
  el.style.border = s.border;
  el.style.boxShadow = s.boxShadow;
  el.style.background = s.background;
  // small aria-label update for screen readers
  el.setAttribute('aria-label', `Network status: ${status}`);
}

// (previous saucer/mascot code removed)

function updateShieldStatus(devices){
  try{
    const regMap = loadRegisteredDevices();
    if (!devices || !Array.isArray(devices) || devices.length === 0){
      _setShieldVisual('yellow');
      return;
    }
  const total = devices.length;
  // normalize MAC addresses to lowercase for comparison
  const regMacs = new Set(Object.keys(regMap || {}).map(m => m ? m.toLowerCase() : m));
  const unreg = devices.filter(d => { const mac = (d.mac || '').toLowerCase(); return !regMacs.has(mac); }).length;
    let status = 'green';
    if (unreg === 0) status = 'green';
    else if (unreg / total >= 0.5) status = 'red';
    else status = 'yellow';
    _setShieldVisual(status);
  }catch(e){
    // on error, fallback to yellow
    _setShieldVisual('yellow');
  }
}

// ===== Matrix animation helpers (optional)
function sizeCanvas(){
  if (!canvas || !ctx) return;
  const dpr = Math.max(1, Math.min(2, window.devicePixelRatio || 1));
  canvas.width = Math.floor(canvas.clientWidth * dpr);
  canvas.height = Math.floor(canvas.clientHeight * dpr);
  ctx.setTransform(dpr,0,0,dpr,0,0);
  const columnWidth = 16;
  columns = Math.ceil(canvas.clientWidth / columnWidth);
  drops = new Array(columns).fill(0).map(()=> Math.floor(Math.random()*canvas.clientHeight));
}

function drawMatrix(){
  if (!ctx || !canvas) return;
  ctx.fillStyle = "rgba(0, 0, 0, 0.08)";
  ctx.fillRect(0, 0, canvas.clientWidth, canvas.clientHeight);

  ctx.font = "16px monospace";
  for(let i=0;i<columns;i++){
    const char = String.fromCharCode(0x30A0 + Math.floor(Math.random()*96));
    const x = i*16;
    const y = drops[i]*16;
    ctx.fillStyle = "rgba(8, 247, 111, 0.9)";
    ctx.fillText(char, x, y);
    if (y > canvas.clientHeight && Math.random() > 0.975) drops[i] = 0;
    drops[i]++;
  }
  if (running) rafId = requestAnimationFrame(drawMatrix);
}

function showWord(word, visibleMs = 900){
  if (!textEl) return;
  textEl.textContent = word;
  textEl.classList.add('show');
  setTimeout(()=>textEl.classList.remove('show'), visibleMs);
}

// Loading pulse: small “Loading …” flashes while overlay is up
function startLoadingPulse(){
  stopLoadingPulse();
  setTimeout(()=> showWord('Loading ...'), 3000);
  loadingInterval = setInterval(()=> showWord('Loading ...'), 10000);
}
function stopLoadingPulse(){
  if (loadingInterval){
    clearInterval(loadingInterval);
    loadingInterval = null;
  }
}

function startTransition(){
  if (!overlay) return;
  overlay.style.display = 'block';
  sizeCanvas();
  running = true;
  drawMatrix();
  setTimeout(()=>showWord('HOME', 900), 600);
  setTimeout(()=>showWord('NET', 900), 1300);
  setTimeout(()=>showWord('SAFE', 900), 2000);
  startLoadingPulse();
}
function endTransition(){
  running = false;
  cancelAnimationFrame(rafId);
  stopLoadingPulse();
  if (overlay) overlay.style.display = 'none';
}

// ===== Registered devices (localStorage)
const REG_KEY = 'homenetsafe_registered_devices_v1';
function loadRegisteredDevices(){
  try{ const raw = localStorage.getItem(REG_KEY); return raw ? JSON.parse(raw) : {}; }catch{return {};}
}
function saveRegisteredDevices(obj){ localStorage.setItem(REG_KEY, JSON.stringify(obj)); }
function registerDevice(dev, customName, notes){
  const map = loadRegisteredDevices();
  map[dev.mac] = { ...dev, customName, notes, registeredAt: new Date().toISOString() };
  saveRegisteredDevices(map);
}
function unregisterDevice(mac){
  const map = loadRegisteredDevices();
  delete map[mac];
  saveRegisteredDevices(map);
}

// ===== Device table rendering
function renderDevices(devices){
  const tbody = document.getElementById('devicesBody');
  const failMsg = document.getElementById('scanFailMsg');
  const tableWrap = document.getElementById('devicesTableWrap');

  if (!devices || !Array.isArray(devices) || devices.length === 0){
    if (failMsg) failMsg.style.display = 'block';
    if (tableWrap) tableWrap.style.display = 'none';
    if (tbody) tbody.innerHTML = '';
    // ensure user gets feedback
    showScanNotification('Scan failed. No devices found.');
    return;
  }

  if (failMsg) failMsg.style.display = 'none';
  if (tableWrap) tableWrap.style.display = 'block';

  const regMap = loadRegisteredDevices();
  if (!tbody) return;

  tbody.innerHTML = devices.map(dev => {
    const reg = !!regMap[dev.mac];
    const statusLabel = reg ? 'Registered' : 'New';
    const statusColor = reg ? '#08f76f' : '#9fc9db';
    const registeredInfo = reg ? regMap[dev.mac] : null;
    return `
      <tr>
        <td style="text-align:center;color:${statusColor};font-weight:700;padding:12px 8px;border-bottom:1px solid var(--line);">${statusLabel}</td>
        <td style="text-align:left;padding:12px 8px;border-bottom:1px solid var(--line);">${registeredInfo?.customName || dev.name || ''}</td>
        <td style="text-align:center;padding:12px 8px;font-family:monospace;border-bottom:1px solid var(--line);">${dev.ip || ''}</td>
        <td style="text-align:center;padding:12px 8px;font-family:monospace;border-bottom:1px solid var(--line);">${dev.mac || ''}</td>
        <td style="text-align:left;padding:12px 8px;border-bottom:1px solid var(--line);">${dev.vendor || ''}</td>
        <td style="text-align:center;padding:12px 8px;border-bottom:1px solid var(--line);">${dev.first_seen || ''}</td>
        <td style="text-align:center;padding:12px 8px;border-bottom:1px solid var(--line);">${dev.last_seen || ''}</td>
        <td style="text-align:center;padding:12px 8px;border-bottom:1px solid var(--line);">
          ${reg ?
            `<button class="unregBtn" data-mac="${dev.mac}" style="padding:6px 10px;border-radius:8px;border:none;cursor:pointer;background:#666;color:var(--ink);font-weight:700;white-space:nowrap;">Unregister</button>`
            :
            `<button class="regBtn" data-mac="${dev.mac}" style="padding:6px 10px;border-radius:8px;border:none;cursor:pointer;background:var(--accent);color:#032c33;font-weight:700;white-space:nowrap;">Register</button>`
          }
        </td>
      </tr>
      ${registeredInfo?.notes ? `
      <tr>
        <td colspan="8" style="text-align:left;padding:12px 16px;background:rgba(0,229,255,.05);border-bottom:1px solid var(--line);">
          <div style="display:flex;align-items:center;gap:8px;">
            <strong style="color:var(--accent);">Notes:</strong>
            <span style="color:var(--muted);">${registeredInfo.notes}</span>
          </div>
        </td>
      </tr>` : ''}
    `;
  }).join('');

  // Register handlers
  Array.from(document.getElementsByClassName('regBtn')).forEach(btn => {
    btn.onclick = () => {
      const mac = btn.getAttribute('data-mac');
      const idx = devices.findIndex(d => d.mac === mac);
      if (idx > -1) {
        document.getElementById('regDeviceMac').value = devices[idx].mac;
        document.getElementById('regDeviceName').value = devices[idx].name || '';
        document.getElementById('regDeviceNotes').value = '';
        document.getElementById('registerModal').style.display = 'block';
      }
    };
  });

  // Unregister handlers
  Array.from(document.getElementsByClassName('unregBtn')).forEach(btn => {
    btn.onclick = () => {
      const mac = btn.getAttribute('data-mac');
      if (confirm('Are you sure you want to unregister this device?')) {
        unregisterDevice(mac);
        renderDevices(devices);
        showScanNotification('Device unregistered'); // <-- toast on unregister
      }
    };
  });

  // Registration form submit
  const regForm = document.getElementById('registerForm');
  if (regForm) {
    regForm.onsubmit = (e) => {
      e.preventDefault();
      const mac = document.getElementById('regDeviceMac').value;
      const customName = document.getElementById('regDeviceName').value;
      const notes = document.getElementById('regDeviceNotes').value;
      const idx = devices.findIndex(d => d.mac === mac);
      if (idx > -1) {
        registerDevice(devices[idx], customName, notes);
        document.getElementById('registerModal').style.display = 'none';
        renderDevices(devices);
        showScanNotification('Device registered'); // <-- toast on register
      }
    };
  }

  // success toast after render
  // update shield status based on discovered devices
  try { updateShieldStatus(devices); } catch (e) {}
  showScanNotification('Scan complete! Devices discovered.');
}

// ===== Backend call
async function runDeviceDiscovery(){
  // run device discovery via backend
  try {
    if (scanOutput) scanOutput.textContent = "Running scan...";
    const r = await fetch(API_URL, { method:'GET', mode:'cors', cache:'no-store' });
    if(!r.ok){
      const txt = await r.text().catch(()=> '');
      throw new Error(`HTTP ${r.status} ${r.statusText}${txt ? ' — ' + txt : ''}`);
    }
    const data = await r.json();
    let out = '';
    if (data && typeof data.stdout === 'string') out += data.stdout.trim();
    if (data && data.stderr && data.stderr.trim()) out += (out?'\n\n':'') + '[stderr]\n' + data.stderr.trim();
    if (data && data.devices) {
      pendingOutput = JSON.stringify(data.devices);
    } else {
      pendingOutput = out || "(no output)";
    }
  } catch (e) {
    pendingOutput = "Failed to contact server.\n" + e;
  } finally {
    // scan finished
  }
  return pendingOutput;
}

// ===== Auto-run on load + button for manual scan
window.addEventListener('load', async ()=>{
  // Add “Scan Network” button in header if not already present
  if (brandDiv && !brandDiv.querySelector('button[data-scan]')) {
    const scanButton = document.createElement('button');
    scanButton.dataset.scan = '1';
    scanButton.style.cssText = 'margin-left:16px;padding:8px 16px;border-radius:8px;background:var(--accent);color:#032c33;font-weight:700;border:none;cursor:pointer;';
    scanButton.textContent = 'Scan Network';
    scanButton.onclick = async () => {
      scanButton.disabled = true;
      scanButton.textContent = 'Scanning...';

      // immediate toast so user sees feedback right away
      showScanNotification('Scanning…');

      const result = await runDeviceDiscovery();
      let devices = [];
      if (result && typeof result === 'string') {
        try { devices = JSON.parse(result); } catch { devices = []; }
      }
      renderDevices(devices);
      showScanNotification(devices.length ? 'Scan complete! Devices discovered.' : 'Scan failed. No devices found.');
      scanButton.disabled = false;
      scanButton.textContent = 'Scan Network';
    };
  // also add a lightweight notification button (for testing/showing toasts)
  const notifyButton = document.createElement('button');
  notifyButton.dataset.notify = '1';
  notifyButton.style.cssText = 'margin-left:8px;padding:6px 10px;border-radius:8px;background:transparent;border:1px solid rgba(255,255,255,0.06);color:var(--muted);cursor:pointer;';
  notifyButton.textContent = 'Notify';
  notifyButton.title = 'Show a test notification';
  notifyButton.onclick = () => { try { showScanNotification('Scan has started'); } catch (e) { /* noop */ } };
  brandDiv.appendChild(scanButton);
  brandDiv.appendChild(notifyButton);
  }

  // Initial auto-scan
  const result = await runDeviceDiscovery();
  let devices = [];
  if (result && typeof result === 'string'){
    try { devices = JSON.parse(result); } catch { devices = []; }
  }
  if (!devices || !devices.length){
    // fallback demo entries so UI isn’t empty
    devices = [
      { name:'Router', ip:'192.168.1.1', mac:'6C:DD:6C:B1:FF:02', vendor:'NetGear', first_seen:'2025-10-01', last_seen:'2025-10-22', status:'Healthy' },
      { name:'Laptop', ip:'192.168.1.11', mac:'4E:4C:29:F6:13:C2', vendor:'Dell', first_seen:'2025-09-30', last_seen:'2025-10-22', status:'Healthy' }
    ];
  }
  renderDevices(devices);
  showScanNotification(devices.length ? 'Scan complete! Devices discovered.' : 'Scan failed. No devices found.');
});

// Keep overlay responsive
window.addEventListener('resize', ()=>{ if(overlay && overlay.style.display==='block') sizeCanvas(); });

// Optional: expose a public scan trigger (e.g., for a big logo click)
async function runScanWithOverlay(){
  startTransition();
  let devices = [];
  try {
    // immediate feedback
    showScanNotification('Scanning…');

    await runDeviceDiscovery();
    try { devices = JSON.parse(pendingOutput); } catch { devices = []; }
  } finally {
    showWord('SAFE', 900);
    setTimeout(() => {
      endTransition();
      switchToDevices();
      renderDevices(devices);
      showScanNotification(devices.length ? 'Scan complete! Devices discovered.' : 'Scan failed. No devices found.');
    }, 800);
  }
}
window.runScanWithOverlay = runScanWithOverlay;

/* ===== BubbleMenu vanilla initializer (uses GSAP) ===== */
(function initBubbleMenu(){
  const MENU_ITEMS = [
    { label: 'home', href: '#', ariaLabel: 'Home', rotation: -8, hoverStyles: { bgColor: '#3b82f6', textColor: '#ffffff' } },
    { label: 'about', href: '#', ariaLabel: 'About', rotation: 8, hoverStyles: { bgColor: '#10b981', textColor: '#ffffff' } },
    { label: 'projects', href: '#', ariaLabel: 'Documentation', rotation: 8, hoverStyles: { bgColor: '#f59e0b', textColor: '#ffffff' } },
    { label: 'blog', href: '#', ariaLabel: 'Blog', rotation: 8, hoverStyles: { bgColor: '#ef4444', textColor: '#ffffff' } },
    { label: 'contact', href: '#', ariaLabel: 'Contact', rotation: -8, hoverStyles: { bgColor: '#8b5cf6', textColor: '#ffffff' } }
  ];

  // Ensure DOM ready
  function ready(fn){ if (document.readyState !== 'loading') fn(); else document.addEventListener('DOMContentLoaded', fn); }

  ready(()=>{
    // Wait until GSAP exists (we load it before this script in the HTML). If not present, skip gracefully.
    if (typeof window.gsap === 'undefined') return;

    const nav = document.querySelector('.bubble-menu');
    const overlay = document.querySelector('.bubble-menu-items');
    if (!nav || !overlay) return;
    let pillList = overlay.querySelector('.pill-list');
    if (!pillList){ pillList = document.createElement('ul'); pillList.className = 'pill-list'; pillList.setAttribute('role','menu'); overlay.appendChild(pillList); }

    const bubbles = [];
    const labels = [];
    function renderItems(){
      pillList.innerHTML = '';
      MENU_ITEMS.forEach((item, i) => {
        const li = document.createElement('li');
        li.className = 'pill-col';
        li.setAttribute('role','none');

        const a = document.createElement('a');
        a.className = 'pill-link';
        a.setAttribute('role','menuitem');
        a.href = item.href || '#';
        a.setAttribute('aria-label', item.ariaLabel || item.label);

        // CSS custom properties used by the stylesheet
        a.style.setProperty('--item-rot', (item.rotation || 0) + 'deg');
        a.style.setProperty('--pill-bg', '#ffffff');
        a.style.setProperty('--pill-color', '#111111');
        a.style.setProperty('--hover-bg', item.hoverStyles?.bgColor || '#f3f4f6');
        a.style.setProperty('--hover-color', item.hoverStyles?.textColor || '#111111');

        const span = document.createElement('span');
        span.className = 'pill-label';
        span.textContent = item.label;

        a.appendChild(span);
        li.appendChild(a);
        pillList.appendChild(li);

        bubbles.push(a);
        labels.push(span);

        // Keep default navigation, but expose sample click behavior
        a.addEventListener('click', (ev) => {
          // allow standard navigation. If you want single-page behavior, handle it here.
        });
      });
    }

    renderItems();

    const toggle = nav.querySelector('.menu-btn');
    let isOpen = false;

    function applyRotations(){
      const isDesktop = window.innerWidth >= 900;
      bubbles.forEach((b, i) => {
        const rot = isDesktop ? (MENU_ITEMS[i].rotation || 0) : 0;
        b.style.setProperty('--item-rot', rot + 'deg');
      });
    }

    function openMenu(){
      if (!overlay) return;
      overlay.style.display = 'flex';
      overlay.setAttribute('aria-hidden', 'false');
      gsap.killTweensOf([...bubbles, ...labels]);
      gsap.set(bubbles, { scale: 0, transformOrigin: '50% 50%' });
      gsap.set(labels, { y: 24, autoAlpha: 0 });

      gsap.to(bubbles, {
        scale: 1,
        duration: 0.5,
        ease: 'back.out(1.5)',
        stagger: 0.12
      });

      gsap.to(labels, {
        y: 0,
        autoAlpha: 1,
        duration: 0.45,
        ease: 'power3.out',
        stagger: 0.12,
        delay: 0.03
      });
    }

    function closeMenu(){
      if (!overlay) return;
      gsap.killTweensOf([...bubbles, ...labels]);
      gsap.to(labels, { y: 24, autoAlpha: 0, duration: 0.18, ease: 'power3.in' });
      gsap.to(bubbles, {
        scale: 0,
        duration: 0.18,
        ease: 'power3.in',
        onComplete: () => {
          gsap.set(overlay, { display: 'none' });
          overlay.setAttribute('aria-hidden', 'true');
        }
      });
    }

    toggle.addEventListener('click', () => {
      isOpen = !isOpen;
      toggle.classList.toggle('open', isOpen);
      toggle.setAttribute('aria-pressed', String(isOpen));
      applyRotations();
      if (isOpen) openMenu(); else closeMenu();
    });

    // keyboard toggling
    toggle.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggle.click(); }
    });

    // responsive rotations
    window.addEventListener('resize', applyRotations);
    // initial
    applyRotations();
  });
})();

// Tiny settings toggle
function toggle(el){ el.textContent = el.textContent === 'On' ? 'Off' : 'On'; }
window.toggle = toggle;

// Optional: small boot check (you can remove if you want)
window.addEventListener('load', () => {
  try { showScanNotification('Notifications ready ✅'); } catch {}
});
