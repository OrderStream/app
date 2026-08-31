from fastapi import APIRouter, Depends, Form, Request, Response
from sqlalchemy.orm import Session
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
    Unified Ingestion Layer: Twilio SMS, WhatsApp & Multi-Channel with Full Order Intelligence.
    """
    clean_body = Body.strip()
    
    # 1. Handle Confirmation Reply ("YES", "CONFIRM", "OK")
    if clean_body.upper() in ["YES", "CONFIRM", "OK", "Y", "YEP", "CORRECT"]:
        recent_order = db.query(models.Order).filter(
            models.Order.customer_phone == From
        ).order_by(models.Order.id.desc()).first()
        
        if recent_order:
            recent_order.confirmation_status = "Confirmed via SMS"
            if not recent_order.is_anomaly and not recent_order.is_duplicate:
                recent_order.status = "Ready"
            db.commit()
            
            twiml_reply = (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<Response><Message>OrderStream: Your order is CONFIRMED for tomorrow morning\'s bake! 🥖</Message></Response>'
            )
            return Response(content=twiml_reply, media_type="application/xml")

    # 2. Parse Incoming Raw Text
    parsed_data = parse_order_text(clean_body)
    extracted_name = parsed_data.get("customer_name")
    
    # 3. Match / Recognize Customer Account
    customer = match_or_create_customer(db, phone=From, extracted_name=extracted_name)
    
    # 4. Master Order Intelligence Layer (Memory, Jargon, Anomaly, Duplicate)
    intel = process_order_intelligence(
        db=db,
        customer=customer,
        raw_text=clean_body,
        parsed_items=parsed_data.get("items", []),
        channel=Channel
    )
    
    # 5. Save Order
    new_order = models.Order(
        customer_id=customer.id,
        customer_phone=From,
        customer_name=customer.business_name,
        channel=Channel,
        raw_message=clean_body,
        status=intel["status"],
        confirmation_status="Pending Confirmation",
        confidence_score=intel["confidence_score"],
        delivery_date="Tomorrow (5:00 AM)",
        is_anomaly=intel["is_anomaly"],
        anomaly_reason=intel["anomaly_reason"],
        is_duplicate=intel["is_duplicate"],
        duplicate_of_id=intel["duplicate_of_id"],
        history_cloned=intel["history_cloned"],
        history_note=intel["history_note"],
        ai_agent_clarification=intel["ai_clarification"]
    )
    db.add(new_order)
    db.commit()
    db.refresh(new_order)
    
    # 6. Save Line Items
    order_total = 0.0
    for item in intel["items"]:
        order_total += item["line_total"]
        db.add(models.OrderItem(
            order_id=new_order.id,
            product_id=item["product_id"],
            matched_sku=item["matched_sku"],
            item_name=item["item_name"],
            quantity=item["quantity"],
            unit_price=item["unit_price"],
            line_total=item["line_total"],
            match_confidence=item["match_confidence"]
        ))
    db.commit()
    
    # 7. Generate Two-Way Confirmation SMS or Autonomous Clarification Question
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
