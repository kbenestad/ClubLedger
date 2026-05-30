/* ClubLedger – shared helpers */

let cfg = { currency_unit: 'pence', currency_symbol: '£', currency_divisor: 100, club_name: 'ClubLedger' };

async function loadConfig() {
  try {
    const r = await fetch('/config');
    cfg = await r.json();
    const brand = document.getElementById('navBrand');
    if (brand) brand.textContent = cfg.club_name;
    document.title = document.title.replace('ClubLedger', cfg.club_name);
    document.querySelectorAll('.currency-unit').forEach(el => { el.textContent = cfg.currency_unit; });
  } catch (e) { /* use defaults */ }
}

function fmtAmount(pence) {
  return cfg.currency_symbol + (pence / cfg.currency_divisor).toFixed(2);
}

function balanceClass(v) {
  return v < 0 ? 'balance-neg' : 'balance-pos';
}

function setMsg(id, text, type) {
  const el = document.getElementById(id);
  el.textContent = text;
  el.className = 'msg ' + (type || '');
}

async function apiFetch(url, opts) {
  const r = await fetch(url, opts);
  const json = await r.json();
  if (!r.ok) throw new Error(json.detail || 'Server error');
  return json;
}

function esc(str) {
  if (str == null) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

// ---------------------------------------------------------------------------
// Staff dropdown
// ---------------------------------------------------------------------------

async function loadStaffInto(selectId) {
  const sel = document.getElementById(selectId);
  if (!sel) return;
  try {
    const data = await apiFetch('/staff');
    const saved = sessionStorage.getItem('lastStaff') || '';
    sel.innerHTML = '<option value="">&mdash; select staff &mdash;</option>' +
      data.staff.map(n => `<option value="${esc(n)}"${n === saved ? ' selected' : ''}>${esc(n)}</option>`).join('');
    sel.addEventListener('change', () => {
      if (sel.value) sessionStorage.setItem('lastStaff', sel.value);
    });
  } catch (e) { console.error('Could not load staff', e); }
}

async function refreshAllStaffDropdowns() {
  try {
    const data = await apiFetch('/staff');
    const saved = sessionStorage.getItem('lastStaff') || '';
    document.querySelectorAll('select[id$="Staff"]').forEach(sel => {
      sel.innerHTML = '<option value="">&mdash; select staff &mdash;</option>' +
        data.staff.map(n => `<option value="${esc(n)}"${n === saved ? ' selected' : ''}>${esc(n)}</option>`).join('');
    });
    renderStaffChips(data.staff);
  } catch (e) { console.error(e); }
}

function renderStaffChips(staffList) {
  const div = document.getElementById('staffChips');
  if (!div) return;
  div.innerHTML = staffList.map(n => `
    <span class="staff-chip">
      ${esc(n)}
      <button class="chip-del" onclick="removeStaff('${esc(n)}')" title="Remove">&times;</button>
    </span>`).join('');
}

async function addStaff() {
  const input = document.getElementById('staffNameInput');
  const name = input.value.trim();
  if (!name) return;
  try {
    const data = await apiFetch('/staff', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name })
    });
    input.value = '';
    setMsg('staffMsg', `Added: ${name}`, 'ok');
    renderStaffChips(data.staff);
    await refreshAllStaffDropdowns();
  } catch (e) {
    setMsg('staffMsg', e.message, 'err');
  }
}

async function removeStaff(name) {
  try {
    const data = await apiFetch(`/staff/${encodeURIComponent(name)}`, { method: 'DELETE' });
    renderStaffChips(data.staff);
    await refreshAllStaffDropdowns();
  } catch (e) { console.error(e); }
}
