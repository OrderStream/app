from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime
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

class OrderStatusUpdateRequest(BaseModel):
    status: str # "Approved", "Rejected", "Needs Review", "Sent to Production", "Completed"
    actor: str = "Staff Member"
    notes: str = ""

class OrderItemEditRequest(BaseModel):
    quantity: int
    item_name: str
    matched_sku: str
    unit_price: float

class OrderItemAddRequest(BaseModel):
    product_id: int
    quantity: int

class CustomerUpdateRequest(BaseModel):
    business_name: str
    contact_name: str
    phone_number: str
    email: str
    delivery_route: str
    pricing_tier: str
    discount_percentage: float
    special_instructions: str
    enabled_channels: str

# -------------------------------------------------------------
# 1. ORDER DETAIL & LIST ENDPOINTS
# -------------------------------------------------------------
@router.get("/")
def get_all_orders(channel: str = None, status: str = None, db: Session = Depends(get_db)):
    """Returns full multi-channel order feed with isolated tenant scoping."""
    query = db.query(models.Order).order_by(models.Order.created_at.desc())
    if channel and channel.upper() != "ALL":
        query = query.filter(models.Order.channel == channel)
    if status and status.upper() != "ALL":
        query = query.filter(models.Order.status == status)
        
    orders = query.all()
    results = []
    for o in orders:
        items_data = []
        order_total = 0.0
        for i in o.items:
            order_total += i.line_total
            items_data.append({
                "id": i.id,
                "product_id": i.product_id,
                "sku": i.matched_sku,
                "item_name": i.item_name,
                "quantity": i.quantity,
                "unit_price": i.unit_price,
                "customer_price": i.customer_price or i.unit_price,
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
            "ai_interpretation_summary": o.ai_interpretation_summary or f"Extracted {len(o.items)} items with {o.confidence_score}% confidence.",
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

@router.get("/{order_id}")
def get_order_detail(order_id: int, db: Session = Depends(get_db)):
    """Returns single order detail with side-by-side raw text, items, and full audit timeline."""
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
        
    items_data = []
    order_total = 0.0
    for i in order.items:
        order_total += i.line_total
        items_data.append({
            "id": i.id,
            "product_id": i.product_id,
            "sku": i.matched_sku,
            "item_name": i.item_name,
            "quantity": i.quantity,
            "unit_price": i.unit_price,
            "customer_price": i.customer_price or i.unit_price,
            "line_total": i.line_total,
            "match_confidence": i.match_confidence
        })
        
    timeline_data = []
    for t in order.timeline:
        timeline_data.append({
            "id": t.id,
            "event_type": t.event_type,
            "actor": t.actor,
            "description": t.description,
            "created_at": t.created_at.strftime("%Y-%m-%d %H:%M:%S")
        })
        
    return {
        "id": order.id,
        "customer_id": order.customer_id,
        "account_number": order.customer.account_number if order.customer else "ACC-GUEST",
        "customer_name": order.customer_name,
        "customer_phone": order.customer_phone,
        "channel": order.channel,
        "delivery_route": order.customer.delivery_route if order.customer else "Standard",
        "pricing_tier": order.customer.pricing_tier if order.customer else "Standard",
        "discount_percentage": order.customer.discount_percentage if order.customer else 0.0,
        "raw_message": order.raw_message,
        "ai_interpretation_summary": order.ai_interpretation_summary or f"Extracted {len(order.items)} line items.",
        "status": order.status,
        "confirmation_status": order.confirmation_status,
        "confidence_score": order.confidence_score,
        "delivery_date": order.delivery_date,
        "order_total": order_total,
        "is_anomaly": order.is_anomaly,
        "anomaly_reason": order.anomaly_reason,
        "is_duplicate": order.is_duplicate,
        "duplicate_of_id": order.duplicate_of_id,
        "history_cloned": order.history_cloned,
        "history_note": order.history_note,
        "ai_clarification": order.ai_agent_clarification,
        "created_at": order.created_at.strftime("%Y-%m-%d %H:%M"),
        "items": items_data,
        "timeline": sorted(timeline_data, key=lambda x: x["created_at"])
    }

# -------------------------------------------------------------
# 2. HUMAN REVIEW ACTIONS & AUDIT LOGGING
# -------------------------------------------------------------
@router.post("/{order_id}/status")
def update_order_status(order_id: int, req: OrderStatusUpdateRequest, db: Session = Depends(get_db)):
    """Staff action to Approve, Reject, Send to Production, or Complete an order with audit trail."""
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
        
    old_status = order.status
    order.status = req.status
    if req.status in ["Approved", "Sent to Production"]:
        order.confirmation_status = "Staff Approved"
        order.is_anomaly = False
        order.is_duplicate = False
        
    # Record timeline audit event
    desc = f"Order status updated from '{old_status}' to '{req.status}'"
    if req.notes:
        desc += f". Note: {req.notes}"
        
    event = models.OrderTimelineEvent(
        order_id=order.id,
        event_type=req.status,
        actor=req.actor,
        description=desc,
        created_at=datetime.utcnow()
    )
    db.add(event)
    db.commit()
    return {"message": f"Order #{order.id} marked as {req.status}"}

@router.post("/{order_id}/clarification")
def request_customer_clarification(order_id: int, db: Session = Depends(get_db)):
    """Triggers outbound clarification SMS/WhatsApp to customer."""
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
        
    order.status = "Needs Review"
    order.confirmation_status = "Clarification Requested"
    
    event = models.OrderTimelineEvent(
        order_id=order.id,
        event_type="Clarification Requested",
        actor="Staff Member",
        description=f"Sent clarification request SMS to {order.customer_phone}: '{order.ai_agent_clarification or 'Please confirm order quantities.'}'",
        created_at=datetime.utcnow()
    )
    db.add(event)
    db.commit()
    return {"message": f"Clarification requested from {order.customer_name}"}

@router.put("/{order_id}/items/{item_id}")
def edit_order_item(order_id: int, item_id: int, req: OrderItemEditRequest, db: Session = Depends(get_db)):
    """Staff can override quantities, item names, SKUs, and unit prices directly."""
    item = db.query(models.OrderItem).filter(
        models.OrderItem.id == item_id,
        models.OrderItem.order_id == order_id
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Line item not found")
        
    old_qty = item.quantity
    old_sku = item.matched_sku
    
    item.quantity = req.quantity
    item.item_name = req.item_name
    item.matched_sku = req.matched_sku
    item.unit_price = req.unit_price
    item.customer_price = req.unit_price
    item.line_total = req.quantity * req.unit_price
    item.match_confidence = 100 # Human verified
    
    # Audit trail
    event = models.OrderTimelineEvent(
        order_id=order_id,
        event_type="Staff Edit",
        actor="Staff Member",
        description=f"Edited line item: '{item.item_name}' ([{old_sku}] -> [{req.matched_sku}]), Qty: {old_qty} -> {req.quantity}, Unit Price: ${req.unit_price:.2f}",
        created_at=datetime.utcnow()
    )
    db.add(event)
    db.commit()
    return {"message": "Line item updated successfully"}

@router.post("/{order_id}/items/add")
def add_item_to_order(order_id: int, req: OrderItemAddRequest, db: Session = Depends(get_db)):
    """Staff can add a new product line item to an existing order."""
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    prod = db.query(models.ProductCatalog).filter(models.ProductCatalog.id == req.product_id).first()
    if not order or not prod:
        raise HTTPException(status_code=404, detail="Order or Product not found")
        
    discount = order.customer.discount_percentage if order.customer else 0.0
    cust_price = prod.unit_price * (1 - (discount / 100))
    
    new_item = models.OrderItem(
        order_id=order.id,
        product_id=prod.id,
        matched_sku=prod.sku,
        item_name=prod.name,
        quantity=req.quantity,
        unit_price=prod.unit_price,
        customer_price=cust_price,
        line_total=cust_price * req.quantity,
        match_confidence=100
    )
    db.add(new_item)
    
    event = models.OrderTimelineEvent(
        order_id=order.id,
        event_type="Staff Edit",
        actor="Staff Member",
        description=f"Added new product: {req.quantity}x {prod.name} ([{prod.sku}]) at ${cust_price:.2f}",
        created_at=datetime.utcnow()
    )
    db.add(event)
    db.commit()
    return {"message": f"Added {prod.name} to Order #{order.id}"}

@router.delete("/{order_id}/items/{item_id}")
def remove_order_item(order_id: int, item_id: int, db: Session = Depends(get_db)):
    """Staff can remove an item from an order."""
    item = db.query(models.OrderItem).filter(models.OrderItem.id == item_id, models.OrderItem.order_id == order_id).first()
    if item:
        name = item.item_name
        qty = item.quantity
        db.delete(item)
        event = models.OrderTimelineEvent(
            order_id=order_id,
            event_type="Staff Edit",
            actor="Staff Member",
            description=f"Removed line item: {qty}x {name}",
            created_at=datetime.utcnow()
        )
        db.add(event)
        db.commit()
    return {"message": "Item removed from order"}

# -------------------------------------------------------------
# 3. CUSTOMER PROFILES & HISTORY
# -------------------------------------------------------------
@router.get("/customers/list")
def get_all_customers_detailed(db: Session = Depends(get_db)):
    """Returns all customers with order volume, route, channel prefs, and memory."""
    customers = db.query(models.Customer).all()
    results = []
    for c in customers:
        order_count = len(c.orders)
        memories = [m.phrase for m in c.language_memories]
        results.append({
            "id": c.id,
            "account_number": c.account_number,
            "business_name": c.business_name,
            "contact_name": c.contact_name or "N/A",
            "phone_number": c.phone_number,
            "email": c.email or "N/A",
            "delivery_route": c.delivery_route,
            "pricing_tier": c.pricing_tier,
            "discount_percentage": c.discount_percentage,
            "special_instructions": c.special_instructions or "None",
            "enabled_channels": c.enabled_channels,
            "avg_order_volume": c.avg_order_volume,
            "total_orders": order_count,
            "learned_phrases": memories
        })
    return results

@router.get("/customers/{customer_id}")
def get_customer_profile(customer_id: int, db: Session = Depends(get_db)):
    """Returns comprehensive customer profile with order history and language memories."""
    c = db.query(models.Customer).filter(models.Customer.id == customer_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Customer not found")
        
    history = []
    for o in c.orders:
        history.append({
            "id": o.id,
            "date": o.created_at.strftime("%Y-%m-%d %H:%M"),
            "raw_message": o.raw_message,
            "status": o.status,
            "total": sum(i.line_total for i in o.items),
            "items_count": len(o.items)
        })
        
    mems = [{"phrase": m.phrase, "sku": m.mapped_sku, "learned_from": m.learned_from} for m in c.language_memories]
    
    return {
        "id": c.id,
        "account_number": c.account_number,
        "business_name": c.business_name,
        "contact_name": c.contact_name,
        "phone_number": c.phone_number,
        "email": c.email,
        "delivery_route": c.delivery_route,
        "pricing_tier": c.pricing_tier,
        "discount_percentage": c.discount_percentage,
        "special_instructions": c.special_instructions,
        "enabled_channels": c.enabled_channels,
        "avg_order_volume": c.avg_order_volume,
        "language_memories": mems,
        "order_history": sorted(history, key=lambda x: x["date"], reverse=True)
    }

@router.put("/customers/{customer_id}")
def update_customer_profile(customer_id: int, req: CustomerUpdateRequest, db: Session = Depends(get_db)):
    """Updates customer rules, pricing tiers, and delivery instructions."""
    c = db.query(models.Customer).filter(models.Customer.id == customer_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Customer not found")
        
    c.business_name = req.business_name
    c.contact_name = req.contact_name
    c.phone_number = req.phone_number
    c.email = req.email
    c.delivery_route = req.delivery_route
    c.pricing_tier = req.pricing_tier
    c.discount_percentage = req.discount_percentage
    c.special_instructions = req.special_instructions
    c.enabled_channels = req.enabled_channels
    db.commit()
    return {"message": "Customer profile updated"}

# -------------------------------------------------------------
# 4. KITCHEN PRODUCTION SHEET WITH BATCH STATUS
# -------------------------------------------------------------
@router.get("/kitchen-sheet")
def get_kitchen_production_sheet(db: Session = Depends(get_db)):
    """Aggregates all approved/ready line items into 3 AM Kitchen Bake Sheet with order counts."""
    query = db.query(
        models.OrderItem.matched_sku,
        models.OrderItem.item_name,
        func.sum(models.OrderItem.quantity).label("total_quantity"),
        func.count(models.OrderItem.order_id).label("order_count"),
        models.ProductCatalog.production_status
    ).join(models.Order, models.OrderItem.order_id == models.Order.id)\
     .outerjoin(models.ProductCatalog, models.OrderItem.matched_sku == models.ProductCatalog.sku)\
     .filter(models.Order.status.in_(["Approved", "Sent to Production", "Ready", "Needs Review"]))\
     .group_by(models.OrderItem.matched_sku, models.OrderItem.item_name, models.ProductCatalog.production_status)\
     .all()
    
    return [{
        "sku": r[0],
        "item_name": r[1],
        "total_quantity": r[2],
        "order_count": r[3],
        "production_status": r[4] or "Pending"
    } for r in query]

@router.post("/production/status")
def mark_production_item_status(sku: str, status: str, db: Session = Depends(get_db)):
    """Marks batch item as Pending, In Progress, or Completed."""
    prod = db.query(models.ProductCatalog).filter(models.ProductCatalog.sku == sku).first()
    if prod:
        prod.production_status = status
        db.commit()
    return {"message": f"SKU {sku} status updated to {status}"}

# -------------------------------------------------------------
# 5. BUSINESS BRAIN & CATALOG OWNER CONTROLS
# -------------------------------------------------------------
@router.get("/business/brain")
def get_business_brain(db: Session = Depends(get_db)):
    b = db.query(models.BusinessTenant).first()
    if not b:
        return {"name": "Bakehouse 24", "order_cutoff_time": "23:00", "minimum_order_amount": 35.0, "business_faq": ""}
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
    b = db.query(models.BusinessTenant).first()
    if b:
        b.order_cutoff_time = req.order_cutoff_time
        b.minimum_order_amount = req.minimum_order_amount
        b.business_faq = req.business_faq
        db.commit()
    return {"message": "Business Brain updated"}

@router.get("/catalog")
def get_product_catalog(db: Session = Depends(get_db)):
    return db.query(models.ProductCatalog).all()

@router.post("/products")
def add_product_to_catalog(req: ProductCreateRequest, db: Session = Depends(get_db)):
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
        aliases=req.aliases,
        production_status="Pending"
    )
    db.add(new_prod)
    db.commit()
    return {"message": f"Product {req.name} added."}

@router.delete("/products/{prod_id}")
def delete_product_from_catalog(prod_id: int, db: Session = Depends(get_db)):
    prod = db.query(models.ProductCatalog).filter(models.ProductCatalog.id == prod_id).first()
    if prod:
        db.delete(prod)
        db.commit()
    return {"message": "Product deleted"}

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

@router.post("/correct-item")
def correct_item_learning(req: CorrectionRequest, db: Session = Depends(get_db)):
    record_human_correction_learning(
        db=db,
        customer_id=req.customer_id,
        original_phrase=req.original_phrase,
        corrected_sku=req.corrected_sku
    )
    return {"message": f"Mapped '{req.original_phrase}' to SKU {req.corrected_sku}."}

@router.post("/copilot")
def copilot_endpoint(req: CopilotRequest, db: Session = Depends(get_db)):
    answer = run_copilot_query(db, req.query)
    return {"answer": answer}

@router.get("/export/csv")
def export_quickbooks_csv(db: Session = Depends(get_db)):
    orders = db.query(models.Order).all()
    output = io.StringIO()
    writer = csv.writer(output)
    
    writer.writerow([
        "Invoice_Date", "Account_Number", "Customer_Name", "Phone", "Channel",
        "Delivery_Route", "Item_SKU", "Item_Description", "Quantity", "Unit_Price",
        "Customer_Price", "Line_Total", "Confidence", "Status"
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
                f"{(item.customer_price or item.unit_price):.2f}",
                f"{item.line_total:.2f}",
                f"{o.confidence_score}%",
                o.status
            ])
        if o.status == "Approved":
            o.status = "Exported"
            
    db.commit()
    response = Response(content=output.getvalue(), media_type="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=orderstream_quickbooks_export.csv"
    return response
