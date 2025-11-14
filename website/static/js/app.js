// ===== Config
  const API_URL = 'http://127.0.0.1:5000/run-script'; // Flask endpoint

  // ===== Tabs helper
  function switchToDevices(){ document.getElementById('tab-devices').checked = true; }

  // ===== Elements
  const enterScanBtn = document.getElementById('enterScan');
  const overlay = document.getElementById('matrixOverlay');
  const canvas = document.getElementById('matrixCanvas');
  const ctx = canvas.getContext('2d');
  const textEl = document.getElementById('matrixText');
  const scanOutput = document.getElementById('scanOutput');

  let columns = [], drops = [], rafId = null, running = false;
  let pendingOutput = "Waiting for scan...";
  let loadingInterval = null;

  function sizeCanvas(){
    const dpr = Math.max(1, Math.min(2, window.devicePixelRatio || 1));
    canvas.width = Math.floor(canvas.clientWidth * dpr);
    canvas.height = Math.floor(canvas.clientHeight * dpr);
    ctx.setTransform(dpr,0,0,dpr,0,0);
    const columnWidth = 16;
    columns = Math.ceil(canvas.clientWidth / columnWidth);
    drops = new Array(columns).fill(0).map(()=> Math.floor(Math.random()*canvas.clientHeight));
  }

  function drawMatrix(){
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

  function showWord(word, visibleMs = 1000){
    textEl.textContent = word;
    textEl.classList.add('show');
    setTimeout(()=>textEl.classList.remove('show'), visibleMs);
  }

  // ===== Loading pulse logic
  function startLoadingPulse(){
    stopLoadingPulse();
    // First “Loading …” shortly after intro words
    setTimeout(()=> showWord('Loading ...'), 3000);
    // Then every 10 seconds
    loadingInterval = setInterval(()=> showWord('Loading ...'), 10000);
  }
  function stopLoadingPulse(){
    if (loadingInterval){
      clearInterval(loadingInterval);
      loadingInterval = null;
    }
  }

  function startTransition(){
    overlay.style.display = 'block';
    sizeCanvas();
    running = true;
    drawMatrix();

    // Sequence: HOME -> NET -> SAFE
    setTimeout(()=>showWord('HOME', 900), 600);
    setTimeout(()=>showWord('NET', 900), 1300);
    setTimeout(()=>showWord('SAFE', 900), 2000);

    // Begin periodic loading pulses after the intro
    startLoadingPulse();
  }

  // ===== localStorage helpers for registered devices
  const REG_KEY = 'homenetsafe_registered_devices_v1';
  function loadRegisteredDevices(){
    try{ const raw = localStorage.getItem(REG_KEY); return raw ? JSON.parse(raw) : {}; }catch{return {};}
  }
  function saveRegisteredDevices(obj){ localStorage.setItem(REG_KEY, JSON.stringify(obj)); }
  function isRegistered(mac){ const map = loadRegisteredDevices(); return !!map[mac]; }
  function registerDevice(dev, customName, notes){ 
    const map = loadRegisteredDevices(); 
    map[dev.mac] = { 
      ...dev, 
      customName: customName,
      notes: notes,
      registeredAt: new Date().toISOString() 
    }; 
    saveRegisteredDevices(map); 
  }
  function unregisterDevice(mac){
    const map = loadRegisteredDevices();
    delete map[mac];
    saveRegisteredDevices(map);
  }

  // Device type icons
  function getDeviceIcon(vendor, name) {
    const v = (vendor || '').toLowerCase();
    const n = (name || '').toLowerCase();
    
    if (v.includes('apple') || n.includes('iphone') || n.includes('ipad')) return '📱';
    if (v.includes('samsung') || n.includes('android')) return '📱';
    if (v.includes('nintendo')) return '🎮';
    if (v.includes('raspberry')) return '🥧';
    if (v.includes('amazon') || n.includes('echo')) return '🔊';
    if (v.includes('hp') || v.includes('canon') || n.includes('printer')) return '🖨️';
    if (n.includes('router') || v.includes('netgear')) return '📡';
    if (v.includes('proxmox') || n.includes('server')) return '🖥️';
    if (v.includes('tuya') || n.includes('smart')) return '🏠';
    return '💻';
  }
  
  // Time ago helper with attractive formatting
  function timeAgo(dateString) {
    if (!dateString) return '<span style="color:var(--muted);font-style:italic;">Unknown</span>';
    const now = new Date();
    const date = new Date(dateString);
    const diff = now - date;
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(minutes / 60);
    const days = Math.floor(hours / 24);
    
    let timeText, color;
    if (minutes < 1) {
      timeText = 'Just now';
      color = '#08f76f'; // Green for very recent
    } else if (minutes < 60) {
      timeText = `${minutes}m ago`;
      color = '#00e5ff'; // Cyan for recent
    } else if (hours < 24) {
      timeText = `${hours}h ago`;
      color = '#ffa726'; // Orange for hours
    } else if (days < 7) {
      timeText = `${days}d ago`;
      color = '#ff7043'; // Red-orange for days
    } else {
      timeText = `${days}d ago`;
      color = 'var(--muted)'; // Muted for old
    }
    
    return `<span style="color:${color};font-weight:600;">${timeText}</span>`;
  }
  
  // Format date for display
  function formatDate(dateString) {
    if (!dateString) return '<span style="color:var(--muted);font-style:italic;">Unknown</span>';
    const date = new Date(dateString);
    const options = { 
      month: 'short', 
      day: 'numeric', 
      hour: '2-digit', 
      minute: '2-digit',
      hour12: false
    };
    const formatted = date.toLocaleDateString('en-US', options);
    return `<span style="color:var(--ink);font-size:11px;">${formatted}</span>`;
  }
  
  function renderDevices(discoveredDevices, manualDevices){
    // Render discovered devices (excluding registered ones)
    const discoveredBody = document.getElementById('discoveredBody');
    const failMsg = document.getElementById('scanFailMsg');
    const discoveredTableWrap = document.getElementById('discoveredTableWrap');
    
    // Filter out registered devices from discovered list
    const regMap = loadRegisteredDevices();
    const unregisteredDevices = discoveredDevices ? discoveredDevices.filter(dev => !regMap[dev.mac]) : [];
    
    if (!unregisteredDevices || unregisteredDevices.length === 0){
      failMsg.style.display = 'block'; 
      discoveredTableWrap.style.display = 'none'; 
      discoveredBody.innerHTML = '';
    } else {
      failMsg.style.display = 'none'; 
      discoveredTableWrap.style.display = 'block';
      discoveredBody.innerHTML = unregisteredDevices.map(dev => {
        const reg = false; // All devices in this list are unregistered
        const status = dev.status || 'unknown';
        const statusDot = `<span class="status-dot status-${status}"></span>`;
        const deviceIcon = `<span class="device-icon">${getDeviceIcon(dev.vendor, dev.name)}</span>`;
        const lastSeenText = `<div class="last-seen">${timeAgo(dev.last_seen)}</div>`;
        const registeredInfo = reg ? regMap[dev.mac] : null;
        
        return `
          <tr>
            <td style="text-align:center;padding:12px 8px;border-bottom:1px solid var(--line);">${statusDot}${status}</td>
            <td style="text-align:left;padding:12px 8px;border-bottom:1px solid var(--line);">${deviceIcon}${registeredInfo?.customName || dev.name || 'Unknown Device'}</td>
            <td style="text-align:center;padding:12px 8px;font-family:monospace;border-bottom:1px solid var(--line);">${dev.ip || ''}</td>
            <td style="text-align:center;padding:12px 8px;font-family:monospace;border-bottom:1px solid var(--line);">${dev.mac || ''}</td>
            <td style="text-align:left;padding:12px 8px;border-bottom:1px solid var(--line);">${dev.vendor || 'Unknown'}</td>
            <td style="text-align:center;padding:12px 8px;border-bottom:1px solid var(--line);">
              <div>${formatDate(dev.first_seen)}</div>
            </td>
            <td style="text-align:center;padding:12px 8px;border-bottom:1px solid var(--line);">
              <div>${formatDate(dev.last_seen)}</div>
              <div style="margin-top:2px;">${timeAgo(dev.last_seen)}</div>
            </td>
            <td style="text-align:center;padding:12px 8px;border-bottom:1px solid var(--line);">
              <button class="historyBtn" data-id="${dev.id}" style="padding:4px 8px;border-radius:6px;border:none;cursor:pointer;background:var(--muted);color:var(--bg);font-weight:700;font-size:11px;margin-right:4px;">History</button>
              ${reg ? 
                `<button class="unregBtn" data-mac="${dev.mac}" style="padding:6px 10px;border-radius:8px;border:none;cursor:pointer;background:#666;color:var(--ink);font-weight:700;white-space:nowrap;">Unregister</button>` :
                `<button class="regBtn" data-mac="${dev.mac}" style="padding:6px 10px;border-radius:8px;border:none;cursor:pointer;background:var(--accent);color:#032c33;font-weight:700;white-space:nowrap;">Register</button>`
              }
            </td>
          </tr>
        `;
      }).join('');
    }
    
    // Render registered devices (manual + registered discovered devices)
    const manualBody = document.getElementById('manualBody');
    const manualTableWrap = document.getElementById('manualTableWrap');
    
    // Combine manual devices with registered discovered devices
    const registeredDiscovered = discoveredDevices ? discoveredDevices.filter(dev => regMap[dev.mac]).map(dev => ({
      ...dev,
      name: regMap[dev.mac].customName || dev.name,
      vendor: dev.vendor || 'Registered'
    })) : [];
    
    const allRegisteredDevices = [...(manualDevices || []), ...registeredDiscovered];
    
    if (!allRegisteredDevices || allRegisteredDevices.length === 0){
      manualBody.innerHTML = '<tr><td colspan="6" style="text-align:center;padding:20px;color:var(--muted);">No registered devices added</td></tr>';
    } else {
      manualBody.innerHTML = allRegisteredDevices.map(dev => `
        <tr>
          <td style="text-align:left;padding:12px 8px;border-bottom:1px solid var(--line);">${dev.name || ''}</td>
          <td style="text-align:center;padding:12px 8px;font-family:monospace;border-bottom:1px solid var(--line);">${dev.ip || ''}</td>
          <td style="text-align:center;padding:12px 8px;font-family:monospace;border-bottom:1px solid var(--line);">${dev.mac || ''}</td>
          <td style="text-align:left;padding:12px 8px;border-bottom:1px solid var(--line);">${dev.vendor || 'Registered'}</td>
          <td style="text-align:center;padding:12px 8px;border-bottom:1px solid var(--line);">
            <div>${formatDate(dev.first_seen)}</div>
          </td>
          <td style="text-align:center;padding:12px 8px;border-bottom:1px solid var(--line);">
            <button class="removeBtn" data-id="${dev.id}" style="padding:6px 10px;border-radius:8px;border:none;cursor:pointer;background:#ff6b6b;color:white;font-weight:700;white-space:nowrap;">Remove</button>
          </td>
        </tr>
      `).join('');
    }

    // attach handlers for registration buttons
    Array.from(document.getElementsByClassName('regBtn')).forEach(btn => {
      btn.onclick = () => {
        const mac = btn.getAttribute('data-mac');
        const device = discoveredDevices.find(d => d.mac === mac);
        if (device) {
          document.getElementById('regDeviceMac').value = device.mac;
          document.getElementById('regDeviceName').value = device.name || '';
          document.getElementById('regDeviceNotes').value = '';
          document.getElementById('registerModal').style.display = 'block';
        }
      };
    });

    // attach handlers for unregister buttons
    Array.from(document.getElementsByClassName('unregBtn')).forEach(btn => {
      btn.onclick = () => {
        const mac = btn.getAttribute('data-mac');
        if (confirm('Are you sure you want to unregister this device?')) {
          unregisterDevice(mac);
          renderDevices(discoveredDevices, manualDevices);
        }
      };
    });

    // attach handlers for remove buttons (manual devices)
    Array.from(document.getElementsByClassName('removeBtn')).forEach(btn => {
      btn.onclick = async () => {
        const deviceId = parseInt(btn.getAttribute('data-id'));
        if (confirm('Are you sure you want to remove this device?')) {
          if (await removeManualDevice(deviceId)) {
            showToast('Device removed successfully', 'success');
            await loadAndRenderDevices();
            await updateDeviceStats();
          } else {
            showToast('Failed to remove device', 'error');
          }
        }
      };
    });

    // handle registration form submission
    document.getElementById('registerForm').onsubmit = async (e) => {
      e.preventDefault();
      const mac = document.getElementById('regDeviceMac').value;
      const customName = document.getElementById('regDeviceName').value;
      const notes = document.getElementById('regDeviceNotes').value;
      const device = currentDevices.discovered.find(d => d.mac === mac);
      
      if (device) {
        // Add to manual devices database
        const success = await addManualDevice(customName, device.ip, device.mac);
        if (success) {
          // Also keep in localStorage for UI state
          registerDevice(device, customName, notes);
          document.getElementById('registerModal').style.display = 'none';
          showToast('Device registered successfully', 'success');
          await loadAndRenderDevices();
          await updateDeviceStats();
        } else {
          showToast('Failed to register device', 'error');
        }
      }
    };
  }

  // Enhanced network interface display for Settings tab
  async function updateNetworkStatus() {
    try {
      const response = await fetch('/network-interface');
      const data = await response.json();
      
      const connectionIcon = document.getElementById('connectionIcon');
      const connectionLabel = document.getElementById('connectionLabel');
      const connectionDetails = document.getElementById('connectionDetails');
      const localIpAddress = document.getElementById('localIpAddress');
      const securityStatus = document.getElementById('securityStatus');
      
      // Update local IP address
      if (localIpAddress && data.local_ip) {
        localIpAddress.textContent = data.local_ip;
      }
      
      if (data.type === 'wifi') {
        connectionIcon.textContent = '📶';
        connectionLabel.textContent = 'WiFi Connection';
        connectionDetails.textContent = `Wireless network connection`;
        
        if (data.is_insecure) {
          securityStatus.style.background = 'rgba(255,107,107,0.1)';
          securityStatus.style.borderLeftColor = '#ff6b6b';
          securityStatus.innerHTML = `
            <div style="font-size:12px;font-weight:600;color:#ff6b6b;">⚠️ Insecure Connection</div>
            <div style="font-size:11px;color:var(--muted);margin-top:2px;">${data.security} - Consider upgrading to WPA2/WPA3</div>
          `;
        } else {
          securityStatus.style.background = 'rgba(8,247,111,0.1)';
          securityStatus.style.borderLeftColor = '#08f76f';
          securityStatus.innerHTML = `
            <div style="font-size:12px;font-weight:600;color:#08f76f;">✓ Secure WiFi Connection</div>
            <div style="font-size:11px;color:var(--muted);margin-top:2px;">${data.security} encryption</div>
          `;
        }
      } else {
        connectionIcon.textContent = '🔌';
        connectionLabel.textContent = 'Ethernet Connection';
        connectionDetails.textContent = 'Wired network connection';
        securityStatus.style.background = 'rgba(8,247,111,0.1)';
        securityStatus.style.borderLeftColor = '#08f76f';
        securityStatus.innerHTML = `
          <div style="font-size:12px;font-weight:600;color:#08f76f;">✓ Secure Connection</div>
          <div style="font-size:11px;color:var(--muted);margin-top:2px;">Wired connections are inherently secure</div>
        `;
      }
    } catch (error) {
      console.log('Network interface detection failed:', error);
      // Show error state
      const securityStatus = document.getElementById('securityStatus');
      if (securityStatus) {
        securityStatus.style.background = 'rgba(159,201,219,0.1)';
        securityStatus.style.borderLeftColor = 'var(--muted)';
        securityStatus.innerHTML = `
          <div style="font-size:12px;font-weight:600;color:var(--muted);">ℹ️ Connection Status Unknown</div>
          <div style="font-size:11px;color:var(--muted);margin-top:2px;">Unable to detect network interface</div>
        `;
      }
    }
  }
  
  // System uptime display
  function updateSystemUptime() {
    const uptimeElement = document.getElementById('systemUptime');
    if (uptimeElement) {
      const startTime = Date.now();
      setInterval(() => {
        const uptime = Date.now() - startTime;
        const minutes = Math.floor(uptime / 60000);
        const hours = Math.floor(minutes / 60);
        if (hours > 0) {
          uptimeElement.textContent = `${hours}h ${minutes % 60}m`;
        } else {
          uptimeElement.textContent = `${minutes}m`;
        }
      }, 60000); // Update every minute
      uptimeElement.textContent = '0m';
    }
  }
  
  // Export devices functionality
  function exportDevices() {
    const devices = [...currentDevices.discovered, ...currentDevices.manual];
    const csv = 'Name,IP,MAC,Vendor,Type,Status,First Seen,Last Seen\n' + 
      devices.map(d => `"${d.name || ''}","${d.ip || ''}","${d.mac || ''}","${d.vendor || ''}","${d.manual ? 'Manual' : 'Discovered'}","${d.status || ''}","${d.first_seen || ''}","${d.last_seen || ''}"`).join('\n');
    
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `homenetsafe-devices-${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    window.URL.revokeObjectURL(url);
    showToast('Device list exported successfully', 'success');
  }
  
  // Show system logs (placeholder)
  function showSystemLogs() {
    showToast('System logs feature coming soon', 'info');
  }

  // Device management functions
  async function loadAllDevices() {
    let devices = [];
    
    // Load discovered devices
    try {
      const networkDeviceList = await getNetworkDeviceList();
      for (const networkDevice of networkDeviceList) {
        devices.push({ip: networkDevice.ip, mac: networkDevice.mac, vendor: networkDevice.vendor, first_seen: networkDevice.first_seen, last_seen: networkDevice.last_seen, status: "TODO", manual: false});
      }
    } catch (e) {
      console.log('Failed to load discovered devices:', e);
    }
    
    // Load manual devices
    try {
      const response = await fetch('/manual-devices');
      const manualDevices = await response.json();
      devices = devices.concat(manualDevices);
    } catch (e) {
      console.log('Failed to load manual devices:', e);
    }
    
    return devices;
  }

  async function addManualDevice(name, ip, mac) {
    try {
      const response = await fetch('/manual-devices', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          name: name,
          ip: ip,
          mac: mac || '',
          first_seen: new Date().toISOString().split('T')[0],
          last_seen: new Date().toISOString().split('T')[0]
        })
      });
      return response.ok;
    } catch (e) {
      console.log('Failed to add device:', e);
      return false;
    }
  }

  async function removeManualDevice(deviceId) {
    try {
      const response = await fetch(`/manual-devices/${deviceId}`, {method: 'DELETE'});
      return response.ok;
    } catch (e) {
      console.log('Failed to remove device:', e);
      return false;
    }
  }

  // Global variables
  let autoRefreshInterval = null;
  let currentDevices = {discovered: [], manual: []};
  
  // Toast notification system
  function showToast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
      <div style="display:flex;align-items:center;gap:8px;">
        <span>${type === 'success' ? '✅' : type === 'error' ? '❌' : 'ℹ️'}</span>
        <span>${message}</span>
      </div>
    `;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 4000);
  }
  
  // Device statistics
  async function updateDeviceStats() {
    try {
      const stats = await fetch('/device-stats').then(r => r.json());
      document.getElementById('totalDevices').textContent = `${stats.total} devices`;
      document.getElementById('onlineDevices').textContent = `${stats.online} online`;
      document.getElementById('offlineDevices').textContent = `${stats.offline} offline`;
    } catch (e) {
      console.log('Failed to load device stats:', e);
    }
  }
  
  // Device search and filter
  function filterDevices() {
    const searchTerm = document.getElementById('deviceSearch').value.toLowerCase();
    const rows = document.querySelectorAll('#discoveredBody tr, #manualBody tr');
    
    rows.forEach(row => {
      const text = row.textContent.toLowerCase();
      row.style.display = text.includes(searchTerm) ? '' : 'none';
    });
  }
  
  // Auto-refresh functionality
  function setupAutoRefresh() {
    const checkbox = document.getElementById('autoRefresh');
    const refreshBtn = document.getElementById('refreshBtn');
    
    function toggleAutoRefresh() {
      if (checkbox.checked) {
        autoRefreshInterval = setInterval(refreshAllData, 30000);
      } else {
        clearInterval(autoRefreshInterval);
      }
    }
    
    checkbox.addEventListener('change', toggleAutoRefresh);
    refreshBtn.addEventListener('click', refreshAllData);
    
    toggleAutoRefresh(); // Start if checked
  }
  
  // Refresh all data
  async function refreshAllData() {
    const refreshBtn = document.getElementById('refreshBtn');
    refreshBtn.classList.add('refreshing');
    
    try {
      await loadAndRenderDevices();
      await updateDeviceStats();
      await updateNetworkStatus();
      showToast('Data refreshed successfully', 'success');
    } catch (e) {
      showToast('Failed to refresh data', 'error');
    } finally {
      refreshBtn.classList.remove('refreshing');
    }
  }
  
  // Load and render devices
  async function loadAndRenderDevices() {
    // Load devices separately
    const discoveredDevices = [];
    try {
      const networkDeviceList = await getNetworkDeviceList();
      for (const networkDevice of networkDeviceList) {
        discoveredDevices.push({...networkDevice, status: networkDevice.status || 'unknown', manual: false});
      }
    } catch (e) {
      console.log('Failed to load discovered devices:', e);
    }
    
    const manualDevices = await fetch('/manual-devices').then(r => r.json()).catch(() => []);
    
    currentDevices = {discovered: discoveredDevices, manual: manualDevices};
    renderDevices(discoveredDevices, manualDevices);
    renderNetworkMap(discoveredDevices, manualDevices);
  }
  
  // Actual scan function
  async function actualScan() {
    const scanButton = document.getElementById('scanNetworkBtn');
    
    // Show loading state immediately
    scanButton.disabled = true;
    scanButton.textContent = 'Scanning Network...';
    scanButton.style.background = '#ff6b6b';
    scanButton.style.color = 'white';
    
    try {
      // Run the actual network discovery script
      const response = await fetch('/run-script');
      const result = await response.json();
      
      if (result.ok) {
        showToast('Network scan completed successfully', 'success');
      } else {
        showToast('Network scan failed: ' + (result.stderr || 'Unknown error'), 'error');
      }
    } catch (error) {
      console.error('Scan error:', error);
      showToast('Network scan failed: ' + error.message, 'error');
    }
    
    // Refresh device list after scan
    await loadAndRenderDevices();
    await updateDeviceStats();
    
    // Reset button state
    scanButton.disabled = false;
    scanButton.textContent = 'Scan Network';
    scanButton.style.background = 'var(--accent)';
    scanButton.style.color = '#032c33';
  }
  
  // Auto-scan on load
  window.addEventListener('load', async ()=>{
    // Update network status in Settings
    updateNetworkStatus();
    updateSystemUptime();
    
    // Load devices
    await loadAndRenderDevices();
    await updateDeviceStats();
    
    // Setup UI
    setupAutoRefresh();
    document.getElementById('deviceSearch').addEventListener('input', filterDevices);
    
    // Setup scan button handler
    const scanButton = document.getElementById('scanNetworkBtn');
    console.log('Scan button element:', scanButton);
    
    if (scanButton) {
      // Remove inline onclick and replace with proper handler
      scanButton.onclick = async () => {
        console.log('Scan button clicked via JavaScript');
        
        // Show loading state immediately
        scanButton.disabled = true;
        scanButton.textContent = 'Scanning...';
        scanButton.style.background = '#ff6b6b';
        scanButton.style.color = 'white';
        scanButton.style.opacity = '0.8';
        
        // Add pulsing animation
        let pulse = true;
        const pulseInterval = setInterval(() => {
          scanButton.style.opacity = pulse ? '0.5' : '0.8';
          pulse = !pulse;
        }, 500);
        
        showToast('Starting network scan...', 'info');
        
        try {
          // Run the actual network discovery script
          const response = await fetch('/run-script');
          const result = await response.json();
          
          if (result.ok) {
            showToast('Network scan completed successfully', 'success');
          } else {
            showToast('Network scan failed: ' + (result.stderr || 'Unknown error'), 'error');
          }
        } catch (error) {
          console.error('Scan error:', error);
          showToast('Network scan failed: ' + error.message, 'error');
        }
        
        // Stop pulsing animation
        clearInterval(pulseInterval);
        
        // Refresh device list after scan
        await loadAndRenderDevices();
        await updateDeviceStats();
        
        // Reset button state
        scanButton.disabled = false;
        scanButton.textContent = 'Scan Network';
        scanButton.style.background = 'var(--accent)';
        scanButton.style.color = '#032c33';
        scanButton.style.opacity = '1';
      };
    } else {
      console.error('Scan button not found');
    }
    
    // Add device button handler
    document.getElementById('addDeviceBtn').onclick = () => {
      document.getElementById('addDeviceModal').style.display = 'block';
    };
    
    // Add device form handler
    document.getElementById('addDeviceForm').onsubmit = async (e) => {
      e.preventDefault();
      const name = document.getElementById('addDeviceName').value;
      const ip = document.getElementById('addDeviceIP').value;
      const mac = document.getElementById('addDeviceMAC').value;
      
      if (await addManualDevice(name, ip, mac)) {
        document.getElementById('addDeviceModal').style.display = 'none';
        document.getElementById('addDeviceForm').reset();
        showToast('Device added successfully', 'success');
        await loadAndRenderDevices();
        await updateDeviceStats();
      } else {
        showToast('Failed to add device (may already exist)', 'error');
      }
    };
  });

  // Update network indicator every 30 seconds
  setInterval(updateNetworkIndicator, 30000);

async function getNetworkDeviceList() {
  const response = await fetch('/get_network_device_list');  // Call Flask route
  const data = await response.json();            // Parse JSON
  return data;                           // Return string
}



  async function runDeviceDiscovery(){
    // Hit your Flask endpoint that runs "Device Discovery.py"
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
      // If backend returned structured JSON devices, prefer that
      if (data && data.devices) {
        pendingOutput = JSON.stringify(data.devices);
      } else {
        pendingOutput = out || "(no output)";
      }
    } catch (e) {
      pendingOutput = "Failed to contact server.\n" + e;
    }
    return pendingOutput;
  }

  function endMatrixTransitionAndShowOutput(){
    running = false;
    cancelAnimationFrame(rafId);
    stopLoadingPulse();
    overlay.style.display = 'none';
    switchToScan();
    scanOutput.textContent = pendingOutput;
  }

  // Click the logo: start transition, run Python, then reveal output
  enterScanBtn?.addEventListener('click', async () => {
    startTransition();
    let scanFailed = false;
    let resultText = '';
    let devices = [];
    try {
      await runDeviceDiscovery();
      if (pendingOutput.startsWith('Failed to contact server')) {
        scanFailed = true;
        resultText = 'Scan failed. No devices found.';
      } else {
        // Try to parse output as JSON array of devices, fallback to plain text
        try {
          devices = JSON.parse(pendingOutput);
        } catch {
          resultText = pendingOutput;
        }
      }
    } catch (e) {
      scanFailed = true;
      resultText = 'Scan failed. No devices found.';
    }
    showWord('SAFE', 900);
    setTimeout(() => {
      running = false;
      cancelAnimationFrame(rafId);
      stopLoadingPulse();
      overlay.style.display = 'none';
      switchToDevices();
      // Show/hide device table or error
      const failMsg = document.getElementById('scanFailMsg');
      const tableWrap = document.getElementById('devicesTableWrap');
      const tbody = document.getElementById('devicesBody');
      if (scanFailed || !devices || !Array.isArray(devices) || devices.length === 0) {
        failMsg.style.display = 'block';
        tableWrap.style.display = 'none';
        tbody.innerHTML = '';
      } else {
        failMsg.style.display = 'none';
        tableWrap.style.display = 'block';
        tbody.innerHTML = devices.map(dev => `
          <tr style="text-align:center;">
            <td style="text-align:center;">${dev.name || ''}</td>
            <td style="text-align:center;">${dev.ip || ''}</td>
            <td style="text-align:center;">${dev.mac || ''}</td>
            <td style="text-align:center;">${dev.type || ''}</td>
            <td style="text-align:center;"><span style="color:${dev.status === 'Healthy' ? '#08f76f' : '#9fc9db'}">${dev.status || ''}</span></td>
          </tr>
        `).join('');
      }
    }, 800);
  });

  window.addEventListener('resize', ()=>{ if(overlay.style.display==='block') sizeCanvas(); });

  // tiny toggle button
  function toggle(el){ el.textContent = el.textContent === 'On' ? 'Off' : 'On'; }