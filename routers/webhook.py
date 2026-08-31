from fastapi import APIRouter, Depends, Form, Request, Response
from sqlalchemy.orm import Session
from database import get_db
import models
from services.llm_parser import parse_order_text

router = APIRouter()

@router.post("/twilio")
async def twilio_webhook(
    request: Request,
    From: str = Form(...),
    Body: str = Form(...),
    db: Session = Depends(get_db)
):
    """
    Receives SMS from Twilio webhook.
    """
    # 1. Parse order using LLM
    parsed_data = parse_order_text(Body)
    
    # 2. Save order
    new_order = models.Order(
        customer_phone=From,
        customer_name=parsed_data.get("customer_name"),
        raw_message=Body,
        status=parsed_data.get("status", "Needs Review")
    )
    db.add(new_order)
    db.commit()
    db.refresh(new_order)
    
    # 3. Save items
    for item in parsed_data.get("items", []):
        new_item = models.OrderItem(
            order_id=new_order.id,
            item_name=item["item_name"],
            quantity=item["quantity"]
        )
        db.add(new_item)
        
    db.commit()
    
    # Twilio requires TwiML response
    return Response(content='<?xml version="1.0" encoding="UTF-8"?><Response></Response>', media_type="application/xml")
