from fastapi import APIRouter, Depends, Form, Request, Response
from sqlalchemy.orm import Session
from datetime import datetime
from database import get_db
import models
from services.llm_parser import parse_order_text
from services.matcher import match_or_create_customer, generate_confirmation_sms
from services.intelligence import process_order_intelligence

router = APIRouter()

@router.post("/twilio")
async def twilio_webhook(
    request: Request,
    From: str = Form(...),
    Body: str = Form(...),
    Channel: str = Form(default="SMS"),
    db: Session = Depends(get_db)
):
    """
    Unified Ingestion Layer with multi-tenant isolation, audit logging, and human safety workflows.
    """
    clean_body = Body.strip()
    business = db.query(models.BusinessTenant).first()
    b_id = business.id if business else 1
    
    # 1. Handle Confirmation Reply ("YES", "CONFIRM", "OK")
    if clean_body.upper() in ["YES", "CONFIRM", "OK", "Y", "YEP", "CORRECT"]:
        recent_order = db.query(models.Order).filter(
            models.Order.business_id == b_id,
            models.Order.customer_phone == From
        ).order_by(models.Order.id.desc()).first()
        
        if recent_order:
            recent_order.confirmation_status = f"Confirmed via {Channel}"
            if not recent_order.is_anomaly and not recent_order.is_duplicate and recent_order.confidence_score >= 80:
                recent_order.status = "Approved"
            else:
                recent_order.status = "Needs Review"
                
            # Log timeline event
            event = models.OrderTimelineEvent(
                order_id=recent_order.id,
                event_type="Customer Confirmed",
                actor=f"Customer via {Channel}",
                description=f"Buyer replied '{clean_body}' to confirm order.",
                created_at=datetime.utcnow()
            )
            db.add(event)
            db.commit()
            
            twiml_reply = (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<Response><Message>OrderStream: Your order is CONFIRMED for tomorrow morning\'s bake! 🥖</Message></Response>'
            )
            return Response(content=twiml_reply, media_type="application/xml")

    # 2. Parse Incoming Raw Text
    parsed_data = parse_order_text(clean_body)
    extracted_name = parsed_data.get("customer_name")
    
    # 3. Match / Recognize Customer Account (Scoped to Tenant)
    customer = match_or_create_customer(db, phone=From, extracted_name=extracted_name, business_id=b_id)
    
    # 4. Master Order Intelligence Layer (Memory, Jargon, Anomaly, Duplicate, Cutoff)
    intel = process_order_intelligence(
        db=db,
        business=business,
        customer=customer,
        raw_text=clean_body,
        parsed_items=parsed_data.get("items", []),
        channel=Channel
    )
    
    # Check if FAQ Inquiry (No Order Needed)
    if intel.get("is_inquiry"):
        twiml_response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>{intel['ai_clarification']}</Message>
</Response>"""
        return Response(content=twiml_response, media_type="application/xml")
    
    # 5. Determine Human Workflow Status based on Confidence & Safety Rule:
    # High Confidence + No Anomaly -> "AI Processed" (Eligible for auto production)
    # Low Confidence / Anomaly / Duplicate -> "Needs Review" (NEVER silently approve)
    if intel["is_anomaly"] or intel["is_duplicate"] or intel["confidence_score"] < 80:
        initial_status = "Needs Review"
    else:
        initial_status = "AI Processed"
        
    summary_text = f"AI Extracted {len(intel['items'])} line items with {intel['confidence_score']}% confidence."
    if intel["is_anomaly"]:
        summary_text += f" [FLAGGED: {intel['anomaly_reason']}]"
    if intel["history_cloned"]:
        summary_text += f" [{intel['history_note']}]"
        
    # 6. Save Order
    new_order = models.Order(
        business_id=b_id,
        customer_id=customer.id,
        customer_phone=From,
        customer_name=customer.business_name,
        channel=Channel,
        raw_message=clean_body,
        status=initial_status,
        confirmation_status="Pending Confirmation",
        confidence_score=intel["confidence_score"],
        delivery_date="Tomorrow (4:30 AM)",
        is_anomaly=intel["is_anomaly"],
        anomaly_reason=intel["anomaly_reason"],
        is_duplicate=intel["is_duplicate"],
        duplicate_of_id=intel["duplicate_of_id"],
        history_cloned=intel["history_cloned"],
        history_note=intel["history_note"],
        ai_agent_clarification=intel["ai_clarification"],
        ai_interpretation_summary=summary_text,
        created_at=datetime.utcnow()
    )
    db.add(new_order)
    db.commit()
    db.refresh(new_order)
    
    # 7. Save Line Items (Apply Customer Pricing Tier)
    order_total = 0.0
    discount = customer.discount_percentage if customer else 0.0
    
    for item in intel["items"]:
        unit_price = item["unit_price"]
        cust_price = unit_price * (1 - (discount / 100))
        line_total = cust_price * item["quantity"]
        order_total += line_total
        
        db.add(models.OrderItem(
            order_id=new_order.id,
            product_id=item["product_id"],
            matched_sku=item["matched_sku"],
            item_name=item["item_name"],
            quantity=item["quantity"],
            unit_price=unit_price,
            customer_price=cust_price,
            line_total=line_total,
            match_confidence=item["match_confidence"]
        ))
    db.commit()
    
    # 8. Record Initial Audit Trail Events
    db.add_all([
        models.OrderTimelineEvent(
            order_id=new_order.id,
            event_type="Message Received",
            actor=f"Customer via {Channel}",
            description=f"Inbound {Channel} received from {From}",
            created_at=new_order.created_at
        ),
        models.OrderTimelineEvent(
            order_id=new_order.id,
            event_type="Customer Identified",
            actor="OrderStream AI",
            description=f"Customer matched as '{customer.business_name}' ({customer.account_number}). Applied pricing tier: {customer.pricing_tier}.",
            created_at=new_order.created_at
        ),
        models.OrderTimelineEvent(
            order_id=new_order.id,
            event_type="AI Interpretation",
            actor="OrderStream AI",
            description=summary_text,
            created_at=new_order.created_at
        )
    ])
    if intel["is_anomaly"]:
        db.add(models.OrderTimelineEvent(
            order_id=new_order.id,
            event_type="Anomaly Intercepted",
            actor="OrderStream AI",
            description=f"Flagged for human operator review: {intel['anomaly_reason']}",
            created_at=new_order.created_at
        ))
    db.commit()
    
    # 9. Two-Way Confirmation SMS or Autonomous Clarification Question
    if intel["ai_clarification"]:
        reply_msg = intel["ai_clarification"]
    elif intel["is_duplicate"]:
        reply_msg = f"OrderStream: ⚠️ Notice: We noticed a recent duplicate order #{intel['duplicate_of_id']}. Please reply YES if you meant to double this order."
    elif intel["is_anomaly"]:
        reply_msg = f"OrderStream: ⚠️ Received unusually large order ({sum(i['quantity'] for i in intel['items'])} units). Reply YES to confirm or text changes."
    else:
        reply_msg = generate_confirmation_sms(
            customer_name=customer.business_name,
            items=intel["items"],
            total_amount=order_total
        )
        
    twiml_response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>{reply_msg}</Message>
</Response>"""

    return Response(content=twiml_response, media_type="application/xml")
