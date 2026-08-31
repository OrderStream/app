// State & Tab Switching
let currentTab = 'orders';

function switchTab(tabName) {
    currentTab = tabName;
    ['orders', 'kitchen', 'catalog', 'customers'].forEach(t => {
        const el = document.getElementById(`tab-${t}`);
        const btn = document.getElementById(`tab-btn-${t}`);
        if (t === tabName) {
            el.classList.remove('hidden');
            btn.classList.add('border-indigo-500', 'text-indigo-400', 'font-semibold');
            btn.classList.remove('border-transparent', 'text-slate-400');
        } else {
            el.classList.add('hidden');
            btn.classList.remove('border-indigo-500', 'text-indigo-400', 'font-semibold');
            btn.classList.add('border-transparent', 'text-slate-400');
        }
    });

    if (tabName === 'kitchen') fetchKitchenSheet();
    if (tabName === 'catalog') fetchCatalog();
    if (tabName === 'customers') fetchCustomers();
}

// Fetch and Render Live Orders
async function fetchOrders() {
    try {
        const res = await fetch('/api/orders/');
        const orders = await res.json();
        const tbody = document.getElementById('orders-table-body');
        tbody.innerHTML = '';

        let totalOrders = orders.length;
        let confirmedCount = 0;
        let totalUnits = 0;
        let totalRev = 0.0;

        if (orders.length === 0) {
            tbody.innerHTML = `<tr><td colspan="6" class="px-4 py-8 text-center text-slate-500 text-xs">No orders yet. Send a simulated SMS below!</td></tr>`;
            updateMetrics(0, 0, 0, 0);
            return;
        }

        orders.forEach(order => {
            totalRev += order.order_total;
            if (order.confirmation_status.includes('Confirmed') || order.confirmation_status.includes('Approved')) {
                confirmedCount++;
            }

            // Items tags with SKU mapping
            let itemsHtml = '<div class="space-y-1.5">';
            order.items.forEach(item => {
                totalUnits += item.quantity;
                itemsHtml += `
                    <div class="flex items-center justify-between text-xs bg-slate-900/80 px-2.5 py-1 rounded border border-slate-700/60">
                        <span class="font-medium text-slate-200">
                            <span class="text-indigo-400 font-mono text-[11px] font-bold">[${item.sku}]</span> 
                            ${item.quantity}x ${item.item_name}
                        </span>
                        <span class="text-slate-400 font-mono text-[11px]">$${item.line_total.toFixed(2)}</span>
                    </div>
                `;
            });
            itemsHtml += `
                <div class="text-right text-[11px] font-semibold text-emerald-400 pt-0.5 font-mono">
                    Total: $${order.order_total.toFixed(2)}
                </div>
            </div>`;

            // Confidence Score Badge
            let confBadge = '';
            if (order.confidence_score >= 90) {
                confBadge = `<span class="bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-2 py-0.5 rounded text-[11px] font-medium font-mono">🟢 ${order.confidence_score}% High</span>`;
            } else if (order.confidence_score >= 70) {
                confBadge = `<span class="bg-amber-500/10 text-amber-400 border border-amber-500/20 px-2 py-0.5 rounded text-[11px] font-medium font-mono">🟡 ${order.confidence_score}% Match</span>`;
            } else {
                confBadge = `<span class="bg-rose-500/10 text-rose-400 border border-rose-500/20 px-2 py-0.5 rounded text-[11px] font-medium font-mono">🔴 ${order.confidence_score}% Review</span>`;
            }

            // Confirmation Status Badge
            let confirmBadge = '';
            if (order.confirmation_status.includes('SMS')) {
                confirmBadge = `<span class="bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 px-2 py-0.5 rounded-full text-[11px] font-semibold">✓ Confirmed (SMS)</span>`;
            } else if (order.confirmation_status.includes('Approved')) {
                confirmBadge = `<span class="bg-blue-500/20 text-blue-300 border border-blue-500/40 px-2 py-0.5 rounded-full text-[11px] font-semibold">✓ Manual Approved</span>`;
            } else {
                confirmBadge = `<span class="bg-amber-500/20 text-amber-300 border border-amber-500/40 px-2 py-0.5 rounded-full text-[11px] font-semibold animate-pulse">⏳ Awaiting "YES"</span>`;
            }

            const tr = document.createElement('tr');
            tr.className = 'hover:bg-slate-800/30 transition';
            tr.innerHTML = `
                <td class="px-4 py-3">
                    <div class="font-bold text-white text-xs">${order.customer_name}</div>
                    <div class="text-[11px] text-slate-400 font-mono">${order.account_number} • ${order.customer_phone}</div>
                    <div class="text-[10px] text-indigo-400 mt-0.5">🚚 ${order.delivery_route}</div>
                </td>
                <td class="px-4 py-3 max-w-xs">
                    <div class="text-xs text-slate-300 italic bg-slate-900/50 p-2 rounded border border-slate-800">
                        "${order.raw_message}"
                    </div>
                    <div class="text-[10px] text-slate-500 mt-1">${order.created_at}</div>
                </td>
                <td class="px-4 py-3 min-w-[240px]">
                    ${itemsHtml}
                </td>
                <td class="px-4 py-3">
                    ${confBadge}
                </td>
                <td class="px-4 py-3">
                    ${confirmBadge}
                </td>
                <td class="px-4 py-3 text-right">
                    ${order.confirmation_status.includes('Confirmed') || order.confirmation_status.includes('Approved') ? 
                        `<span class="text-xs text-slate-500">Locked 🔒</span>` : 
                        `<button onclick="confirmOrder(${order.id})" class="text-xs bg-slate-700 hover:bg-slate-600 text-white px-2.5 py-1 rounded transition font-medium">Approve</button>`
                    }
                </td>
            `;
            tbody.appendChild(tr);
        });

        updateMetrics(totalOrders, confirmedCount, totalUnits, totalRev);
    } catch (err) {
        console.error('Error fetching orders:', err);
    }
}

function updateMetrics(orders, confirmed, units, revenue) {
    document.getElementById('stat-total-orders').innerText = orders;
    document.getElementById('stat-confirmed-orders').innerText = confirmed;
    document.getElementById('stat-total-units').innerText = units;
    document.getElementById('stat-total-revenue').innerText = `$${revenue.toFixed(2)}`;
}

// Fetch Kitchen Production Sheet
async function fetchKitchenSheet() {
    try {
        const res = await fetch('/api/orders/kitchen-sheet');
        const items = await res.json();
        const tbody = document.getElementById('kitchen-sheet-body');
        tbody.innerHTML = '';

        if (items.length === 0) {
            tbody.innerHTML = `<tr><td colspan="3" class="px-4 py-6 text-center text-slate-500 text-xs">No active production batches for tomorrow.</td></tr>`;
            return;
        }

        items.forEach(item => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td class="px-4 py-3 font-mono text-indigo-400 font-bold text-xs">${item.sku}</td>
                <td class="px-4 py-3 font-medium text-slate-200 text-sm">${item.item_name}</td>
                <td class="px-4 py-3 text-right font-black text-amber-400 text-base font-mono">${item.total_quantity} Units</td>
            `;
            tbody.appendChild(tr);
        });
    } catch (err) {
        console.error(err);
    }
}

// Fetch Catalog
async function fetchCatalog() {
    try {
        const res = await fetch('/api/orders/catalog');
        const products = await res.json();
        const tbody = document.getElementById('catalog-table-body');
        tbody.innerHTML = '';

        products.forEach(p => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td class="px-4 py-3 font-mono text-indigo-400 font-bold text-xs">${p.sku}</td>
                <td class="px-4 py-3 font-medium text-slate-200 text-xs">${p.name} <span class="text-[10px] text-slate-500">(${p.category})</span></td>
                <td class="px-4 py-3 text-xs text-slate-300 font-mono">${p.unit}</td>
                <td class="px-4 py-3 text-xs text-emerald-400 font-mono font-semibold">$${p.unit_price.toFixed(2)}</td>
                <td class="px-4 py-3 text-xs text-slate-400 italic">${p.aliases}</td>
            `;
            tbody.appendChild(tr);
        });
    } catch (err) {
        console.error(err);
    }
}

// Fetch Customers
async function fetchCustomers() {
    try {
        const res = await fetch('/api/orders/customers');
        const customers = await res.json();
        const tbody = document.getElementById('customers-table-body');
        tbody.innerHTML = '';

        customers.forEach(c => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td class="px-4 py-3 font-mono text-indigo-400 font-bold text-xs">${c.account_number}</td>
                <td class="px-4 py-3 font-bold text-white text-xs">${c.business_name}</td>
                <td class="px-4 py-3 text-xs text-slate-300">${c.contact_name || 'N/A'}</td>
                <td class="px-4 py-3 text-xs text-slate-300 font-mono">${c.phone_number}</td>
                <td class="px-4 py-3 text-xs text-indigo-300">${c.delivery_route}</td>
                <td class="px-4 py-3 text-xs text-amber-400 font-mono">${c.pricing_tier}</td>
            `;
            tbody.appendChild(tr);
        });
    } catch (err) {
        console.error(err);
    }
}

// Send Simulated Webhook (SMS)
async function sendSimulatedWebhook() {
    const phone = document.getElementById('sim-phone').value;
    const body = document.getElementById('sim-body').value;

    if (!body.trim()) return;

    try {
        const formData = new URLSearchParams();
        formData.append('From', phone);
        formData.append('Body', body);

        const res = await fetch('/api/webhook/twilio', {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: formData.toString()
        });

        const xmlText = await res.text();
        
        // Extract SMS message from XML
        const parser = new DOMParser();
        const xmlDoc = parser.parseFromString(xmlText, "text/xml");
        const messageNode = xmlDoc.getElementsByTagName("Message")[0];
        const replyText = messageNode ? messageNode.textContent : "Confirmation Sent.";

        // Show Response Bubble
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

// Manual Approve
async function confirmOrder(orderId) {
    try {
        await fetch(`/api/orders/${orderId}/confirm`, { method: 'POST' });
        fetchOrders();
    } catch (err) {
        console.error(err);
    }
}

// Quick Sample Pre-fills
function setSample(num) {
    const phoneSelect = document.getElementById('sim-phone');
    const bodyText = document.getElementById('sim-body');
    if (num === 1) {
        phoneSelect.value = "+15559876"; // The Daily Grind
        bodyText.value = "Hey Tony, Sarah here from Daily Grind. Need 6 sourdough loaves, actually make it 8, and 2 dozen blueberry muffins by 5am.";
    } else if (num === 2) {
        phoneSelect.value = "+15551234"; // Cafe Bella
        bodyText.value = "Hey 10 croissants and 4 seeded rye for tomorrow please - Marco";
    } else if (num === 3) {
        phoneSelect.value = "+15559876";
        bodyText.value = "YES";
    }
}

// Initial Load & Polling
fetchOrders();
setInterval(fetchOrders, 4000);
