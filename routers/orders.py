from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import get_db
import models
from services.intelligence import run_copilot_query, record_human_correction_learning
import csv
import io

router = APIRouter()

class CopilotRequest(BaseModel):
    query: str

class CorrectionRequest(BaseModel):
    order_id: int
    customer_id: int
    original_phrase: str
    corrected_sku: str

@router.get("/")
def get_all_orders(channel: str = None, db: Session = Depends(get_db)):
    """
    Returns full order feed with multi-channel tags, intelligence flags, and SKU line items.
    """
    query = db.query(models.Order).order_by(models.Order.created_at.desc())
    if channel and channel.upper() != "ALL":
        query = query.filter(models.Order.channel == channel)
        
    orders = query.all()
    results = []
    for o in orders:
        items_data = []
        order_total = 0.0
        for i in o.items:
            order_total += i.line_total
            items_data.append({
                "id": i.id,
                "sku": i.matched_sku,
                "item_name": i.item_name,
                "quantity": i.quantity,
                "unit_price": i.unit_price,
                "line_total": i.line_total,
                "match_confidence": i.match_confidence
            })
            
        results.append({
            "id": o.id,
            "account_number": o.customer.account_number if o.customer else "ACC-GUEST",
            "customer_id": o.customer_id,
            "customer_name": o.customer_name,
            "customer_phone": o.customer_phone,
            "channel": o.channel,
            "delivery_route": o.customer.delivery_route if o.customer else "Standard",
            "raw_message": o.raw_message,
            "status": o.status,
            "confirmation_status": o.confirmation_status,
            "confidence_score": o.confidence_score,
            "delivery_date": o.delivery_date,
            "order_total": order_total,
            "is_anomaly": o.is_anomaly,
            "anomaly_reason": o.anomaly_reason,
            "is_duplicate": o.is_duplicate,
            "duplicate_of_id": o.duplicate_of_id,
            "history_cloned": o.history_cloned,
            "history_note": o.history_note,
            "ai_clarification": o.ai_agent_clarification,
            "created_at": o.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "items": items_data
        })
    return results

@router.post("/copilot")
def copilot_endpoint(req: CopilotRequest, db: Session = Depends(get_db)):
    """OrderStream Copilot AI assistant endpoint."""
    answer = run_copilot_query(db, req.query)
    return {"answer": answer}

@router.post("/correct-item")
def correct_item_learning(req: CorrectionRequest, db: Session = Depends(get_db)):
    """Human-in-the-loop correction: learns customer language memory."""
    record_human_correction_learning(
        db=db,
        customer_id=req.customer_id,
        original_phrase=req.original_phrase,
        corrected_sku=req.corrected_sku
    )
    return {"message": f"Successfully mapped '{req.original_phrase}' to SKU {req.corrected_sku} for this customer."}

@router.get("/kitchen-sheet")
def get_kitchen_production_sheet(db: Session = Depends(get_db)):
    """Aggregates all line items into a single 3 AM Kitchen Bake Batch Sheet."""
    query = db.query(
        models.OrderItem.matched_sku,
        models.OrderItem.item_name,
        func.sum(models.OrderItem.quantity).label("total_quantity")
    ).join(models.Order).filter(
        models.Order.status.in_(["Ready", "Exported", "Needs Review"])
    ).group_by(
        models.OrderItem.matched_sku,
        models.OrderItem.item_name
    ).all()
    
    return [{"sku": r[0], "item_name": r[1], "total_quantity": r[2]} for r in query]

@router.get("/catalog")
def get_product_catalog(db: Session = Depends(get_db)):
    return db.query(models.ProductCatalog).all()

@router.get("/customers")
def get_customers(db: Session = Depends(get_db)):
    return db.query(models.Customer).all()

@router.get("/memories")
def get_language_memories(db: Session = Depends(get_db)):
    """Returns all learned customer-specific aliases and nicknames."""
    mems = db.query(models.CustomerLanguageMemory).all()
    return [{
        "id": m.id,
        "customer_name": m.customer.business_name if m.customer else "Unknown",
        "phrase": m.phrase,
        "mapped_sku": m.mapped_sku,
        "learned_from": m.learned_from,
        "created_at": m.created_at.strftime("%Y-%m-%d")
    } for m in mems]

@router.post("/{order_id}/confirm")
def manual_confirm_order(order_id: int, db: Session = Depends(get_db)):
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    order.confirmation_status = "Manual Approved"
    order.status = "Ready"
    order.is_anomaly = False
    order.is_duplicate = False
    db.commit()
    return {"message": "Order approved"}

@router.get("/export/csv")
def export_quickbooks_csv(db: Session = Depends(get_db)):
    orders = db.query(models.Order).all()
    output = io.StringIO()
    writer = csv.writer(output)
    
    writer.writerow([
        "Invoice_Date", "Account_Number", "Customer_Name", "Phone", "Channel",
        "Delivery_Route", "Item_SKU", "Item_Description", "Quantity", "Unit_Price",
        "Line_Total", "Confidence", "Status"
    ])
    
    for o in orders:
        acc = o.customer.account_number if o.customer else "ACC-UNKNOWN"
        route = o.customer.delivery_route if o.customer else "Standard"
        for item in o.items:
            writer.writerow([
                o.created_at.strftime("%Y-%m-%d"),
                acc,
                o.customer_name,
                o.customer_phone,
                o.channel,
                route,
                item.matched_sku,
                item.item_name,
                item.quantity,
                f"{item.unit_price:.2f}",
                f"{item.line_total:.2f}",
                f"{o.confidence_score}%",
                o.confirmation_status
            ])
        o.status = "Exported"
        
    db.commit()
    response = Response(content=output.getvalue(), media_type="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=orderstream_quickbooks_export.csv"
    return response
