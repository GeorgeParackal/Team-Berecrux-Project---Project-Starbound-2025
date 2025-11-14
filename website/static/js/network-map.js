// Network Map Visualization
function renderNetworkMap(discoveredDevices, manualDevices) {
  const mapContainer = document.getElementById('mapDevices');
  const allDevices = [...discoveredDevices, ...manualDevices];
  
  if (allDevices.length === 0) {
    mapContainer.innerHTML = '<div style="text-align:center;color:var(--muted);padding:40px;">No devices to display</div>';
    return;
  }
  
  // Group devices by status
  const online = allDevices.filter(d => d.status === 'online');
  const offline = allDevices.filter(d => d.status === 'offline');
  const unknown = allDevices.filter(d => d.status === 'unknown' || !d.status);
  
  mapContainer.innerHTML = `
    <div style="display:flex;flex-direction:column;align-items:center;gap:20px;width:100%;">
      <!-- Router/Gateway (center) -->
      <div class="network-device online" style="font-size:24px;padding:16px;">
        📡
        <div style="font-size:12px;margin-top:4px;">Gateway</div>
      </div>
      
      <!-- Online Devices -->
      ${online.length > 0 ? `
        <div style="text-align:center;">
          <div style="color:#08f76f;font-weight:700;margin-bottom:12px;">Online Devices (${online.length})</div>
          <div style="display:flex;flex-wrap:wrap;gap:12px;justify-content:center;">
            ${online.map(device => `
              <div class="network-device online" onclick="showDeviceDetails('${device.id || device.ip}')">
                ${getDeviceIcon(device.vendor, device.name)}
                <div style="font-size:10px;margin-top:4px;max-width:60px;overflow:hidden;text-overflow:ellipsis;">${device.name || device.ip}</div>
              </div>
            `).join('')}
          </div>
        </div>
      ` : ''}
      
      <!-- Offline Devices -->
      ${offline.length > 0 ? `
        <div style="text-align:center;">
          <div style="color:#ff6b6b;font-weight:700;margin-bottom:12px;">Offline Devices (${offline.length})</div>
          <div style="display:flex;flex-wrap:wrap;gap:12px;justify-content:center;">
            ${offline.map(device => `
              <div class="network-device offline" onclick="showDeviceDetails('${device.id || device.ip}')">
                ${getDeviceIcon(device.vendor, device.name)}
                <div style="font-size:10px;margin-top:4px;max-width:60px;overflow:hidden;text-overflow:ellipsis;">${device.name || device.ip}</div>
              </div>
            `).join('')}
          </div>
        </div>
      ` : ''}
      
      <!-- Unknown Status Devices -->
      ${unknown.length > 0 ? `
        <div style="text-align:center;">
          <div style="color:var(--muted);font-weight:700;margin-bottom:12px;">Unknown Status (${unknown.length})</div>
          <div style="display:flex;flex-wrap:wrap;gap:12px;justify-content:center;">
            ${unknown.map(device => `
              <div class="network-device" onclick="showDeviceDetails('${device.id || device.ip}')">
                ${getDeviceIcon(device.vendor, device.name)}
                <div style="font-size:10px;margin-top:4px;max-width:60px;overflow:hidden;text-overflow:ellipsis;">${device.name || device.ip}</div>
              </div>
            `).join('')}
          </div>
        </div>
      ` : ''}
    </div>
  `;
}

// Show device details (placeholder for future enhancement)
function showDeviceDetails(deviceId) {
  const device = [...currentDevices.discovered, ...currentDevices.manual].find(d => 
    (d.id && d.id.toString() === deviceId) || d.ip === deviceId
  );
  
  if (device) {
    showToast(`${device.name || device.ip} - ${device.vendor || 'Unknown vendor'}`, 'info');
  }
}

// Device history functionality
async function showDeviceHistory(deviceId) {
  try {
    const history = await fetch(`/device-history/${deviceId}`).then(r => r.json());
    const modal = document.getElementById('historyModal');
    const content = document.getElementById('historyContent');
    
    if (history.length === 0) {
      content.innerHTML = '<div style="text-align:center;color:var(--muted);padding:20px;">No history available</div>';
    } else {
      content.innerHTML = `
        <div style="max-height:300px;overflow-y:auto;">
          ${history.map(event => `
            <div style="padding:8px 0;border-bottom:1px solid var(--line);">
              <div style="font-weight:700;color:var(--accent);">${event.event_type}</div>
              <div style="font-size:12px;color:var(--muted);">${new Date(event.timestamp).toLocaleString()}</div>
              ${event.details ? `<div style="font-size:12px;margin-top:4px;">${event.details}</div>` : ''}
            </div>
          `).join('')}
        </div>
      `;
    }
    
    modal.style.display = 'block';
  } catch (e) {
    showToast('Failed to load device history', 'error');
  }
}