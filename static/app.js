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

function populateTransferTypes() {
  const types = Array.isArray(cfg.transfer_types) ? cfg.transfer_types : [];
  ['cashierTransferType', 'withdrawalTransferType'].forEach(id => {
    const sel = document.getElementById(id);
    if (!sel) return;
    const prev = sel.value;
    sel.innerHTML = '<option value="">&mdash; select &mdash;</option>' +
      types.map(t => `<option value="${esc(t)}">${esc(t)}</option>`).join('');
    if (prev && types.includes(prev)) sel.value = prev;
  });
}

async function startApp() {
  document.getElementById('loginOverlay').classList.add('hidden');
  await loadConfig();
  populateTransferTypes();

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
        <button class="btn row-btn" onclick="openEditModal(${m.id},'${esc(m.name)}','${esc(m.member_number)}',${JSON.stringify(m.overdraft_override)})">Edit</button>
        ${m.balance === 0
          ? `<button class="btn btn-danger row-btn" onclick="deleteMember(${m.id},'${esc(m.name)}')">Delete</button>`
          : ''}
      </td>
    </tr>`).join('');
}

// Edit member modal
function openEditModal(id, name, number, overdraftOverride) {
  editMemberId = id;
  document.getElementById('edit-number').value = number;
  document.getElementById('edit-name').value   = name;
  document.getElementById('edit-pin').value    = '';
  setMsg('editMsg', '', '');

  const policy = cfg.overdraft_policy || 'never';
  const overrideRow   = document.getElementById('editOverdraftRow');
  const overrideCheck = document.getElementById('edit-overdraft');
  const overrideLabel = document.getElementById('editOverdraftLabel');

  if (policy === 'staff_override' || (policy === 'admin_override' && currentUser.role === 'admin')) {
    overrideLabel.textContent = 'Allow overdraft for this member';
    overrideCheck.checked = (overdraftOverride === 1);
    overrideRow.classList.remove('hidden');
  } else if (policy === 'staff_block') {
    overrideLabel.textContent = 'Block overdraft for this member';
    overrideCheck.checked = (overdraftOverride === 0);
    overrideRow.classList.remove('hidden');
  } else {
    overrideRow.classList.add('hidden');
  }

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

  const policy = cfg.overdraft_policy || 'never';
  const overrideRow = document.getElementById('editOverdraftRow');
  if (!overrideRow.classList.contains('hidden')) {
    const checked = document.getElementById('edit-overdraft').checked;
    if (policy === 'staff_block') {
      body.overdraft_override = checked ? 0 : null;
    } else {
      body.overdraft_override = checked ? 1 : null;
    }
  }
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
  setMsg('cashierTopupMsg', '', '');
  setMsg('cashierWithdrawalMsg', '', '');
  setMsg('cashierMsg', '', '');
}

function clearCashierSelection() {
  cashierMember = null;
  document.getElementById('cashierForm').classList.add('hidden');
  document.getElementById('cashierAmount').value        = '';
  document.getElementById('cashierTransferType').value  = '';
  document.getElementById('cashierTransferRef').value   = '';
  document.getElementById('cashierNote').value          = '';
  document.getElementById('withdrawalAmount').value     = '';
  document.getElementById('withdrawalPin').value        = '';
  document.getElementById('withdrawalTransferType').value = '';
  document.getElementById('withdrawalTransferRef').value  = '';
  document.getElementById('withdrawalNote').value       = '';
  setMsg('cashierTopupMsg', '', '');
  setMsg('cashierWithdrawalMsg', '', '');
  setMsg('cashierMsg', '', '');
}

async function doTopup() {
  if (!cashierMember) return;
  const amount       = toMinor('cashierAmount');
  const transferType = document.getElementById('cashierTransferType').value || null;
  const transferRef  = document.getElementById('cashierTransferRef').value.trim() || null;
  const note         = document.getElementById('cashierNote').value.trim() || null;
  if (!amount) { setMsg('cashierTopupMsg', 'Enter a valid amount.', 'err'); return; }
  try {
    const r = await apiFetch('/topup', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ member_id: cashierMember.id, amount, note,
                             transfer_type: transferType, transfer_ref: transferRef })
    });
    window.open(`/receipt/${r.entry_id}`, '_blank');
    document.getElementById('cashierAmount').value       = '';
    document.getElementById('cashierTransferType').value = '';
    document.getElementById('cashierTransferRef').value  = '';
    document.getElementById('cashierNote').value         = '';
    setMsg('cashierTopupMsg', `Top-up complete. New balance: ${r.new_balance_display}`, 'ok');
  } catch (err) { setMsg('cashierTopupMsg', err.message, 'err'); }
}

async function doWithdrawal() {
  if (!cashierMember) return;
  const amount       = toMinor('withdrawalAmount');
  const pin          = document.getElementById('withdrawalPin').value;
  const transferType = document.getElementById('withdrawalTransferType').value || null;
  const transferRef  = document.getElementById('withdrawalTransferRef').value.trim() || null;
  const note         = document.getElementById('withdrawalNote').value.trim() || null;
  if (!amount) { setMsg('cashierWithdrawalMsg', 'Enter a valid amount.', 'err'); return; }
  if (!pin)    { setMsg('cashierWithdrawalMsg', 'PIN is required.', 'err'); return; }
  try {
    const r = await apiFetch('/withdrawal', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ member_id: cashierMember.id, amount, pin, note,
                             transfer_type: transferType, transfer_ref: transferRef })
    });
    window.open(`/receipt/${r.entry_id}`, '_blank');
    document.getElementById('withdrawalAmount').value       = '';
    document.getElementById('withdrawalPin').value          = '';
    document.getElementById('withdrawalTransferType').value = '';
    document.getElementById('withdrawalTransferRef').value  = '';
    document.getElementById('withdrawalNote').value         = '';
    setMsg('cashierWithdrawalMsg', `Withdrawal complete. New balance: ${r.new_balance_display}`, 'ok');
  } catch (err) { setMsg('cashierWithdrawalMsg', err.message, 'err'); }
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
  document.getElementById('barNote').value   = '';
  hidePinOverlay();
  setMsg('barMsg', '', '');
}

function hidePinOverlay() {
  document.getElementById('pinOverlay').classList.add('hidden');
  document.getElementById('barPin').value = '';
  setMsg('pinMsg', '', '');
}

function cancelPin() {
  hidePinOverlay();
  // return focus to amount so staff can adjust
  document.getElementById('barAmount').focus();
}

function prepareCharge() {
  if (!barMember) return;
  const amount = toMinor('barAmount');
  if (!amount) { setMsg('barMsg', 'Enter a valid amount.', 'err'); return; }
  setMsg('barMsg', '', '');
  // populate overlay
  document.getElementById('pinAmount').textContent =
    'Charge: ' + fmtAmount(amount);
  document.getElementById('pinMember').textContent = barMember.name;
  document.getElementById('barPin').value = '';
  setMsg('pinMsg', '', '');
  document.getElementById('pinOverlay').classList.remove('hidden');
  document.getElementById('barPin').focus();
}

async function confirmCharge() {
  if (!barMember) return;
  const amount = toMinor('barAmount');
  const pin    = document.getElementById('barPin').value;
  const note   = document.getElementById('barNote').value.trim();
  if (!pin) { setMsg('pinMsg', 'PIN required.', 'err'); return; }
  try {
    const r = await apiFetch('/charge', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ member_id: barMember.id, amount, pin, note: note || null })
    });
    window.open(`/receipt/${r.entry_id}`, '_blank');
    setMsg('barMsg', `Charge complete. New balance: ${r.new_balance_display}`, 'ok');
    clearBarSelection();
  } catch (err) { setMsg('pinMsg', err.message, 'err'); }
}

// ---------------------------------------------------------------------------
// Admin view
// ---------------------------------------------------------------------------
async function loadAdminView() {
  await Promise.all([loadAdminSettings(), loadStaffAccounts()]);
  setupLogoUpload();
}

let _logoUploadWired = false;
function setupLogoUpload() {
  if (_logoUploadWired) return;
  const input = document.getElementById('s-logo-upload');
  if (!input) return;
  _logoUploadWired = true;
  input.addEventListener('change', async function() {
    const file = this.files[0];
    if (!file) return;
    const fd = new FormData();
    fd.append('file', file);
    try {
      const r = await fetch('/admin/logo', { method: 'POST', body: fd });
      const json = await r.json();
      if (!r.ok) throw new Error(json.detail || 'Upload failed');
      document.getElementById('s-logo-url').value = json.url;
      setMsg('logoUploadMsg', 'Logo uploaded.', 'ok');
    } catch (e) { setMsg('logoUploadMsg', e.message, 'err'); }
    this.value = '';
  });
}

async function loadAdminSettings() {
  try {
    const s = await apiFetch('/admin/settings');
    const div = s.currency_divisor || 100;
    const majorUnit = s.currency_major || 'major units';
    // General
    document.getElementById('s-club-name').value        = s.club_name        || '';
    document.getElementById('s-currency-symbol').value  = s.currency_symbol  || '';
    document.getElementById('s-currency-major').value   = s.currency_major   || '';
    document.getElementById('s-currency-minor').value   = s.currency_minor   || '';
    document.getElementById('s-currency-divisor').value = div;
    document.getElementById('s-min-topup').value        = ((s.min_topup  || 0) / div).toFixed(2);
    document.getElementById('s-max-topup').value        = ((s.max_topup  || 0) / div).toFixed(2);
    document.getElementById('s-max-charge').value       = ((s.max_charge || 0) / div).toFixed(2);
    document.getElementById('s-overdraft-policy').value = s.overdraft_policy || 'never';
    document.getElementById('s-timezone').value         = s.timezone         || '';
    document.getElementById('s-paper-size').value       = s.paper_size       || 'A4';
    document.getElementById('s-min-hint').textContent   = `in ${majorUnit}`;
    document.getElementById('s-max-hint').textContent   = `in ${majorUnit}`;
    document.getElementById('s-charge-hint').textContent= `in ${majorUnit}`;
    // Business address
    document.getElementById('s-biz-address1').value = s.biz_address1 || '';
    document.getElementById('s-biz-address2').value = s.biz_address2 || '';
    document.getElementById('s-biz-address3').value = s.biz_address3 || '';
    document.getElementById('s-biz-address4').value = s.biz_address4 || '';
    document.getElementById('s-biz-country').value  = s.biz_country  || '';
    document.getElementById('s-biz-phone').value    = s.biz_phone    || '';
    document.getElementById('s-biz-email').value    = s.biz_email    || '';
    document.getElementById('s-biz-website').value  = s.biz_website  || '';
    // Branding
    document.getElementById('s-logo-url').value        = s.logo_url        || '';
    document.getElementById('s-logo-align').value      = s.logo_align      || 'left';
    document.getElementById('s-logo-max-width').value  = s.logo_max_width  || '';
    document.getElementById('s-logo-max-height').value = s.logo_max_height || '';
    document.getElementById('s-bar-name').value     = s.bar_name     || '';
    document.getElementById('s-cashier-name').value = s.cashier_name || '';
    // Transactions
    document.getElementById('s-txn-ref-prefix').value = s.txn_ref_prefix || '';
    // transfer_types from /admin/settings is the raw comma-separated string
    const rawTT = Array.isArray(s.transfer_types) ? s.transfer_types.join(',') : (s.transfer_types || '');
    document.getElementById('s-transfer-types').value = rawTT;
    // Receipt labels
    document.getElementById('s-lbl-receipt').value            = s.lbl_receipt            || '';
    document.getElementById('s-lbl-topup-receipt').value      = s.lbl_topup_receipt      || '';
    document.getElementById('s-lbl-withdrawal-receipt').value = s.lbl_withdrawal_receipt || '';
    document.getElementById('s-lbl-staff').value              = s.lbl_staff              || '';
    document.getElementById('s-lbl-transaction').value        = s.lbl_transaction        || '';
    document.getElementById('s-lbl-charge').value             = s.lbl_charge_venue       || '';
    document.getElementById('s-lbl-txn-time').value           = s.lbl_txn_time           || '';
    document.getElementById('s-lbl-amount-charged').value     = s.lbl_amount_charged     || '';
    document.getElementById('s-lbl-remaining-balance').value  = s.lbl_remaining_balance  || '';
    document.getElementById('s-lbl-balance-transfer').value   = s.lbl_balance_transfer   || '';
    document.getElementById('s-lbl-amount-topup').value       = s.lbl_amount_topup       || '';
    document.getElementById('s-lbl-amount-withdrawal').value  = s.lbl_amount_withdrawal  || '';
    document.getElementById('s-lbl-transfer-type').value      = s.lbl_transfer_type      || '';
    document.getElementById('s-lbl-transfer-ref').value       = s.lbl_transfer_ref       || '';
    // Footers
    document.getElementById('s-receipt-footer').value         = s.receipt_footer         || '';
    document.getElementById('s-receipt-footer-charge').value  = s.receipt_footer_charge  || '';
    document.getElementById('s-receipt-footer-cashier').value = s.receipt_footer_cashier || '';
  } catch (err) { setMsg('settingsMsg', err.message, 'err'); }
}

function _sv(id) { return document.getElementById(id).value; }
function _svt(id) { return _sv(id).trim(); }

async function saveSettings() {
  const div = parseInt(_sv('s-currency-divisor'), 10) || 100;
  const body = {
    // General
    club_name:              _svt('s-club-name'),
    currency_symbol:        _svt('s-currency-symbol'),
    currency_major:         _svt('s-currency-major'),
    currency_minor:         _svt('s-currency-minor'),
    currency_divisor:       div,
    min_topup:              Math.round(parseFloat(_sv('s-min-topup'))  * div),
    max_topup:              Math.round(parseFloat(_sv('s-max-topup'))  * div),
    max_charge:             Math.round(parseFloat(_sv('s-max-charge')) * div),
    overdraft_policy:       _sv('s-overdraft-policy'),
    timezone:               _svt('s-timezone'),
    paper_size:             _sv('s-paper-size'),
    // Business address
    biz_address1:  _svt('s-biz-address1'),
    biz_address2:  _svt('s-biz-address2'),
    biz_address3:  _svt('s-biz-address3'),
    biz_address4:  _svt('s-biz-address4'),
    biz_country:   _svt('s-biz-country'),
    biz_phone:     _svt('s-biz-phone'),
    biz_email:     _svt('s-biz-email'),
    biz_website:   _svt('s-biz-website'),
    // Branding
    logo_url:        _svt('s-logo-url'),
    logo_align:      _sv('s-logo-align'),
    logo_max_width:  parseInt(_sv('s-logo-max-width'),  10) || null,
    logo_max_height: parseInt(_sv('s-logo-max-height'), 10) || null,
    bar_name:      _svt('s-bar-name'),
    cashier_name:  _svt('s-cashier-name'),
    // Transactions
    txn_ref_prefix: _svt('s-txn-ref-prefix'),
    transfer_types: _svt('s-transfer-types'),
    // Receipt labels
    lbl_receipt:            _svt('s-lbl-receipt'),
    lbl_topup_receipt:      _svt('s-lbl-topup-receipt'),
    lbl_withdrawal_receipt: _svt('s-lbl-withdrawal-receipt'),
    lbl_staff:              _svt('s-lbl-staff'),
    lbl_transaction:        _svt('s-lbl-transaction'),
    lbl_charge_venue:       _svt('s-lbl-charge'),
    lbl_txn_time:           _svt('s-lbl-txn-time'),
    lbl_amount_charged:     _svt('s-lbl-amount-charged'),
    lbl_remaining_balance:  _svt('s-lbl-remaining-balance'),
    lbl_balance_transfer:   _svt('s-lbl-balance-transfer'),
    lbl_amount_topup:       _svt('s-lbl-amount-topup'),
    lbl_amount_withdrawal:  _svt('s-lbl-amount-withdrawal'),
    lbl_transfer_type:      _svt('s-lbl-transfer-type'),
    lbl_transfer_ref:       _svt('s-lbl-transfer-ref'),
    // Footers
    receipt_footer:         _sv('s-receipt-footer'),
    receipt_footer_charge:  _sv('s-receipt-footer-charge'),
    receipt_footer_cashier: _sv('s-receipt-footer-cashier'),
  };
  try {
    await apiFetch('/admin/settings', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    setMsg('settingsMsg', 'Settings saved.', 'ok');
    await loadConfig();
    populateTransferTypes();
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
