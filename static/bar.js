/* ClubLedger – bar page */

let barMember = null;

(async function init() {
  await loadConfig();
  await loadStaffInto('barStaff');

  document.getElementById('barSearch').addEventListener('keydown', e => { if (e.key === 'Enter') barSearchMembers(); });
})();

// ---------------------------------------------------------------------------
// Member selection
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
  document.getElementById('barPin').value = '';
  document.getElementById('barNote').value = '';
  document.getElementById('barProductSearch').value = '';
  document.getElementById('barProductResults').innerHTML = '';
  setMsg('barMsg', '', '');
}

// ---------------------------------------------------------------------------
// Product search
// ---------------------------------------------------------------------------
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
  document.getElementById('barNote').value = label;
  document.getElementById('barProductResults').innerHTML = '';
  document.getElementById('barProductSearch').value = '';
}

// ---------------------------------------------------------------------------
// Charge
// ---------------------------------------------------------------------------
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
