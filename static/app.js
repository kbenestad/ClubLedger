/* ClubLedger – main SPA */

let currentUser  = null;
let cashierMember = null;
let barMember     = null;
let editMemberId  = null;
let editAccountId = null;

// ---------------------------------------------------------------------------
// Boot – check session, then either show login or start the app
// ---------------------------------------------------------------------------
(async function boot() {
  // Load config first so the login page shows the club name
  await loadConfig();
  document.getElementById('loginBrand').textContent = cfg.club_name;

  let me = null;
  try { me = await apiFetch('/auth/me'); } catch (e) { /* not logged in */ }

  if (!me) { showLogin(); return; }
  currentUser = me;
  await startApp();
})();

function showLogin() {
  document.getElementById('loginOverlay').classList.remove('hidden');
  document.getElementById('loginUsername').focus();
  document.getElementById('loginForm').addEventListener('submit', doLogin, { once: true });
}

async function doLogin(e) {
  e.preventDefault();
  const username = document.getElementById('loginUsername').value.trim();
  const password = document.getElementById('loginPassword').value;
  try {
    currentUser = await apiFetch('/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password })
    });
    document.getElementById('loginOverlay').classList.add('hidden');
    await startApp();
  } catch (err) {
    setMsg('loginMsg', err.message, 'err');
    document.getElementById('loginForm').addEventListener('submit', doLogin, { once: true });
  }
}

async function doLogout() {
  try { await fetch('/auth/logout', { method: 'POST' }); } catch (e) { /* ignore */ }
  currentUser = null;
  // Reset tab visibility for next login
  document.getElementById('adminTabBtn').classList.add('hidden');
  document.querySelector('[data-view="cashier"]').classList.remove('hidden');
  document.querySelector('[data-view="bar"]').classList.remove('hidden');
  // Reset to members tab
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  document.querySelector('[data-view="members"]').classList.add('active');
  document.querySelectorAll('.view').forEach(v => v.classList.add('hidden'));
  document.getElementById('view-members').classList.remove('hidden');
  showLogin();
}

async function startApp() {
  document.getElementById('loginOverlay').classList.add('hidden');
  await loadConfig();

  const brand = document.getElementById('navBrand');
  if (brand) brand.textContent = cfg.club_name;
  document.getElementById('navUser').textContent = currentUser.name;

  // Role-based tab visibility
  if (currentUser.role === 'admin') {
    document.getElementById('adminTabBtn').classList.remove('hidden');
  }
  if (currentUser.role === 'pos-staff') {
    document.querySelector('[data-view="cashier"]').classList.add('hidden');
  }
  if (currentUser.role === 'cashier') {
    document.querySelector('[data-view="bar"]').classList.add('hidden');
  }

  // Nav tab switching
  document.querySelectorAll('.nav-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      document.querySelectorAll('.view').forEach(v => v.classList.add('hidden'));
      document.getElementById('view-' + btn.dataset.view).classList.remove('hidden');
      if (btn.dataset.view === 'admin') loadAdminView();
    });
  });

  // Form submit handlers
  document.getElementById('registerForm').addEventListener('submit', e => { e.preventDefault(); registerMember(); });
  document.getElementById('editForm').addEventListener('submit', e => { e.preventDefault(); saveEdit(); });
  document.getElementById('editAccountForm').addEventListener('submit', e => { e.preventDefault(); saveEditAccount(); });
  document.getElementById('settingsForm').addEventListener('submit', e => { e.preventDefault(); saveSettings(); });
  document.getElementById('addAccountForm').addEventListener('submit', e => { e.preventDefault(); addAccount(); });

  // Enter-key on search inputs
  document.getElementById('memberSearch').addEventListener('keydown',  e => { if (e.key === 'Enter') searchMembers(); });
  document.getElementById('cashierSearch').addEventListener('keydown', e => { if (e.key === 'Enter') cashierSearchMembers(); });
  document.getElementById('barSearch').addEventListener('keydown',     e => { if (e.key === 'Enter') barSearchMembers(); });

  searchMembers();
}

// ---------------------------------------------------------------------------
// Amount helpers  (users enter major units, we send minor units)
// ---------------------------------------------------------------------------

const ROLE_LABELS = { admin: 'Admin', cashier: 'Cashier', 'pos-staff': 'POS Staff' };
function fmtRole(role) { return ROLE_LABELS[role] || role; }

function toMinor(inputId) {
  const v = parseFloat(document.getElementById(inputId).value);
  if (isNaN(v) || v <= 0) return null;
  return Math.round(v * cfg.currency_divisor);
}

// ---------------------------------------------------------------------------
// Members view
// ---------------------------------------------------------------------------
async function registerMember() {
  const number = document.getElementById('reg-number').value.trim();
  const name   = document.getElementById('reg-name').value.trim();
  const pin    = document.getElementById('reg-pin').value;
  if (!number || !name || !pin) { setMsg('registerMsg', 'All fields required.', 'err'); return; }
  try {
    const m = await apiFetch('/members', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ member_number: number, name, pin })
    });
    setMsg('registerMsg', `Registered: ${m.name} (#${m.member_number})`, 'ok');
    document.getElementById('registerForm').reset();
    searchMembers();
  } catch (err) { setMsg('registerMsg', err.message, 'err'); }
}

async function searchMembers() {
  const q = document.getElementById('memberSearch').value.trim();
  try {
    const members = await apiFetch(q ? `/members?q=${encodeURIComponent(q)}` : '/members');
    renderMemberTable(members);
  } catch (e) { console.error(e); }
}

function renderMemberTable(members) {
  const tbody = document.querySelector('#memberTable tbody');
  if (!members.length) {
    tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:#888">No members found</td></tr>';
    return;
  }
  tbody.innerHTML = members.map(m => `
    <tr>
      <td>${esc(m.member_number)}</td>
      <td>${esc(m.name)}</td>
      <td class="num ${balanceClass(m.balance)}">${esc(m.balance_display)}</td>
      <td>${m.created_at ? m.created_at.slice(0, 10) : ''}</td>
      <td class="row-actions">
        <a href="/members/${m.id}/statement" target="_blank" class="btn row-btn">Statement</a>
        <button class="btn row-btn" onclick="openEditModal(${m.id},'${esc(m.name)}','${esc(m.member_number)}')">Edit</button>
        ${m.balance === 0
          ? `<button class="btn btn-danger row-btn" onclick="deleteMember(${m.id},'${esc(m.name)}')">Delete</button>`
          : ''}
      </td>
    </tr>`).join('');
}

// Edit member modal
function openEditModal(id, name, number) {
  editMemberId = id;
  document.getElementById('edit-number').value = number;
  document.getElementById('edit-name').value   = name;
  document.getElementById('edit-pin').value    = '';
  setMsg('editMsg', '', '');
  document.getElementById('editModal').classList.remove('hidden');
  document.getElementById('edit-name').focus();
}

function closeEditModal() {
  editMemberId = null;
  document.getElementById('editModal').classList.add('hidden');
}

async function saveEdit() {
  if (!editMemberId) return;
  const body = {
    member_number: document.getElementById('edit-number').value.trim(),
    name:          document.getElementById('edit-name').value.trim(),
  };
  const pin = document.getElementById('edit-pin').value;
  if (pin) body.pin = pin;
  try {
    await apiFetch(`/members/${editMemberId}`, {
      method: 'PUT', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    closeEditModal();
    searchMembers();
  } catch (err) { setMsg('editMsg', err.message, 'err'); }
}

async function deleteMember(id, name) {
  if (!confirm(`Delete member "${name}"?\n\nThis permanently removes their account and transaction history.`)) return;
  try {
    await apiFetch(`/members/${id}`, { method: 'DELETE' });
    searchMembers();
  } catch (err) { alert(err.message); }
}

// ---------------------------------------------------------------------------
// Cashier view
// ---------------------------------------------------------------------------
async function cashierSearchMembers() {
  const q = document.getElementById('cashierSearch').value.trim();
  try {
    const members = await apiFetch(q ? `/members?q=${encodeURIComponent(q)}` : '/members');
    document.getElementById('cashierMemberList').innerHTML = members.map(m => `
      <div class="member-pick-item" onclick="selectCashierMember(${m.id},'${esc(m.name)}','${esc(m.member_number)}',${m.balance},'${esc(m.balance_display)}')">
        <div><div class="member-pick-name">${esc(m.name)}</div><div class="member-pick-sub">#${esc(m.member_number)}</div></div>
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
  document.getElementById('cashierNote').value   = '';
  setMsg('cashierMsg', '', '');
}

async function doTopup() {
  if (!cashierMember) return;
  const amount = toMinor('cashierAmount');
  const note   = document.getElementById('cashierNote').value.trim();
  if (!amount) { setMsg('cashierMsg', 'Enter a valid amount.', 'err'); return; }
  try {
    const r = await apiFetch('/topup', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ member_id: cashierMember.id, amount, note: note || null })
    });
    window.open(`/receipt/${r.entry_id}`, '_blank');
    setMsg('cashierMsg', `Top-up complete. New balance: ${r.new_balance_display}`, 'ok');
    clearCashierSelection();
  } catch (err) { setMsg('cashierMsg', err.message, 'err'); }
}

// ---------------------------------------------------------------------------
// Bar view
// ---------------------------------------------------------------------------
async function barSearchMembers() {
  const q = document.getElementById('barSearch').value.trim();
  try {
    const members = await apiFetch(q ? `/members?q=${encodeURIComponent(q)}` : '/members');
    document.getElementById('barMemberList').innerHTML = members.map(m => `
      <div class="member-pick-item" onclick="selectBarMember(${m.id},'${esc(m.name)}','${esc(m.member_number)}',${m.balance},'${esc(m.balance_display)}')">
        <div><div class="member-pick-name">${esc(m.name)}</div><div class="member-pick-sub">#${esc(m.member_number)}</div></div>
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
  setMsg('barMsg', '', '');
}

function clearBarSelection() {
  barMember = null;
  document.getElementById('barForm').classList.add('hidden');
  document.getElementById('barAmount').value = '';
  document.getElementById('barPin').value    = '';
  document.getElementById('barNote').value   = '';
  setMsg('barMsg', '', '');
}

async function doCharge() {
  if (!barMember) return;
  const amount = toMinor('barAmount');
  const pin    = document.getElementById('barPin').value;
  const note   = document.getElementById('barNote').value.trim();
  if (!amount) { setMsg('barMsg', 'Enter a valid amount.', 'err'); return; }
  if (!pin)    { setMsg('barMsg', 'PIN required.', 'err'); return; }
  try {
    const r = await apiFetch('/charge', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ member_id: barMember.id, amount, pin, note: note || null })
    });
    window.open(`/receipt/${r.entry_id}`, '_blank');
    setMsg('barMsg', `Charge complete. New balance: ${r.new_balance_display}`, 'ok');
    clearBarSelection();
  } catch (err) { setMsg('barMsg', err.message, 'err'); }
}

// ---------------------------------------------------------------------------
// Admin view
// ---------------------------------------------------------------------------
async function loadAdminView() {
  await Promise.all([loadAdminSettings(), loadStaffAccounts()]);
}

async function loadAdminSettings() {
  try {
    const s = await apiFetch('/admin/settings');
    const div = s.currency_divisor || 100;
    document.getElementById('s-club-name').value        = s.club_name        || '';
    document.getElementById('s-currency-symbol').value  = s.currency_symbol  || '';
    document.getElementById('s-currency-major').value   = s.currency_major   || '';
    document.getElementById('s-currency-minor').value   = s.currency_minor   || '';
    document.getElementById('s-currency-divisor').value = div;
    document.getElementById('s-min-topup').value        = ((s.min_topup  || 0) / div).toFixed(2);
    document.getElementById('s-max-topup').value        = ((s.max_topup  || 0) / div).toFixed(2);
    document.getElementById('s-max-charge').value       = ((s.max_charge || 0) / div).toFixed(2);
    document.getElementById('s-receipt-footer').value   = s.receipt_footer   || '';
    document.getElementById('s-allow-negative').checked = !!s.allow_negative_balance;
    const sym = s.currency_symbol || '';
    document.getElementById('s-min-hint').textContent   = `in ${s.currency_major || 'major units'}`;
    document.getElementById('s-max-hint').textContent   = `in ${s.currency_major || 'major units'}`;
    document.getElementById('s-charge-hint').textContent= `in ${s.currency_major || 'major units'}`;
  } catch (err) { setMsg('settingsMsg', err.message, 'err'); }
}

async function saveSettings() {
  const div = parseInt(document.getElementById('s-currency-divisor').value, 10) || 100;
  const body = {
    club_name:              document.getElementById('s-club-name').value.trim(),
    currency_symbol:        document.getElementById('s-currency-symbol').value.trim(),
    currency_major:         document.getElementById('s-currency-major').value.trim(),
    currency_minor:         document.getElementById('s-currency-minor').value.trim(),
    currency_divisor:       div,
    min_topup:              Math.round(parseFloat(document.getElementById('s-min-topup').value)  * div),
    max_topup:              Math.round(parseFloat(document.getElementById('s-max-topup').value)  * div),
    max_charge:             Math.round(parseFloat(document.getElementById('s-max-charge').value) * div),
    receipt_footer:         document.getElementById('s-receipt-footer').value,
    allow_negative_balance: document.getElementById('s-allow-negative').checked,
  };
  try {
    await apiFetch('/admin/settings', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    setMsg('settingsMsg', 'Settings saved.', 'ok');
    await loadConfig();  // refresh frontend cfg
    document.querySelectorAll('.currency-unit').forEach(el => { el.textContent = cfg.currency_major || cfg.currency_unit; });
    if (document.getElementById('navBrand'))
      document.getElementById('navBrand').textContent = cfg.club_name;
  } catch (err) { setMsg('settingsMsg', err.message, 'err'); }
}

// Staff accounts table
async function loadStaffAccounts() {
  try {
    const accounts = await apiFetch('/admin/staff-accounts');
    const tbody = document.querySelector('#staffAccountsTable tbody');
    tbody.innerHTML = accounts.map(a => `
      <tr>
        <td>${esc(a.name)}</td>
        <td>${esc(a.username)}</td>
        <td>${esc(fmtRole(a.role))}</td>
        <td>${a.active ? '<span style="color:#080">Active</span>' : '<span style="color:#999">Inactive</span>'}</td>
        <td class="row-actions">
          <button class="btn row-btn" onclick="openEditAccountModal(${a.id},'${esc(a.name)}','${esc(a.username)}','${esc(a.role)}',${a.active})">Edit</button>
          <button class="btn btn-danger row-btn" onclick="deleteAccount(${a.id},'${esc(a.name)}')">Delete</button>
        </td>
      </tr>`).join('');
  } catch (err) { console.error(err); }
}

async function addAccount() {
  const body = {
    name:     document.getElementById('acc-name').value.trim(),
    username: document.getElementById('acc-username').value.trim(),
    password: document.getElementById('acc-password').value,
    role:     document.getElementById('acc-role').value,
  };
  if (!body.name || !body.username || !body.password) {
    setMsg('accountMsg', 'All fields required.', 'err'); return;
  }
  try {
    await apiFetch('/admin/staff-accounts', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    setMsg('accountMsg', `Account created for ${body.name}.`, 'ok');
    document.getElementById('addAccountForm').reset();
    loadStaffAccounts();
  } catch (err) { setMsg('accountMsg', err.message, 'err'); }
}

function openEditAccountModal(id, name, username, role, active) {
  editAccountId = id;
  document.getElementById('eacc-name').value     = name;
  document.getElementById('eacc-username').value  = username;
  document.getElementById('eacc-password').value  = '';
  document.getElementById('eacc-role').value      = role;
  document.getElementById('eacc-active').checked  = !!active;
  setMsg('editAccountMsg', '', '');
  document.getElementById('editAccountModal').classList.remove('hidden');
}

function closeEditAccountModal() {
  editAccountId = null;
  document.getElementById('editAccountModal').classList.add('hidden');
}

async function saveEditAccount() {
  if (!editAccountId) return;
  const body = {
    name:     document.getElementById('eacc-name').value.trim(),
    username: document.getElementById('eacc-username').value.trim(),
    role:     document.getElementById('eacc-role').value,
    active:   document.getElementById('eacc-active').checked,
  };
  const pw = document.getElementById('eacc-password').value;
  if (pw) body.password = pw;
  try {
    await apiFetch(`/admin/staff-accounts/${editAccountId}`, {
      method: 'PUT', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    closeEditAccountModal();
    loadStaffAccounts();
  } catch (err) { setMsg('editAccountMsg', err.message, 'err'); }
}

async function deleteAccount(id, name) {
  if (!confirm(`Delete account for "${name}"?`)) return;
  try {
    await apiFetch(`/admin/staff-accounts/${id}`, { method: 'DELETE' });
    loadStaffAccounts();
  } catch (err) { alert(err.message); }
}
