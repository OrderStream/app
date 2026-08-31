document.addEventListener('DOMContentLoaded', () => {
    fetchOrders();

    document.getElementById('simBtn').addEventListener('click', sendMockWebhook);
    document.getElementById('exportCsvBtn').addEventListener('click', exportCsv);
});

async function fetchOrders() {
    try {
        const res = await fetch('/api/orders/');
        const orders = await res.json();
        renderOrders(orders);
    } catch (e) {
        console.error("Failed to fetch orders", e);
    }
}

function renderOrders(orders) {
    const tbody = document.getElementById('ordersTableBody');
    tbody.innerHTML = '';

    if (orders.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" class="px-6 py-4 text-center text-gray-500">No orders found. Send a test SMS to begin.</td></tr>';
        return;
    }

    orders.forEach(order => {
        const tr = document.createElement('tr');
        
        let statusBadge = '';
        if (order.status === 'Parsed') {
            statusBadge = `<span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-green-100 text-green-800">Parsed</span>`;
        } else if (order.status === 'Exported') {
            statusBadge = `<span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-blue-100 text-blue-800">Exported</span>`;
        } else {
            statusBadge = `<span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-yellow-100 text-yellow-800">Needs Review</span>`;
        }

        const itemsHtml = order.items.map(i => `<div class="text-sm text-gray-900 font-medium">${i.quantity}x ${i.item_name}</div>`).join('');

        tr.innerHTML = `
            <td class="px-6 py-4 whitespace-nowrap">${statusBadge}</td>
            <td class="px-6 py-4 whitespace-nowrap">
                <div class="text-sm font-medium text-gray-900">${order.customer_name || 'Unknown'}</div>
                <div class="text-sm text-gray-500">${order.customer_phone}</div>
            </td>
            <td class="px-6 py-4 text-sm text-gray-500 max-w-xs truncate" title="${order.raw_message}">
                "${order.raw_message}"
            </td>
            <td class="px-6 py-4 whitespace-nowrap">
                ${itemsHtml}
            </td>
        `;
        tbody.appendChild(tr);
    });
}

async function sendMockWebhook() {
    const phone = document.getElementById('simPhone').value;
    const body = document.getElementById('simBody').value;
    
    if (!phone || !body) return alert("Fill out phone and body");
    
    const formData = new URLSearchParams();
    formData.append('From', phone);
    formData.append('Body', body);

    try {
        await fetch('/api/webhook/twilio', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded'
            },
            body: formData.toString()
        });
        document.getElementById('simBody').value = '';
        fetchOrders();
    } catch (e) {
        console.error("Webhook failed", e);
    }
}

async function exportCsv() {
    try {
        const res = await fetch('/api/orders/');
        const orders = await res.json();
        
        let csvContent = "data:text/csv;charset=utf-8,";
        csvContent += "Customer,Phone,Item,Quantity,Status\n";
        
        orders.forEach(order => {
            order.items.forEach(item => {
                const row = [
                    `"${order.customer_name || ''}"`,
                    `"${order.customer_phone || ''}"`,
                    `"${item.item_name || ''}"`,
                    item.quantity,
                    `"${order.status || ''}"`
                ].join(",");
                csvContent += row + "\n";
            });
            
            // Mark as exported
            if(order.status !== 'Exported') {
                fetch(`/api/orders/${order.id}/status?status=Exported`, {method: 'PUT'});
            }
        });
        
        const encodedUri = encodeURI(csvContent);
        const link = document.createElement("a");
        link.setAttribute("href", encodedUri);
        link.setAttribute("download", `orders_${new Date().toISOString().split('T')[0]}.csv`);
        document.body.appendChild(link);
        link.click();
        
        setTimeout(fetchOrders, 1000);
    } catch (e) {
        console.error("Export failed", e);
    }
}
