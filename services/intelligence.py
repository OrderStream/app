import re
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
import models
from services.matcher import match_product_sku

def process_order_intelligence(
    db: Session, 
    business: models.BusinessTenant,
    customer: models.Customer, 
    raw_text: str, 
    parsed_items: list, 
    channel: str = "SMS"
) -> dict:
    """
    Master Order Intelligence & Business Brain Engine:
    - 1. Checks if message is a General FAQ / Policy inquiry (Pricing, Delivery, Cutoff)
    - 2. Resolves 'Same as last time' historical order cloning
    - 3. Applies Business-specific Customer Language Memory
    - 4. Checks Minimum Order Amounts & Cutoff Policies
    - 5. Anomaly & Volume Spike Defense
    - 6. Duplicate Interceptor
    """
    clean_text = raw_text.lower().strip()
    b_id = business.id if business else 1
    
    # -------------------------------------------------------------
    # 0. CONVERSATIONAL BUSINESS BRAIN (FAQ & Inquiry Handler)
    # -------------------------------------------------------------
    # If the customer is asking a question rather than ordering
    is_inquiry = False
    inquiry_reply = None
    
    faq_triggers = ["how much", "what is the price", "cost of", "cutoff", "cut off", "delivery time", "minimum order", "deliver to", "allergen", "gluten"]
    if any(ft in clean_text for ft in faq_triggers) and not parsed_items:
        is_inquiry = True
        if "cutoff" in clean_text or "cut off" in clean_text:
            inquiry_reply = f"OrderStream ({business.name if business else 'Bakery'}): Our order cutoff is {business.order_cutoff_time if business else '11:00 PM'} for next-day morning delivery."
        elif "minimum" in clean_text:
            inquiry_reply = f"OrderStream: Our minimum wholesale order is ${business.minimum_order_amount if business else 35.0:.2f}."
        elif "how much" in clean_text or "price" in clean_text or "cost" in clean_text:
            # Look up product in catalog
            prod, _ = match_product_sku(db, clean_text, business_id=b_id)
            if prod:
                inquiry_reply = f"OrderStream: {prod.name} ([{prod.sku}]) is ${prod.unit_price:.2f} per {prod.unit} wholesale."
            else:
                inquiry_reply = f"OrderStream: {business.business_faq if business else 'Wholesale catalog available. Please text your item request.'}"
        else:
            inquiry_reply = f"OrderStream: {business.business_faq if business else 'Thank you for reaching out. How can our kitchen help you?'}"

        return {
            "items": [],
            "status": "Inquiry Answered",
            "confidence_score": 99,
            "is_anomaly": False,
            "anomaly_reason": None,
            "is_duplicate": False,
            "duplicate_of_id": None,
            "history_cloned": False,
            "history_note": None,
            "ai_clarification": inquiry_reply,
            "is_inquiry": True
        }

    final_items = []
    history_cloned = False
    history_note = None
    is_anomaly = False
    anomaly_reason = None
    is_duplicate = False
    duplicate_of_id = None
    ai_clarification = None
    confidence_score = 95

    # -------------------------------------------------------------
    # 1. ORDER MEMORY ENGINE: 'Same as last time' / 'The Usual'
    # -------------------------------------------------------------
    history_triggers = ["same as last", "repeat last", "the usual", "same order", "repeat previous", "like last week"]
    wants_history = any(t in clean_text for t in history_triggers)
    
    if wants_history and customer:
        last_order = db.query(models.Order).filter(
            models.Order.business_id == b_id,
            models.Order.customer_id == customer.id,
            models.Order.status.in_(["Ready", "Exported", "Confirmed"])
        ).order_by(models.Order.id.desc()).first()
        
        if last_order and last_order.items:
            history_cloned = True
            history_note = f"Auto-cloned {len(last_order.items)} items from Order #{last_order.id}"
            
            for prev_item in last_order.items:
                final_items.append({
                    "product_id": prev_item.product_id,
                    "matched_sku": prev_item.matched_sku,
                    "item_name": prev_item.item_name,
                    "quantity": prev_item.quantity,
                    "unit_price": prev_item.unit_price,
                    "line_total": prev_item.line_total,
                    "match_confidence": 98
                })

    # -------------------------------------------------------------
    # 2. CUSTOMER LANGUAGE MEMORY & CATALOG SKU RESOLVER
    # -------------------------------------------------------------
    customer_memories = {}
    if customer:
        mems = db.query(models.CustomerLanguageMemory).filter(
            models.CustomerLanguageMemory.business_id == b_id,
            models.CustomerLanguageMemory.customer_id == customer.id
        ).all()
        for m in mems:
            customer_memories[m.phrase.lower().strip()] = m.mapped_sku

    for item in parsed_items:
        raw_name = item.get("item_name", "").strip()
        qty = item.get("quantity", 1)
        raw_name_lower = raw_name.lower()

        matched_sku = None
        if raw_name_lower in customer_memories:
            matched_sku = customer_memories[raw_name_lower]
            prod = db.query(models.ProductCatalog).filter(
                models.ProductCatalog.business_id == b_id,
                models.ProductCatalog.sku == matched_sku
            ).first()
            item_confidence = 99
        else:
            prod, item_confidence = match_product_sku(db, raw_name, business_id=b_id)
            matched_sku = prod.sku if prod else "MISC-001"

        final_name = prod.name if prod else raw_name
        price = prod.unit_price if prod else 0.0
        
        existing = next((i for i in final_items if i["matched_sku"] == matched_sku), None)
        if existing:
            existing["quantity"] += qty
            existing["line_total"] = existing["quantity"] * existing["unit_price"]
        else:
            final_items.append({
                "product_id": prod.id if prod else None,
                "matched_sku": matched_sku,
                "item_name": final_name,
                "quantity": qty,
                "unit_price": price,
                "line_total": price * qty,
                "match_confidence": item_confidence
            })
            
        if item_confidence < confidence_score:
            confidence_score = item_confidence

    # -------------------------------------------------------------
    # 3. ANOMALY DETECTION & MINIMUM ORDER ENFORCEMENT
    # -------------------------------------------------------------
    total_units = sum(i["quantity"] for i in final_items)
    order_total_val = sum(i["line_total"] for i in final_items)
    avg_vol = customer.avg_order_volume if customer else 15.0
    
    # Anomaly 1: Volume Spike
    if total_units >= (avg_vol * 4) and total_units > 30:
        is_anomaly = True
        multiplier = round(total_units / max(avg_vol, 1), 1)
        anomaly_reason = f"Volume Spike: {total_units} units is {multiplier}x higher than client's avg ({avg_vol:.0f} units)"
        confidence_score = min(confidence_score, 65)
        
    # Anomaly 2: Below Minimum Order Amount Policy
    min_order = business.minimum_order_amount if business else 0.0
    if min_order > 0 and order_total_val < min_order and order_total_val > 0:
        is_anomaly = True
        anomaly_reason = f"Policy Alert: Order total (${order_total_val:.2f}) is below ${min_order:.2f} wholesale minimum."
        confidence_score = min(confidence_score, 60)

    # Anomaly 3: Unmatched product
    for item in final_items:
        if item["matched_sku"] == "MISC-001" or item["match_confidence"] < 60:
            is_anomaly = True
            anomaly_reason = f"Uncertain Product: '{item['item_name']}' could not be matched to catalog."
            confidence_score = 45
            ai_clarification = f"OrderStream: We received '{item['item_name']}'. Did you mean Country Sourdough (BRD-001) or Whole Wheat (BRD-004)?"

    # -------------------------------------------------------------
    # 4. DUPLICATE ORDER DETECTION
    # -------------------------------------------------------------
    if customer:
        one_hour_ago = datetime.utcnow() - timedelta(minutes=60)
        recent_orders = db.query(models.Order).filter(
            models.Order.business_id == b_id,
            models.Order.customer_id == customer.id,
            models.Order.created_at >= one_hour_ago
        ).all()
        
        for r_order in recent_orders:
            r_skus = sorted([i.matched_sku for i in r_order.items])
            curr_skus = sorted([i["matched_sku"] for i in final_items])
            if r_skus and r_skus == curr_skus:
                is_duplicate = True
                duplicate_of_id = r_order.id
                confidence_score = 40
                anomaly_reason = f"Possible Duplicate: Identical to {r_order.channel} Order #{r_order.id} sent {r_order.created_at.strftime('%H:%M')}"
                break

    order_status = "Needs Review" if (is_duplicate or is_anomaly or confidence_score < 70) else "Ready"

    return {
        "items": final_items,
        "status": order_status,
        "confidence_score": confidence_score,
        "is_anomaly": is_anomaly,
        "anomaly_reason": anomaly_reason,
        "is_duplicate": is_duplicate,
        "duplicate_of_id": duplicate_of_id,
        "history_cloned": history_cloned,
        "history_note": history_note,
        "ai_clarification": ai_clarification,
        "is_inquiry": False
    }

def record_human_correction_learning(db: Session, customer_id: int, original_phrase: str, corrected_sku: str, business_id: int = 1):
    """Saves customer-specific language memory permanently."""
    if not customer_id or not original_phrase or not corrected_sku:
        return
        
    phrase_clean = original_phrase.strip().lower()
    existing = db.query(models.CustomerLanguageMemory).filter(
        models.CustomerLanguageMemory.business_id == business_id,
        models.CustomerLanguageMemory.customer_id == customer_id,
        models.CustomerLanguageMemory.phrase == phrase_clean
    ).first()
    
    if existing:
        existing.mapped_sku = corrected_sku
        existing.created_at = datetime.utcnow()
    else:
        mem = models.CustomerLanguageMemory(
            business_id=business_id,
            customer_id=customer_id,
            phrase=phrase_clean,
            mapped_sku=corrected_sku,
            confidence_boost=98,
            learned_from="Human Staff Correction"
        )
        db.add(mem)
    db.commit()

def run_copilot_query(db: Session, query: str, business_id: int = 1) -> str:
    """Answers operational questions about incoming demand and business rules."""
    q = query.lower()
    orders = db.query(models.Order).filter(models.Order.business_id == business_id).all()
    customers = db.query(models.Customer).filter(models.Customer.business_id == business_id).all()
    business = db.query(models.BusinessTenant).filter(models.BusinessTenant.id == business_id).first()
    
    if "cutoff" in q or "policy" in q:
        return f"⏰ **Business Policy:** Nightly cutoff is **{business.order_cutoff_time if business else '11:00 PM'}**. Minimum order amount is **${business.minimum_order_amount if business else 35.0:.2f}**."
        
    elif "why" in q and ("review" in q or "flag" in q or "anomaly" in q):
        flagged = [o for o in orders if o.is_anomaly or o.status == "Needs Review"]
        if not flagged:
            return "✅ All current orders are high-confidence (95%+) and ready for kitchen production."
        
        reasons = [f"• **Order #{o.id} ({o.customer_name})**: {o.anomaly_reason or 'Confidence below threshold'}" for o in flagged[:3]]
        return "⚠️ **Flagged Order Explanations:**\n" + "\n".join(reasons)
        
    elif "not ordered" in q or "missing" in q or "inactive" in q:
        recent_cust_ids = set(o.customer_id for o in orders)
        missing = [c for c in customers if c.id not in recent_cust_ids]
        if not missing:
            return "🎉 All active wholesale accounts have submitted their orders for tomorrow!"
        return f"🚨 **Predictive Notice: 1 Account has NOT ordered yet:**\n• **{missing[0].business_name}** ({missing[0].phone_number}) normally orders by 9:30 PM on Route {missing[0].delivery_route}."
        
    elif "most common" in q or "top" in q or "popular" in q:
        items = db.query(models.OrderItem).join(models.Order).filter(models.Order.business_id == business_id).all()
        sku_counts = {}
        for i in items:
            sku_counts[i.item_name] = sku_counts.get(i.item_name, 0) + i.quantity
        sorted_items = sorted(sku_counts.items(), key=lambda x: x[1], reverse=True)[:3]
        summary = ", ".join([f"{name} ({qty} units)" for name, qty in sorted_items])
        return f"📊 **Top Demand Items Tonight:** {summary}."
        
    else:
        total_rev = sum(sum(i.line_total for i in o.items) for o in orders)
        total_units = sum(sum(i.quantity for i in o.items) for o in orders)
        return f"💡 **OrderStream Intelligence Summary:** Managing **{len(orders)} multi-channel orders** across **{len(customers)} accounts**. Total bake batch: **{total_units} units**. Queued batch value: **${total_rev:.2f}**."
