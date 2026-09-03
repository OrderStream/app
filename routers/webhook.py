import os
import hmac
import hashlib
import base64
from fastapi import APIRouter, Depends, Form, Request, Response, Header, HTTPException, BackgroundTasks
from typing import Optional
from sqlalchemy.orm import Session
from datetime import datetime
from urllib.parse import urlparse

from database import get_db
import models
from services.llm_parser import parse_order_text
from services.matcher import match_or_create_customer, generate_confirmation_sms
from services.intelligence import process_order_intelligence

router = APIRouter()

@router.post("/twilio")
async def twilio_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    From: str = Form(...),
    Body: str = Form(...),
    To: Optional[str] = Form(None),
    MessageSid: Optional[str] = Form(None),
    Channel: str = Form(default="SMS"),
    x_twilio_signature: Optional[str] = Header(None, alias="X-Twilio-Signature"),
    db: Session = Depends(get_db)
):
    """
    Reliable Inbound Order Webhook Pipeline:
    1. Idempotency Check (MessageSid)
    2. Server-side Tenant Resolution (via 'To' recipient number)
    3. Customer Identity & Historical Context Recognition
    4. Business Intelligence & Anomaly Defense
    5. Human Review Workflow Assignment (Safe -> Approved / Uncertain -> Review)
    6. Audit Trail Recording
    7. Automated Two-Way Confirmation Response
    """
    # -------------------------------------------------------------
    # 0. TWILIO REQUEST VALIDATION
    # -------------------------------------------------------------
    # In production, TWILIO_AUTH_TOKEN must be set. If we are running tests, we may bypass it.
    twilio_auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
    is_test_env = os.environ.get("ORDERSTREAM_TEST_ENV") == "true"

    if not twilio_auth_token and not is_test_env:
        raise HTTPException(status_code=500, detail="Server configuration error: TWILIO_AUTH_TOKEN is not set.")

    if not is_test_env and x_twilio_signature:
        # Twilio sends form data, we need it ordered by key for validation
        form_data = await request.form()
        url = str(request.url)
        # Twilio validation requires HTTPS typically, ensure scheme matches if forwarded
        forwarded_proto = request.headers.get("x-forwarded-proto")
        if forwarded_proto:
            parsed = urlparse(url)
            url = parsed._replace(scheme=forwarded_proto).geturl()

        params = dict(form_data)
        sorted_keys = sorted(params.keys())
        data_to_sign = url
        for k in sorted_keys:
            data_to_sign += k + params[k]

        mac = hmac.new(twilio_auth_token.encode('utf-8'), data_to_sign.encode('utf-8'), hashlib.sha1)
        expected_sig = base64.b64encode(mac.digest()).decode('utf-8')

        if not hmac.compare_digest(expected_sig, x_twilio_signature):
            raise HTTPException(status_code=403, detail="Invalid Twilio Signature")

    clean_body = Body.strip()
    clean_from = From.strip()
    provider_msg_id = MessageSid.strip() if MessageSid else f"manual-{datetime.utcnow().timestamp()}"

    # -------------------------------------------------------------
    # 1. SERVER-SIDE TENANT RESOLUTION (Never trust arbitrary client data)
    # -------------------------------------------------------------
    business = None
    if To and To.strip():
        clean_to = To.strip()
        business = db.query(models.BusinessTenant).filter(models.BusinessTenant.assigned_inbound_number == clean_to).first()
        
    if not business:
        # Fallback to default primary tenant workspace
        business = db.query(models.BusinessTenant).order_by(models.BusinessTenant.id.asc()).first()
        
    if not business:
        twiml_error = '<?xml version="1.0" encoding="UTF-8"?><Response><Message>OrderStream: Kitchen workspace not found.</Message></Response>'
        return Response(content=twiml_error, media_type="application/xml")

    b_id = business.id

    # -------------------------------------------------------------
    # 2. IDEMPOTENCY CHECK (Prevents duplicate processing on provider retry)
    # -------------------------------------------------------------
    existing_event = db.query(models.InboundWebhookEvent).filter(
        models.InboundWebhookEvent.business_id == b_id,
        models.InboundWebhookEvent.provider_message_id == provider_msg_id
    ).first()

    if existing_event:
        # Provider retried event: acknowledge without re-creating order
        twiml_cached = '<?xml version="1.0" encoding="UTF-8"?><Response><Message>OrderStream: Order already received and in processing queue.</Message></Response>'
        return Response(content=twiml_cached, media_type="application/xml")

    # Record event in inbound audit table and catch race conditions
    try:
        webhook_event = models.InboundWebhookEvent(
            business_id=b_id,
            provider=f"twilio_{Channel.lower()}",
            provider_message_id=provider_msg_id,
            sender=clean_from,
            recipient=To,
            payload=clean_body,
            status="processing",
            received_at=datetime.utcnow()
        )
        db.add(webhook_event)
        db.commit()
    except Exception:
        db.rollback()
        twiml_cached = '<?xml version="1.0" encoding="UTF-8"?><Response><Message>OrderStream: Order already received and in processing queue.</Message></Response>'
        return Response(content=twiml_cached, media_type="application/xml")

    background_tasks.add_task(
        process_inbound_webhook_task,
        db=db,
        b_id=b_id,
        business=business,
        clean_body=clean_body,
        clean_from=clean_from,
        Channel=Channel,
        webhook_event_id=webhook_event.id
    )
    twiml_ack = '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'
    return Response(content=twiml_ack, media_type="application/xml")

def process_inbound_webhook_task(
    db: Session,
    b_id: int,
    business: models.BusinessTenant,
    clean_body: str,
    clean_from: str,
    Channel: str,
    webhook_event_id: int
):
    webhook_event = db.query(models.InboundWebhookEvent).filter(models.InboundWebhookEvent.id == webhook_event_id).first()

    try:
        # -------------------------------------------------------------
        # 3. HANDLE BUYER CONFIRMATION ("YES", "CONFIRM", "OK")
        # -------------------------------------------------------------
        if clean_body.upper() in ["YES", "CONFIRM", "OK", "Y", "YEP", "CORRECT"]:
            recent_order = db.query(models.Order).filter(
                models.Order.business_id == b_id,
                models.Order.customer_phone == clean_from
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
                webhook_event.status = "processed"
                db.commit()
                
                print(f"Async Task: Confirmed Order #{recent_order.id}")
                return

        # -------------------------------------------------------------
        # 4. PARSE INBOUND NATURAL LANGUAGE MESSAGE
        # -------------------------------------------------------------
        parsed_data = parse_order_text(clean_body)
        extracted_name = parsed_data.get("customer_name")
        
        # -------------------------------------------------------------
        # 5. RECOGNIZE CUSTOMER ACCOUNT (TENANT-SCOPED)
        # -------------------------------------------------------------
        customer = match_or_create_customer(db, phone=clean_from, extracted_name=extracted_name, business_id=b_id)
        
        # -------------------------------------------------------------
        # 6. ORDER INTELLIGENCE (PRICING, JARGON, ANOMALY, DUPLICATE)
        # -------------------------------------------------------------
        intel = process_order_intelligence(
            db=db,
            business=business,
            customer=customer,
            raw_text=clean_body,
            parsed_items=parsed_data.get("items", []),
            channel=Channel
        )
        
        # Check if Informational Inquiry / Policy Question (No Order Created)
        if intel.get("is_inquiry"):
            webhook_event.status = "processed"
            db.commit()
            print("Async Task: Handled informational inquiry.")
            return
        
        # -------------------------------------------------------------
        # 7. ASSIGN OPERATIONAL STATUS (SAFE -> APPROVED / UNCERTAIN -> REVIEW)
        # -------------------------------------------------------------
        if intel["is_anomaly"] or intel["is_duplicate"] or intel["confidence_score"] < 80:
            initial_status = "Needs Review"
        else:
            initial_status = "Approved"
            
        summary_text = f"OrderStream parsed {len(intel['items'])} items with {intel['confidence_score']}% match confidence."
        if intel["is_anomaly"]:
            summary_text += f" [REVIEW: {intel['anomaly_reason']}]"
        if intel["history_cloned"]:
            summary_text += f" [{intel['history_note']}]"
            
        # -------------------------------------------------------------
        # 8. PERSIST ORDER
        # -------------------------------------------------------------
        new_order = models.Order(
            business_id=b_id,
            customer_id=customer.id,
            customer_phone=clean_from,
            customer_name=customer.business_name,
            channel=Channel,
            raw_message=clean_body,
            status=initial_status,
            confirmation_status="Pending Confirmation",
            confidence_score=intel["confidence_score"],
            delivery_date="Tomorrow Morning",
            shift="Morning",
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
        
        # -------------------------------------------------------------
        # 9. SAVE LINE ITEMS (APPLY CUSTOMER PRICING TIER)
        # -------------------------------------------------------------
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
                completed_quantity=0,
                unit_price=unit_price,
                customer_price=cust_price,
                line_total=line_total,
                match_confidence=item["match_confidence"]
            ))
        db.commit()
        
        # -------------------------------------------------------------
        # 10. RECORD INITIAL AUDIT TRAIL
        # -------------------------------------------------------------
        db.add_all([
            models.OrderTimelineEvent(
                order_id=new_order.id,
                event_type="Message Received",
                actor=f"Customer via {Channel}",
                description=f"Inbound {Channel} order received from {clean_from}.",
                created_at=new_order.created_at
            ),
            models.OrderTimelineEvent(
                order_id=new_order.id,
                event_type="Customer Identified",
                actor="OrderStream",
                description=f"Customer recognized as '{customer.business_name}' ({customer.account_number}). Applied pricing tier: {customer.pricing_tier}.",
                created_at=new_order.created_at
            ),
            models.OrderTimelineEvent(
                order_id=new_order.id,
                event_type="Order Interpreted",
                actor="OrderStream",
                description=summary_text,
                created_at=new_order.created_at
            )
        ])
        if intel["is_anomaly"]:
            db.add(models.OrderTimelineEvent(
                order_id=new_order.id,
                event_type="Anomaly Intercepted",
                actor="OrderStream",
                description=f"Flagged for staff review: {intel['anomaly_reason']}",
                created_at=new_order.created_at
            ))
            
        webhook_event.status = "processed"
        db.commit()
        
        # -------------------------------------------------------------
        # 11. AUTOMATED TWO-WAY CONFIRMATION SMS
        # -------------------------------------------------------------
        # Phase 1 Backgrounding Note: Twilio response is now handled synchronously above via empty Response.
        # Ideally, we would use the Twilio REST API here to send `reply_msg` outbound.
        # For pilot constraints, since we no longer return TwiML directly, this log acknowledges completion.
        print("Async AI Task Completed. Outbound SMS would send here in production.")

    except Exception as e:
        webhook_event.status = "failed"
        webhook_event.error_message = str(e)

        # Phase 3: Create fallback order explicitly instead of dropping the payload if AI fails.
        customer = match_or_create_customer(db, phone=clean_from, extracted_name="Unknown (AI Failed)", business_id=b_id)

        fallback_order = models.Order(
            business_id=b_id,
            customer_id=customer.id,
            customer_phone=clean_from,
            customer_name=customer.business_name,
            channel=Channel,
            raw_message=clean_body,
            status="Needs Review",
            confirmation_status="Pending Confirmation",
            confidence_score=0,
            delivery_date="Tomorrow Morning",
            shift="Morning",
            is_anomaly=True,
            anomaly_reason="AI Parsing Failure - Manual Review Required",
            ai_interpretation_summary="System encountered an error during parsing. Please review manually.",
            created_at=datetime.utcnow()
        )
        db.add(fallback_order)
        db.commit()
        db.refresh(fallback_order)

        db.add(models.OrderTimelineEvent(
            order_id=fallback_order.id,
            event_type="Message Received (Fallback)",
            actor="System",
            description=f"Message caught by fallback handler due to AI failure: {str(e)}",
            created_at=fallback_order.created_at
        ))
        db.commit()
        print("Async Task: Logged AI failure fallback.")
