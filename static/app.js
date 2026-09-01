let currentTab = 'orders';
let activeStatus = 'ALL';
let activeChannel = 'ALL';
let uiMode = 'business';
let activeCorrection = { orderId: null, customerId: null, phrase: '' };
let currentDetailOrderId = null;
let currentDetailOrder = null;

// Mode Switcher: Business Mode vs Demo Mode
function setUIMode(mode) {
    uiMode = mode;
    const btnBiz = document.getElementById('mode-btn-business');
    const btnDemo = document.getElementById('mode-btn-demo');
    const demoLab = document.getElementById('demo-lab-container');

    if (mode === 'business') {
        btnBiz.className = 'px-3 py-1.5 rounded-md bg-indigo-600 text-white font-bold transition';
        btnDemo.className = 'px-3 py-1.5 rounded-md text-slate-400 hover:text-white transition flex items-center gap-1';
        demoLab.classList.add('hidden');
    } else {
        btnDemo.className = 'px-3 py-1.5 rounded-md bg-indigo-600 text-white font-bold transition flex items-center gap-1';
        btnBiz.className = 'px-3 py-1.5 rounded-md text-slate-400 hover:text-white transition';
        demoLab.classList.remove('hidden');
    }
}

function switchTab(tabName) {
    currentTab = tabName;
    ['orders', 'customers', 'brain', 'kitchen'].forEach(t => {
        const el = document.getElementById(`tab-${t}`);
        const btn = document.getElementById(`tab-btn-${t}`);
        if (el && btn) {
            if (t === tabName) {
                el.classList.remove('hidden');
                btn.classList.add('border-indigo-500', 'text-indigo-400');
                btn.classList.remove('border-transparent', 'text-slate-400');
            } else {
                el.classList.add('hidden');
                btn.classList.remove('border-indigo-500', 'text-indigo-400');
                btn.classList.add('border-transparent', 'text-slate-400');
            }
        }
    });

    if (tabName === 'orders') fetchOrders();
    if (tabName === 'customers') fetchCustomers();
    if (tabName === 'brain') {
        fetchCatalog();
        fetchMemories();
        fetchBusinessBrain();
    }
    if (tabName === 'kitchen') fetchKitchenSheet();
}

function filterStatus(status) {
    activeStatus = status;
    ['ALL', 'Needs Review', 'Approved', 'Sent to Production'].forEach(s => {
        const btn = document.getElementById(`status-btn-${s}`);
        if (btn) {
            if (s === status) {
                btn.className = 'text-xs bg-indigo-600 text-white font-bold px-3 py-1 rounded-full';
            } else {
                btn.className = 'text-xs bg-slate-800 text-slate-300 hover:text-white px-3 py-1 rounded-full border border-slate-700';
            }
        }
    });
    fetchOrders();
}

// -------------------------------------------------------------
// 1. FETCH & RENDER LIVE ORDERS
// -------------------------------------------------------------
async function fetchOrders() {
    try {
        let url = '/api/orders/?';
        if (activeStatus !== 'ALL') url += `status=${encodeURIComponent(activeStatus)}&`;
        if (activeChannel !== 'ALL') url += `channel=${encodeURIComponent(activeChannel)}`;

        const res = await fetch(url);
        const orders = await res.json();
        const tbody = document.getElementById('orders-table-body');
        tbody.innerHTML = '';

        let totalOrders = orders.length;
        let reviewCount = 0;
        let totalUnits = 0;
        let totalRev = 0.0;

        if (orders.length === 0) {
            tbody.innerHTML = `<tr><td colspan="6" class="px-4 py-8 text-center text-slate-500 text-xs">No orders found matching this filter.</td></tr>`;
            updateMetrics(0, 0, 0, 0);
            return;
        }

        orders.forEach(order => {
            totalRev += order.order_total;
            if (order.status === 'Needs Review' || order.is_anomaly || order.is_duplicate) reviewCount++;

            let channelIcon = '📱 SMS';
            if (order.channel === 'WhatsApp') channelIcon = '💬 WhatsApp';
            if (order.channel === 'Email') channelIcon = '📧 Email';

            let itemsHtml = '<div class="space-y-1">';
            order.items.forEach(item => {
                totalUnits += item.quantity;
                itemsHtml += `
                    <div class="flex items-center justify-between text-xs bg-slate-950/80 px-2.5 py-1 rounded border border-slate-800">
                        <span class="font-medium text-slate-200">
                            <span class="text-indigo-400 font-mono text-[10px] font-bold">[${item.sku}]</span> 
                            ${item.quantity}x ${item.item_name}
                        </span>
                        <span class="text-slate-400 font-mono text-[11px]">$${item.line_total.toFixed(2)}</span>
                    </div>
                `;
            });
            itemsHtml += `
                <div class="text-right text-[11px] font-bold text-emerald-400 pt-0.5 font-mono">
                    Total: $${order.order_total.toFixed(2)}
                </div>
            </div>`;

            // Confidence Scoring Display
            let confHtml = '';
            if (order.confidence_score >= 90) {
                confHtml = `<span class="text-emerald-400 text-xs font-bold font-mono">🟢 ${order.confidence_score}% High</span>`;
            } else if (order.confidence_score >= 70) {
                confHtml = `<span class="text-amber-400 text-xs font-bold font-mono">🟡 ${order.confidence_score}% Match</span>`;
            } else {
                confHtml = `<span class="text-rose-400 text-xs font-bold font-mono">🔴 ${order.confidence_score}% Review</span>`;
            }

            if (order.is_anomaly) {
                confHtml += `<div class="text-[10px] bg-rose-500/10 text-rose-400 border border-rose-500/30 px-1.5 py-0.5 rounded font-medium mt-1">🚨 Anomaly Spike</div>`;
            }
            if (order.history_cloned) {
                confHtml += `<div class="text-[10px] bg-indigo-500/10 text-indigo-300 border border-indigo-500/30 px-1.5 py-0.5 rounded font-medium mt-1">🧠 Order Memory</div>`;
            }

            // Order Status Badge
            let statusBadge = '';
            if (order.status === 'Approved') {
                statusBadge = `<span class="bg-indigo-500/20 text-indigo-300 border border-indigo-500/40 px-2.5 py-0.5 rounded-full text-[11px] font-bold">✓ Approved</span>`;
            } else if (order.status === 'Sent to Production') {
                statusBadge = `<span class="bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 px-2.5 py-0.5 rounded-full text-[11px] font-bold">👨‍🍳 In Production</span>`;
            } else if (order.status === 'Needs Review') {
                statusBadge = `<span class="bg-amber-500/20 text-amber-300 border border-amber-500/40 px-2.5 py-0.5 rounded-full text-[11px] font-bold animate-pulse">⚠️ Needs Review</span>`;
            } else if (order.status === 'Rejected') {
                statusBadge = `<span class="bg-rose-500/20 text-rose-300 border border-rose-500/40 px-2.5 py-0.5 rounded-full text-[11px] font-bold">✕ Rejected</span>`;
            } else {
                statusBadge = `<span class="bg-slate-800 text-slate-300 px-2.5 py-0.5 rounded-full text-[11px] font-bold">${order.status}</span>`;
            }

            const tr = document.createElement('tr');
            tr.className = 'hover:bg-slate-850/50 transition cursor-pointer';
            tr.innerHTML = `
                <td class="px-4 py-3.5 align-top" onclick="openOrderDetail(${order.id})">
                    <div class="font-mono text-indigo-400 text-xs font-bold">#${order.id}</div>
                    <div class="font-bold text-white text-xs mt-0.5">${order.customer_name}</div>
                    <div class="text-[10px] text-slate-400 font-mono">${order.account_number} • ${order.customer_phone}</div>
                    <div class="text-[10px] text-indigo-300 mt-1">🚚 ${order.delivery_route}</div>
                </td>
                <td class="px-4 py-3.5 align-top max-w-xs" onclick="openOrderDetail(${order.id})">
                    <span class="text-[10px] bg-slate-800 text-slate-300 font-semibold px-2 py-0.5 rounded border border-slate-700">${channelIcon}</span>
                    <div class="text-xs text-slate-300 italic bg-slate-950 p-2 rounded border border-slate-800 mt-1.5">
                        "${order.raw_message}"
                    </div>
                    <div class="text-[10px] text-slate-400 mt-1"><b>AI:</b> ${order.ai_interpretation_summary}</div>
                </td>
                <td class="px-4 py-3.5 align-top min-w-[200px]" onclick="openOrderDetail(${order.id})">
                    ${itemsHtml}
                </td>
                <td class="px-4 py-3.5 align-top" onclick="openOrderDetail(${order.id})">
                    ${confHtml}
                </td>
                <td class="px-4 py-3.5 align-top" onclick="openOrderDetail(${order.id})">
                    ${statusBadge}
                    <div class="text-[10px] text-slate-500 mt-1">${order.created_at}</div>
                </td>
                <td class="px-4 py-3.5 align-top text-right space-y-1.5">
                    <button onclick="openOrderDetail(${order.id})" class="text-xs bg-slate-800 hover:bg-slate-700 text-indigo-300 font-semibold px-3 py-1 rounded border border-slate-700 block w-full">
                        Inspect & Review
                    </button>
                    ${order.status !== 'Approved' && order.status !== 'Sent to Production' ? `
                        <button onclick="quickApproveOrder(${order.id})" class="text-xs bg-indigo-600 hover:bg-indigo-500 text-white font-bold px-3 py-1 rounded transition block w-full">
                            ✓ Approve
                        </button>
                    ` : ''}
                </td>
            `;
            tbody.appendChild(tr);
        });

        updateMetrics(totalOrders, reviewCount, totalUnits, totalRev);
    } catch (err) {
        console.error(err);
    }
}

function updateMetrics(orders, reviews, units, revenue) {
    document.getElementById('stat-total-orders').innerText = orders;
    document.getElementById('stat-anomalies').innerText = reviews;
    document.getElementById('stat-total-units').innerText = units;
    document.getElementById('stat-total-revenue').innerText = `$${revenue.toFixed(2)}`;
}

// -------------------------------------------------------------
// 2. ORDER DETAIL MODAL & AUDIT TIMELINE LOGIC
// -------------------------------------------------------------
async function openOrderDetail(orderId) {
    currentDetailOrderId = orderId;
    try {
        const res = await fetch(`/api/orders/${orderId}`);
        const order = await res.json();
        currentDetailOrder = order;

        document.getElementById('detail-order-id').innerText = `#${order.id}`;
        document.getElementById('detail-customer-header').innerText = `${order.customer_name} (${order.account_number}) • ${order.delivery_route} • ${order.pricing_tier}`;
        document.getElementById('detail-raw-msg').innerText = `"${order.raw_message}"`;
        document.getElementById('detail-ai-summary').innerText = order.ai_interpretation_summary;

        // Render Items Table
        renderDetailItemsTable(order);

        // Render Audit Timeline
        const timelineList = document.getElementById('detail-timeline-list');
        timelineList.innerHTML = '';
        order.timeline.forEach(t => {
            const div = document.createElement('div');
            div.className = 'text-xs text-slate-300 flex items-start justify-between border-b border-slate-800/80 pb-1.5';
            div.innerHTML = `
                <div>
                    <span class="text-indigo-400 font-bold font-mono">[${t.event_type}]</span>
                    <span class="text-slate-400 font-medium">by ${t.actor}:</span>
                    <span class="text-slate-200">${t.description}</span>
                </div>
                <span class="text-[10px] text-slate-500 font-mono whitespace-nowrap ml-3">${t.created_at}</span>
            `;
            timelineList.appendChild(div);
        });

        document.getElementById('order-detail-modal').classList.remove('hidden');
    } catch (err) {
        console.error(err);
    }
}

function renderDetailItemsTable(order) {
    const tbody = document.getElementById('detail-items-tbody');
    tbody.innerHTML = '';
    let total = 0.0;

    order.items.forEach(item => {
        total += item.line_total;
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td class="px-3 py-2 font-mono text-indigo-400 font-bold">${item.sku}</td>
            <td class="px-3 py-2 font-semibold text-white">
                <input type="text" id="edit-name-${item.id}" value="${item.item_name}" class="bg-slate-900 border border-slate-700 rounded px-2 py-0.5 text-xs text-white w-40">
            </td>
            <td class="px-3 py-2">
                <input type="number" id="edit-qty-${item.id}" value="${item.quantity}" class="bg-slate-900 border border-slate-700 rounded px-2 py-0.5 text-xs text-white w-16">
            </td>
            <td class="px-3 py-2 text-slate-400 font-mono">$${item.unit_price.toFixed(2)}</td>
            <td class="px-3 py-2 font-mono text-white font-semibold">
                $<input type="number" step="0.01" id="edit-price-${item.id}" value="${item.customer_price.toFixed(2)}" class="bg-slate-900 border border-slate-700 rounded px-1.5 py-0.5 text-xs text-emerald-400 font-bold w-16 inline">
            </td>
            <td class="px-3 py-2 font-mono text-emerald-400 font-bold">$${item.line_total.toFixed(2)}</td>
            <td class="px-3 py-2 text-right space-x-1.5">
                <button onclick="saveItemEdit(${item.id})" class="text-indigo-400 hover:text-indigo-300 font-bold">Save</button>
                <button onclick="deleteItemRow(${item.id})" class="text-rose-400 hover:text-rose-300 font-bold">Remove</button>
            </td>
        `;
        tbody.appendChild(tr);
    });

    document.getElementById('detail-order-total-sum').innerText = `Order Total: $${total.toFixed(2)}`;
}

async function saveItemEdit(itemId) {
    const qty = parseInt(document.getElementById(`edit-qty-${itemId}`).value) || 1;
    const name = document.getElementById(`edit-name-${itemId}`).value;
    const price = parseFloat(document.getElementById(`edit-price-${itemId}`).value) || 0.0;

    const item = currentDetailOrder.items.find(i => i.id === itemId);
    const sku = item ? item.sku : "MISC-001";

    try {
        await fetch(`/api/orders/${currentDetailOrderId}/items/${itemId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                quantity: qty,
                item_name: name,
                matched_sku: sku,
                unit_price: price
            })
        });
        openOrderDetail(currentDetailOrderId);
        fetchOrders();
    } catch (err) {
        alert('Error saving line item edit.');
    }
}

async function deleteItemRow(itemId) {
    if (!confirm('Remove this line item from order?')) return;
    try {
        await fetch(`/api/orders/${currentDetailOrderId}/items/${itemId}`, { method: 'DELETE' });
        openOrderDetail(currentDetailOrderId);
        fetchOrders();
    } catch (err) {
        console.error(err);
    }
}

async function updateStatusCurrentOrder(newStatus) {
    try {
        await fetch(`/api/orders/${currentDetailOrderId}/status`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: newStatus, actor: 'Staff Member', notes: 'Status updated via Review Cockpit' })
        });
        closeOrderDetailModal();
        fetchOrders();
    } catch (err) {
        alert('Error updating order status.');
    }
}

async function quickApproveOrder(orderId) {
    try {
        await fetch(`/api/orders/${orderId}/status`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: 'Approved', actor: 'Staff Member', notes: 'Quick Approved from feed' })
        });
        fetchOrders();
    } catch (err) {
        console.error(err);
    }
}

async function requestClarificationCurrentOrder() {
    try {
        await fetch(`/api/orders/${currentDetailOrderId}/clarification`, { method: 'POST' });
        alert('💬 Clarification SMS sent to customer!');
        openOrderDetail(currentDetailOrderId);
        fetchOrders();
    } catch (err) {
        alert('Error requesting clarification.');
    }
}

function closeOrderDetailModal() {
    document.getElementById('order-detail-modal').classList.add('hidden');
}

// -------------------------------------------------------------
// 3. CUSTOMER PROFILES & RULES
// -------------------------------------------------------------
async function fetchCustomers() {
    try {
        const res = await fetch('/api/orders/customers/list');
        const customers = await res.json();
        const tbody = document.getElementById('customers-table-body');
        tbody.innerHTML = '';

        customers.forEach(c => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td class="px-3 py-2 font-mono text-indigo-400 font-bold">${c.account_number}</td>
                <td class="px-3 py-2">
                    <div class="font-bold text-white">${c.business_name}</div>
                    <div class="text-slate-400 text-[11px]">${c.contact_name} • ${c.email}</div>
                </td>
                <td class="px-3 py-2 text-slate-300 font-mono">
                    <div>${c.phone_number}</div>
                    <div class="text-[10px] text-slate-400">${c.enabled_channels}</div>
                </td>
                <td class="px-3 py-2 text-indigo-300">${c.delivery_route}</td>
                <td class="px-3 py-2 font-mono text-emerald-400 font-bold">${c.pricing_tier} (${c.discount_percentage}% off)</td>
                <td class="px-3 py-2 text-slate-400 italic">${c.special_instructions}</td>
                <td class="px-3 py-2 text-right">
                    <button onclick="openCustomerEditModal(${c.id})" class="text-indigo-400 hover:text-indigo-300 font-bold">Edit Profile</button>
                </td>
            `;
            tbody.appendChild(tr);
        });
    } catch (err) {
        console.error(err);
    }
}

async function openCustomerEditModal(custId) {
    try {
        const res = await fetch(`/api/orders/customers/${custId}`);
        const c = await res.json();

        document.getElementById('cust-edit-id').value = c.id;
        document.getElementById('cust-edit-name').value = c.business_name;
        document.getElementById('cust-edit-contact').value = c.contact_name;
        document.getElementById('cust-edit-phone').value = c.phone_number;
        document.getElementById('cust-edit-route').value = c.delivery_route;
        document.getElementById('cust-edit-discount').value = c.discount_percentage;
        document.getElementById('cust-edit-instructions').value = c.special_instructions;

        document.getElementById('customer-edit-modal').classList.remove('hidden');
    } catch (err) {
        console.error(err);
    }
}
function closeCustomerModal() {
    document.getElementById('customer-edit-modal').classList.add('hidden');
}

async function submitCustomerUpdate() {
    const custId = document.getElementById('cust-edit-id').value;
    const name = document.getElementById('cust-edit-name').value;
    const contact = document.getElementById('cust-edit-contact').value;
    const phone = document.getElementById('cust-edit-phone').value;
    const route = document.getElementById('cust-edit-route').value;
    const discount = parseFloat(document.getElementById('cust-edit-discount').value) || 0.0;
    const instructions = document.getElementById('cust-edit-instructions').value;

    try {
        await fetch(`/api/orders/customers/${custId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                business_name: name,
                contact_name: contact,
                phone_number: phone,
                email: '',
                delivery_route: route,
                pricing_tier: discount > 0 ? `Tier Discount (-${discount}%)` : "Wholesale Standard",
                discount_percentage: discount,
                special_instructions: instructions,
                enabled_channels: "SMS, WhatsApp, Email"
            })
        });
        closeCustomerModal();
        fetchCustomers();
        alert('✅ Customer profile updated!');
    } catch (err) {
        alert('Error saving customer profile.');
    }
}

// -------------------------------------------------------------
// 4. KITCHEN PRODUCTION SHEET WITH STATUS
// -------------------------------------------------------------
async function fetchKitchenSheet() {
    try {
        const res = await fetch('/api/orders/kitchen-sheet');
        const items = await res.json();
        const tbody = document.getElementById('kitchen-sheet-body');
        tbody.innerHTML = '';

        if (items.length === 0) {
            tbody.innerHTML = `<tr><td colspan="5" class="px-4 py-6 text-center text-slate-500 text-xs">No active production batches for tomorrow.</td></tr>`;
            return;
        }

        items.forEach(item => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td class="px-4 py-3 font-mono text-indigo-400 font-bold text-xs">${item.sku}</td>
                <td class="px-4 py-3 font-semibold text-slate-200 text-sm">${item.item_name}</td>
                <td class="px-4 py-3 text-center text-xs text-slate-400">${item.order_count} client orders</td>
                <td class="px-4 py-3 text-right font-black text-amber-400 text-base font-mono">${item.total_quantity} Units</td>
                <td class="px-4 py-3 text-right">
                    <select onchange="updateProductionStatus('${item.sku}', this.value)" class="bg-slate-900 border border-slate-700 rounded px-2 py-1 text-xs text-slate-200">
                        <option value="Pending" ${item.production_status === 'Pending' ? 'selected' : ''}>⏳ Pending</option>
                        <option value="In Progress" ${item.production_status === 'In Progress' ? 'selected' : ''}>👨‍🍳 Baking</option>
                        <option value="Completed" ${item.production_status === 'Completed' ? 'selected' : ''}>✓ Baked & Packed</option>
                    </select>
                </td>
            `;
            tbody.appendChild(tr);
        });
    } catch (err) {
        console.error(err);
    }
}

async function updateProductionStatus(sku, newStatus) {
    try {
        await fetch(`/api/orders/production/status?sku=${sku}&status=${encodeURIComponent(newStatus)}`, { method: 'POST' });
        fetchKitchenSheet();
    } catch (err) {
        console.error(err);
    }
}

// -------------------------------------------------------------
// 5. BUSINESS BRAIN & CATALOG
// -------------------------------------------------------------
async function fetchBusinessBrain() {
    try {
        const res = await fetch('/api/orders/business/brain');
        const b = await res.json();
        document.getElementById('header-business-name').innerText = b.name;
        document.getElementById('brain-cutoff').value = b.order_cutoff_time;
        document.getElementById('brain-min-order').value = b.minimum_order_amount;
        document.getElementById('brain-faq').value = b.business_faq;
    } catch (err) {
        console.error(err);
    }
}

async function saveBusinessBrain() {
    const cutoff = document.getElementById('brain-cutoff').value;
    const minOrder = parseFloat(document.getElementById('brain-min-order').value) || 0;
    const faq = document.getElementById('brain-faq').value;

    try {
        await fetch('/api/orders/business/brain', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                order_cutoff_time: cutoff,
                minimum_order_amount: minOrder,
                business_faq: faq
            })
        });
        alert('✅ Business Brain & Policies saved!');
    } catch (err) {
        alert('Error saving brain.');
    }
}

async function fetchCatalog() {
    try {
        const res = await fetch('/api/orders/catalog');
        const products = await res.json();
        const tbody = document.getElementById('catalog-table-body');
        tbody.innerHTML = '';

        products.forEach(p => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td class="px-3 py-2 font-mono text-indigo-400 font-bold">${p.sku}</td>
                <td class="px-3 py-2 font-semibold text-white">${p.name}</td>
                <td class="px-3 py-2 text-emerald-400 font-mono font-bold">$${p.unit_price.toFixed(2)} / ${p.unit}</td>
                <td class="px-3 py-2 text-amber-400 font-mono">${p.stock_available}</td>
                <td class="px-3 py-2 text-slate-400 italic">${p.aliases}</td>
                <td class="px-3 py-2 text-right">
                    <button onclick="deleteProduct(${p.id})" class="text-rose-400 hover:text-rose-300 text-[11px] font-semibold">Delete</button>
                </td>
            `;
            tbody.appendChild(tr);
        });
    } catch (err) {
        console.error(err);
    }
}

function openAddProductModal() {
    document.getElementById('add-product-modal').classList.remove('hidden');
}
function closeAddProductModal() {
    document.getElementById('add-product-modal').classList.add('hidden');
}

async function submitNewProduct() {
    const sku = document.getElementById('new-prod-sku').value;
    const name = document.getElementById('new-prod-name').value;
    const unit = document.getElementById('new-prod-unit').value;
    const price = parseFloat(document.getElementById('new-prod-price').value) || 0;
    const aliases = document.getElementById('new-prod-aliases').value;

    if (!sku || !name) {
        alert('Please provide SKU and Product Name.');
        return;
    }

    try {
        await fetch('/api/orders/products', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                sku, name, unit, unit_price: price, aliases, stock_available: 100, category: 'Bakery'
            })
        });
        closeAddProductModal();
        fetchCatalog();
    } catch (err) {
        alert('Error adding product.');
    }
}

async function deleteProduct(prodId) {
    if (!confirm('Remove product from catalog?')) return;
    try {
        await fetch(`/api/orders/products/${prodId}`, { method: 'DELETE' });
        fetchCatalog();
    } catch (err) {
        console.error(err);
    }
}

async function fetchMemories() {
    try {
        const res = await fetch('/api/orders/memories');
        const mems = await res.json();
        const tbody = document.getElementById('memories-table-body');
        tbody.innerHTML = '';

        mems.forEach(m => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td class="px-3 py-2 font-bold text-white">${m.customer_name}</td>
                <td class="px-3 py-2 font-mono text-amber-300 font-semibold">"${m.phrase}"</td>
                <td class="px-3 py-2 font-mono text-indigo-400 font-bold">${m.mapped_sku}</td>
                <td class="px-3 py-2 text-slate-400">${m.learned_from}</td>
                <td class="px-3 py-2 text-slate-500 font-mono">${m.created_at}</td>
            `;
            tbody.appendChild(tr);
        });
    } catch (err) {
        console.error(err);
    }
}

// -------------------------------------------------------------
// 6. COPILOT & INBOUND SIMULATOR
// -------------------------------------------------------------
async function askCopilot(query) {
    document.getElementById('copilot-input').value = query;
    sendCopilotQuery();
}
async function sendCopilotQuery() {
    const input = document.getElementById('copilot-input').value;
    if (!input.trim()) return;

    const box = document.getElementById('copilot-answer-box');
    const txt = document.getElementById('copilot-answer-text');
    box.classList.remove('hidden');
    txt.innerHTML = '<span class="animate-pulse">Consulting Business Brain & orders...</span>';

    try {
        const res = await fetch('/api/orders/copilot', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query: input })
        });
        const data = await res.json();
        txt.innerHTML = data.answer.replace(/\*\*(.*?)\*\*/g, '<b>$1</b>').replace(/\n/g, '<br>');
    } catch (err) {
        txt.innerText = 'Error connecting to Copilot.';
    }
}

async function sendSimulatedWebhook() {
    const phone = document.getElementById('sim-phone').value;
    const body = document.getElementById('sim-body').value;
    const channel = document.getElementById('sim-channel').value;

    if (!body.trim()) return;

    try {
        const formData = new URLSearchParams();
        formData.append('From', phone);
        formData.append('Body', body);
        formData.append('Channel', channel);

        const res = await fetch('/api/webhook/twilio', {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: formData.toString()
        });

        const xmlText = await res.text();
        const parser = new DOMParser();
        const xmlDoc = parser.parseFromString(xmlText, "text/xml");
        const messageNode = xmlDoc.getElementsByTagName("Message")[0];
        const replyText = messageNode ? messageNode.textContent : "Order processed.";

        const respBox = document.getElementById('sim-response-box');
        const respText = document.getElementById('sim-response-text');
        respText.innerText = replyText;
        respBox.classList.remove('hidden');

        document.getElementById('sim-body').value = '';
        fetchOrders();
    } catch (err) {
        console.error(err);
    }
}

function setScenario(type) {
    const phone = document.getElementById('sim-phone');
    const body = document.getElementById('sim-body');
    const channel = document.getElementById('sim-channel');

    if (type === 'memory') {
        phone.value = "+15551234"; // Cafe Bella
        body.value = "Hey Tony, same as last week + 4 baguettes for tomorrow please - Marco";
        channel.value = "SMS";
    } else if (type === 'jargon') {
        phone.value = "+15551234";
        body.value = "Need 8 of the big bread and 2 dozen muffins by 6am";
        channel.value = "WhatsApp";
    } else if (type === 'anomaly') {
        phone.value = "+15559876";
        body.value = "Please deliver 500 sourdough loaves and 200 rye for the stadium festival";
        channel.value = "Email";
    } else if (type === 'faq') {
        phone.value = "+15556789";
        body.value = "What is your order cutoff time for tomorrow morning?";
        channel.value = "SMS";
    }
}

function openOnboardingModal() {
    document.getElementById('onboarding-modal').classList.remove('hidden');
}
function closeOnboardingModal() {
    document.getElementById('onboarding-modal').classList.add('hidden');
}
function finishOnboarding() {
    const name = document.getElementById('onboard-name').value;
    if (!name) {
        alert('Please enter a business name.');
        return;
    }
    alert(`🎉 Provisioned new AI Clerk Workspace for ${name}!\nAssigned dedicated hotline: +1 (555) 839-2011`);
    closeOnboardingModal();
}

// Initial
fetchOrders();
fetchBusinessBrain();
setInterval(fetchOrders, 4000);
