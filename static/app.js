/* ClubLedger – main SPA */

let cashierMember = null;
let barMember     = null;
let editMemberId  = null;

// ---------------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------------
(async function init() {
  await loadConfig();
  await loadStaffInto('cashierStaff');
  await loadStaffInto('barStaff');

  try {
    const data = await apiFetch('/staff');
    renderStaffChips(data.staff);
  } catch (e) { /* ignore */ }

  // Nav
  document.querySelectorAll('.nav-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      document.querySelectorAll('.view').forEach(v => v.classList.add('hidden'));
      document.getElementById('view-' + btn.dataset.view).classList.remove('hidden');
    });
  });

  document.getElementById('registerForm').addEventListener('submit', async e => {
    e.preventDefault();
    await registerMember();
  });
  document.getElementById('editForm').addEventListener('submit', async e => {
    e.preventDefault();
    await saveEdit();
  });

  document.getElementById('memberSearch').addEventListener('keydown',  e => { if (e.key === 'Enter') searchMembers(); });
  document.getElementById('cashierSearch').addEventListener('keydown', e => { if (e.key === 'Enter') cashierSearchMembers(); });
  document.getElementById('barSearch').addEventListener('keydown',     e => { if (e.key === 'Enter') barSearchMembers(); });
  document.getElementById('staffNameInput').addEventListener('keydown',e => { if (e.key === 'Enter') addStaff(); });

  searchMembers();
})();

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

// ---------------------------------------------------------------------------
// Edit member
// ---------------------------------------------------------------------------
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
  const number = document.getElementById('edit-number').value.trim();
  const name   = document.getElementById('edit-name').value.trim();
  const pin    = document.getElementById('edit-pin').value;
  const body   = { member_number: number, name };
  if (pin) body.pin = pin;
  try {
    await apiFetch(`/members/${editMemberId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    closeEditModal();
    searchMembers();
  } catch (e) {
    setMsg('editMsg', e.message, 'err');
  }
}

// ---------------------------------------------------------------------------
// Delete member
// ---------------------------------------------------------------------------
async function deleteMember(id, name) {
  if (!confirm(`Delete member "${name}"?\n\nThis will permanently remove their account and transaction history.`)) return;
  try {
    await apiFetch(`/members/${id}`, { method: 'DELETE' });
    searchMembers();
  } catch (e) {
    alert(e.message);
  }
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
      <div class="member-pick-item" onclick="selectCashierMember(${m.id},'${esc(m.name)}','${esc(m.member_number)}',${m.balance},'${esc(m.balance_display)}')">
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
  document.getElementById('cashierNote').value   = '';
  setMsg('cashierMsg', '', '');
}

async function doTopup() {
  if (!cashierMember) return;
  const amount = parseInt(document.getElementById('cashierAmount').value, 10);
  const staff  = document.getElementById('cashierStaff').value;
  const note   = document.getElementById('cashierNote').value.trim();
  if (!amount || isNaN(amount) || amount <= 0) { setMsg('cashierMsg', 'Enter a valid amount.', 'err'); return; }
  if (!staff) { setMsg('cashierMsg', 'Select a staff member.', 'err'); return; }
  try {
    const r = await apiFetch('/topup', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ member_id: cashierMember.id, amount, staff_name: staff, note: note || null })
    });
    window.open(`/receipt/${r.entry_id}`, '_blank');
    setMsg('cashierMsg', `Top-up complete. New balance: ${r.new_balance_display}`, 'ok');
    clearCashierSelection();
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
      <div class="member-pick-item" onclick="selectBarMember(${m.id},'${esc(m.name)}','${esc(m.member_number)}',${m.balance},'${esc(m.balance_display)}')">
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
  document.getElementById('barPin').value    = '';
  document.getElementById('barNote').value   = '';
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
      if (!products.length) {
        div.innerHTML = '<div style="color:#888;font-size:.88rem;padding:4px">No products found</div>';
        return;
      }
      div.innerHTML = products.map(p => `
        <div class="product-item" onclick="selectProduct(${p.price},${p.member_price || p.price},'${esc(p.name)}${p.brand ? ' – ' + esc(p.brand) : ''}')">
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
  document.getElementById('barNote').value   = label;
  document.getElementById('barProductResults').innerHTML = '';
  document.getElementById('barProductSearch').value = '';
}

async function doCharge() {
  if (!barMember) return;
  const amount = parseInt(document.getElementById('barAmount').value, 10);
  const pin    = document.getElementById('barPin').value;
  const staff  = document.getElementById('barStaff').value;
  const note   = document.getElementById('barNote').value.trim();
  if (!amount || isNaN(amount) || amount <= 0) { setMsg('barMsg', 'Enter a valid amount.', 'err'); return; }
  if (!pin)   { setMsg('barMsg', 'PIN required.', 'err'); return; }
  if (!staff) { setMsg('barMsg', 'Select a staff member.', 'err'); return; }
  try {
    const r = await apiFetch('/charge', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ member_id: barMember.id, amount, pin, staff_name: staff, note: note || null })
    });
    window.open(`/receipt/${r.entry_id}`, '_blank');
    setMsg('barMsg', `Charge complete. New balance: ${r.new_balance_display}`, 'ok');
    clearBarSelection();
  } catch (e) {
    setMsg('barMsg', e.message, 'err');
  }
}
