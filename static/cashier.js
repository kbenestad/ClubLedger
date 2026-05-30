/* ClubLedger – cashier page */

let cashierMember = null;

(async function init() {
  await loadConfig();
  await loadStaffInto('cashierStaff');

  // load initial staff chips
  try {
    const data = await apiFetch('/staff');
    renderStaffChips(data.staff);
  } catch (e) { /* ignore */ }

  document.getElementById('registerForm').addEventListener('submit', async e => {
    e.preventDefault();
    await registerMember();
  });

  document.getElementById('memberSearch').addEventListener('keydown', e => { if (e.key === 'Enter') searchMembers(); });
  document.getElementById('cashierSearch').addEventListener('keydown', e => { if (e.key === 'Enter') cashierSearchMembers(); });
  document.getElementById('staffNameInput').addEventListener('keydown', e => { if (e.key === 'Enter') addStaff(); });

  searchMembers();
})();

// ---------------------------------------------------------------------------
// Register
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

// ---------------------------------------------------------------------------
// Member list
// ---------------------------------------------------------------------------
async function searchMembers() {
  const q = document.getElementById('memberSearch').value.trim();
  const url = q ? `/members?q=${encodeURIComponent(q)}` : '/members';
  try {
    const members = await apiFetch(url);
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
        <td>
          <a href="/members/${m.id}/statement" target="_blank" class="btn" style="padding:4px 10px;font-size:.82rem">Statement</a>
        </td>
      </tr>`).join('');
  } catch (e) { console.error(e); }
}

// ---------------------------------------------------------------------------
// Top-up
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
  document.getElementById('cashierNote').value = '';
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
    searchMembers();
  } catch (e) {
    setMsg('cashierMsg', e.message, 'err');
  }
}
