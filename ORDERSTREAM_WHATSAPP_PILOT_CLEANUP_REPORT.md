# OrderStream WhatsApp Pilot Cleanup Report

## Summary
WhatsApp Business is not fully supported for the first customer pilot. The application does not correctly normalize the `whatsapp:` prefix for tenant resolution and customer matching on inbound webhooks. Therefore, all user-visible and database default references to WhatsApp as an active, supported channel have been removed.

## WhatsApp References Found
- **Backend Defaults:** `models.py` had default channels and provider comments including WhatsApp. `routers/orders.py` schemas had default `enabled_channels` including WhatsApp, and `/api/dashboard/summary` surfaced it in `channels_health`.
- **Database Seeds:** `services/seeder.py` seeded mock customers with `enabled_channels` including WhatsApp, and created a mocked order that claimed to come via WhatsApp. `test_tenant_isolation_suite.py` contained a mocked test order claiming to originate from WhatsApp.
- **Frontend UI:** `static/index.html` contained a dropdown filter option for WhatsApp, a checkbox indicating WhatsApp Business was an active channel, and a text claim that "Multi-channel feed active". `static/app.js` contained a default `enabled_channels` that included WhatsApp when editing a customer.

## Exact Changes Made
1. `models.py`: Removed "WhatsApp" from the default value of the `enabled_channels` column, removed it from the `channel` column's comment, and removed `twilio_whatsapp` from the `provider` column's comment.
2. `services/seeder.py`: Changed all instances of `enabled_channels="SMS, WhatsApp, Email"` (and similar) to omit WhatsApp. Changed the mocked order channel, confirmation status, actor, and descriptions to use "SMS" instead of "WhatsApp".
3. `routers/orders.py`: Updated the default `enabled_channels` in `CustomerCreateRequest` and `CustomerUpdateRequest` to remove WhatsApp. Removed the mock health check entry for "WhatsApp Business" in the `channels_health` list.
4. `static/index.html`: Removed the `<option value="WhatsApp">WhatsApp</option>` in the channel selector dropdown. Removed the "WhatsApp Business" checkbox in the Active Channels section. Removed the "Multi-channel feed active" label.
5. `static/app.js`: Removed "WhatsApp" from the default `enabled_channels` when initializing customer edit data.
6. `test_tenant_isolation_suite.py`: Changed the test setup parameter `channel="WhatsApp"` to `channel="SMS"`.

## Files Changed
- `models.py`
- `services/seeder.py`
- `routers/orders.py`
- `static/index.html`
- `static/app.js`
- `test_tenant_isolation_suite.py`

## Testing Results
- **Tests run:** `python -m unittest test_tenant_isolation_suite.py test_full_pilot_suite.py`
- **Result:** All 19 tests passed successfully.
- **Confirmation:** The SMS functionality remains entirely unchanged and fully operational. No webhook architecture or parsing logic was altered.

## Remaining WhatsApp Technical Limitations
While the user-facing claims have been removed, the underlying Twilio webhook (`/api/webhook/twilio`) may still technically accept an incoming HTTP POST with the `whatsapp:` prefix in the `From` and `To` numbers. However, the current pilot application logic does not adequately strip or normalize this prefix before matching tenants and customers in the database. When full WhatsApp support is built out for future phases, the webhook router will need to explicitly parse and map `whatsapp:+1...` to the underlying standardized phone numbers.