let currentTab = 'inbox';
let activeChannel = 'ALL';
let activeCorrection = { orderId: null, customerId: null, phrase: '' };

function switchTab(tabName) {
    currentTab = tabName;
    ['inbox', 'copilot', 'kitchen', 'memories', 'catalog', 'customers'].forEach(t => {
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

    if (tabName === 'kitchen') fetchKitchenSheet();
    if (tabName === 'memories') fetchMemories();
    if (tabName === 'catalog') fetchCatalog();
    if (tabName === 'customers') fetchCustomers();
}

function filterChannel(channel) {
    activeChannel = channel;
    ['ALL', 'SMS', 'WhatsApp', 'Email', 'Voice'].forEach(c => {
        const btn = document.getElementById(`filter-btn-${c}`);
        if (btn) {
            if (c === channel) {
                btn.className = 'text-xs bg-indigo-600 text-white font-bold px-3 py-1 rounded-full';
            } else {
                btn.className = 'text-xs bg-slate-800 text-slate-300 hover:text-white px-3 py-1 rounded-full border border-slate-700';
            }
        }
    });
    fetchOrders();
}

// Fetch and Render Live Orders with Intelligence Layer
async function fetchOrders() {
    try {
        const url = activeChannel === 'ALL' ? '/api/orders/' : `/api/orders/?channel=${activeChannel}`;
        const res = await fetch(url);
        const orders = await res.json();
        const tbody = document.getElementById('orders-table-body');
        tbody.innerHTML = '';

        let totalOrders = orders.length;
        let anomalyCount = 0;
        let totalUnits = 0;
        let totalRev = 0.0;

        if (orders.length === 0) {
            tbody.innerHTML = `<tr><td colspan="6" class="px-4 py-8 text-center text-slate-500 text-xs">No orders in this channel feed. Send a test order in the Lab below!</td></tr>`;
            updateMetrics(0, 0, 0, 0);
            return;
        }

        orders.forEach(order => {
            totalRev += order.order_total;
            if (order.is_anomaly || order.is_duplicate) anomalyCount++;

            // Channel Icon
            let channelIcon = '📱 SMS';
            if (order.channel === 'WhatsApp') channelIcon = '💬 WhatsApp';
            if (order.channel === 'Email') channelIcon = '📧 Email';
            if (order.channel === 'Voice') channelIcon = '🎙️ Voice';

            // Items tags with SKU mapping
            let itemsHtml = '<div class="space-y-1.5">';
            order.items.forEach(item => {
                totalUnits += item.quantity;
                itemsHtml += `
                    <div class="flex items-center justify-between text-xs bg-slate-950/80 px-2.5 py-1 rounded border border-slate-800">
                        <span class="font-medium text-slate-200 flex items-center gap-1.5">
                            <span class="text-indigo-400 font-mono text-[11px] font-bold">[${item.sku}]</span> 
                            ${item.quantity}x ${item.item_name}
                        </span>
                        <span class="text-slate-400 font-mono text-[11px]">$${item.line_total.toFixed(2)}</span>
                    </div>
                `;
            });
            itemsHtml += `
                <div class="text-right text-[11px] font-bold text-emerald-400 pt-0.5 font-mono">
                    Order Total: $${order.order_total.toFixed(2)}
                </div>
            </div>`;

            // Intelligence Defense Alerts
            let intelBadges = '<div class="space-y-1">';
            if (order.is_anomaly) {
                intelBadges += `<div class="text-[11px] bg-rose-500/10 text-rose-400 border border-rose-500/30 p-1.5 rounded font-medium">🚨 <b>Anomaly Alert:</b> ${order.anomaly_reason}</div>`;
            }
            if (order.is_duplicate) {
                intelBadges += `<div class="text-[11px] bg-amber-500/10 text-amber-400 border border-amber-500/30 p-1.5 rounded font-medium">🔁 <b>Duplicate Alert:</b> ${order.anomaly_reason}</div>`;
            }
            if (order.history_cloned) {
                intelBadges += `<div class="text-[11px] bg-indigo-500/10 text-indigo-300 border border-indigo-500/30 p-1.5 rounded font-medium">🧠 <b>Order Memory:</b> ${order.history_note}</div>`;
            }
            if (order.ai_clarification) {
                intelBadges += `<div class="text-[11px] bg-blue-500/10 text-blue-300 border border-blue-500/30 p-1.5 rounded font-medium">💬 <b>AI Clarification:</b> Sent to buyer</div>`;
            }
            if (!order.is_anomaly && !order.is_duplicate && !order.history_cloned) {
                intelBadges += `<div class="text-[11px] text-emerald-400 flex items-center gap-1 font-mono">🟢 ${order.confidence_score}% High Confidence Match</div>`;
            }
            intelBadges += '</div>';

            // Confirmation Status Badge
            let confirmBadge = '';
            if (order.confirmation_status.includes('SMS') || order.confirmation_status.includes('WhatsApp')) {
                confirmBadge = `<span class="bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 px-2 py-0.5 rounded-full text-[11px] font-bold">✓ Confirmed (${order.channel})</span>`;
            } else if (order.confirmation_status.includes('Approved')) {
                confirmBadge = `<span class="bg-blue-500/20 text-blue-300 border border-blue-500/40 px-2 py-0.5 rounded-full text-[11px] font-bold">✓ Staff Approved</span>`;
            } else {
                confirmBadge = `<span class="bg-amber-500/20 text-amber-300 border border-amber-500/40 px-2 py-0.5 rounded-full text-[11px] font-bold">⏳ Awaiting "YES"</span>`;
            }

            const tr = document.createElement('tr');
            tr.className = 'hover:bg-slate-850/50 transition';
            tr.innerHTML = `
                <td class="px-4 py-3.5 align-top">
                    <div class="font-bold text-white text-xs">${order.customer_name}</div>
                    <div class="text-[11px] text-slate-400 font-mono">${order.account_number} • ${order.customer_phone}</div>
                    <div class="text-[10px] text-indigo-400 mt-1">🚚 ${order.delivery_route}</div>
                </td>
                <td class="px-4 py-3.5 align-top max-w-xs">
                    <span class="text-[10px] bg-slate-800 text-slate-300 font-semibold px-2 py-0.5 rounded border border-slate-700">${channelIcon}</span>
                    <div class="text-xs text-slate-300 italic bg-slate-950 p-2 rounded border border-slate-800 mt-1.5">
                        "${order.raw_message}"
                    </div>
                    <div class="text-[10px] text-slate-500 mt-1">${order.created_at}</div>
                </td>
                <td class="px-4 py-3.5 align-top min-w-[220px]">
                    ${itemsHtml}
                </td>
                <td class="px-4 py-3.5 align-top max-w-xs">
                    ${intelBadges}
                </td>
                <td class="px-4 py-3.5 align-top">
                    ${confirmBadge}
                </td>
                <td class="px-4 py-3.5 align-top text-right space-y-1">
                    ${order.confirmation_status.includes('Confirmed') || order.confirmation_status.includes('Approved') ? 
                        `<span class="text-xs text-slate-500 block">Locked 🔒</span>` : 
                        `<button onclick="confirmOrder(${order.id})" class="text-xs bg-indigo-600 hover:bg-indigo-500 text-white font-semibold px-2.5 py-1 rounded transition block w-full">Approve</button>`
                    }
                    <button onclick="openCorrectionModal(${order.id}, ${order.customer_id}, '${order.raw_message.replace(/'/g, "\\'")}')" class="text-[10px] text-slate-400 hover:text-slate-200 underline block w-full text-right pt-1">
                        Teach Memory
                    </button>
                </td>
            `;
            tbody.appendChild(tr);
        });

        updateMetrics(totalOrders, anomalyCount, totalUnits, totalRev);
    } catch (err) {
        console.error('Error fetching orders:', err);
    }
}

function updateMetrics(orders, anomalies, units, revenue) {
    document.getElementById('stat-total-orders').innerText = orders;
    document.getElementById('stat-anomalies').innerText = anomalies;
    document.getElementById('stat-total-units').innerText = units;
    document.getElementById('stat-total-revenue').innerText = `$${revenue.toFixed(2)}`;
}

// Copilot Assistant API
async function askCopilot(presetQuery) {
    document.getElementById('copilot-input').value = presetQuery;
    sendCopilotQuery();
}

async function sendCopilotQuery() {
    const input = document.getElementById('copilot-input').value;
    if (!input.trim()) return;

    const answerBox = document.getElementById('copilot-answer-box');
    const answerText = document.getElementById('copilot-answer-text');
    answerBox.classList.remove('hidden');
    answerText.innerHTML = '<span class="animate-pulse">Thinking and analyzing operational data...</span>';

    try {
        const res = await fetch('/api/orders/copilot', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query: input })
        });
        const data = await res.json();
        // Render markdown bolding
        answerText.innerHTML = data.answer.replace(/\*\*(.*?)\*\*/g, '<b>$1</b>').replace(/\n/g, '<br>');
    } catch (err) {
        answerText.innerText = 'Error querying Copilot.';
    }
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

// Fetch Customer Language Memories
async function fetchMemories() {
    try {
        const res = await fetch('/api/orders/memories');
        const mems = await res.json();
        const tbody = document.getElementById('memories-table-body');
        tbody.innerHTML = '';

        if (mems.length === 0) {
            tbody.innerHTML = `<tr><td colspan="5" class="px-4 py-6 text-center text-slate-500 text-xs">No custom jargon learned yet. Use 'Teach Memory' on an order!</td></tr>`;
            return;
        }

        mems.forEach(m => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td class="px-4 py-3 font-bold text-white text-xs">${m.customer_name}</td>
                <td class="px-4 py-3 font-mono text-amber-300 text-xs font-semibold">"${m.phrase}"</td>
                <td class="px-4 py-3 font-mono text-indigo-400 font-bold text-xs">${m.mapped_sku}</td>
                <td class="px-4 py-3 text-xs text-slate-300">${m.learned_from}</td>
                <td class="px-4 py-3 text-xs text-slate-500 font-mono">${m.created_at}</td>
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
                <td class="px-4 py-3 text-xs text-amber-400 font-mono font-semibold">${p.stock_available} units</td>
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
                <td class="px-4 py-3 text-xs text-slate-300 font-mono">${c.phone_number}</td>
                <td class="px-4 py-3 text-xs text-indigo-300">${c.delivery_route}</td>
                <td class="px-4 py-3 text-xs text-amber-400 font-mono">${c.pricing_tier}</td>
                <td class="px-4 py-3 text-xs text-slate-300 font-mono text-right font-semibold">${c.avg_order_volume} units/order</td>
            `;
            tbody.appendChild(tr);
        });
    } catch (err) {
        console.error(err);
    }
}

// Send Simulated Inbound Order
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

// Manual Approve Order
async function confirmOrder(orderId) {
    try {
        await fetch(`/api/orders/${orderId}/confirm`, { method: 'POST' });
        fetchOrders();
    } catch (err) {
        console.error(err);
    }
}

// Human Correction Modal Logic
function openCorrectionModal(orderId, customerId, rawMsg) {
    activeCorrection = { orderId, customerId, phrase: rawMsg };
    document.getElementById('modal-phrase').value = rawMsg;
    document.getElementById('correction-modal').classList.remove('hidden');
}

function closeCorrectionModal() {
    document.getElementById('correction-modal').classList.add('hidden');
}

async function submitCorrection() {
    const sku = document.getElementById('modal-sku').value;
    try {
        await fetch('/api/orders/correct-item', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                order_id: activeCorrection.orderId,
                customer_id: activeCorrection.customerId,
                original_phrase: activeCorrection.phrase,
                corrected_sku: sku
            })
        });
        closeCorrectionModal();
        alert('🎉 Memory Learned! OrderStream will now automatically map this phrase to this SKU for this customer.');
        fetchMemories();
    } catch (err) {
        alert('Error saving memory.');
    }
}

// Pre-fill Scenarios
function setScenario(type) {
    const channelSelect = document.getElementById('sim-channel');
    const phoneSelect = document.getElementById('sim-phone');
    const bodyText = document.getElementById('sim-body');

    if (type === 'memory') {
        // Cafe Bella has historical order (10 Sourdough + 6 Croissants)
        channelSelect.value = "SMS";
        phoneSelect.value = "+15551234"; // Cafe Bella
        bodyText.value = "Hey Tony, same as last week + 4 baguettes for tomorrow please - Marco";
    } else if (type === 'jargon') {
        // Cafe Bella has jargon: "the big bread" -> BRD-001
        channelSelect.value = "WhatsApp";
        phoneSelect.value = "+15551234";
        bodyText.value = "Need 8 of the big bread and 2 dozen muffins by 6am";
    } else if (type === 'anomaly') {
        // Daily Grind avg is 20 units -> order 500 units!
        channelSelect.value = "Email";
        phoneSelect.value = "+15559876"; // Daily Grind
        bodyText.value = "Please deliver 500 sourdough loaves and 200 rye for the stadium festival tomorrow";
    } else if (type === 'confirm') {
        channelSelect.value = "SMS";
        phoneSelect.value = "+15551234";
        bodyText.value = "YES";
    }
}

// Initial Load & Polling
fetchOrders();
setInterval(fetchOrders, 4000);
