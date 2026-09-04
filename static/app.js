let currentTab = 'overview';
let activeStatus = 'ALL';
let activeChannel = 'ALL';
let currentShift = 'Morning';
let currentDetailOrderId = null;
let currentDetailOrder = null;
let cachedCatalog = [];
let cachedOrders = [];
let searchDebounceTimer = null;
let orderPollingInterval = null;

// -------------------------------------------------------------
// 1. INITIALIZATION & SHORTCUTS
// -------------------------------------------------------------
document.addEventListener('DOMContentLoaded', () => {
    switchTab('overview');
    initCommandPalette();
    initNotificationEvents();

    // Phase 7: Simple polling for data freshness
    orderPollingInterval = setInterval(() => {
        if (currentTab === 'orders') {
            fetchOrders(true);
        } else if (currentTab === 'overview') {
            renderOverviewDashboard();
        }
    }, 15000); // 15 seconds
});

function initCommandPalette() {
    window.addEventListener('keydown', (e) => {
        if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
            e.preventDefault();
            openCommandPalette();
        }
        if (e.key === 'Escape') {
            closeCommandPalette();
            closeOrderDrawer();
            closeContributingOrdersModal();
            closeCustomerModal();
            closeAddProductModal();
            closeAddItemModal();
            closeOnboardingModal();
        }
    });
}

function openCommandPalette() {
    const modal = document.getElementById('command-palette-modal');
    const input = document.getElementById('cmd-search-input');
    if (modal) modal.classList.remove('hidden');
    if (input) {
        input.value = '';
        input.focus();
        renderDefaultCmdActions();
    }
}

function closeCommandPalette() {
    const modal = document.getElementById('command-palette-modal');
    if (modal) modal.classList.add('hidden');
}

function renderDefaultCmdActions() {
    const container = document.getElementById('cmd-search-results');
    if (!container) return;
    container.innerHTML = `
        <div class="px-2 py-1 text-[10px] font-bold uppercase tracking-wider text-ink-muted">Quick Navigation</div>
        <button onclick="closeCommandPalette(); switchTab('orders');" class="w-full text-left px-3 py-2 rounded-lg hover:bg-surface-subtle flex items-center justify-between text-ink-primary">
            <span>Go to Wholesale Orders Feed</span>
            <span class="text-ink-muted font-mono text-[10px]">Jump</span>
        </button>
        <button onclick="closeCommandPalette(); switchTab('kitchen');" class="w-full text-left px-3 py-2 rounded-lg hover:bg-surface-subtle flex items-center justify-between text-ink-primary">
            <span>Go to Kitchen Production Floor Sheet</span>
            <span class="text-ink-muted font-mono text-[10px]">Jump</span>
        </button>
        <button onclick="closeCommandPalette(); switchTab('customers');" class="w-full text-left px-3 py-2 rounded-lg hover:bg-surface-subtle flex items-center justify-between text-ink-primary">
            <span>Go to Customer Accounts Directory</span>
            <span class="text-ink-muted font-mono text-[10px]">Jump</span>
        </button>
        <button onclick="closeCommandPalette(); openAddProductModal();" class="w-full text-left px-3 py-2 rounded-lg hover:bg-surface-subtle flex items-center justify-between text-ink-primary">
            <span>+ Add New Product to Catalog</span>
            <span class="text-ink-muted font-mono text-[10px]">Action</span>
        </button>
        <button onclick="closeCommandPalette(); window.location.href='/api/orders/export/csv';" class="w-full text-left px-3 py-2 rounded-lg hover:bg-surface-subtle flex items-center justify-between text-ink-primary">
            <span>Export QuickBooks CSV File</span>
            <span class="text-ink-muted font-mono text-[10px]">Export</span>
        </button>
    `;
}

function handleCmdSearch(query) {
    if (searchDebounceTimer) clearTimeout(searchDebounceTimer);
    const trimmed = query.trim();
    if (!trimmed) {
        renderDefaultCmdActions();
        return;
    }
    searchDebounceTimer = setTimeout(async () => {
        try {
            const res = await fetch(`/api/orders/search?q=${encodeURIComponent(trimmed)}`);
            if (!res.ok) return;
            const data = await res.json();
            const container = document.getElementById('cmd-search-results');
            if (!container) return;
            container.innerHTML = '';

            let hasResults = false;

            if (data.orders && data.orders.length > 0) {
                hasResults = true;
                container.innerHTML += `<div class="px-2 py-1 text-[10px] font-bold uppercase tracking-wider text-ink-muted">Orders</div>`;
                data.orders.forEach(o => {
                    container.innerHTML += `
                        <button onclick="closeCommandPalette(); openOrderDetail(${o.id});" class="w-full text-left px-3 py-2 rounded-lg hover:bg-surface-subtle flex items-center justify-between text-ink-primary">
                            <span class="font-medium">Order #${o.id} • ${o.customer_name}</span>
                            <span class="text-ink-muted text-[11px]">${o.status}</span>
                        </button>
                    `;
                });
            }

            if (data.customers && data.customers.length > 0) {
                hasResults = true;
                container.innerHTML += `<div class="px-2 py-1 text-[10px] font-bold uppercase tracking-wider text-ink-muted mt-2">Customers</div>`;
                data.customers.forEach(c => {
                    container.innerHTML += `
                        <button onclick="closeCommandPalette(); switchTab('customers'); openCustomerModal(${c.id});" class="w-full text-left px-3 py-2 rounded-lg hover:bg-surface-subtle flex items-center justify-between text-ink-primary">
                            <span class="font-medium">${c.name}</span>
                            <span class="text-ink-muted text-[11px]">${c.route}</span>
                        </button>
                    `;
                });
            }

            if (data.products && data.products.length > 0) {
                hasResults = true;
                container.innerHTML += `<div class="px-2 py-1 text-[10px] font-bold uppercase tracking-wider text-ink-muted mt-2">Products</div>`;
                data.products.forEach(p => {
                    container.innerHTML += `
                        <button onclick="closeCommandPalette(); switchTab('products');" class="w-full text-left px-3 py-2 rounded-lg hover:bg-surface-subtle flex items-center justify-between text-ink-primary">
                            <span class="font-medium">[${p.sku}] ${p.name}</span>
                            <span class="text-ink-muted font-mono text-[11px]">$${p.price.toFixed(2)}</span>
                        </button>
                    `;
                });
            }

            if (!hasResults) {
                container.innerHTML = `<div class="px-3 py-6 text-center text-xs text-ink-muted">No orders, customers, or products match "${trimmed}".</div>`;
            }
        } catch (err) {
            console.error(err);
        }
    }, 150);
}

// -------------------------------------------------------------
// 2. TAB & NAVIGATION CONTROLLER
// -------------------------------------------------------------
function switchTab(tabName, presetFilter = null) {
    currentTab = tabName;
    const allTabs = ['overview', 'orders', 'kitchen', 'customers', 'products', 'brain'];

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

    const contextMap = {
        'overview': 'Operations Overview',
        'orders': 'Wholesale Orders Feed',
        'kitchen': 'Kitchen Production Floor Sheet',
        'customers': 'Customer Directory (CRM)',
        'products': 'Product Catalog Management',
        'brain': 'Rules & Business Knowledge'

    };
    const headerTitle = document.getElementById('header-context-title');
    if (headerTitle) {
        headerTitle.innerText = contextMap[tabName] || 'Operations';
    }

    if (presetFilter) {
        filterStatus(presetFilter);
    }

    if (tabName === 'overview') {
        renderOverviewDashboard();
    } else if (tabName === 'orders') {
        fetchOrders();
    } else if (tabName === 'kitchen') {
        fetchKitchenSheet();
    } else if (tabName === 'customers') {
        fetchCustomers();
    } else if (tabName === 'products') {
        fetchCatalog();
    } else if (tabName === 'brain') {
        fetchMemories();
        fetchBusinessBrain();
    }
}

// -------------------------------------------------------------
// 3. OVERVIEW DASHBOARD (SINGLE SOURCE OF TRUTH)
// -------------------------------------------------------------
async function renderOverviewDashboard() {
    try {
        const res = await fetch('/api/orders/dashboard-summary');
        if (!res.ok) return;
        const data = await res.json();

        // 1. Operational Briefing Greeting
        const greetingEl = document.getElementById('overview-operational-greeting');
        if (greetingEl) greetingEl.innerText = data.operational_brief;

        // 2. Typographic Metrics
        const totOrdersEl = document.getElementById('stat-total-orders');
        const revOrdersEl = document.getElementById('stat-review-orders');
        const totUnitsEl = document.getElementById('stat-total-units');
        const totRevEl = document.getElementById('stat-total-rev');

        if (totOrdersEl) totOrdersEl.innerText = data.metrics.orders_today;
        if (revOrdersEl) revOrdersEl.innerText = data.metrics.needs_review;
        if (totUnitsEl) totUnitsEl.innerText = data.metrics.approved_units;
        if (totRevEl) totRevEl.innerText = `$${data.metrics.order_value.toFixed(2)}`;

        // Update Nav Review Badge
        const navBadge = document.getElementById('nav-badge-review');
        if (navBadge) {
            if (data.metrics.needs_review > 0) {
                navBadge.innerText = data.metrics.needs_review;
                navBadge.classList.remove('hidden');
            } else {
                navBadge.classList.add('hidden');
            }
        }

        // 3. Attention Required Section
        const attContainer = document.getElementById('overview-attention-container');
        const attSection = document.getElementById('overview-attention-section');

        if (attContainer) {
            attContainer.innerHTML = '';
            if (data.attention_required.length === 0) {
                if (attSection) attSection.classList.add('hidden');
            } else {
                if (attSection) attSection.classList.remove('hidden');
                data.attention_required.forEach(item => {
                    const card = document.createElement('div');
                    card.className = 'bg-white border-l-4 border-l-amber-600 border border-surface-border rounded-xl p-4 shadow-sm space-y-2';
                    card.innerHTML = `
                        <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                            <div class="flex items-center gap-2.5">
                                <span class="font-bold text-xs text-ink-primary">${item.customer_name}</span>
                                <span class="text-[10px] font-mono text-ink-muted">Order #${item.order_id}</span>
                                <span class="text-[10px] font-semibold px-2 py-0.5 rounded bg-amber-50 text-amber-900 border border-amber-200/80">Needs Review</span>
                            </div>
                            <span class="text-[11px] text-ink-muted">${item.channel} · ${item.created_at}</span>
                        </div>
                        <div class="text-xs text-ink-secondary font-mono bg-surface-subtle p-2.5 rounded-lg border border-surface-border">
                            "${item.raw_message}"
                        </div>
                        <div class="flex flex-col sm:flex-row sm:items-center justify-between pt-1 gap-2">
                            <div class="text-[11px] text-amber-900 font-medium">
                                ⚠️ Reason: ${item.anomaly_reason}
                            </div>
                            <button onclick="openOrderDetail(${item.order_id})" class="px-3 py-1.5 rounded-lg bg-ink-primary hover:bg-black text-white text-xs font-semibold transition self-start sm:self-auto shadow-sm">
                                Review order →
                            </button>
                        </div>
                    `;
                    attContainer.appendChild(card);
                });
            }
        }

        // 4. Recent Inbound Activity Stream
        const actContainer = document.getElementById('overview-activity-stream');
        if (actContainer) {
            actContainer.innerHTML = '';
            if (data.recent_activity.length === 0) {
                actContainer.innerHTML = `<div class="text-xs text-ink-muted p-4 text-center">No recent orders recorded today.</div>`;
            } else {
                data.recent_activity.forEach(a => {
                    const row = document.createElement('div');
                    row.className = 'flex items-center justify-between p-3 rounded-lg border border-surface-border bg-white text-xs';
                    row.innerHTML = `
                        <div class="flex items-center gap-3">
                            <span class="font-mono text-[11px] text-ink-muted">${a.timestamp}</span>
                            <span class="font-semibold text-ink-primary">${a.customer_name}</span>
                            <span class="text-ink-secondary truncate max-w-xs">${a.summary}</span>
                        </div>
                        <button onclick="openOrderDetail(${a.order_id})" class="text-xs text-ink-secondary hover:text-ink-primary font-medium">
                            Inspect →
                        </button>
                    `;
                    actContainer.appendChild(row);
                });
            }
        }

        // 5. Tomorrow's Production Summary Preview
        const prodContainer = document.getElementById('overview-production-summary');
        const cutoffEl = document.getElementById('overview-next-cutoff');
        if (cutoffEl) cutoffEl.innerText = `Cutoff: ${data.whats_next.next_cutoff}`;

        if (prodContainer) {
            prodContainer.innerHTML = '';
            if (data.whats_next.top_production.length === 0) {
                prodContainer.innerHTML = `<div class="text-xs text-ink-muted p-4 text-center">No approved orders for tomorrow yet.</div>`;
            } else {
                data.whats_next.top_production.forEach(p => {
                    const row = document.createElement('div');
                    row.className = 'flex items-center justify-between p-3 rounded-lg border border-surface-border bg-white text-xs';
                    row.innerHTML = `
                        <div>
                            <span class="font-mono text-[10px] text-ink-muted mr-1.5">[${p.sku}]</span>
                            <span class="font-medium text-ink-primary">${p.item_name}</span>
                        </div>
                        <span class="font-bold text-xs text-ink-primary font-mono">${p.quantity} units</span>
                    `;
                    prodContainer.appendChild(row);
                });
            }
        }

        // 6. Update Notification Center
        updateNotifications(data.attention_required);

    } catch (err) {
        console.error('Error loading dashboard summary:', err);
    }
}

// -------------------------------------------------------------
// 4. NOTIFICATIONS CENTER
// -------------------------------------------------------------
function initNotificationEvents() {
    window.addEventListener('click', (e) => {
        const notifDropdown = document.getElementById('notif-dropdown');
        const notifBtn = document.getElementById('notif-btn');
        if (notifDropdown && notifBtn && !notifBtn.contains(e.target) && !notifDropdown.contains(e.target)) {
            notifDropdown.classList.add('hidden');
        }
    });
}

function toggleNotificationsDropdown() {
    const dropdown = document.getElementById('notif-dropdown');
    if (dropdown) dropdown.classList.toggle('hidden');
}

function updateNotifications(attentionList) {
    const badge = document.getElementById('notif-badge');
    const container = document.getElementById('notif-items-container');
    if (!badge || !container) return;

    if (attentionList && attentionList.length > 0) {
        badge.innerText = attentionList.length;
        badge.classList.remove('hidden');

        container.innerHTML = '';
        attentionList.forEach(a => {
            container.innerHTML += `
                <div onclick="document.getElementById('notif-dropdown').classList.add('hidden'); openOrderDetail(${a.order_id});" class="p-2 rounded-lg hover:bg-surface-subtle cursor-pointer border border-surface-border text-xs space-y-0.5">
                    <div class="flex items-center justify-between">
                        <span class="font-bold text-ink-primary">${a.customer_name}</span>
                        <span class="text-[10px] text-amber-800 font-semibold">Action Required</span>
                    </div>
                    <div class="text-[11px] text-ink-secondary truncate">${a.anomaly_reason}</div>
                </div>
            `;
        });
    } else {
        badge.classList.add('hidden');
        container.innerHTML = `<div class="text-xs text-ink-muted py-3 text-center">No unread alerts. Operations smooth.</div>`;
    }
}

// -------------------------------------------------------------
// 5. ORDERS TABLE & FILTERING
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

function handleOrdersSearch(e) {
    fetchOrders();
}

async function fetchOrders(isBackgroundRefresh = false) {
    try {
        let url = '/api/orders/?';
        if (activeStatus !== 'ALL') url += `status=${encodeURIComponent(activeStatus)}&`;
        if (activeChannel !== 'ALL') url += `channel=${encodeURIComponent(activeChannel)}&`;
        
        const searchVal = document.getElementById('orders-search-input')?.value;
        if (searchVal && searchVal.trim()) url += `q=${encodeURIComponent(searchVal.trim())}`;

        const res = await fetch(url);
        if (!res.ok) return;
        const orders = await res.json();

        // Phase 7: Avoid deep re-render on poll if data didn't change
        if (isBackgroundRefresh && JSON.stringify(cachedOrders) === JSON.stringify(orders)) {
            return;
        }

        cachedOrders = orders;
        
        const tbody = document.getElementById('orders-table-body');
        if (!tbody) return;
        tbody.innerHTML = '';

        if (orders.length === 0) {
            tbody.innerHTML = `<tr><td colspan="7" class="px-5 py-8 text-center text-xs text-ink-muted">No orders match these filters.</td></tr>`;
            return;
        }

        orders.forEach(order => {
            let statusPillClass = 'bg-surface-subtle text-ink-secondary border-surface-border';
            if (order.status === 'Approved') statusPillClass = 'bg-emerald-50 text-emerald-800 border-emerald-200/60';
            if (order.status === 'Sent to Production') statusPillClass = 'bg-indigo-50 text-indigo-800 border-indigo-200/60';
            if (order.status === 'Needs Review') statusPillClass = 'bg-amber-50 text-amber-900 border-amber-200/60';
            if (order.status === 'Rejected') statusPillClass = 'bg-rose-50 text-rose-800 border-rose-200/60';

            let itemsSummary = order.items.map(i => `${i.quantity}× ${i.item_name}`).join(', ');
            if (itemsSummary.length > 45) itemsSummary = itemsSummary.substring(0, 45) + '...';

            let reasonText = 'Standard order — verified';
            if (order.confidence_score === 0) reasonText = `🚨 AI Parsing Failed - Needs Manual Entry`;
            else if (order.is_anomaly) reasonText = `⚠️ ${order.anomaly_reason}`;
            else if (order.is_duplicate) reasonText = `⚠️ Suspected duplicate order`;
            else if (order.history_cloned) reasonText = `✨ Cloned from recurring schedule`;

            const tr = document.createElement('tr');
            tr.className = 'hover:bg-surface-subtle/50 transition cursor-pointer';
            tr.onclick = (e) => {
                if (e.target.tagName !== 'BUTTON') openOrderDetail(order.id);
            };

            tr.innerHTML = `
                <td class="px-5 py-3.5 font-semibold text-ink-primary">
                    <div class="font-bold text-xs">#${order.id}</div>
                    <div class="text-[10px] text-ink-muted font-mono">${order.created_at}</div>
                </td>
                <td class="px-5 py-3.5 text-ink-primary">
                    <div class="font-bold text-xs">${order.customer_name}</div>
                    <div class="text-[10px] text-ink-secondary">${order.channel} • ${order.account_number}</div>
                </td>
                <td class="px-5 py-3.5 text-ink-secondary text-xs">
                    <div>${itemsSummary || 'No line items'}</div>
                    <div class="text-[10px] text-ink-muted">${order.items.length} unique line items</div>
                </td>
                <td class="px-5 py-3.5 text-xs">
                    <span class="${order.is_anomaly || order.is_duplicate ? 'text-amber-900 font-semibold' : 'text-ink-secondary'}">
                        ${reasonText}
                    </span>
                </td>
                <td class="px-5 py-3.5">
                    <span class="border px-2 py-0.5 rounded text-[10px] font-semibold ${statusPillClass}">
                        ${order.status}
                    </span>
                </td>
                <td class="px-5 py-3.5 text-right font-mono font-bold text-xs text-ink-primary">
                    $${order.order_total.toFixed(2)}
                </td>
                <td class="px-5 py-3.5 text-right">
                    <button onclick="openOrderDetail(${order.id})" class="px-2.5 py-1 rounded-lg border border-surface-border text-xs font-semibold text-ink-secondary hover:text-ink-primary hover:border-ink-faint transition">
                        Review →
                    </button>
                </td>
            `;
            tbody.appendChild(tr);
        });
    } catch (err) {
        console.error('Error fetching orders:', err);
    }
}

// -------------------------------------------------------------
// 6. ORDER DETAIL DRAWER & ACTIONS
// -------------------------------------------------------------
async function openOrderDetail(orderId) {
    currentDetailOrderId = orderId;
    try {
        const res = await fetch(`/api/orders/${orderId}`);
        if (!res.ok) {
            alert('Order not found in this workspace.');
            return;
        }
        const order = await res.json();
        currentDetailOrder = order;

        document.getElementById('drawer-order-id').innerText = `Order #${order.id}`;
        
        const statusPill = document.getElementById('drawer-status-pill');
        statusPill.innerText = order.status;
        statusPill.className = 'text-[10px] font-semibold px-2 py-0.5 rounded border ';
        if (order.status === 'Approved') statusPill.className += 'bg-emerald-50 text-emerald-800 border-emerald-200';
        else if (order.status === 'Needs Review') statusPill.className += 'bg-amber-50 text-amber-900 border-amber-200';
        else statusPill.className += 'bg-surface-subtle text-ink-secondary border-surface-border';

        // Duplicate Banner
        const dupBanner = document.getElementById('drawer-duplicate-banner');
        if (order.is_duplicate) {
            dupBanner.classList.remove('hidden');
        } else {
            dupBanner.classList.add('hidden');
        }

        // Inbound raw message
        document.getElementById('drawer-inbound-meta').innerText = `${order.channel} · ${order.created_at}`;
        document.getElementById('drawer-raw-message').innerText = order.raw_message;

        // Customer Profile
        document.getElementById('drawer-cust-acc').innerText = order.account_number;
        document.getElementById('drawer-cust-route').innerText = order.delivery_route;
        document.getElementById('drawer-cust-tier').innerText = `${order.pricing_tier} (${order.discount_percentage}% off)`;
        document.getElementById('drawer-cust-day').innerText = order.usual_order_day || 'Schedule active';
        document.getElementById('drawer-cust-notes').innerText = `Instructions: ${order.special_instructions || 'None'}`;

        const aiSummaryEl = document.getElementById('drawer-ai-summary');
        if (order.confidence_score === 0) {
            aiSummaryEl.innerHTML = `<span class="text-rose-700 font-bold">🚨 AI Parsing Failed:</span> System error parsing raw message. Please enter line items manually.`;
        } else {
            aiSummaryEl.innerText = order.ai_interpretation_summary || 'Standard line items parsed.';
        }

        // Order Items Table
        renderDrawerItems(order.items, order.order_total);

        // Audit Trail Timeline
        const timelineContainer = document.getElementById('drawer-timeline-container');
        timelineContainer.innerHTML = '';
        order.timeline.forEach(t => {
            const el = document.createElement('div');
            el.className = 'relative pl-2';
            el.innerHTML = `
                <div class="flex items-center gap-2">
                    <span class="font-bold text-ink-primary">${t.event_type}</span>
                    <span class="text-[10px] text-ink-muted font-mono">${t.created_at}</span>
                </div>
                <div class="text-ink-secondary text-[11px] mt-0.5">${t.description}</div>
                <div class="text-[10px] text-ink-muted">Actor: ${t.actor}</div>
            `;
            timelineContainer.appendChild(el);
        });

        document.getElementById('order-detail-drawer').classList.remove('hidden');
    } catch (err) {
        console.error(err);
    }
}

function renderDrawerItems(items, total) {
    const tbody = document.getElementById('drawer-items-body');
    tbody.innerHTML = '';
    items.forEach(item => {
        const tr = document.createElement('tr');
        let confWarning = '';
        if (item.match_confidence && item.match_confidence < 80) {
            confWarning = `<span class="ml-2 px-1.5 py-0.5 rounded text-[9px] font-bold bg-amber-100 text-amber-900">Low Confidence (${item.match_confidence}%)</span>`;
        } else if (item.match_confidence === 0) {
            confWarning = `<span class="ml-2 px-1.5 py-0.5 rounded text-[9px] font-bold bg-rose-100 text-rose-900">AI Failed</span>`;
        }

        tr.innerHTML = `
            <td class="px-3 py-2 font-mono text-[11px] text-ink-muted">${item.sku}</td>
            <td class="px-3 py-2 font-medium">${item.item_name}${confWarning}</td>
            <td class="px-3 py-2 text-center">
                <input type="number" min="1" value="${item.quantity}" onchange="updateItemQty(${item.id}, this.value)" class="w-14 text-center border border-surface-border rounded px-1.5 py-0.5 text-xs font-mono font-bold">
            </td>
            <td class="px-3 py-2 text-right font-mono text-ink-secondary">$${item.customer_price.toFixed(2)}</td>
            <td class="px-3 py-2 text-right font-mono font-bold">$${item.line_total.toFixed(2)}</td>
            <td class="px-3 py-2 text-right">
                <button onclick="deleteItemFromOrder(${item.id})" class="text-rose-700 hover:text-rose-900 text-xs">&times;</button>
            </td>
        `;
        tbody.appendChild(tr);
    });
    document.getElementById('drawer-order-total').innerText = `$${total.toFixed(2)}`;
}

function closeOrderDrawer() {
    const drawer = document.getElementById('order-detail-drawer');
    if (drawer) drawer.classList.add('hidden');
    currentDetailOrderId = null;
    currentDetailOrder = null;
}

async function approveCurrentOrder() {
    if (!currentDetailOrderId) return;
    const btn = document.getElementById('btn-approve-order');
    if (btn) {
        btn.disabled = true;
        btn.innerText = 'Processing...';
    }
    try {
        const res = await fetch(`/api/orders/${currentDetailOrderId}/status`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: 'Approved', actor: 'Alex (Operations)' })
        });
        if (res.ok) {
            await openOrderDetail(currentDetailOrderId);
            if (currentTab === 'overview') renderOverviewDashboard();
            else fetchOrders();
        }
    } catch (err) {
        console.error(err);
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerText = 'Approve Order';
        }
    }
}

async function sendCurrentOrderToProduction() {
    if (!currentDetailOrderId) return;
    const btn = document.getElementById('btn-send-production');
    if (btn) {
        btn.disabled = true;
        btn.innerText = 'Processing...';
    }
    try {
        const res = await fetch(`/api/orders/${currentDetailOrderId}/status`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: 'Sent to Production', actor: 'Alex (Operations)' })
        });
        if (res.ok) {
            await openOrderDetail(currentDetailOrderId);
            if (currentTab === 'overview') renderOverviewDashboard();
            else fetchOrders();
        }
    } catch (err) {
        console.error(err);
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerText = 'Send to Production';
        }
    }
}

async function rejectCurrentOrder() {
    if (!currentDetailOrderId) return;
    if (!confirm('Reject this order and notify customer?')) return;
    try {
        const res = await fetch(`/api/orders/${currentDetailOrderId}/status`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: 'Rejected', actor: 'Alex (Operations)', notes: 'Customer notified of cancellation.' })
        });
        if (res.ok) {
            openOrderDetail(currentDetailOrderId);
            if (currentTab === 'overview') renderOverviewDashboard();
            else fetchOrders();
        }
    } catch (err) {
        console.error(err);
    }
}

async function requestClarification() {
    if (!currentDetailOrderId) return;
    try {
        const res = await fetch(`/api/orders/${currentDetailOrderId}/clarification`, {
            method: 'POST'
        });
        if (res.ok) {
            alert('Clarification request sent to buyer and recorded in audit trail.');
            openOrderDetail(currentDetailOrderId);
        }
    } catch (err) {
        console.error(err);
    }
}

async function updateItemQty(itemId, newQty) {
    if (!currentDetailOrderId || !currentDetailOrder) return;
    const item = currentDetailOrder.items.find(i => i.id === itemId);
    if (!item) return;

    try {
        await fetch(`/api/orders/${currentDetailOrderId}/items/${itemId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                quantity: parseInt(newQty) || 1,
                item_name: item.item_name,
                matched_sku: item.sku,
                unit_price: item.customer_price
            })
        });
        openOrderDetail(currentDetailOrderId);
    } catch (err) {
        console.error(err);
    }
}

async function deleteItemFromOrder(itemId) {
    if (!currentDetailOrderId) return;
    try {
        await fetch(`/api/orders/${currentDetailOrderId}/items/${itemId}`, {
            method: 'DELETE'
        });
        openOrderDetail(currentDetailOrderId);
    } catch (err) {
        console.error(err);
    }
}

function openAddItemModal() {
    const modal = document.getElementById('add-item-modal');
    const select = document.getElementById('add-item-prod-select');
    if (!select) return;
    select.innerHTML = '';
    cachedCatalog.forEach(p => {
        select.innerHTML += `<option value="${p.id}">[${p.sku}] ${p.name} ($${p.unit_price.toFixed(2)})</option>`;
    });
    if (modal) modal.classList.remove('hidden');
}

function closeAddItemModal() {
    const modal = document.getElementById('add-item-modal');
    if (modal) modal.classList.add('hidden');
}

async function submitAddItemToOrder() {
    if (!currentDetailOrderId) return;
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
    } catch (err) {
        console.error(err);
    }
}

// -------------------------------------------------------------
// 7. PRODUCTION BATCH SHEET (PRINTABLE & TRACEABLE)
// -------------------------------------------------------------
function switchProductionShift(shift) {
    currentShift = shift;
    ['Morning', 'Afternoon', 'Evening', 'All Day'].forEach(s => {
        const btn = document.getElementById(`shift-btn-${s}`);
        if (btn) {
            if (s === shift) {
                btn.className = 'px-3 py-1.5 rounded-md bg-ink-primary text-white transition';
            } else {
                btn.className = 'px-3 py-1.5 rounded-md text-ink-secondary hover:text-ink-primary transition';
            }
        }
    });
    fetchKitchenSheet();
}

async function fetchKitchenSheet() {
    try {
        const res = await fetch(`/api/orders/production/sheet?shift=${encodeURIComponent(currentShift)}`);
        if (!res.ok) return;
        const data = await res.json();

        // Populate Summary
        document.getElementById('prod-sum-orders').innerText = data.summary.total_approved_orders;
        document.getElementById('prod-sum-skus').innerText = data.summary.total_products;
        document.getElementById('prod-sum-units').innerText = data.summary.total_units_required;
        document.getElementById('prod-sum-completed').innerText = data.summary.total_units_completed;
        document.getElementById('prod-sum-remaining').innerText = data.summary.remaining_units;

        // Populate Print Headers
        const printShiftEl = document.getElementById('print-shift');
        if (printShiftEl) printShiftEl.innerText = `Shift: ${data.shift}`;

        const tbody = document.getElementById('kitchen-table-body');
        if (!tbody) return;
        tbody.innerHTML = '';

        if (data.items.length === 0) {
            tbody.innerHTML = `<tr><td colspan="7" class="px-5 py-8 text-center text-xs text-ink-muted">No approved production requirements for this shift.</td></tr>`;
            return;
        }

        data.items.forEach(it => {
            const tr = document.createElement('tr');
            tr.className = 'hover:bg-surface-subtle/50 transition';

            let statusBadge = 'bg-surface-subtle text-ink-secondary';
            if (it.production_status === 'In Progress') statusBadge = 'bg-amber-50 text-amber-900 border border-amber-200';
            if (it.production_status === 'Completed') statusBadge = 'bg-emerald-50 text-emerald-800 border border-emerald-200';

            tr.innerHTML = `
                <td class="px-5 py-3.5 font-semibold text-ink-primary">
                    <span class="font-mono text-[10px] text-ink-muted mr-1">[${it.sku}]</span>
                    ${it.item_name}
                </td>
                <td class="px-5 py-3.5 text-center font-mono font-bold text-xs text-ink-primary">
                    ${it.required_quantity} ${it.unit}
                </td>
                <td class="px-5 py-3.5 text-center font-mono text-xs text-emerald-800 font-semibold">
                    ${it.completed_quantity}
                </td>
                <td class="px-5 py-3.5 text-center font-mono font-bold text-xs text-amber-800">
                    ${it.remaining_quantity}
                </td>
                <td class="px-5 py-3.5 text-center">
                    <button onclick="openContributingOrdersModal('${it.sku}', '${it.item_name}')" class="px-2.5 py-1 rounded bg-surface-subtle border border-surface-border hover:bg-surface-border text-xs text-ink-primary transition">
                        ${it.order_count} orders →
                    </button>
                </td>
                <td class="px-5 py-3.5">
                    <span class="text-[10px] font-semibold px-2 py-0.5 rounded ${statusBadge}">
                        ${it.production_status}
                    </span>
                </td>
                <td class="no-print px-5 py-3.5 text-right">
                    <button onclick="promptProgressUpdate('${it.sku}', ${it.required_quantity}, ${it.completed_quantity})" class="text-xs text-ink-primary font-semibold hover:underline">
                        Update Progress
                    </button>
                </td>
            `;
            tbody.appendChild(tr);
        });
    } catch (err) {
        console.error(err);
    }
}

async function promptProgressUpdate(sku, reqQty, currentComp) {
    const input = prompt(`Update completed batch quantity for SKU ${sku} (Required: ${reqQty}):`, currentComp);
    if (input === null) return;
    const completed = parseInt(input) || 0;
    const status = completed >= reqQty ? 'Completed' : (completed > 0 ? 'In Progress' : 'Pending');

    try {
        await fetch('/api/orders/production/update-progress', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ sku: sku, completed_quantity: completed, status: status })
        });
        fetchKitchenSheet();
    } catch (err) {
        console.error(err);
    }
}

async function openContributingOrdersModal(sku, itemName) {
    const modal = document.getElementById('contributing-orders-modal');
    const title = document.getElementById('contrib-modal-title');
    const tbody = document.getElementById('contrib-orders-body');
    if (title) title.innerText = `Contributing Orders: [${sku}] ${itemName}`;

    try {
        const res = await fetch(`/api/orders/production/contributing-orders?sku=${encodeURIComponent(sku)}&shift=${encodeURIComponent(currentShift)}`);
        if (!res.ok) return;
        const orders = await res.json();
        if (tbody) {
            tbody.innerHTML = '';
            orders.forEach(o => {
                tbody.innerHTML += `
                    <tr>
                        <td class="px-3 py-2 font-mono font-bold">#${o.order_id}</td>
                        <td class="px-3 py-2 font-medium">${o.customer_name} (${o.account_number})</td>
                        <td class="px-3 py-2 text-ink-muted text-[11px]">${o.route}</td>
                        <td class="px-3 py-2 text-center font-mono font-bold">${o.quantity} units</td>
                        <td class="px-3 py-2 text-right"><span class="text-[10px] bg-emerald-50 text-emerald-800 px-1.5 py-0.5 rounded">${o.status}</span></td>
                    </tr>
                `;
            });
        }
        if (modal) modal.classList.remove('hidden');
    } catch (err) {
        console.error(err);
    }
}

function closeContributingOrdersModal() {
    const modal = document.getElementById('contributing-orders-modal');
    if (modal) modal.classList.add('hidden');
}

function exportCurrentProductionCsv() {
    window.location.href = `/api/orders/production/export?shift=${encodeURIComponent(currentShift)}`;
}

// -------------------------------------------------------------
// 8. CUSTOMER DIRECTORY (CRM-LITE)
// -------------------------------------------------------------
async function fetchCustomers() {
    try {
        const res = await fetch('/api/orders/customers/list');
        if (!res.ok) return;
        const customers = await res.json();
        const tbody = document.getElementById('customers-table-body');
        if (!tbody) return;
        tbody.innerHTML = '';

        customers.forEach(c => {
            const tr = document.createElement('tr');
            tr.className = 'hover:bg-surface-subtle/50 transition';
            tr.innerHTML = `
                <td class="px-5 py-3.5 font-semibold text-ink-primary">
                    <div class="font-bold text-xs">${c.business_name}</div>
                    <div class="text-[10px] text-ink-muted font-mono">${c.account_number} • ${c.order_count} orders placed</div>
                </td>
                <td class="px-5 py-3.5 text-ink-secondary">
                    <div>${c.contact_name || 'Owner'}</div>
                    <div class="text-[10px] text-ink-muted font-mono">${c.phone_number}</div>
                </td>
                <td class="px-5 py-3.5 text-ink-secondary font-medium">
                    ${c.delivery_route}
                </td>
                <td class="px-5 py-3.5">
                    <span class="bg-surface-subtle border border-surface-border text-ink-primary text-[10px] font-semibold px-2 py-0.5 rounded">
                        ${c.pricing_tier} (-${c.discount_percentage}%)
                    </span>
                </td>
                <td class="px-5 py-3.5 text-ink-secondary text-[11px]">
                    ${c.usual_order_day || 'Regular'}
                </td>
                <td class="px-5 py-3.5 text-right">
                    <button onclick="openCustomerModal(${c.id})" class="text-xs text-ink-primary font-semibold hover:underline">
                        Edit Profile →
                    </button>
                </td>
            `;
            tbody.appendChild(tr);
        });
    } catch (err) {
        console.error(err);
    }
}

function openCustomerModal(id = null) {
    const modal = document.getElementById('customer-edit-modal');
    document.getElementById('cust-edit-id').value = id || '';
    if (id) {
        document.getElementById('cust-modal-title').innerText = 'Edit Customer Profile';
        fetch(`/api/orders/customers/${id}`)
            .then(res => res.json())
            .then(c => {
                document.getElementById('cust-edit-name').value = c.business_name;
                document.getElementById('cust-edit-contact').value = c.contact_name || '';
                document.getElementById('cust-edit-phone').value = c.phone_number;
                document.getElementById('cust-edit-route').value = c.delivery_route;
                document.getElementById('cust-edit-discount').value = c.discount_percentage;
                document.getElementById('cust-edit-instructions').value = c.special_instructions || '';
            });
    } else {
        document.getElementById('cust-modal-title').innerText = 'Add Customer Account';
        document.getElementById('cust-edit-name').value = '';
        document.getElementById('cust-edit-contact').value = '';
        document.getElementById('cust-edit-phone').value = '';
        document.getElementById('cust-edit-route').value = 'Route A - Downtown Core';
        document.getElementById('cust-edit-discount').value = '0';
        document.getElementById('cust-edit-instructions').value = '';
    }
    if (modal) modal.classList.remove('hidden');
}

function closeCustomerModal() {
    const modal = document.getElementById('customer-edit-modal');
    if (modal) modal.classList.add('hidden');
}

async function submitCustomerSave() {
    const id = document.getElementById('cust-edit-id').value;
    const payload = {
        business_name: document.getElementById('cust-edit-name').value,
        contact_name: document.getElementById('cust-edit-contact').value,
        phone_number: document.getElementById('cust-edit-phone').value,
        delivery_route: document.getElementById('cust-edit-route').value,
        pricing_tier: 'Wholesale Tier',
        discount_percentage: parseFloat(document.getElementById('cust-edit-discount').value) || 0.0,
        special_instructions: document.getElementById('cust-edit-instructions').value,
        enabled_channels: 'SMS, WhatsApp, Email'
    };

    try {
        if (id) {
            await fetch(`/api/orders/customers/${id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
        } else {
            await fetch('/api/orders/customers', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
        }
        closeCustomerModal();
        fetchCustomers();
    } catch (err) {
        console.error(err);
    }
}

// -------------------------------------------------------------
// 9. PRODUCT CATALOG
// -------------------------------------------------------------
async function fetchCatalog() {
    try {
        const res = await fetch('/api/orders/catalog');
        if (!res.ok) return;
        const products = await res.json();
        cachedCatalog = products;

        const tbody = document.getElementById('products-table-body');
        if (!tbody) return;
        tbody.innerHTML = '';

        products.forEach(p => {
            const tr = document.createElement('tr');
            tr.className = 'hover:bg-surface-subtle/50 transition';
            tr.innerHTML = `
                <td class="px-5 py-3.5 font-mono font-bold text-xs text-ink-primary">
                    ${p.sku}
                </td>
                <td class="px-5 py-3.5 font-semibold text-ink-primary">
                    ${p.name}
                </td>
                <td class="px-5 py-3.5 text-ink-secondary">
                    ${p.category}
                </td>
                <td class="px-5 py-3.5 text-ink-secondary font-mono text-[11px]">
                    ${p.unit}
                </td>
                <td class="px-5 py-3.5 font-mono font-bold text-xs text-ink-primary">
                    $${p.unit_price.toFixed(2)}
                </td>
                <td class="px-5 py-3.5 text-ink-secondary text-[11px] truncate max-w-xs">
                    ${p.aliases || 'None'}
                </td>
                <td class="px-5 py-3.5 text-right">
                    <button onclick="archiveProduct(${p.id})" class="text-xs text-rose-700 hover:text-rose-900 font-semibold">
                        Archive
                    </button>
                </td>
            `;
            tbody.appendChild(tr);
        });
    } catch (err) {
        console.error(err);
    }
}

function openAddProductModal() {
    const modal = document.getElementById('add-product-modal');
    if (modal) modal.classList.remove('hidden');
}

function closeAddProductModal() {
    const modal = document.getElementById('add-product-modal');
    if (modal) modal.classList.add('hidden');
}

async function submitNewProduct() {
    const sku = document.getElementById('new-prod-sku').value;
    const name = document.getElementById('new-prod-name').value;
    const unit = document.getElementById('new-prod-unit').value;
    const price = parseFloat(document.getElementById('new-prod-price').value) || 0.0;
    const aliases = document.getElementById('new-prod-aliases').value;

    if (!sku || !name) {
        alert('Please fill out SKU and Item Name.');
        return;
    }

    try {
        await fetch('/api/orders/products', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ sku, name, unit, unit_price: price, aliases, stock_available: 100 })
        });
        closeAddProductModal();
        fetchCatalog();
    } catch (err) {
        console.error(err);
    }
}

async function archiveProduct(id) {
    if (!confirm('Archive this product? Historical orders will retain existing details.')) return;
    try {
        await fetch(`/api/orders/products/${id}`, { method: 'DELETE' });
        fetchCatalog();
    } catch (err) {
        console.error(err);
    }
}

// -------------------------------------------------------------
// 10. RULES & BUSINESS KNOWLEDGE
// -------------------------------------------------------------
async function fetchBusinessBrain() {
    try {
        const res = await fetch('/api/orders/business/brain');
        if (!res.ok) return;
        const b = await res.json();
        document.getElementById('brain-cutoff').value = b.order_cutoff_time || '23:00';
        document.getElementById('brain-min-order').value = b.minimum_order_amount || 35.0;
        document.getElementById('brain-faq').value = b.business_faq || '';
        document.getElementById('header-business-name').innerText = b.name || 'Hudson Artisan Wholesale';
        document.getElementById('sidebar-business-name').innerText = b.name || 'Hudson Artisan Wholesale';
        const printBakeryEl = document.getElementById('print-bakery-name');
        if (printBakeryEl) printBakeryEl.innerText = b.name || 'Hudson Artisan Wholesale';
    } catch (err) {
        console.error(err);
    }
}

async function saveBusinessBrain() {
    const cutoff = document.getElementById('brain-cutoff').value;
    const minOrder = parseFloat(document.getElementById('brain-min-order').value) || 35.0;
    const faq = document.getElementById('brain-faq').value;

    try {
        await fetch('/api/orders/business/brain', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ order_cutoff_time: cutoff, minimum_order_amount: minOrder, business_faq: faq })
        });
        alert('Wholesale operating policies updated.');
        fetchBusinessBrain();
    } catch (err) {
        console.error(err);
    }
}

async function fetchMemories() {
    try {
        const res = await fetch('/api/orders/memories');
        if (!res.ok) return;
        const mems = await res.json();
        const tbody = document.getElementById('memories-table-body');
        if (!tbody) return;
        tbody.innerHTML = '';

        mems.forEach(m => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td class="px-4 py-2.5 font-semibold text-ink-primary">${m.customer_name}</td>
                <td class="px-4 py-2.5 font-mono text-ink-secondary">"${m.phrase}"</td>
                <td class="px-4 py-2.5 font-mono font-bold text-brand-800">[${m.mapped_sku}]</td>
                <td class="px-4 py-2.5 text-ink-muted text-[11px]">${m.learned_from}</td>
                <td class="px-4 py-2.5 text-ink-muted text-[11px] font-mono">${m.created_at}</td>
            `;
            tbody.appendChild(tr);
        });
    } catch (err) {
        console.error(err);
    }
}

// -------------------------------------------------------------
// 11. OPERATIONS INTELLIGENCE ("ASK ORDERSTREAM")
// -------------------------------------------------------------

// -------------------------------------------------------------
// 12. "SEE ORDERSTREAM IN ACTION" (DEMO SCENARIOS)
// -------------------------------------------------------------


// -------------------------------------------------------------
// 13. ONBOARDING & INTEGRATIONS MODALS
// -------------------------------------------------------------
function openOnboardingModal() {
    const modal = document.getElementById('onboarding-modal');
    if (modal) modal.classList.remove('hidden');
}

function closeOnboardingModal() {
    const modal = document.getElementById('onboarding-modal');
    if (modal) modal.classList.add('hidden');
}

function finishOnboarding() {
    closeOnboardingModal();
    alert('Workspace channels updated.');
}

