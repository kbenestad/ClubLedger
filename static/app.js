/* ClubLedger – frontend */

let cfg = { currency_unit: 'pence', currency_symbol: '£', currency_divisor: 100, club_name: 'ClubLedger' };
let cashierMember = null;
let barMember = null;

// ---------------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------------
(async function init() {
  try {
    const r = await fetch('/config');
    cfg = await r.json();
    document.getElementById('navBrand').textContent = cfg.club_name;
    document.title = cfg.club_name;
    document.querySelectorAll('.currency-unit').forEach(el => {
      el.textContent = cfg.currency_unit;
    });
  } catch (e) { /* use defaults */ }

  // Nav
  document.querySelectorAll('.nav-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      document.querySelectorAll('.view').forEach(v => v.classList.add('hidden'));
      document.getElementById('view-' + btn.dataset.view).classList.remove('hidden');
    });
  });

  // Register form
  document.getElementById('registerForm').addEventListener('submit', async e => {
    e.preventDefault();
    await registerMember();
  });

  // Enter key on search fields
  document.getElementById('memberSearch').addEventListener('keydown', e => { if (e.key === 'Enter') searchMembers(); });
  document.getElementById('cashierSearch').addEventListener('keydown', e => { if (e.key === 'Enter') cashierSearchMembers(); });
  document.getElementById('barSearch').addEventListener('keydown', e => { if (e.key === 'Enter') barSearchMembers(); });

  searchMembers();
})();

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
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

// ---------------------------------------------------------------------------
// Members view
// ---------------------------------------------------------------------------
async function registerMember() {
  const number = document.getElementById('reg-number').value.trim();
  const name = document.getElementById('reg-name').value.trim();
  const pin = document.getElementById('reg-pin').value;
  if (!number || !name || !pin) { setMsg('registerMsg', 'All fields required.', 'err'); return; }
  try {
    const m = await apiFetch('/members', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ member_number: number, name, pin })
    });
    setMsg('registerMsg', `Registered: ${m.name} (#${m.member_number})`, 'ok');
    document.getElementById('registerForm').reset();
    searchMembers();
  } catch (e) {
    setMsg('registerMsg', e.message, 'err');
  }
}

async function searchMembers() {
  const q = document.getElementById('memberSearch').value.trim();
  const url = q ? `/members?q=${encodeURIComponent(q)}` : '/members';
  try {
    const members = await apiFetch(url);
    renderMemberTable(members);
  } catch (e) {
    console.error(e);
  }
}

function renderMemberTable(members) {
  const tbody = document.querySelector('#memberTable tbody');
  if (!members.length) { tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:#888">No members found</td></tr>'; return; }
  tbody.innerHTML = members.map(m => `
    <tr>
      <td>${esc(m.member_number)}</td>
      <td>${esc(m.name)}</td>
      <td class="num ${balanceClass(m.balance)}">${esc(m.balance_display)}</td>
      <td>${m.created_at ? m.created_at.slice(0,10) : ''}</td>
      <td>
        <a href="/members/${m.id}/statement" target="_blank" class="btn" style="padding:4px 10px;font-size:.82rem">Statement</a>
      </td>
    </tr>`).join('');
}

// ---------------------------------------------------------------------------
// Cashier view
// ---------------------------------------------------------------------------
async function cashierSearchMembers() {
  const q = document.getElementById('cashierSearch').value.trim();
  const url = q ? `/members?q=${encodeURIComponent(q)}` : '/members';
  try {
    const members = await apiFetch(url);
    const list = document.getElementById('cashierMemberList');
    list.innerHTML = members.map(m => `
      <div class="member-pick-item" onclick="selectCashierMember(${m.id}, '${esc(m.name)}', '${esc(m.member_number)}', ${m.balance}, '${esc(m.balance_display)}')">
        <div>
          <div class="member-pick-name">${esc(m.name)}</div>
          <div class="member-pick-sub">#${esc(m.member_number)}</div>
        </div>
        <div class="${balanceClass(m.balance)}">${esc(m.balance_display)}</div>
      </div>`).join('');
  } catch (e) { console.error(e); }
}

function selectCashierMember(id, name, number, balance, balanceDisplay) {
  cashierMember = { id, name, number };
  document.getElementById('cashierMemberList').innerHTML = '';
  document.getElementById('cashierSelected').innerHTML =
    `<strong>${esc(name)}</strong> &nbsp; #${esc(number)} &nbsp; Balance: <span class="${balanceClass(balance)}">${esc(balanceDisplay)}</span>`;
  document.getElementById('cashierForm').classList.remove('hidden');
  setMsg('cashierMsg', '', '');
}

function clearCashierSelection() {
  cashierMember = null;
  document.getElementById('cashierForm').classList.add('hidden');
  document.getElementById('cashierAmount').value = '';
  document.getElementById('cashierStaff').value = '';
  document.getElementById('cashierNote').value = '';
  setMsg('cashierMsg', '', '');
}

async function doTopup() {
  if (!cashierMember) return;
  const amount = parseInt(document.getElementById('cashierAmount').value, 10);
  const staff = document.getElementById('cashierStaff').value.trim();
  const note = document.getElementById('cashierNote').value.trim();
  if (!amount || isNaN(amount) || amount <= 0) { setMsg('cashierMsg', 'Enter a valid amount.', 'err'); return; }
  if (!staff) { setMsg('cashierMsg', 'Staff name required.', 'err'); return; }
  try {
    const r = await apiFetch('/topup', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ member_id: cashierMember.id, amount, staff_name: staff, note: note || null })
    });
    setMsg('cashierMsg', `Top-up complete. New balance: ${r.new_balance_display}`, 'ok');
    clearCashierSelection();
    searchMembers();
  } catch (e) {
    setMsg('cashierMsg', e.message, 'err');
  }
}

// ---------------------------------------------------------------------------
// Bar view
// ---------------------------------------------------------------------------
async function barSearchMembers() {
  const q = document.getElementById('barSearch').value.trim();
  const url = q ? `/members?q=${encodeURIComponent(q)}` : '/members';
  try {
    const members = await apiFetch(url);
    const list = document.getElementById('barMemberList');
    list.innerHTML = members.map(m => `
      <div class="member-pick-item" onclick="selectBarMember(${m.id}, '${esc(m.name)}', '${esc(m.member_number)}', ${m.balance}, '${esc(m.balance_display)}')">
        <div>
          <div class="member-pick-name">${esc(m.name)}</div>
          <div class="member-pick-sub">#${esc(m.member_number)}</div>
        </div>
        <div class="${balanceClass(m.balance)}">${esc(m.balance_display)}</div>
      </div>`).join('');
  } catch (e) { console.error(e); }
}

function selectBarMember(id, name, number, balance, balanceDisplay) {
  barMember = { id, name, number };
  document.getElementById('barMemberList').innerHTML = '';
  document.getElementById('barSelected').innerHTML =
    `<strong>${esc(name)}</strong> &nbsp; #${esc(number)} &nbsp; Balance: <span class="${balanceClass(balance)}">${esc(balanceDisplay)}</span>`;
  document.getElementById('barForm').classList.remove('hidden');
  document.getElementById('barProductSearch').value = '';
  document.getElementById('barProductResults').innerHTML = '';
  setMsg('barMsg', '', '');
}

function clearBarSelection() {
  barMember = null;
  document.getElementById('barForm').classList.add('hidden');
  document.getElementById('barAmount').value = '';
  document.getElementById('barPin').value = '';
  document.getElementById('barStaff').value = '';
  document.getElementById('barNote').value = '';
  document.getElementById('barProductSearch').value = '';
  document.getElementById('barProductResults').innerHTML = '';
  setMsg('barMsg', '', '');
}

let productTimer = null;
async function barProductLookup() {
  clearTimeout(productTimer);
  productTimer = setTimeout(async () => {
    const q = document.getElementById('barProductSearch').value.trim();
    if (!q) { document.getElementById('barProductResults').innerHTML = ''; return; }
    try {
      const products = await apiFetch(`/products?q=${encodeURIComponent(q)}`);
      const div = document.getElementById('barProductResults');
      if (!products.length) { div.innerHTML = '<div style="color:#888;font-size:.88rem;padding:4px">No products found</div>'; return; }
      div.innerHTML = products.map(p => `
        <div class="product-item" onclick="selectProduct(${p.price}, ${p.member_price || p.price}, '${esc(p.name)}${p.brand ? ' – '+esc(p.brand) : ''}')">
          <div>
            <strong>${esc(p.name)}</strong>${p.brand ? ` <span style="color:#888">– ${esc(p.brand)}</span>` : ''}
            ${p.search_tags ? `<div style="font-size:.78rem;color:#aaa">${esc(p.search_tags)}</div>` : ''}
          </div>
          <div>
            <span class="product-price">${esc(p.price_display)}</span>
            ${p.member_price_display ? `<span style="font-size:.82rem;color:#34d399;margin-left:6px">mbr: ${esc(p.member_price_display)}</span>` : ''}
          </div>
        </div>`).join('');
    } catch (e) { console.error(e); }
  }, 250);
}

function selectProduct(price, memberPrice, label) {
  document.getElementById('barAmount').value = memberPrice;
  document.getElementById('barNote').value = label;
  document.getElementById('barProductResults').innerHTML = '';
  document.getElementById('barProductSearch').value = '';
}

async function doCharge() {
  if (!barMember) return;
  const amount = parseInt(document.getElementById('barAmount').value, 10);
  const pin = document.getElementById('barPin').value;
  const staff = document.getElementById('barStaff').value.trim();
  const note = document.getElementById('barNote').value.trim();
  if (!amount || isNaN(amount) || amount <= 0) { setMsg('barMsg', 'Enter a valid amount.', 'err'); return; }
  if (!pin) { setMsg('barMsg', 'PIN required.', 'err'); return; }
  if (!staff) { setMsg('barMsg', 'Staff name required.', 'err'); return; }
  try {
    const r = await apiFetch('/charge', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ member_id: barMember.id, amount, pin, staff_name: staff, note: note || null })
    });
    setMsg('barMsg', `Charge complete. New balance: ${r.new_balance_display}`, 'ok');
    clearBarSelection();
    searchMembers();
  } catch (e) {
    setMsg('barMsg', e.message, 'err');
  }
}

// ---------------------------------------------------------------------------
// XSS-safe escape
// ---------------------------------------------------------------------------
function esc(str) {
  if (str == null) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}
