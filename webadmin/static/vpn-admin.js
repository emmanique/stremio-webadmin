(() => {
  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const fmtBytes = value => {
    const n = Number(value || 0);
    if (!n) return '0 B';
    const units = ['B','KB','MB','GB','TB'];
    const i = Math.min(units.length - 1, Math.floor(Math.log(n) / Math.log(1024)));
    return `${(n / (1024 ** i)).toFixed(i > 1 ? 1 : 0)} ${units[i]}`;
  };
  const badge = (ok, text) => `<span class="badge ${ok ? '' : 'vpnBad'}">● ${esc(text)}</span>`;

  const css = document.createElement('style');
  css.textContent = `
    .vpnBad{color:#ff8d95!important;border-color:#8b3341!important;background:#40161d!important}
    .vpnGrid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-bottom:16px}
    .vpnCard{padding:14px;border:1px solid rgba(232,207,105,.25);border-radius:10px;background:rgba(13,30,21,.95);min-width:0}
    .vpnCard span{display:block;color:var(--muted);font-size:10px;text-transform:uppercase}.vpnCard b{display:block;margin-top:5px;font-size:15px;overflow-wrap:anywhere}
    .vpnActions{display:flex;gap:8px;flex-wrap:wrap;margin:14px 0}.vpnInfo{padding:12px;border:1px solid rgba(232,207,105,.2);border-radius:9px;background:rgba(15,24,18,.92);color:var(--muted);font-size:12px;margin:10px 0}.vpnResult{white-space:pre-wrap;font:12px/1.5 ui-monospace,SFMono-Regular,Consolas,monospace}.vpnLogs{min-height:220px;max-height:420px;overflow:auto;padding:14px;border:1px solid #827632;border-radius:9px;background:rgba(2,8,5,.96);color:#cdd4d8;font:11px/1.5 ui-monospace,SFMono-Regular,Consolas,monospace;white-space:pre-wrap;overflow-wrap:anywhere}
    .vpnProfiles{display:grid;gap:10px}.vpnProfile{border:1px solid rgba(232,207,105,.25);border-radius:12px;background:rgba(11,28,19,.9);padding:14px}.vpnProfileTop{display:flex;gap:10px;align-items:flex-start;justify-content:space-between}.vpnProfileTitle{font-size:16px;font-weight:800}.vpnProfileMeta{color:var(--muted);font-size:11px;margin-top:4px;overflow-wrap:anywhere}.vpnFlags{display:flex;gap:6px;flex-wrap:wrap;margin:9px 0}.vpnFlag{border:1px solid #506238;border-radius:99px;padding:3px 8px;font-size:10px;color:#d9d2ac}.vpnFlag.active{border-color:#3da864;color:var(--green)}.vpnFlag.startup{border-color:#caa841;color:#ffe77a}.vpnFiles{font-size:11px;color:var(--muted);margin-top:7px}.vpnProfileButtons{display:flex;gap:6px;flex-wrap:wrap;margin-top:12px}
    .vpnForm{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.vpnField{min-width:0}.vpnField.full{grid-column:1/-1}.vpnField label{display:block;color:#e6cf68;font-size:11px;margin-bottom:5px}.vpnField input,.vpnField select{width:100%;border:1px solid rgba(229,198,74,.3);border-radius:8px;background:rgba(13,30,21,.95);color:var(--text);padding:10px;font:inherit}.vpnChecks{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.vpnCheck{display:flex;align-items:center;gap:8px;background:rgba(13,30,21,.75);border:1px solid rgba(229,198,74,.18);border-radius:8px;padding:10px}.vpnCheck input{width:auto}.vpnSecretState{color:var(--muted);font-size:10px;margin-top:4px}.vpnBundleState{margin-top:8px;color:var(--muted);font-size:11px}.vpnHidden{display:none!important}.vpnFormHeader{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:14px}.vpnFormHeader h3{margin:0}.vpnEmpty{text-align:center;color:var(--muted);padding:24px}.vpnWarn{color:#ffe073}
    @media(max-width:900px){.vpnGrid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:650px){.vpnGrid,.vpnForm,.vpnChecks{grid-template-columns:1fr}.vpnField.full{grid-column:auto}.vpnProfileTop{display:block}}
  `;
  document.head.appendChild(css);

  const nav = document.querySelector('.tabs');
  if (!nav || $('vpn')) return;
  const logsTab = [...nav.querySelectorAll('.tab')].find(btn => btn.dataset.page === 'logs');
  const tab = document.createElement('button');
  tab.className = 'tab';
  tab.dataset.page = 'vpn';
  tab.textContent = 'VPN';
  nav.insertBefore(tab, logsTab || null);

  const section = document.createElement('section');
  section.className = 'page hidden';
  section.id = 'vpn';
  section.innerHTML = `
    <article class="panel"><div class="title row"><span>VPN · CYBERGHOST / GLUETUN</span><button class="copy" id="vpnRefresh">↻ Refresh</button></div><div class="inner">
      <div class="vpnGrid">
        <div class="vpnCard"><span>Deployment</span><b id="vpnMode">—</b></div>
        <div class="vpnCard"><span>Tunnel</span><b id="vpnTunnel">—</b></div>
        <div class="vpnCard"><span>Active connection</span><b id="vpnActive">—</b></div>
        <div class="vpnCard"><span>VPN public IP</span><b id="vpnPublicIp">—</b></div>
        <div class="vpnCard"><span>Kill switch</span><b id="vpnKill">—</b></div>
        <div class="vpnCard"><span>Transport</span><b id="vpnTransport">—</b></div>
        <div class="vpnCard"><span>Received</span><b id="vpnRx">—</b></div>
        <div class="vpnCard"><span>Sent</span><b id="vpnTx">—</b></div>
      </div>
      <div id="vpnModeHint" class="vpnInfo"></div>
      <div class="vpnActions">
        <button class="btn" id="vpnConnect">Connect</button>
        <button class="btn danger" id="vpnDisconnect">Disconnect (block traffic)</button>
        <button class="btn ghost" id="vpnReconnect">Reconnect</button>
        <button class="btn ghost" id="vpnTest">Test protection</button>
      </div>
      <div id="vpnActionState" class="saveState"></div>
      <div id="vpnTestResult" class="vpnInfo vpnResult">Protection test has not been run yet.</div>
    </div><div class="foot">Only Stremio is routed through Gluetun. WebAdmin and Pi-hole stay on the LAN; VPN failure remains fail-closed.</div></article>

    <article class="panel"><div class="title row"><span>VPN CONNECTIONS</span><button class="btn" id="vpnNew">+ New connection</button></div><div class="inner">
      <div class="vpnInfo"><b>CyberGhost router/OpenVPN profiles are managed independently.</b> Every new connection requires the CyberGhost ZIP containing <code>openvpn.ovpn</code>, <code>ca.crt</code>, <code>client.crt</code> and <code>client.key</code>. Credentials and keys remain in the private <code>vpn-data</code> volume.</div>
      <div id="vpnProfiles" class="vpnProfiles"><div class="vpnEmpty">Loading connections…</div></div>
    </div><div class="foot">One profile can be marked for startup. You can still activate another profile temporarily without changing the startup default.</div></article>

    <article class="panel vpnHidden" id="vpnEditor"><div class="title">CONNECTION PROFILE</div><div class="inner">
      <div class="vpnFormHeader"><h3 id="vpnEditorTitle">New CyberGhost connection</h3><button class="btn ghost" id="vpnCancelEdit">Cancel</button></div>
      <div class="vpnForm">
        <div class="vpnField"><label>Connection name</label><input id="vpnName" placeholder="e.g. CyberGhost Portugal"></div>
        <div class="vpnField"><label>Protocol</label><input value="OpenVPN" disabled></div>
        <div class="vpnField"><label>Country</label><input id="vpnCountry" placeholder="e.g. Portugal"></div>
        <div class="vpnField"><label>Server group</label><input id="vpnServerGroup" placeholder="Auto-detected from openvpn.ovpn"></div>
        <div class="vpnField"><label>Transport</label><select id="vpnTransportCfg"><option value="auto">Auto from ZIP</option><option value="udp">UDP</option><option value="tcp">TCP</option></select></div>
        <div class="vpnField"><label>Pre-shared</label><input id="vpnPreShared" type="password" autocomplete="new-password" placeholder="CyberGhost / leave blank to keep saved"><div id="vpnPreState" class="vpnSecretState"></div></div>
        <div class="vpnField"><label>Generated OpenVPN username</label><input id="vpnUser" autocomplete="off" placeholder="Leave blank to keep saved value"><div id="vpnUserState" class="vpnSecretState"></div></div>
        <div class="vpnField"><label>Generated OpenVPN password</label><input id="vpnPass" type="password" autocomplete="new-password" placeholder="Leave blank to keep saved value"><div id="vpnPassState" class="vpnSecretState"></div></div>
        <div class="vpnField full"><label>CyberGhost configuration ZIP</label><input id="vpnBundle" type="file" accept=".zip,application/zip"><div id="vpnBundleState" class="vpnBundleState">Required for a new connection. Expected files: openvpn.ovpn, ca.crt, client.crt, client.key.</div></div>
        <div class="vpnField full"><label>LAN CIDRs allowed outside the VPN</label><input id="vpnCidrs" value="192.168.0.0/16,10.0.0.0/8,172.30.0.0/24"></div>
        <div class="vpnField full"><label>CyberGhost extra features used when generating this profile</label><div class="vpnChecks">
          <label class="vpnCheck"><input id="vpnMalicious" type="checkbox"> Protection against malicious websites</label>
          <label class="vpnCheck"><input id="vpnAds" type="checkbox"> Block ads</label>
          <label class="vpnCheck"><input id="vpnTracking" type="checkbox"> Block online tracking</label>
          <label class="vpnCheck"><input id="vpnHttps" type="checkbox"> Redirect to HTTPS</label>
        </div><div class="vpnSecretState">These switches record the CyberGhost portal options used to generate the profile. They are not independently toggled by Gluetun; replace the CyberGhost ZIP if you regenerate the connection with different provider-side features.</div></div>
        <div class="vpnField full"><label class="vpnCheck"><input id="vpnStartup" type="checkbox"> Use this connection automatically when the VPN gateway starts</label></div>
      </div>
      <div class="vpnActions"><button class="btn" id="vpnSaveProfile">Save connection</button><button class="btn ghost" id="vpnSaveActivate">Save & Activate</button></div>
      <div id="vpnSaveState" class="saveState"></div>
    </div><div class="foot">Secrets are write-only. Existing passwords, pre-shared values and certificate material are never sent back to the browser.</div></article>

    <article class="panel"><div class="title row"><span>VPN LOGS</span><button class="copy" id="vpnLogsRefresh">↻ Refresh</button></div><div class="inner"><pre class="vpnLogs" id="vpnLogs">VPN logs not loaded.</pre></div><div class="foot">Recent Gluetun output. Saved credentials are redacted before logs are returned.</div></article>
  `;
  document.querySelector('main.shell').appendChild(section);

  let editingId = null;
  let profiles = [];

  function setAction(text, bad = false) {
    $('vpnActionState').textContent = text || '';
    $('vpnActionState').style.color = bad ? 'var(--danger)' : '';
  }
  function setSave(text, bad = false) {
    $('vpnSaveState').textContent = text || '';
    $('vpnSaveState').style.color = bad ? 'var(--danger)' : '';
  }
  async function api(path, opts = {}) {
    const response = await fetch(path, {cache:'no-store', ...opts});
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(body.detail || body.message || `HTTP ${response.status}`);
    return body;
  }
  function showVpnPage() {
    document.querySelectorAll('.page').forEach(page => page.classList.add('hidden'));
    document.querySelectorAll('.tab').forEach(item => item.classList.remove('active'));
    section.classList.remove('hidden');
    tab.classList.add('active');
    refreshAll();
  }
  tab.addEventListener('click', showVpnPage);

  function renderStatus(data) {
    const g = data.gluetun || {}, routing = data.routing || {}, active = data.activeProfile || {};
    $('vpnMode').innerHTML = data.deploymentMode === 'vpn' ? badge(true, 'VPN') : badge(false, 'Direct');
    const running = g.vpnStatus === 'running';
    $('vpnTunnel').innerHTML = badge(running, g.vpnStatus || (g.present ? 'starting' : 'not deployed'));
    $('vpnActive').textContent = active.name || 'None';
    $('vpnPublicIp').textContent = g.publicIp || '—';
    $('vpnKill').innerHTML = badge(!!routing.killSwitchActive, routing.killSwitchActive ? 'Active' : 'Not verified');
    $('vpnTransport').textContent = String(active.transport || (data.runtime || {}).protocol || '—').toUpperCase();
    $('vpnRx').textContent = fmtBytes(g.rxBytes);
    $('vpnTx').textContent = fmtBytes(g.txBytes);
    if (data.deploymentMode !== 'vpn') {
      $('vpnModeHint').innerHTML = '<b>Direct mode is active.</b> The gateway remains online; create/import a connection and enable VPN when ready.';
    } else if (!g.controlAvailable) {
      $('vpnModeHint').innerHTML = `<b>VPN stack detected, control API not ready.</b> ${esc(g.controlError || 'Gluetun may still be starting or waiting for a valid profile.')}`;
    } else {
      $('vpnModeHint').innerHTML = `<b>VPN mode is active.</b> ${esc(active.name || 'Selected connection')} routes Stremio through Gluetun. ${(data.startupProfileId && data.startupProfileId === data.activeProfileId) ? 'This is also the startup connection.' : ''}`;
    }
    const controllable = !!g.present;
    $('vpnConnect').disabled = !controllable || running || data.deploymentMode === 'vpn';
    $('vpnDisconnect').disabled = !controllable || data.deploymentMode !== 'vpn';
    $('vpnReconnect').disabled = !controllable || data.deploymentMode !== 'vpn';
  }

  function featureLabels(p) {
    const f = p.features || {};
    const values = [];
    if (f.malicious_websites) values.push('Malicious-site protection');
    if (f.block_ads) values.push('Ads');
    if (f.block_tracking) values.push('Tracking');
    if (f.redirect_https) values.push('HTTPS redirect');
    return values;
  }

  function renderProfiles(data) {
    profiles = data.profiles || [];
    if (!profiles.length) {
      $('vpnProfiles').innerHTML = '<div class="vpnEmpty">No VPN connections yet. Create one from your CyberGhost router/OpenVPN ZIP.</div>';
      return;
    }
    $('vpnProfiles').innerHTML = profiles.map(p => {
      const flags = [
        p.active ? '<span class="vpnFlag active">ACTIVE</span>' : '',
        p.startupEnabled ? '<span class="vpnFlag startup">START AT BOOT</span>' : '',
        `<span class="vpnFlag">OPENVPN ${esc(String(p.transport || '').toUpperCase())}</span>`,
        ...featureLabels(p).map(v => `<span class="vpnFlag">${esc(v)}</span>`),
      ].filter(Boolean).join('');
      const files = (p.bundleFiles || []).map(name => `✓ ${esc(name)}`).join(' · ');
      return `<div class="vpnProfile">
        <div class="vpnProfileTop"><div><div class="vpnProfileTitle">${esc(p.name)}</div><div class="vpnProfileMeta">${esc(p.country || 'Country not specified')} · ${esc(p.serverGroup || 'Server group unavailable')}${p.serverPort ? ':' + esc(p.serverPort) : ''}</div></div><div>${p.active ? badge(true, 'active') : ''}</div></div>
        <div class="vpnFlags">${flags}</div>
        <div class="vpnFiles">${files || 'Bundle material incomplete'}</div>
        <div class="vpnProfileButtons">
          <button class="mini" data-vpn-action="edit" data-id="${esc(p.id)}">Edit</button>
          <button class="mini" data-vpn-action="activate" data-id="${esc(p.id)}" ${p.active ? 'disabled' : ''}>Activate</button>
          <button class="mini" data-vpn-action="startup" data-id="${esc(p.id)}" data-enabled="${p.startupEnabled ? '0' : '1'}">${p.startupEnabled ? 'Disable startup' : 'Enable at startup'}</button>
          <button class="mini delete" data-vpn-action="delete" data-id="${esc(p.id)}" ${p.active ? 'disabled title="Activate another connection first"' : ''}>Delete</button>
        </div>
      </div>`;
    }).join('');
  }

  async function loadStatus() {
    try { renderStatus(await api('/api/vpn/status')); }
    catch (error) { setAction(`Status error: ${error.message}`, true); }
  }
  async function loadProfiles() {
    try { renderProfiles(await api('/api/vpn/profiles')); }
    catch (error) { $('vpnProfiles').innerHTML = `<div class="vpnInfo">Could not load VPN connections: ${esc(error.message)}</div>`; }
  }
  async function loadLogs() {
    try {
      const data = await api('/api/vpn/logs?lines=250');
      $('vpnLogs').textContent = data.available ? (data.lines || []).join('\n') || 'No VPN log lines yet.' : 'Gluetun container is not running.';
      $('vpnLogs').scrollTop = $('vpnLogs').scrollHeight;
    } catch (error) { $('vpnLogs').textContent = `Could not load VPN logs: ${error.message}`; }
  }
  async function refreshAll() { await Promise.all([loadStatus(), loadProfiles(), loadLogs()]); }

  function resetEditor() {
    editingId = null;
    $('vpnEditorTitle').textContent = 'New CyberGhost connection';
    $('vpnName').value = '';
    $('vpnCountry').value = '';
    $('vpnServerGroup').value = '';
    $('vpnTransportCfg').value = 'auto';
    $('vpnUser').value = '';
    $('vpnPass').value = '';
    $('vpnPreShared').value = 'CyberGhost';
    $('vpnBundle').value = '';
    $('vpnCidrs').value = '192.168.0.0/16,10.0.0.0/8,172.30.0.0/24';
    $('vpnMalicious').checked = false; $('vpnAds').checked = false; $('vpnTracking').checked = false; $('vpnHttps').checked = false; $('vpnStartup').checked = false;
    $('vpnUserState').textContent = 'Required for a new connection';
    $('vpnPassState').textContent = 'Required for a new connection';
    $('vpnPreState').textContent = 'CyberGhost portal field; stored privately';
    $('vpnBundleState').textContent = 'Required for a new connection. Expected files: openvpn.ovpn, ca.crt, client.crt, client.key.';
    setSave('');
  }
  function openNew() {
    resetEditor();
    $('vpnEditor').classList.remove('vpnHidden');
    $('vpnName').focus();
    $('vpnEditor').scrollIntoView({behavior:'smooth', block:'start'});
  }
  function openEdit(id) {
    const p = profiles.find(item => item.id === id);
    if (!p) return;
    resetEditor(); editingId = id;
    $('vpnEditorTitle').textContent = `Edit · ${p.name}`;
    $('vpnName').value = p.name || '';
    $('vpnCountry').value = p.country || '';
    $('vpnServerGroup').value = p.serverGroup || '';
    $('vpnTransportCfg').value = p.transport || 'auto';
    $('vpnCidrs').value = p.firewallOutboundSubnets || '192.168.0.0/16,10.0.0.0/8,172.30.0.0/24';
    const f = p.features || {};
    $('vpnMalicious').checked = !!f.malicious_websites; $('vpnAds').checked = !!f.block_ads; $('vpnTracking').checked = !!f.block_tracking; $('vpnHttps').checked = !!f.redirect_https;
    $('vpnStartup').checked = !!p.startupEnabled;
    const c = p.credentials || {};
    $('vpnUserState').textContent = c.username ? '✓ Saved (value hidden; blank keeps it)' : 'Not configured';
    $('vpnPassState').textContent = c.password ? '✓ Saved (value hidden; blank keeps it)' : 'Not configured';
    $('vpnPreState').textContent = c.preShared ? '✓ Saved (value hidden; blank keeps it)' : 'Not configured';
    $('vpnPreShared').value = '';
    $('vpnBundleState').textContent = `Current bundle material: ${(p.bundleFiles || []).join(', ') || 'incomplete'}. Choose a ZIP only to replace it.`;
    $('vpnEditor').classList.remove('vpnHidden');
    $('vpnEditor').scrollIntoView({behavior:'smooth', block:'start'});
  }

  async function fileBase64(file) {
    const bytes = new Uint8Array(await file.arrayBuffer());
    let binary = '';
    const chunk = 0x8000;
    for (let i = 0; i < bytes.length; i += chunk) binary += String.fromCharCode(...bytes.subarray(i, i + chunk));
    return btoa(binary);
  }
  async function profileBody() {
    const file = $('vpnBundle').files[0];
    return {
      name: $('vpnName').value.trim(),
      country: $('vpnCountry').value.trim(),
      server_group: $('vpnServerGroup').value.trim(),
      transport: $('vpnTransportCfg').value,
      username: $('vpnUser').value || null,
      password: $('vpnPass').value || null,
      pre_shared: $('vpnPreShared').value || null,
      bundle_base64: file ? await fileBase64(file) : null,
      bundle_filename: file ? file.name : null,
      firewall_outbound_subnets: $('vpnCidrs').value.trim(),
      features: {malicious_websites:$('vpnMalicious').checked, block_ads:$('vpnAds').checked, block_tracking:$('vpnTracking').checked, redirect_https:$('vpnHttps').checked},
      startup_enabled: $('vpnStartup').checked,
    };
  }
  async function saveProfile(activateAfter = false) {
    setSave('Validating CyberGhost connection…');
    try {
      const body = await profileBody();
      if (!body.name) throw new Error('Connection name is required.');
      if (!editingId && !body.bundle_base64) throw new Error('Select the CyberGhost ZIP configuration bundle.');
      if (!editingId && (!body.username || !body.password)) throw new Error('CyberGhost OpenVPN username and password are required.');
      const id = editingId;
      const path = id ? `/api/vpn/profiles/${encodeURIComponent(id)}` : '/api/vpn/profiles';
      const saved = await api(path, {method:id ? 'PUT' : 'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
      editingId = saved.profile.id;
      setSave('Connection saved. Secrets remain hidden.');
      await loadProfiles(); await loadStatus();
      if (activateAfter) {
        setSave('Activating connection…');
        const result = await api(`/api/vpn/profiles/${encodeURIComponent(editingId)}/activate`, {method:'POST'});
        setSave(result.message || 'Connection activated.');
        await refreshAll();
      }
    } catch (error) { setSave(error.message, true); }
  }

  async function activateProfile(id) {
    setAction('Activating selected VPN connection…');
    try {
      const result = await api(`/api/vpn/profiles/${encodeURIComponent(id)}/activate`, {method:'POST'});
      setAction(result.message || 'Connection activated.'); await refreshAll();
    } catch (error) { setAction(error.message, true); }
  }
  async function toggleStartup(id, enabled) {
    setAction(enabled ? 'Setting startup connection…' : 'Disabling startup selection…');
    try {
      const result = await api(`/api/vpn/profiles/${encodeURIComponent(id)}/startup`, {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify({enabled})});
      setAction(result.message || 'Startup preference saved.'); await loadProfiles(); await loadStatus();
    } catch (error) { setAction(error.message, true); }
  }
  async function deleteProfile(id) {
    const p = profiles.find(item => item.id === id);
    if (!confirm(`Delete VPN connection "${p ? p.name : id}"? Credentials and imported certificate files for this profile will be removed.`)) return;
    setAction('Deleting VPN connection…');
    try { await api(`/api/vpn/profiles/${encodeURIComponent(id)}`, {method:'DELETE'}); setAction('Connection deleted.'); await loadProfiles(); await loadStatus(); }
    catch (error) { setAction(error.message, true); }
  }

  $('vpnProfiles').addEventListener('click', event => {
    const button = event.target.closest('[data-vpn-action]'); if (!button) return;
    const id = button.dataset.id, action = button.dataset.vpnAction;
    if (action === 'edit') openEdit(id);
    if (action === 'activate') activateProfile(id);
    if (action === 'startup') toggleStartup(id, button.dataset.enabled === '1');
    if (action === 'delete') deleteProfile(id);
  });
  $('vpnBundle').addEventListener('change', () => {
    const file = $('vpnBundle').files[0];
    $('vpnBundleState').textContent = file ? `Selected: ${file.name} · ${(file.size/1024).toFixed(1)} KB. Server will verify openvpn.ovpn + ca.crt + client.crt + client.key.` : 'No ZIP selected.';
  });
  $('vpnNew').onclick = openNew;
  $('vpnCancelEdit').onclick = () => $('vpnEditor').classList.add('vpnHidden');
  $('vpnSaveProfile').onclick = () => saveProfile(false);
  $('vpnSaveActivate').onclick = () => saveProfile(true);
  $('vpnRefresh').onclick = refreshAll;
  $('vpnLogsRefresh').onclick = loadLogs;

  async function action(path, label) {
    setAction(`${label}…`);
    try { const data = await api(path, {method:'POST'}); setAction(data.message || `${label} requested.`); await refreshAll(); }
    catch (error) { setAction(error.message, true); }
  }
  $('vpnConnect').onclick = () => action('/api/vpn/connect', 'Connecting');
  $('vpnDisconnect').onclick = () => action('/api/vpn/disconnect', 'Disconnecting');
  $('vpnReconnect').onclick = () => action('/api/vpn/reconnect', 'Reconnecting');
  $('vpnTest').onclick = async () => {
    $('vpnTestResult').textContent = 'Running protection test…';
    try {
      const d = await api('/api/vpn/test', {method:'POST'});
      $('vpnTestResult').textContent = [
        `Result: ${d.result}`,
        `Protected: ${d.protected ? 'YES' : 'NO / NOT PROVEN'}`,
        `Host WAN IP: ${d.hostPublicIp || 'unavailable'}`,
        `VPN public IP: ${d.vpnPublicIp || 'unavailable'}`,
        `Stremio public IP: ${d.stremioPublicIp || 'blocked/unavailable'}`,
        `Kill switch: ${d.killSwitchActive ? 'active' : 'not verified'}`,
        `Reason: ${d.reason || ''}`,
      ].join('\n');
    } catch (error) { $('vpnTestResult').textContent = `Protection test failed: ${error.message}`; }
  };

  refreshAll();
  setInterval(() => { if (!section.classList.contains('hidden')) loadStatus(); }, 10000);
})();
