(() => {
  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const fmtBytes = value => {
    const n = Number(value || 0);
    if (!n) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.min(units.length - 1, Math.floor(Math.log(n) / Math.log(1024)));
    return `${(n / (1024 ** i)).toFixed(i > 1 ? 1 : 0)} ${units[i]}`;
  };
  const fmtPct = value => `${Number(value || 0).toFixed(1)}%`;
  const badge = (ok, text) => `<span class="badge ${ok ? '' : 'glBad'}">● ${esc(text)}</span>`;
  const relativeStarted = value => {
    if (!value) return '—';
    const t = new Date(value).getTime();
    if (!Number.isFinite(t)) return String(value);
    let s = Math.max(0, Math.floor((Date.now() - t) / 1000));
    const d = Math.floor(s / 86400); s %= 86400;
    const h = Math.floor(s / 3600); s %= 3600;
    const m = Math.floor(s / 60);
    if (d) return `${d}d ${h}h`;
    if (h) return `${h}h ${m}m`;
    return `${m}m`;
  };

  const css = document.createElement('style');
  css.textContent = `
    .glBad{color:#ff8d95!important;border-color:#8b3341!important;background:#40161d!important}
    .glWarn{color:#ffe073!important;border-color:#8b7933!important;background:#403916!important}
    .glGrid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-bottom:16px}
    .glCard{padding:14px;border:1px solid rgba(232,207,105,.25);border-radius:10px;background:rgba(13,30,21,.95);min-width:0}
    .glCard span{display:block;color:var(--muted);font-size:10px;text-transform:uppercase}.glCard b{display:block;margin-top:5px;font-size:15px;overflow-wrap:anywhere}
    .glActions{display:flex;gap:8px;flex-wrap:wrap;margin:14px 0}.glInfo{padding:12px;border:1px solid rgba(232,207,105,.2);border-radius:9px;background:rgba(15,24,18,.92);color:var(--muted);font-size:12px;margin:10px 0}.glInfo b{color:var(--text)}
    .glConfig{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.glConfigItem{padding:11px;border:1px solid rgba(232,207,105,.18);border-radius:9px;background:rgba(10,25,17,.8);min-width:0}.glConfigItem span{display:block;color:var(--muted);font-size:10px;text-transform:uppercase;margin-bottom:5px}.glConfigItem b,.glConfigItem code{font-size:12px;overflow-wrap:anywhere;white-space:normal}.glConfigItem.full{grid-column:1/-1}
    .glNetwork{display:grid;gap:8px}.glRow{display:grid;grid-template-columns:minmax(150px,.7fr) minmax(0,1.3fr);gap:12px;padding:9px 0;border-bottom:1px solid rgba(232,207,105,.12)}.glRow:last-child{border-bottom:0}.glRow span{color:var(--muted);font-size:11px}.glRow b,.glRow code{font-size:12px;overflow-wrap:anywhere;white-space:normal}
    .glChecks{display:grid;gap:8px}.glCheck{display:grid;grid-template-columns:24px minmax(160px,.8fr) minmax(0,1.2fr);gap:10px;align-items:center;padding:10px;border:1px solid rgba(232,207,105,.18);border-radius:9px;background:rgba(10,25,17,.8)}.glCheckIcon{font-weight:900;font-size:16px}.glCheck.ok .glCheckIcon{color:var(--green)}.glCheck.bad .glCheckIcon{color:var(--danger)}.glCheck small{color:var(--muted);overflow-wrap:anywhere}
    .glLogTools{display:grid;grid-template-columns:auto auto minmax(160px,1fr) auto auto auto;gap:8px;align-items:center;margin-bottom:10px}.glLogTools select,.glLogTools input{border:1px solid rgba(229,198,74,.3);border-radius:8px;background:rgba(13,30,21,.95);color:var(--text);padding:9px;font:inherit;min-width:0}.glAuto{display:flex;align-items:center;gap:6px;color:var(--muted);font-size:11px;white-space:nowrap}.glLogs{min-height:260px;max-height:520px;overflow:auto;padding:14px;border:1px solid #827632;border-radius:9px;background:rgba(2,8,5,.96);color:#cdd4d8;font:11px/1.5 ui-monospace,SFMono-Regular,Consolas,monospace;white-space:pre-wrap;overflow-wrap:anywhere}
    .glStatusLine{color:var(--muted);font-size:11px;margin-top:8px}.glDangerNote{color:#ffacb2}.glLocked{border-left:3px solid #d6b542;padding-left:10px;margin-top:10px;color:var(--muted);font-size:11px}
    @media(max-width:1000px){.glGrid{grid-template-columns:repeat(2,minmax(0,1fr))}.glLogTools{grid-template-columns:1fr 1fr}.glLogTools input{grid-column:1/-1}}
    @media(max-width:650px){.glGrid,.glConfig{grid-template-columns:1fr}.glConfigItem.full{grid-column:auto}.glRow,.glCheck{grid-template-columns:1fr}.glLogTools{grid-template-columns:1fr}.glLogTools input{grid-column:auto}}
  `;
  document.head.appendChild(css);

  const nav = document.querySelector('.tabs');
  if (!nav || $('gluetun')) return;
  const logsTab = [...nav.querySelectorAll('.tab')].find(btn => btn.dataset.page === 'logs');
  const tab = document.createElement('button');
  tab.className = 'tab';
  tab.dataset.page = 'gluetun';
  tab.textContent = 'Gluetun';
  nav.insertBefore(tab, logsTab || null);

  const section = document.createElement('section');
  section.className = 'page hidden';
  section.id = 'gluetun';
  section.innerHTML = `
    <article class="panel"><div class="title row"><span>GLUETUN · GATEWAY STATUS</span><button class="copy" id="glRefresh">↻ Refresh</button></div><div class="inner">
      <div class="glGrid">
        <div class="glCard"><span>Container</span><b id="glContainer">—</b></div>
        <div class="glCard"><span>Docker health</span><b id="glHealth">—</b></div>
        <div class="glCard"><span>VPN tunnel</span><b id="glVpn">—</b></div>
        <div class="glCard"><span>Public IP</span><b id="glPublicIp">—</b></div>
        <div class="glCard"><span>Active profile</span><b id="glProfile">—</b></div>
        <div class="glCard"><span>Uptime</span><b id="glUptime">—</b></div>
        <div class="glCard"><span>CPU</span><b id="glCpu">—</b></div>
        <div class="glCard"><span>Memory</span><b id="glMemory">—</b></div>
        <div class="glCard"><span>Received</span><b id="glRx">—</b></div>
        <div class="glCard"><span>Sent</span><b id="glTx">—</b></div>
        <div class="glCard"><span>DNS</span><b id="glDns">—</b></div>
        <div class="glCard"><span>Updater</span><b id="glUpdater">—</b></div>
      </div>
      <div id="glStatusInfo" class="glInfo">Loading Gluetun status…</div>
      <div class="glActions">
        <button class="btn" id="glStart">Start gateway</button>
        <button class="btn ghost" id="glRestart">Restart gateway</button>
        <button class="btn danger" id="glStop">Stop gateway</button>
        <button class="btn ghost" id="glValidate">Validate path</button>
        <button class="btn ghost" id="glOpenVpn">Open VPN connections</button>
      </div>
      <div id="glActionState" class="saveState"></div>
    </div><div class="foot">Stopping Gluetun is fail-closed: Stremio should lose Internet access instead of falling back to the host WAN.</div></article>

    <article class="panel"><div class="title">GLUETUN CONFIGURATION</div><div class="inner">
      <div class="glConfig">
        <div class="glConfigItem"><span>VPN provider mode</span><b id="glCfgProvider">—</b></div>
        <div class="glConfigItem"><span>VPN type</span><b id="glCfgType">—</b></div>
        <div class="glConfigItem"><span>Firewall / kill switch</span><b id="glCfgFirewall">—</b></div>
        <div class="glConfigItem"><span>Firewall input ports</span><code id="glCfgInputPorts">—</code></div>
        <div class="glConfigItem full"><span>Allowed LAN CIDRs outside VPN</span><code id="glCfgCidrs">—</code></div>
        <div class="glConfigItem"><span>DNS service</span><b id="glCfgDnsServer">—</b></div>
        <div class="glConfigItem"><span>DNS listen address</span><code id="glCfgDnsAddress">—</code></div>
        <div class="glConfigItem"><span>DNS upstream transport</span><b id="glCfgDnsType">—</b></div>
        <div class="glConfigItem"><span>DNS upstream resolvers</span><code id="glCfgDnsResolvers">—</code></div>
        <div class="glConfigItem"><span>DNS cache</span><b id="glCfgDnsCache">—</b></div>
        <div class="glConfigItem"><span>Private Pi-hole DNS proxy</span><code id="glCfgDnsProxy">—</code></div>
        <div class="glConfigItem"><span>Auto-heal VPN</span><b id="glCfgHeal">—</b></div>
        <div class="glConfigItem"><span>Timezone</span><b id="glCfgTz">—</b></div>
        <div class="glConfigItem full"><span>Health TLS targets</span><code id="glCfgTargets">—</code></div>
        <div class="glConfigItem full"><span>Health ICMP targets</span><code id="glCfgIcmp">—</code></div>
      </div>
      <div class="glLocked"><b>Protected settings:</b> firewall/kill-switch, DNS loopback binding, credentials, certificates, private keys and the Gluetun control API secret are not editable or exposed on this page. Connection-specific settings remain under <b>VPN</b>.</div>
    </div></article>

    <article class="panel"><div class="title">NETWORK & SECURITY</div><div class="inner">
      <div class="glNetwork">
        <div class="glRow"><span>Container image</span><code id="glNetImage">—</code></div>
        <div class="glRow"><span>Container ID</span><code id="glNetId">—</code></div>
        <div class="glRow"><span>Docker networks</span><code id="glNetNetworks">—</code></div>
        <div class="glRow"><span>Stremio network mode</span><code id="glNetMode">—</code></div>
        <div class="glRow"><span>Stremio through Gluetun</span><b id="glNetRouted">—</b></div>
        <div class="glRow"><span>Kill switch</span><b id="glNetKill">—</b></div>
        <div class="glRow"><span>Pi-hole upstream</span><code id="glNetPihole">—</code></div>
        <div class="glRow"><span>Control API</span><b id="glNetControl">—</b></div>
      </div>
    </div></article>

    <article class="panel"><div class="title row"><span>HEALTH VALIDATION</span><button class="copy" id="glValidateAgain">Run validation</button></div><div class="inner">
      <div id="glChecks" class="glChecks"><div class="glInfo">Run validation to test container health, VPN, DNS, Pi-hole upstream, routing and kill switch.</div></div>
      <div id="glValidationSummary" class="glStatusLine"></div>
    </div></article>

    <article class="panel"><div class="title row"><span>GLUETUN LOGS</span><span id="glLogState" class="glStatusLine"></span></div><div class="inner">
      <div class="glLogTools">
        <select id="glLogLines" title="Lines"><option>100</option><option selected>200</option><option>500</option><option>1000</option></select>
        <select id="glLogLevel" title="Level"><option value="all">All levels</option><option value="error">Error</option><option value="warn">Warn</option><option value="info">Info</option><option value="debug">Debug</option></select>
        <input id="glLogQuery" placeholder="Filter text…" autocomplete="off">
        <label class="glAuto"><input id="glLogAuto" type="checkbox"> Auto-refresh</label>
        <button class="copy" id="glLogsRefresh">↻ Refresh</button>
        <button class="copy" id="glLogsClear">Clear viewer</button>
      </div>
      <pre class="glLogs" id="glLogs">Gluetun logs not loaded.</pre>
    </div><div class="foot">Viewer filters are local/read-only. Clearing the viewer does not erase Docker logs. VPN credentials and the control API key are redacted server-side.</div></article>
  `;
  document.querySelector('main.shell').appendChild(section);

  let lastStatus = null;
  let refreshBusy = false;
  let logBusy = false;

  async function api(path, opts = {}) {
    const response = await fetch(path, {cache: 'no-store', ...opts});
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(body.detail || body.message || `HTTP ${response.status}`);
    return body;
  }

  function setAction(text, bad = false) {
    $('glActionState').textContent = text || '';
    $('glActionState').style.color = bad ? 'var(--danger)' : '';
  }

  function renderStatus(data) {
    lastStatus = data;
    const c = data.container || {};
    const v = data.vpn || {};
    const d = data.dns || {};
    const u = data.updater || {};
    const r = data.routing || {};
    const p = data.activeProfile || {};
    const ph = data.pihole || {};
    const cfg = data.config || {};

    $('glContainer').innerHTML = badge(!!c.running, c.present ? (c.status || 'unknown') : 'not deployed');
    $('glHealth').innerHTML = badge(c.health === 'healthy', c.health || 'unavailable');
    $('glVpn').innerHTML = badge(v.status === 'running', v.status || 'unavailable');
    $('glPublicIp').textContent = v.publicIp || '—';
    $('glProfile').textContent = p.name || p.id || 'None';
    $('glUptime').textContent = relativeStarted(c.startedAt);
    $('glCpu').textContent = fmtPct(c.cpuPercent);
    $('glMemory').textContent = c.memoryLimit ? `${fmtBytes(c.memoryUsage)} / ${fmtBytes(c.memoryLimit)}` : fmtBytes(c.memoryUsage);
    $('glRx').textContent = fmtBytes(c.rxBytes);
    $('glTx').textContent = fmtBytes(c.txBytes);
    $('glDns').innerHTML = badge(d.status === 'running', d.status || 'unavailable');
    $('glUpdater').textContent = u.status || 'unavailable';

    if (!c.present) {
      $('glStatusInfo').innerHTML = '<b>Gluetun is not deployed.</b> Start VPN mode with <code>sh start-vpn.sh</code> first.';
    } else if (!c.running) {
      $('glStatusInfo').innerHTML = '<b>Gluetun is stopped.</b> Stremio should remain blocked until the gateway is started again.';
    } else if (!v.controlAvailable) {
      $('glStatusInfo').innerHTML = `<b>Container is running but the control API is unavailable.</b> ${esc(v.controlError || 'Gluetun may still be starting.')}`;
    } else if (v.status !== 'running') {
      $('glStatusInfo').innerHTML = `<b>Gateway is running, VPN tunnel is ${esc(v.status || 'not running')}.</b> Use the VPN page to connect or switch profiles.`;
    } else {
      $('glStatusInfo').innerHTML = `<b>Gateway operational.</b> ${esc(p.name || p.id || 'Active VPN profile')} is routed through Gluetun${v.publicIp ? ` with public IP <code>${esc(v.publicIp)}</code>` : ''}.`;
    }

    $('glStart').disabled = !c.present || !!c.running || !!data.busy;
    $('glRestart').disabled = !c.present || !c.running || !!data.busy;
    $('glStop').disabled = !c.present || !c.running || !!data.busy;

    $('glCfgProvider').textContent = cfg.vpnServiceProvider || '—';
    $('glCfgType').textContent = cfg.vpnType || '—';
    $('glCfgFirewall').innerHTML = badge(!!cfg.firewallEnabled, cfg.firewallEnabled ? 'ON' : 'OFF');
    $('glCfgInputPorts').textContent = cfg.firewallInputPorts || '—';
    $('glCfgCidrs').textContent = cfg.firewallOutboundSubnets || '—';
    $('glCfgDnsServer').innerHTML = badge(!!cfg.dnsServerEnabled, cfg.dnsServerEnabled ? 'ON' : 'OFF');
    $('glCfgDnsAddress').textContent = cfg.dnsAddress || '—';
    $('glCfgDnsType').textContent = String(cfg.dnsUpstreamResolverType || '—').toUpperCase();
    $('glCfgDnsResolvers').textContent = cfg.dnsUpstreamResolvers || '—';
    $('glCfgDnsCache').textContent = cfg.dnsCaching ? 'ON' : 'OFF';
    $('glCfgDnsProxy').textContent = `172.30.0.10:${cfg.dnsProxyPort || 1053} → ${cfg.dnsAddress || '127.0.0.1'}:53`;
    $('glCfgHeal').textContent = cfg.healthRestartVpn ? 'ON' : 'OFF';
    $('glCfgTz').textContent = cfg.timezone || '—';
    $('glCfgTargets').textContent = cfg.healthTargetAddresses || '—';
    $('glCfgIcmp').textContent = cfg.healthIcmpTargetIps || '—';

    $('glNetImage').textContent = c.image || '—';
    $('glNetId').textContent = c.id || '—';
    $('glNetNetworks').textContent = (c.networks || []).map(n => `${n.network}: ${n.ip || 'no IP'}${n.gateway ? ` gw ${n.gateway}` : ''}`).join(' | ') || '—';
    $('glNetMode').textContent = r.networkMode || '—';
    $('glNetRouted').innerHTML = badge(!!r.stremioThroughGluetun, r.stremioThroughGluetun ? 'Yes' : 'No');
    $('glNetKill').innerHTML = badge(!!r.killSwitchActive, r.killSwitchActive ? 'Active' : 'Not verified');
    $('glNetPihole').textContent = ph.upstream || '—';
    $('glNetControl').innerHTML = badge(!!v.controlAvailable, v.controlAvailable ? 'Authenticated / available' : 'Unavailable');
  }

  async function refreshStatus() {
    if (refreshBusy) return;
    refreshBusy = true;
    try {
      renderStatus(await api('/api/gluetun/status'));
    } catch (err) {
      setAction(err.message, true);
    } finally {
      refreshBusy = false;
    }
  }

  async function runAction(action) {
    if (action === 'stop' && !window.confirm('Stop Gluetun? Stremio Internet access should remain blocked until the gateway is started again.')) return;
    setAction(`${action[0].toUpperCase()}${action.slice(1)}ing Gluetun…`);
    try {
      const result = await api(`/api/gluetun/${action}`, {method: 'POST'});
      if (result.status) renderStatus(result.status);
      setAction(`Gluetun ${action} completed.`);
    } catch (err) {
      setAction(err.message, true);
    }
  }

  function renderValidation(data) {
    const checks = data.checks || [];
    $('glChecks').innerHTML = checks.map(item => `
      <div class="glCheck ${item.ok ? 'ok' : 'bad'}">
        <div class="glCheckIcon">${item.ok ? '✓' : '✕'}</div>
        <b>${esc(item.label)}</b>
        <small>${esc(item.detail || '')}</small>
      </div>`).join('') || '<div class="glInfo">No checks returned.</div>';
    $('glValidationSummary').textContent = `${data.passed || 0}/${data.total || checks.length} checks passed${data.ok ? ' · gateway path validated' : ' · review failed checks'}`;
  }

  async function validatePath() {
    setAction('Running Gluetun validation…');
    try {
      const data = await api('/api/gluetun/validate', {method: 'POST'});
      renderValidation(data);
      setAction(data.ok ? 'Validation passed.' : 'Validation completed with failed checks.', !data.ok);
      await refreshStatus();
    } catch (err) {
      setAction(err.message, true);
    }
  }

  async function refreshLogs() {
    if (logBusy) return;
    logBusy = true;
    try {
      const params = new URLSearchParams({
        lines: $('glLogLines').value,
        level: $('glLogLevel').value,
        query: $('glLogQuery').value || ''
      });
      const data = await api(`/api/gluetun/logs?${params.toString()}`);
      $('glLogs').textContent = (data.lines || []).join('\n') || (data.available ? 'No log lines match the current filter.' : 'Gluetun logs are not available.');
      $('glLogState').textContent = `${data.count || 0} lines`;
      $('glLogs').scrollTop = $('glLogs').scrollHeight;
    } catch (err) {
      $('glLogState').textContent = err.message;
    } finally {
      logBusy = false;
    }
  }

  function showGluetunPage() {
    document.querySelectorAll('.page').forEach(page => page.classList.add('hidden'));
    document.querySelectorAll('.tab').forEach(item => item.classList.remove('active'));
    section.classList.remove('hidden');
    tab.classList.add('active');
    refreshStatus();
    refreshLogs();
  }

  tab.addEventListener('click', showGluetunPage);
  $('glRefresh').addEventListener('click', refreshStatus);
  $('glStart').addEventListener('click', () => runAction('start'));
  $('glStop').addEventListener('click', () => runAction('stop'));
  $('glRestart').addEventListener('click', () => runAction('restart'));
  $('glValidate').addEventListener('click', validatePath);
  $('glValidateAgain').addEventListener('click', validatePath);
  $('glOpenVpn').addEventListener('click', () => {
    const vpnTab = [...document.querySelectorAll('.tab')].find(item => item.dataset.page === 'vpn');
    if (vpnTab) vpnTab.click();
  });
  $('glLogsRefresh').addEventListener('click', refreshLogs);
  $('glLogsClear').addEventListener('click', () => {
    $('glLogs').textContent = '';
    $('glLogState').textContent = 'viewer cleared';
  });
  $('glLogLines').addEventListener('change', refreshLogs);
  $('glLogLevel').addEventListener('change', refreshLogs);
  $('glLogQuery').addEventListener('keydown', event => { if (event.key === 'Enter') refreshLogs(); });

  setInterval(() => {
    if (!section.classList.contains('hidden')) refreshStatus();
  }, 10000);
  setInterval(() => {
    if (!section.classList.contains('hidden') && $('glLogAuto').checked) refreshLogs();
  }, 5000);
})();
