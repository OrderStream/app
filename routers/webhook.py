from fastapi import APIRouter, Depends, Form, Request, Response
from sqlalchemy.orm import Session
from database import get_db
import models
from services.llm_parser import parse_order_text
from services.matcher import match_or_create_customer, match_product_sku, generate_confirmation_sms

router = APIRouter()

@router.post("/twilio")
async def twilio_webhook(
    request: Request,
    From: str = Form(...),
    Body: str = Form(...),
    db: Session = Depends(get_db)
):
    """
    Receives SMS from Twilio, matches Customer & Catalog SKUs, handles 2-Way SMS Confirmation.
    """
    clean_body = Body.strip()
    
    # 1. Handle Confirmation Reply ("YES", "CONFIRM", "OK")
    if clean_body.upper() in ["YES", "CONFIRM", "OK", "Y", "YEP", "CORRECT"]:
        recent_order = db.query(models.Order).filter(
            models.Order.customer_phone == From
        ).order_by(models.Order.id.desc()).first()
        
        if recent_order:
            recent_order.confirmation_status = "Confirmed via SMS"
            recent_order.status = "Ready"
            db.commit()
            
            twiml_reply = (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<Response><Message>OrderStream: Your order is CONFIRMED for tomorrow morning\'s bake! 🥖</Message></Response>'
            )
            return Response(content=twiml_reply, media_type="application/xml")

    # 2. Parse Incoming Order Text
    parsed_data = parse_order_text(clean_body)
    extracted_name = parsed_data.get("customer_name")
    
    # 3. Match / Recognize Customer Account
    customer = match_or_create_customer(db, phone=From, extracted_name=extracted_name)
    
    # 4. Catalog Matching & SKU Resolution
    total_confidence = 100
    matched_items_list = []
    order_total = 0.0
    
    for item in parsed_data.get("items", []):
        raw_name = item.get("item_name", "Unknown Item")
        quantity = item.get("quantity", 1)
        
        matched_prod, confidence = match_product_sku(db, raw_name)
        
        sku = matched_prod.sku if matched_prod else "MISC-001"
        final_item_name = matched_prod.name if matched_prod else raw_name
        unit_price = matched_prod.unit_price if matched_prod else 0.0
        line_total = unit_price * quantity
        order_total += line_total
        
        if confidence < total_confidence:
            total_confidence = confidence
            
        matched_items_list.append({
            "product_id": matched_prod.id if matched_prod else None,
            "matched_sku": sku,
            "item_name": final_item_name,
            "quantity": quantity,
            "unit_price": unit_price,
            "line_total": line_total
        })

    # Overall Order Status & Confidence
    overall_status = "Ready" if total_confidence >= 80 else "Needs Review"
    
    # 5. Save Order
    new_order = models.Order(
        customer_id=customer.id,
        customer_phone=From,
        customer_name=customer.business_name,
        raw_message=clean_body,
        status=overall_status,
        confirmation_status="Pending Confirmation",
        confidence_score=total_confidence,
        delivery_date="Tomorrow (5:00 AM)"
    )
    db.add(new_order)
    db.commit()
    db.refresh(new_order)
    
    # 6. Save Order Items with SKUs
    for m_item in matched_items_list:
        new_item = models.OrderItem(
            order_id=new_order.id,
            product_id=m_item["product_id"],
            matched_sku=m_item["matched_sku"],
            item_name=m_item["item_name"],
            quantity=m_item["quantity"],
            unit_price=m_item["unit_price"],
            line_total=m_item["line_total"]
        )
        db.add(new_item)
        
    db.commit()
    
    # 7. Generate Two-Way Confirmation SMS for Twilio Response
    confirmation_msg = generate_confirmation_sms(
        customer_name=customer.business_name,
        items=matched_items_list,
        total_amount=order_total
    )
    
    twiml_response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>{confirmation_msg}</Message>
</Response>"""

    return Response(content=twiml_response, media_type="application/xml")
