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

class ProductCreateRequest(BaseModel):
    sku: str
    name: str
    category: str = "Bakery"
    unit: str = "Each"
    unit_price: float
    stock_available: int = 100
    aliases: str = ""

class BrainUpdateRequest(BaseModel):
    order_cutoff_time: str
    minimum_order_amount: float
    business_faq: str

class OrderItemEditRequest(BaseModel):
    quantity: int
    item_name: str
    unit_price: float

@router.get("/")
def get_all_orders(channel: str = None, db: Session = Depends(get_db)):
    """Returns full multi-channel order feed."""
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
            "created_at": o.created_at.strftime("%Y-%m-%d %H:%M"),
            "items": items_data
        })
    return results

@router.get("/business/brain")
def get_business_brain(db: Session = Depends(get_db)):
    """Returns Business Brain configuration."""
    b = db.query(models.BusinessTenant).first()
    if not b:
        return {
            "name": "Bakehouse 24",
            "order_cutoff_time": "23:00",
            "minimum_order_amount": 35.0,
            "business_faq": "Cutoff 11 PM. Min order $35."
        }
    return {
        "id": b.id,
        "name": b.name,
        "assigned_inbound_number": b.assigned_inbound_number,
        "order_cutoff_time": b.order_cutoff_time,
        "minimum_order_amount": b.minimum_order_amount,
        "business_faq": b.business_faq
    }

@router.post("/business/brain")
def update_business_brain(req: BrainUpdateRequest, db: Session = Depends(get_db)):
    """Updates Business Brain policies & cutoff rules."""
    b = db.query(models.BusinessTenant).first()
    if b:
        b.order_cutoff_time = req.order_cutoff_time
        b.minimum_order_amount = req.minimum_order_amount
        b.business_faq = req.business_faq
        db.commit()
    return {"message": "Business Brain updated successfully"}

@router.post("/products")
def add_product_to_catalog(req: ProductCreateRequest, db: Session = Depends(get_db)):
    """Owner can add new products & SKUs."""
    b = db.query(models.BusinessTenant).first()
    b_id = b.id if b else 1
    new_prod = models.ProductCatalog(
        business_id=b_id,
        sku=req.sku,
        name=req.name,
        category=req.category,
        unit=req.unit,
        unit_price=req.unit_price,
        stock_available=req.stock_available,
        aliases=req.aliases
    )
    db.add(new_prod)
    db.commit()
    return {"message": f"Product {req.name} ({req.sku}) added."}

@router.delete("/products/{prod_id}")
def delete_product_from_catalog(prod_id: int, db: Session = Depends(get_db)):
    """Owner can delete products."""
    prod = db.query(models.ProductCatalog).filter(models.ProductCatalog.id == prod_id).first()
    if prod:
        db.delete(prod)
        db.commit()
    return {"message": "Product deleted"}

@router.post("/{order_id}/items/{item_id}")
def edit_order_item(order_id: int, item_id: int, req: OrderItemEditRequest, db: Session = Depends(get_db)):
    """Owner can override and edit quantities directly."""
    item = db.query(models.OrderItem).filter(models.OrderItem.id == item_id).first()
    if item:
        item.quantity = req.quantity
        item.item_name = req.item_name
        item.unit_price = req.unit_price
        item.line_total = req.quantity * req.unit_price
        db.commit()
    return {"message": "Item updated"}

@router.delete("/{order_id}/items/{item_id}")
def remove_order_item(order_id: int, item_id: int, db: Session = Depends(get_db)):
    """Owner can remove an item from an order."""
    item = db.query(models.OrderItem).filter(models.OrderItem.id == item_id).first()
    if item:
        db.delete(item)
        db.commit()
    return {"message": "Item removed"}

@router.post("/copilot")
def copilot_endpoint(req: CopilotRequest, db: Session = Depends(get_db)):
    answer = run_copilot_query(db, req.query)
    return {"answer": answer}

@router.post("/correct-item")
def correct_item_learning(req: CorrectionRequest, db: Session = Depends(get_db)):
    record_human_correction_learning(
        db=db,
        customer_id=req.customer_id,
        original_phrase=req.original_phrase,
        corrected_sku=req.corrected_sku
    )
    return {"message": f"Successfully mapped '{req.original_phrase}' to SKU {req.corrected_sku}."}

@router.get("/kitchen-sheet")
def get_kitchen_production_sheet(db: Session = Depends(get_db)):
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
    order.confirmation_status = "Staff Approved"
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
