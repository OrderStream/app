let currentTab = 'orders';
let activeChannel = 'ALL';
let activeCorrection = { orderId: null, customerId: null, phrase: '' };
let devLabOpen = false;

function switchTab(tabName) {
    currentTab = tabName;
    ['orders', 'brain', 'kitchen'].forEach(t => {
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

    if (tabName === 'brain') {
        fetchCatalog();
        fetchMemories();
        fetchBusinessBrain();
    }
    if (tabName === 'kitchen') {
        fetchKitchenSheet();
    }
}

function toggleDevLab() {
    devLabOpen = !devLabOpen;
    const panel = document.getElementById('dev-lab-panel');
    const btn = document.getElementById('dev-lab-toggle-btn');
    if (devLabOpen) {
        panel.classList.remove('hidden');
        btn.classList.add('bg-indigo-600', 'text-white');
        btn.classList.remove('bg-slate-900', 'text-indigo-300');
    } else {
        panel.classList.add('hidden');
        btn.classList.remove('bg-indigo-600', 'text-white');
        btn.classList.add('bg-slate-900', 'text-indigo-300');
    }
}

function filterChannel(channel) {
    activeChannel = channel;
    ['ALL', 'SMS', 'WhatsApp', 'Email'].forEach(c => {
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

// Fetch Live Orders
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
            tbody.innerHTML = `<tr><td colspan="6" class="px-4 py-8 text-center text-slate-500 text-xs">No active orders found in feed.</td></tr>`;
            updateMetrics(0, 0, 0, 0);
            return;
        }

        orders.forEach(order => {
            totalRev += order.order_total;
            if (order.is_anomaly || order.is_duplicate) anomalyCount++;

            let channelIcon = '📱 SMS';
            if (order.channel === 'WhatsApp') channelIcon = '💬 WhatsApp';
            if (order.channel === 'Email') channelIcon = '📧 Email';

            let itemsHtml = '<div class="space-y-1.5">';
            order.items.forEach(item => {
                totalUnits += item.quantity;
                itemsHtml += `
                    <div class="flex items-center justify-between text-xs bg-slate-950/80 px-2.5 py-1 rounded border border-slate-800">
                        <span class="font-medium text-slate-200">
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

            let intelBadges = '<div class="space-y-1">';
            if (order.is_anomaly) {
                intelBadges += `<div class="text-[11px] bg-rose-500/10 text-rose-400 border border-rose-500/30 p-1.5 rounded font-medium">🚨 <b>Anomaly:</b> ${order.anomaly_reason}</div>`;
            }
            if (order.is_duplicate) {
                intelBadges += `<div class="text-[11px] bg-amber-500/10 text-amber-400 border border-amber-500/30 p-1.5 rounded font-medium">🔁 <b>Duplicate:</b> ${order.anomaly_reason}</div>`;
            }
            if (order.history_cloned) {
                intelBadges += `<div class="text-[11px] bg-indigo-500/10 text-indigo-300 border border-indigo-500/30 p-1.5 rounded font-medium">🧠 <b>Memory:</b> ${order.history_note}</div>`;
            }
            if (!order.is_anomaly && !order.is_duplicate && !order.history_cloned) {
                intelBadges += `<div class="text-[11px] text-emerald-400 flex items-center gap-1 font-mono">🟢 ${order.confidence_score}% High Match</div>`;
            }
            intelBadges += '</div>';

            let confirmBadge = '';
            if (order.confirmation_status.includes('SMS') || order.confirmation_status.includes('WhatsApp')) {
                confirmBadge = `<span class="bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 px-2.5 py-0.5 rounded-full text-[11px] font-bold">✓ Confirmed (${order.channel})</span>`;
            } else if (order.confirmation_status.includes('Staff Approved') || order.confirmation_status.includes('Approved')) {
                confirmBadge = `<span class="bg-blue-500/20 text-blue-300 border border-blue-500/40 px-2.5 py-0.5 rounded-full text-[11px] font-bold">✓ Staff Approved</span>`;
            } else {
                confirmBadge = `<span class="bg-amber-500/20 text-amber-300 border border-amber-500/40 px-2.5 py-0.5 rounded-full text-[11px] font-bold">⏳ Awaiting "YES"</span>`;
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
                        `<button onclick="confirmOrder(${order.id})" class="text-xs bg-indigo-600 hover:bg-indigo-500 text-white font-bold px-3 py-1 rounded transition block w-full">Approve</button>`
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
        console.error(err);
    }
}

function updateMetrics(orders, anomalies, units, revenue) {
    document.getElementById('stat-total-orders').innerText = orders;
    document.getElementById('stat-anomalies').innerText = anomalies;
    document.getElementById('stat-total-units').innerText = units;
    document.getElementById('stat-total-revenue').innerText = `$${revenue.toFixed(2)}`;
}

// Fetch Business Brain
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
        alert('✅ Business Brain & Policies saved successfully!');
    } catch (err) {
        alert('Error saving brain.');
    }
}

// Catalog Controls (Owner Add / Delete)
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
                <td class="px-3 py-2 font-semibold text-white">${p.name} <span class="text-slate-500 font-normal">(${p.category})</span></td>
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
    if (!confirm('Are you sure you want to remove this product from your catalog?')) return;
    try {
        await fetch(`/api/orders/products/${prodId}`, { method: 'DELETE' });
        fetchCatalog();
    } catch (err) {
        console.error(err);
    }
}

// Memories
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

// Kitchen Sheet
async function fetchKitchenSheet() {
    try {
        const res = await fetch('/api/orders/kitchen-sheet');
        const items = await res.json();
        const tbody = document.getElementById('kitchen-sheet-body');
        tbody.innerHTML = '';

        items.forEach(item => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td class="px-4 py-3 font-mono text-indigo-400 font-bold text-xs">${item.sku}</td>
                <td class="px-4 py-3 font-semibold text-slate-200 text-sm">${item.item_name}</td>
                <td class="px-4 py-3 text-right font-black text-amber-400 text-base font-mono">${item.total_quantity} Units</td>
            `;
            tbody.appendChild(tr);
        });
    } catch (err) {
        console.error(err);
    }
}

// Copilot
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

// Inbound Simulation
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

// Onboarding Modal
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

// Scenario Pre-fills
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

// Initial
fetchOrders();
fetchBusinessBrain();
setInterval(fetchOrders, 4000);
