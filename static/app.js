let currentTab = 'overview';
let activeStatus = 'ALL';
let activeChannel = 'ALL';
let currentDetailOrderId = null;
let currentDetailOrder = null;
let cachedCatalog = [];
let cachedOrders = [];

// -------------------------------------------------------------
// 1. TAB & NAVIGATION CONTROLLER
// -------------------------------------------------------------
function switchTab(tabName, presetFilter = null) {
    currentTab = tabName;
    const allTabs = ['overview', 'orders', 'kitchen', 'customers', 'products', 'brain', 'copilot'];

    allTabs.forEach(t => {
        const el = document.getElementById(`tab-${t}`);
        const btn = document.getElementById(`nav-btn-${t}`);
        if (el) {
            if (t === tabName) {
                el.classList.remove('hidden');
            } else {
                el.classList.add('hidden');
            }
        }
        if (btn) {
            if (t === tabName) {
                btn.className = 'w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs font-semibold nav-item-active transition';
            } else {
                btn.className = 'w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs font-semibold nav-item-inactive transition';
            }
        }
    });

    // Update Top Context Header
    const contextMap = {
        'overview': 'Operations Overview',
        'orders': 'Wholesale Orders Feed',
        'kitchen': 'Kitchen Production Batch Sheet',
        'customers': 'Customer Accounts & Rules',
        'products': 'Product Catalog Management',
        'brain': 'Rules & Business Knowledge',
        'copilot': 'Operations Assistant'
    };
    const headerTitle = document.getElementById('header-context-title');
    if (headerTitle) {
        headerTitle.innerText = contextMap[tabName] || 'Operations';
    }

    if (presetFilter) {
        filterStatus(presetFilter);
    }

    if (tabName === 'overview' || tabName === 'orders') fetchOrders();
    if (tabName === 'customers') fetchCustomers();
    if (tabName === 'products') fetchCatalog();
    if (tabName === 'brain') {
        fetchMemories();
        fetchBusinessBrain();
    }
    if (tabName === 'kitchen') fetchKitchenSheet();
}

// -------------------------------------------------------------
// 2. DEMO SCENARIOS DRAWER CONTROLLER
// -------------------------------------------------------------
function toggleDemoDrawer() {
    const drawer = document.getElementById('demo-scenarios-drawer');
    if (drawer) {
        drawer.classList.toggle('hidden');
    }
}

// -------------------------------------------------------------
// 3. ORDERS FILTERING
// -------------------------------------------------------------
function filterStatus(status) {
    activeStatus = status;
    const statuses = ['ALL', 'Needs Review', 'Approved', 'Sent to Production'];
    statuses.forEach(s => {
        const btn = document.getElementById(`status-btn-${s}`);
        if (btn) {
            if (s === status) {
                btn.className = 'px-3 py-1.5 rounded-md bg-ink-primary text-white transition';
            } else {
                btn.className = 'px-3 py-1.5 rounded-md text-ink-secondary hover:text-ink-primary transition';
            }
        }
    });
    fetchOrders();
}

function filterChannel(channel) {
    activeChannel = channel;
    fetchOrders();
}

// -------------------------------------------------------------
// 4. FETCH & RENDER LIVE ORDERS
// -------------------------------------------------------------
async function fetchOrders() {
    try {
        let url = '/api/orders/?';
        if (activeStatus !== 'ALL') url += `status=${encodeURIComponent(activeStatus)}&`;
        if (activeChannel !== 'ALL') url += `channel=${encodeURIComponent(activeChannel)}`;

        const res = await fetch(url);
        const orders = await res.json();
        cachedOrders = orders;
        
        const tbody = document.getElementById('orders-table-body');
        if (tbody) tbody.innerHTML = '';

        let totalOrders = orders.length;
        let reviewCount = 0;
        let totalUnits = 0;
        let totalRev = 0.0;
        let attentionOrders = [];

        orders.forEach(order => {
            const isApproved = (order.status === 'Approved' || order.status === 'Sent to Production' || order.status === 'Ready');
            if (isApproved) {
                totalRev += order.order_total;
            }
            if (order.status === 'Needs Review' || order.is_anomaly || order.is_duplicate) {
                reviewCount++;
                attentionOrders.push(order);
            }

            let itemsHtml = '<div class="space-y-1">';
            order.items.forEach(item => {
                if (isApproved) totalUnits += item.quantity;
                itemsHtml += `
                    <div class="flex items-center justify-between text-xs text-ink-primary">
                        <span><span class="font-mono text-ink-muted text-[10px]">[${item.sku}]</span> ${item.quantity}× ${item.item_name}</span>
                        <span class="text-ink-secondary font-mono text-[11px]">$${item.line_total.toFixed(2)}</span>
                    </div>
                `;
            });
            itemsHtml += `
                <div class="text-right text-[11px] font-bold text-ink-primary pt-1 border-t border-surface-border/60 font-mono">
                    Total: $${order.order_total.toFixed(2)}
                </div>
            </div>`;

            // Confidence Level (Plain English, Not AI Jargon)
            let confBadge = '';
            if (order.confidence_score >= 90) {
                confBadge = `<span class="inline-flex items-center gap-1.5 text-xs font-medium text-emerald-800"><span class="w-1.5 h-1.5 rounded-full bg-emerald-600"></span> High confidence</span>`;
            } else if (order.confidence_score >= 70) {
                confBadge = `<span class="inline-flex items-center gap-1.5 text-xs font-medium text-amber-800"><span class="w-1.5 h-1.5 rounded-full bg-amber-600"></span> Review recommended</span>`;
            } else {
                confBadge = `<span class="inline-flex items-center gap-1.5 text-xs font-medium text-rose-800"><span class="w-1.5 h-1.5 rounded-full bg-rose-600"></span> Confirmation required</span>`;
            }

            if (order.is_anomaly) {
                confBadge += `<div class="text-[10px] font-semibold text-rose-800 mt-1">${order.anomaly_reason || 'Unusual quantity'}</div>`;
            } else if (order.history_cloned) {
                confBadge += `<div class="text-[10px] font-semibold text-ink-muted mt-1">Matched previous pattern</div>`;
            }

            // Status Badge
            let statusBadge = '';
            if (order.status === 'Approved') {
                statusBadge = `<span class="px-2.5 py-1 rounded-md text-[11px] font-semibold bg-emerald-50 text-emerald-800 border border-emerald-200/60">Approved</span>`;
            } else if (order.status === 'Sent to Production') {
                statusBadge = `<span class="px-2.5 py-1 rounded-md text-[11px] font-semibold bg-slate-100 text-slate-800 border border-slate-200">In Production</span>`;
            } else if (order.status === 'Needs Review') {
                statusBadge = `<span class="px-2.5 py-1 rounded-md text-[11px] font-semibold bg-amber-50 text-amber-900 border border-amber-200/80">Needs Review</span>`;
            } else if (order.status === 'Rejected') {
                statusBadge = `<span class="px-2.5 py-1 rounded-md text-[11px] font-semibold bg-rose-50 text-rose-800 border border-rose-200/60">Rejected</span>`;
            } else {
                statusBadge = `<span class="px-2.5 py-1 rounded-md text-[11px] font-semibold bg-surface-subtle text-ink-secondary">${order.status}</span>`;
            }

            if (tbody) {
                const tr = document.createElement('tr');
                tr.className = 'hover:bg-surface-subtle/50 transition cursor-pointer';
                tr.innerHTML = `
                    <td class="px-5 py-4 align-top" onclick="openOrderDetail(${order.id})">
                        <div class="font-bold text-ink-primary text-xs">${order.customer_name}</div>
                        <div class="text-[11px] text-ink-muted font-mono mt-0.5">${order.account_number} • ${order.customer_phone}</div>
                        <div class="text-[11px] text-ink-secondary mt-1">${order.delivery_route}</div>
                    </td>
                    <td class="px-5 py-4 align-top max-w-xs" onclick="openOrderDetail(${order.id})">
                        <div class="flex items-center gap-1.5 mb-1">
                            <span class="text-[10px] font-medium px-1.5 py-0.2 rounded bg-surface-subtle border border-surface-border text-ink-secondary uppercase tracking-wider">${order.channel}</span>
                            <span class="text-[10px] text-ink-muted">${order.created_at}</span>
                        </div>
                        <div class="text-xs text-ink-primary italic bg-surface-subtle/60 p-2.5 rounded-lg border border-surface-border">
                            "${order.raw_message}"
                        </div>
                        <div class="text-[11px] text-ink-secondary mt-1.5 font-medium">${order.ai_interpretation_summary}</div>
                    </td>
                    <td class="px-5 py-4 align-top min-w-[200px]" onclick="openOrderDetail(${order.id})">
                        ${itemsHtml}
                    </td>
                    <td class="px-5 py-4 align-top" onclick="openOrderDetail(${order.id})">
                        ${confBadge}
                    </td>
                    <td class="px-5 py-4 align-top" onclick="openOrderDetail(${order.id})">
                        ${statusBadge}
                    </td>
                    <td class="px-5 py-4 align-top text-right space-y-1.5">
                        <button onclick="openOrderDetail(${order.id})" class="px-3 py-1.5 rounded-lg bg-surface-subtle hover:bg-surface-border text-ink-primary text-xs font-semibold border border-surface-border transition block w-full text-center">
                            Review
                        </button>
                        ${order.status !== 'Approved' && order.status !== 'Sent to Production' ? `
                            <button onclick="quickApproveOrder(${order.id})" class="px-3 py-1.5 rounded-lg bg-ink-primary hover:bg-black text-white text-xs font-semibold transition block w-full text-center">
                                Approve
                            </button>
                        ` : ''}
                    </td>
                `;
                tbody.appendChild(tr);
            }
        });

        // Update Overview & Navigation Metrics
        updateMetrics(totalOrders, reviewCount, totalUnits, totalRev);
        renderOverviewDashboard(attentionOrders, orders);

    } catch (err) {
        console.error(err);
    }
}

function updateMetrics(orders, reviews, units, revenue) {
    const elOrders = document.getElementById('stat-total-orders');
    const elReviews = document.getElementById('stat-anomalies');
    const elUnits = document.getElementById('stat-total-units');
    const elRev = document.getElementById('stat-total-revenue');
    const navBadge = document.getElementById('nav-badge-review');

    if (elOrders) elOrders.innerText = orders;
    if (elReviews) elReviews.innerText = reviews;
    if (elUnits) elUnits.innerText = units;
    if (elRev) elRev.innerText = `$${revenue.toFixed(2)}`;

    if (navBadge) {
        if (reviews > 0) {
            navBadge.innerText = reviews;
            navBadge.classList.remove('hidden');
        } else {
            navBadge.classList.add('hidden');
        }
    }
}

// -------------------------------------------------------------
// 5. RENDER DASHBOARD OVERVIEW (ATTENTION REQUIRED & ACTIVITY)
// -------------------------------------------------------------
function renderOverviewDashboard(attentionOrders, allOrders) {
    const greetingEl = document.getElementById('overview-operational-greeting');
    const attentionCountBadge = document.getElementById('overview-attention-count-badge');
    const attentionContainer = document.getElementById('overview-attention-container');
    const activityStream = document.getElementById('overview-activity-stream');
    const prodList = document.getElementById('overview-production-list');

    // Contextual greeting
    if (greetingEl) {
        if (attentionOrders.length === 0) {
            greetingEl.innerText = "All orders have been reviewed. Production queue is up to date.";
        } else if (attentionOrders.length === 1) {
            greetingEl.innerText = "1 order requires your review before kitchen cutoff at 11:00 PM.";
        } else {
            greetingEl.innerText = `${attentionOrders.length} orders require your review before kitchen cutoff at 11:00 PM.`;
        }
    }

    if (attentionCountBadge) {
        attentionCountBadge.innerText = attentionOrders.length;
    }

    // Render Attention Required Cards
    if (attentionContainer) {
        attentionContainer.innerHTML = '';
        if (attentionOrders.length === 0) {
            attentionContainer.innerHTML = `
                <div class="p-6 bg-white border border-surface-border rounded-xl text-center space-y-1">
                    <div class="text-xs font-semibold text-ink-primary">No orders need review</div>
                    <div class="text-[11px] text-ink-muted">All incoming buyer orders are matched with high confidence.</div>
                </div>
            `;
        } else {
            attentionOrders.forEach(o => {
                const card = document.createElement('div');
                card.className = 'p-4 bg-white border border-surface-border rounded-xl shadow-sm hover:border-amber-400/60 transition flex flex-col md:flex-row md:items-center justify-between gap-4';
                card.innerHTML = `
                    <div class="space-y-1">
                        <div class="flex items-center gap-2">
                            <span class="font-bold text-xs text-ink-primary">${o.customer_name}</span>
                            <span class="text-[10px] font-medium text-ink-muted font-mono">${o.account_number}</span>
                            <span class="px-2 py-0.5 rounded text-[10px] font-semibold bg-amber-50 text-amber-900 border border-amber-200/60">${o.status}</span>
                        </div>
                        <div class="text-xs text-ink-secondary italic">
                            "${o.raw_message}"
                        </div>
                        <div class="text-[11px] font-medium text-amber-900 flex items-center gap-1.5">
                            <span class="w-1.5 h-1.5 rounded-full bg-amber-600"></span>
                            <span>${o.anomaly_reason || 'Requires manual confirmation of quantities or customer aliases'}</span>
                        </div>
                    </div>
                    <div class="flex items-center gap-2 flex-shrink-0">
                        <button onclick="openOrderDetail(${o.id})" class="px-4 py-2 rounded-lg bg-ink-primary hover:bg-black text-white text-xs font-semibold transition shadow-sm">
                            Review order →
                        </button>
                    </div>
                `;
                attentionContainer.appendChild(card);
            });
        }
    }

    // Render Recent Inbound Activity Stream
    if (activityStream) {
        activityStream.innerHTML = '';
        const recent = allOrders.slice(0, 5);
        if (recent.length === 0) {
            activityStream.innerHTML = `<div class="text-xs text-ink-muted py-3">No activity recorded today.</div>`;
        } else {
            recent.forEach(o => {
                const item = document.createElement('div');
                item.className = 'p-3 bg-white border border-surface-border rounded-xl flex items-center justify-between text-xs transition hover:border-ink-faint';
                item.innerHTML = `
                    <div class="flex items-center gap-3">
                        <span class="font-mono text-[10px] text-ink-muted">${o.created_at.split(' ')[1] || 'Today'}</span>
                        <div>
                            <span class="font-semibold text-ink-primary">${o.customer_name}</span>
                            <span class="text-ink-secondary ml-1.5">placed order via ${o.channel}</span>
                        </div>
                    </div>
                    <button onclick="openOrderDetail(${o.id})" class="text-xs font-semibold text-ink-secondary hover:text-ink-primary">
                        View →
                    </button>
                `;
                activityStream.appendChild(item);
            });
        }
    }

    // Render Production Summary Widget
    if (prodList) {
        prodList.innerHTML = '';
        fetch('/api/orders/kitchen-sheet')
            .then(res => res.json())
            .then(items => {
                if (items.length === 0) {
                    prodList.innerHTML = `<div class="text-xs text-ink-muted py-2 text-center">No production batches queued yet.</div>`;
                    return;
                }
                items.slice(0, 4).forEach(it => {
                    const row = document.createElement('div');
                    row.className = 'flex items-center justify-between py-1.5 border-b border-surface-border/50 text-xs';
                    row.innerHTML = `
                        <span class="font-medium text-ink-primary">${it.item_name}</span>
                        <span class="font-mono font-bold text-ink-primary">${it.total_quantity} units</span>
                    `;
                    prodList.appendChild(row);
                });
            })
            .catch(err => console.error(err));
    }
}

// -------------------------------------------------------------
// 6. ORDER DETAIL DRAWER & HUMAN REVIEW CONTROLS
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

        const pill = document.getElementById('detail-status-pill');
        if (pill) {
            pill.innerText = order.status;
            if (order.status === 'Approved') {
                pill.className = 'px-2.5 py-0.5 rounded text-[10px] font-bold bg-emerald-50 text-emerald-800 border border-emerald-200/60';
            } else if (order.status === 'Needs Review') {
                pill.className = 'px-2.5 py-0.5 rounded text-[10px] font-bold bg-amber-50 text-amber-900 border border-amber-200/80';
            } else {
                pill.className = 'px-2.5 py-0.5 rounded text-[10px] font-bold bg-surface-subtle text-ink-secondary';
            }
        }

        renderDetailItemsTable(order);

        // Render Audit Timeline
        const timelineList = document.getElementById('detail-timeline-list');
        timelineList.innerHTML = '';
        if (order.timeline && order.timeline.length > 0) {
            order.timeline.forEach(t => {
                const div = document.createElement('div');
                div.className = 'text-xs text-ink-primary flex items-start justify-between border-b border-surface-border/50 pb-1';
                div.innerHTML = `
                    <div>
                        <span class="text-brand-800 font-bold font-mono text-[10px]">[${t.event_type}]</span>
                        <span class="text-ink-secondary font-medium">${t.actor}:</span>
                        <span class="text-ink-primary">${t.description}</span>
                    </div>
                    <span class="text-[10px] text-ink-muted font-mono whitespace-nowrap ml-3">${t.created_at}</span>
                `;
                timelineList.appendChild(div);
            });
        } else {
            timelineList.innerHTML = '<div class="text-xs text-ink-muted italic">No previous modifications recorded.</div>';
        }

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
            <td class="px-4 py-2 font-mono text-ink-secondary font-semibold">${item.sku}</td>
            <td class="px-4 py-2 font-semibold text-ink-primary">
                <input type="text" id="edit-name-${item.id}" value="${item.item_name}" class="bg-surface-subtle border border-surface-border rounded px-2 py-0.5 text-xs text-ink-primary w-44">
            </td>
            <td class="px-4 py-2">
                <input type="number" id="edit-qty-${item.id}" value="${item.quantity}" min="1" class="bg-surface-subtle border border-surface-border rounded px-2 py-0.5 text-xs text-ink-primary w-16 font-mono">
            </td>
            <td class="px-4 py-2 text-ink-muted font-mono">$${item.unit_price.toFixed(2)}</td>
            <td class="px-4 py-2 font-mono text-ink-primary">
                $<input type="number" step="0.01" id="edit-price-${item.id}" value="${item.customer_price.toFixed(2)}" class="bg-surface-subtle border border-surface-border rounded px-1.5 py-0.5 text-xs text-brand-800 font-bold w-16 inline font-mono">
            </td>
            <td class="px-4 py-2 font-mono font-bold text-ink-primary">$${item.line_total.toFixed(2)}</td>
            <td class="px-4 py-2 text-right space-x-2">
                <button onclick="saveItemEdit(${item.id})" class="text-brand-800 hover:text-brand-900 font-bold">Save</button>
                <button onclick="deleteItemRow(${item.id})" class="text-rose-800 hover:text-rose-900 font-semibold">Remove</button>
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
            body: JSON.stringify({ quantity: qty, item_name: name, matched_sku: sku, unit_price: price })
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

function openAddItemModal() {
    const select = document.getElementById('add-item-prod-select');
    select.innerHTML = '';
    cachedCatalog.forEach(p => {
        const opt = document.createElement('option');
        opt.value = p.id;
        opt.innerText = `[${p.sku}] ${p.name} ($${p.unit_price.toFixed(2)})`;
        select.appendChild(opt);
    });
    document.getElementById('add-item-modal').classList.remove('hidden');
}
function closeAddItemModal() {
    document.getElementById('add-item-modal').classList.add('hidden');
}

async function submitAddItemToOrder() {
    const prodId = parseInt(document.getElementById('add-item-prod-select').value);
    const qty = parseInt(document.getElementById('add-item-qty').value) || 1;

    try {
        await fetch(`/api/orders/${currentDetailOrderId}/items/add`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ product_id: prodId, quantity: qty })
        });
        closeAddItemModal();
        openOrderDetail(currentDetailOrderId);
        fetchOrders();
    } catch (err) {
        alert('Error adding item.');
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
        alert('Clarification SMS dispatched to customer.');
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
// 7. CUSTOMER MANAGEMENT (CRM-LITE)
// -------------------------------------------------------------
async function fetchCustomers() {
    try {
        const res = await fetch('/api/orders/customers/list');
        const customers = await res.json();
        const tbody = document.getElementById('customers-table-body');
        if (!tbody) return;
        tbody.innerHTML = '';

        customers.forEach(c => {
            const tr = document.createElement('tr');
            tr.className = 'hover:bg-surface-subtle/50 transition';
            tr.innerHTML = `
                <td class="px-4 py-3 font-mono text-ink-secondary font-semibold">${c.account_number}</td>
                <td class="px-4 py-3">
                    <div class="font-bold text-ink-primary">${c.business_name}</div>
                    <div class="text-ink-secondary text-[11px]">${c.contact_name} • ${c.email}</div>
                </td>
                <td class="px-4 py-3 font-mono text-xs">
                    <div>${c.phone_number}</div>
                    <div class="text-[10px] text-ink-muted">${c.enabled_channels}</div>
                </td>
                <td class="px-4 py-3 text-ink-secondary font-medium">${c.delivery_route}</td>
                <td class="px-4 py-3 font-mono font-bold text-brand-800">${c.pricing_tier} (${c.discount_percentage}% off)</td>
                <td class="px-4 py-3 text-ink-secondary italic">${c.special_instructions || '—'}</td>
                <td class="px-4 py-3 text-right">
                    <button onclick="openCustomerEditModal(${c.id})" class="text-xs text-ink-primary hover:text-black font-semibold">Edit Profile</button>
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
    } catch (err) {
        alert('Error saving customer profile.');
    }
}

function openAddCustomerModal() {
    document.getElementById('cust-edit-id').value = '';
    document.getElementById('cust-edit-name').value = '';
    document.getElementById('cust-edit-contact').value = '';
    document.getElementById('cust-edit-phone').value = '+1555';
    document.getElementById('cust-edit-route').value = 'Route A - Downtown Core';
    document.getElementById('cust-edit-discount').value = '0';
    document.getElementById('cust-edit-instructions').value = '';
    document.getElementById('customer-edit-modal').classList.remove('hidden');
}

// -------------------------------------------------------------
// 8. PRODUCT CATALOG MANAGEMENT
// -------------------------------------------------------------
async function fetchCatalog() {
    try {
        const res = await fetch('/api/orders/catalog');
        const products = await res.json();
        cachedCatalog = products;
        const tbody = document.getElementById('catalog-table-body');
        if (!tbody) return;
        tbody.innerHTML = '';

        products.forEach(p => {
            const tr = document.createElement('tr');
            tr.className = 'hover:bg-surface-subtle/50 transition';
            tr.innerHTML = `
                <td class="px-4 py-3 font-mono text-ink-secondary font-semibold">${p.sku}</td>
                <td class="px-4 py-3 font-bold text-ink-primary">${p.name}</td>
                <td class="px-4 py-3 text-ink-secondary">${p.category}</td>
                <td class="px-4 py-3 text-brand-800 font-mono font-bold">$${p.unit_price.toFixed(2)} / ${p.unit}</td>
                <td class="px-4 py-3 font-mono text-ink-primary">${p.stock_available}</td>
                <td class="px-4 py-3 text-ink-secondary italic">${p.aliases || '—'}</td>
                <td class="px-4 py-3 text-right">
                    <button onclick="deleteProduct(${p.id})" class="text-rose-800 hover:text-rose-900 font-semibold text-xs">Delete</button>
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
            body: JSON.stringify({ sku, name, unit, unit_price: price, aliases, stock_available: 100, category: 'Bakery' })
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

// -------------------------------------------------------------
// 9. BUSINESS RULES & BRAIN POLICIES
// -------------------------------------------------------------
async function fetchBusinessBrain() {
    try {
        const res = await fetch('/api/orders/business/brain');
        const b = await res.json();
        
        const headerName = document.getElementById('header-business-name');
        const sidebarName = document.getElementById('sidebar-business-name');
        if (headerName) headerName.innerText = b.name;
        if (sidebarName) sidebarName.innerText = b.name;

        const elName = document.getElementById('brain-name');
        const elCutoff = document.getElementById('brain-cutoff');
        const elMinOrder = document.getElementById('brain-min-order');
        const elFaq = document.getElementById('brain-faq');

        if (elName) elName.value = b.name;
        if (elCutoff) elCutoff.value = b.order_cutoff_time;
        if (elMinOrder) elMinOrder.value = b.minimum_order_amount;
        if (elFaq) elFaq.value = b.business_faq;
    } catch (err) {
        console.error(err);
    }
}

async function saveBusinessBrain() {
    const name = document.getElementById('brain-name').value;
    const cutoff = document.getElementById('brain-cutoff').value;
    const minOrder = parseFloat(document.getElementById('brain-min-order').value) || 0;
    const faq = document.getElementById('brain-faq').value;

    try {
        await fetch('/api/orders/business/brain', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name: name,
                order_cutoff_time: cutoff,
                minimum_order_amount: minOrder,
                business_faq: faq
            })
        });
        document.getElementById('header-business-name').innerText = name;
        document.getElementById('sidebar-business-name').innerText = name;
        alert('Business policies updated successfully.');
    } catch (err) {
        alert('Error saving policies.');
    }
}

async function fetchMemories() {
    try {
        const res = await fetch('/api/orders/memories');
        const mems = await res.json();
        const tbody = document.getElementById('memories-table-body');
        if (!tbody) return;
        tbody.innerHTML = '';

        mems.forEach(m => {
            const tr = document.createElement('tr');
            tr.className = 'hover:bg-surface-subtle/50 transition';
            tr.innerHTML = `
                <td class="px-3 py-2 font-bold text-ink-primary">${m.customer_name}</td>
                <td class="px-3 py-2 font-mono text-ink-secondary">"${m.phrase}"</td>
                <td class="px-3 py-2 font-mono text-brand-800 font-bold">${m.mapped_sku}</td>
                <td class="px-3 py-2 text-ink-muted text-xs">${m.learned_from}</td>
                <td class="px-3 py-2 text-ink-muted font-mono text-xs">${m.created_at}</td>
            `;
            tbody.appendChild(tr);
        });
    } catch (err) {
        console.error(err);
    }
}

// -------------------------------------------------------------
// 10. KITCHEN PRODUCTION BATCH SHEET
// -------------------------------------------------------------
async function fetchKitchenSheet() {
    try {
        const res = await fetch('/api/orders/kitchen-sheet');
        const items = await res.json();
        const tbody = document.getElementById('kitchen-sheet-body');
        if (!tbody) return;
        tbody.innerHTML = '';

        if (items.length === 0) {
            tbody.innerHTML = `<tr><td colspan="5" class="px-5 py-8 text-center text-ink-muted text-xs">No approved production batches yet for tomorrow.</td></tr>`;
            return;
        }

        items.forEach(item => {
            const tr = document.createElement('tr');
            tr.className = 'hover:bg-surface-subtle/50 transition';
            tr.innerHTML = `
                <td class="px-5 py-3.5 font-mono text-ink-secondary font-semibold text-xs">${item.sku}</td>
                <td class="px-5 py-3.5 font-bold text-ink-primary text-sm">${item.item_name}</td>
                <td class="px-5 py-3.5 text-center text-xs text-ink-secondary">${item.order_count} client orders</td>
                <td class="px-5 py-3.5 text-right font-black text-ink-primary text-base font-mono">${item.total_quantity} Units</td>
                <td class="px-5 py-3.5 text-right">
                    <select onchange="updateProductionStatus('${item.sku}', this.value)" class="bg-surface-subtle border border-surface-border rounded-lg px-2.5 py-1 text-xs text-ink-primary font-medium outline-none">
                        <option value="Pending" ${item.production_status === 'Pending' ? 'selected' : ''}>Pending</option>
                        <option value="In Progress" ${item.production_status === 'In Progress' ? 'selected' : ''}>Baking</option>
                        <option value="Completed" ${item.production_status === 'Completed' ? 'selected' : ''}>Baked & Packed</option>
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
// 11. COPILOT & INBOUND SIMULATION
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
    txt.innerHTML = '<span class="text-ink-muted">Querying order operations...</span>';

    try {
        const res = await fetch('/api/orders/copilot', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query: input })
        });
        const data = await res.json();
        txt.innerHTML = data.answer.replace(/\*\*(.*?)\*\*/g, '<b>$1</b>').replace(/\n/g, '<br>');
    } catch (err) {
        txt.innerText = 'Error connecting to operations assistant.';
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

// -------------------------------------------------------------
// 12. CHANNELS & ONBOARDING
// -------------------------------------------------------------
async function openIntegrationsModal() {
    try {
        const res = await fetch('/api/orders/integrations/status');
        const channels = await res.json();
        const tbody = document.getElementById('integrations-table-body');
        tbody.innerHTML = '';

        channels.forEach(ch => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td class="px-3 py-2 font-bold text-ink-primary">${ch.channel}</td>
                <td class="px-3 py-2 text-ink-secondary font-mono text-[11px]">${ch.type}</td>
                <td class="px-3 py-2 font-semibold text-emerald-800 text-[11px]">${ch.status}</td>
                <td class="px-3 py-2 text-ink-secondary text-[11px]">${ch.details}</td>
            `;
            tbody.appendChild(tr);
        });

        document.getElementById('integrations-modal').classList.remove('hidden');
    } catch (err) {
        console.error(err);
    }
}
function closeIntegrationsModal() {
    document.getElementById('integrations-modal').classList.add('hidden');
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
    alert(`Workspace configuration saved for ${name}.`);
    closeOnboardingModal();
}

// -------------------------------------------------------------
// 13. INITIAL BOOTSTRAP
// -------------------------------------------------------------
fetchOrders();
fetchCatalog();
fetchBusinessBrain();
setInterval(fetchOrders, 8000);
