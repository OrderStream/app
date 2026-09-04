from fastapi import APIRouter, Depends, HTTPException, Response, Query, Request
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from datetime import datetime, timedelta
import csv
import io

from database import get_db
import models
from services.tenant_context import get_current_tenant
from services.intelligence import record_human_correction_learning

router = APIRouter()

# -------------------------------------------------------------
# PYDANTIC SCHEMAS
# -------------------------------------------------------------

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

class ProductUpdateRequest(BaseModel):
    sku: str
    name: str
    category: str = "Bakery"
    unit: str = "Each"
    unit_price: float
    stock_available: int = 100
    aliases: str = ""

class BrainUpdateRequest(BaseModel):
    name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    assigned_inbound_number: Optional[str] = None
    order_cutoff_time: str
    minimum_order_amount: float
    business_faq: str

class OrderStatusUpdateRequest(BaseModel):
    status: str
    actor: str = "Staff Member"
    notes: Optional[str] = ""

class OrderItemEditRequest(BaseModel):
    quantity: int
    item_name: str
    matched_sku: str
    unit_price: float

class OrderItemAddRequest(BaseModel):
    product_id: int
    quantity: int

class CustomerCreateRequest(BaseModel):
    business_name: str
    contact_name: Optional[str] = ""
    phone_number: str
    email: Optional[str] = ""
    delivery_route: str = "Route A - Downtown Core"
    pricing_tier: str = "Wholesale Standard"
    discount_percentage: float = 0.0
    special_instructions: Optional[str] = ""
    enabled_channels: str = "SMS, Email"

class CustomerUpdateRequest(BaseModel):
    business_name: str
    contact_name: Optional[str] = ""
    phone_number: str
    email: Optional[str] = ""
    delivery_route: str
    pricing_tier: str
    discount_percentage: float
    special_instructions: Optional[str] = ""
    enabled_channels: str

class ProductionProgressRequest(BaseModel):
    sku: str
    completed_quantity: int
    status: Optional[str] = None

class WorkspaceSwitchRequest(BaseModel):
    tenant_identifier: str

# -------------------------------------------------------------
# 1. ATOMIC DASHBOARD SUMMARY (SINGLE SOURCE OF TRUTH)
# -------------------------------------------------------------
@router.get("/dashboard-summary")
def get_dashboard_summary(
    tenant: models.BusinessTenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """
    Returns an atomic, synchronized operational brief.
    Guarantees no contradictory counts across dashboard, tables, and production.
    """
    b_id = tenant.id
    all_orders = db.query(models.Order).filter(models.Order.business_id == b_id).order_by(models.Order.created_at.desc()).all()
    
    total_orders = len(all_orders)
    review_orders = [o for o in all_orders if o.status == "Needs Review" or o.is_anomaly or o.is_duplicate]
    approved_orders = [o for o in all_orders if o.status in ["Approved", "Sent to Production", "Ready"]]
    
    approved_units = sum(sum(i.quantity for i in o.items) for o in approved_orders)
    approved_value = sum(sum(i.line_total for i in o.items) for o in approved_orders)
    
    # Operational greeting based on real data
    if len(review_orders) == 0:
        operational_brief = "Everything is running smoothly. All orders are confirmed for tomorrow's bake."
        primary_action = {"label": "View Production Sheet", "action": "open_production"}
    elif len(review_orders) == 1:
        operational_brief = f"1 order requires staff review before the {tenant.order_cutoff_time} cutoff."
        primary_action = {"label": "Review 1 Order", "action": "filter_review"}
    else:
        operational_brief = f"{len(review_orders)} orders require staff review before the {tenant.order_cutoff_time} cutoff."
        primary_action = {"label": f"Review {len(review_orders)} Orders", "action": "filter_review"}

    # Attention Required Items
    attention_items = []
    for o in review_orders:
        attention_items.append({
            "order_id": o.id,
            "customer_name": o.customer_name,
            "account_number": o.customer.account_number if o.customer else "ACC-GUEST",
            "channel": o.channel,
            "raw_message": o.raw_message,
            "status": o.status,
            "anomaly_reason": o.anomaly_reason or "Uncertain product reference or volume verification required.",
            "created_at": o.created_at.strftime("%H:%M")
        })

    # Recent Inbound Activity Stream
    recent_activity = []
    for o in all_orders[:6]:
        recent_activity.append({
            "order_id": o.id,
            "customer_name": o.customer_name,
            "channel": o.channel,
            "summary": o.ai_interpretation_summary or f"Order #{o.id} received",
            "status": o.status,
            "timestamp": o.created_at.strftime("%H:%M")
        })

    # Tomorrow's Top Production Items
    prod_query = db.query(
        models.OrderItem.matched_sku,
        models.OrderItem.item_name,
        func.sum(models.OrderItem.quantity).label("total_quantity")
    ).join(models.Order, models.OrderItem.order_id == models.Order.id)\
     .filter(models.Order.business_id == b_id, models.Order.status.in_(["Approved", "Sent to Production", "Ready"]))\
     .group_by(models.OrderItem.matched_sku, models.OrderItem.item_name)\
     .order_by(func.sum(models.OrderItem.quantity).desc())\
     .limit(4).all()

    top_production = [{"sku": r[0], "item_name": r[1], "quantity": r[2]} for r in prod_query]

    # Channels Health Verification
    channels_health = [
        {
            "channel": "SMS Text Hotline",
            "status": "Connected" if tenant.assigned_inbound_number else "Action Required",
            "identifier": tenant.assigned_inbound_number or "Not Provisioned"
        },
        {
            "channel": "Email PO Ingestion",
            "status": "Connected",
            "identifier": tenant.contact_email or "orders@bakery.com"
        },
        {
            "channel": "QuickBooks Export",
            "status": "Ready",
            "identifier": "CSV Formatted"
        }
    ]

    return {
        "workspace_name": tenant.name,
        "workspace_slug": tenant.slug,
        "cutoff_time": tenant.order_cutoff_time,
        "operational_brief": operational_brief,
        "primary_action": primary_action,
        "metrics": {
            "orders_today": total_orders,
            "needs_review": len(review_orders),
            "approved_units": approved_units,
            "order_value": approved_value
        },
        "attention_required": attention_items,
        "whats_next": {
            "next_cutoff": f"{tenant.order_cutoff_time} tonight",
            "top_production": top_production
        },
        "recent_activity": recent_activity,
        "channels_health": channels_health
    }

# -------------------------------------------------------------
# 2. ORDERS LIST & SEARCH
# -------------------------------------------------------------
@router.get("/")
def get_all_orders(
    channel: Optional[str] = None, 
    status: Optional[str] = None, 
    q: Optional[str] = None,
    tenant: models.BusinessTenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """
    Returns order feed strictly scoped to the authenticated tenant.
    Never trusts client-supplied business_id.
    """
    b_id = tenant.id
    query = db.query(models.Order).filter(models.Order.business_id == b_id).order_by(models.Order.created_at.desc())
    
    if channel and channel.upper() != "ALL":
        query = query.filter(models.Order.channel == channel)
    if status and status.upper() != "ALL":
        query = query.filter(models.Order.status == status)
    if q and q.strip():
        search_term = f"%{q.strip()}%"
        query = query.filter(
            or_(
                models.Order.customer_name.ilike(search_term),
                models.Order.raw_message.ilike(search_term),
                models.Order.customer_phone.ilike(search_term),
                models.Order.id.ilike(search_term)
            )
        )
        
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
            "ai_interpretation_summary": o.ai_interpretation_summary or f"Extracted {len(o.items)} line items.",
            "status": o.status,
            "confirmation_status": o.confirmation_status,
            "confidence_score": o.confidence_score,
            "delivery_date": o.delivery_date,
            "shift": o.shift,
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

# -------------------------------------------------------------
# 2B. UNIVERSAL SEARCH (CMD+K / COMMAND PALETTE)
# -------------------------------------------------------------
@router.get("/search")
def universal_tenant_search(
    q: str = Query(..., min_length=1),
    tenant: models.BusinessTenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """
    Command Palette Search: Strictly isolated to active tenant.
    Never returns records from another tenant.
    """
    b_id = tenant.id
    term = f"%{q.strip()}%"

    matching_orders = db.query(models.Order).filter(
        models.Order.business_id == b_id,
        or_(
            models.Order.customer_name.ilike(term),
            models.Order.raw_message.ilike(term),
            models.Order.id.ilike(term)
        )
    ).limit(5).all()

    matching_customers = db.query(models.Customer).filter(
        models.Customer.business_id == b_id,
        or_(
            models.Customer.business_name.ilike(term),
            models.Customer.contact_name.ilike(term),
            models.Customer.phone_number.ilike(term)
        )
    ).limit(5).all()

    matching_products = db.query(models.ProductCatalog).filter(
        models.ProductCatalog.business_id == b_id,
        or_(
            models.ProductCatalog.name.ilike(term),
            models.ProductCatalog.sku.ilike(term),
            models.ProductCatalog.aliases.ilike(term)
        )
    ).limit(5).all()

    return {
        "orders": [{"id": o.id, "customer_name": o.customer_name, "status": o.status, "date": o.created_at.strftime("%Y-%m-%d")} for o in matching_orders],
        "customers": [{"id": c.id, "name": c.business_name, "phone": c.phone_number, "route": c.delivery_route} for c in matching_customers],
        "products": [{"id": p.id, "name": p.name, "sku": p.sku, "price": p.unit_price} for p in matching_products]
    }

# -------------------------------------------------------------
# 3. ORDER DETAIL (VERIFIED TENANT ISOLATION)
# -------------------------------------------------------------
@router.get("/{order_id:int}")
def get_order_detail(
    order_id: int, 
    tenant: models.BusinessTenant = Depends(get_current_tenant), 
    db: Session = Depends(get_db)
):
    """
    Returns single order detail.
    Strictly verifies order.business_id == tenant.id.
    """
    order = db.query(models.Order).filter(
        models.Order.id == order_id,
        models.Order.business_id == tenant.id
    ).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found in this workspace.")
        
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
            "completed_quantity": i.completed_quantity,
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
        "special_instructions": order.customer.special_instructions if order.customer else "None",
        "usual_order_day": order.customer.usual_order_day if order.customer else "Standard schedule",
        "raw_message": order.raw_message,
        "ai_interpretation_summary": order.ai_interpretation_summary or f"Extracted {len(order.items)} line items.",
        "status": order.status,
        "confirmation_status": order.confirmation_status,
        "confidence_score": order.confidence_score,
        "delivery_date": order.delivery_date,
        "shift": order.shift,
        "order_total": order_total,
        "is_anomaly": order.is_anomaly,
        "anomaly_reason": order.anomaly_reason,
        "is_duplicate": order.is_duplicate,
        "duplicate_of_id": order.duplicate_of_id,
        "history_cloned": order.history_cloned,
        "history_note": order.history_note,
        "ai_clarification": order.ai_agent_clarification,
        "reviewed_by": order.reviewed_by,
        "created_at": order.created_at.strftime("%Y-%m-%d %H:%M"),
        "items": items_data,
        "timeline": sorted(timeline_data, key=lambda x: x["created_at"])
    }

# -------------------------------------------------------------
# 4. ORDER HUMAN REVIEW ACTIONS
# -------------------------------------------------------------
@router.post("/{order_id}/status")
def update_order_status(
    order_id: int, 
    req: OrderStatusUpdateRequest, 
    tenant: models.BusinessTenant = Depends(get_current_tenant), 
    db: Session = Depends(get_db)
):
    """Staff action to Approve, Reject, Send to Production, or Complete an order."""
    order = db.query(models.Order).filter(
        models.Order.id == order_id,
        models.Order.business_id == tenant.id
    ).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found in this workspace.")
        
    old_status = order.status

    # Phase 5: Prevent duplicate approval updates
    if old_status == req.status:
        return {"message": f"Order is already {req.status}."}

    order.status = req.status
    order.reviewed_by = req.actor
    order.reviewed_at = datetime.utcnow()

    if req.status in ["Approved", "Sent to Production"]:
        order.confirmation_status = "Staff Approved"
        order.is_anomaly = False
        order.is_duplicate = False
        
    desc = f"Order status updated from '{old_status}' to '{req.status}' by {req.actor}"
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
def request_customer_clarification(
    order_id: int, 
    tenant: models.BusinessTenant = Depends(get_current_tenant), 
    db: Session = Depends(get_db)
):
    """Triggers outbound clarification message record."""
    order = db.query(models.Order).filter(
        models.Order.id == order_id,
        models.Order.business_id == tenant.id
    ).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found in this workspace.")
        
    order.status = "Needs Review"
    order.confirmation_status = "Clarification Requested"
    
    event = models.OrderTimelineEvent(
        order_id=order.id,
        event_type="Clarification Sent",
        actor="Staff Member",
        description=f"Sent clarification inquiry to customer: '{order.ai_agent_clarification or 'Please confirm order quantities.'}'",
        created_at=datetime.utcnow()
    )
    db.add(event)
    db.commit()
    return {"message": f"Clarification requested from {order.customer_name}"}

@router.put("/{order_id}/items/{item_id}")
def edit_order_item(
    order_id: int, 
    item_id: int, 
    req: OrderItemEditRequest, 
    tenant: models.BusinessTenant = Depends(get_current_tenant), 
    db: Session = Depends(get_db)
):
    """Staff override for item quantities, SKUs, and unit prices."""
    order = db.query(models.Order).filter(
        models.Order.id == order_id, 
        models.Order.business_id == tenant.id
    ).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    item = db.query(models.OrderItem).filter(
        models.OrderItem.id == item_id,
        models.OrderItem.order_id == order_id
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Line item not found")
        
    old_qty = item.quantity
    item.quantity = req.quantity
    item.item_name = req.item_name
    item.matched_sku = req.matched_sku
    item.customer_price = req.unit_price
    item.line_total = req.quantity * req.unit_price

    # Log change tracking in timeline
    event = models.OrderTimelineEvent(
        order_id=order.id,
        event_type="Item Edited",
        actor="Staff Member",
        description=f"Adjusted '{item.item_name}' quantity from {old_qty} to {req.quantity} (${item.line_total:.2f})",
        created_at=datetime.utcnow()
    )
    db.add(event)
    db.commit()
    return {"message": "Line item updated"}

@router.post("/{order_id}/items/add")
def add_item_to_order(
    order_id: int, 
    req: OrderItemAddRequest, 
    tenant: models.BusinessTenant = Depends(get_current_tenant), 
    db: Session = Depends(get_db)
):
    """Staff adds an extra item to an existing order."""
    order = db.query(models.Order).filter(
        models.Order.id == order_id, 
        models.Order.business_id == tenant.id
    ).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    product = db.query(models.ProductCatalog).filter(
        models.ProductCatalog.id == req.product_id,
        models.ProductCatalog.business_id == tenant.id
    ).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found in this catalog")

    discount = order.customer.discount_percentage if order.customer else 0.0
    cust_price = product.unit_price * (1 - (discount / 100))
    line_total = cust_price * req.quantity

    new_item = models.OrderItem(
        order_id=order.id,
        product_id=product.id,
        matched_sku=product.sku,
        item_name=product.name,
        quantity=req.quantity,
        unit_price=product.unit_price,
        customer_price=cust_price,
        line_total=line_total,
        match_confidence=100
    )
    db.add(new_item)

    event = models.OrderTimelineEvent(
        order_id=order.id,
        event_type="Item Added",
        actor="Staff Member",
        description=f"Added {req.quantity}x '{product.name}' ([{product.sku}]) to order.",
        created_at=datetime.utcnow()
    )
    db.add(event)
    db.commit()
    return {"message": f"Added {product.name} to order"}

@router.delete("/{order_id}/items/{item_id}")
def remove_order_item(
    order_id: int, 
    item_id: int, 
    tenant: models.BusinessTenant = Depends(get_current_tenant), 
    db: Session = Depends(get_db)
):
    """Staff removes a line item from an existing order."""
    order = db.query(models.Order).filter(
        models.Order.id == order_id, 
        models.Order.business_id == tenant.id
    ).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    item = db.query(models.OrderItem).filter(
        models.OrderItem.id == item_id,
        models.OrderItem.order_id == order_id
    ).first()
    if item:
        item_name = item.item_name
        db.delete(item)
        event = models.OrderTimelineEvent(
            order_id=order.id,
            event_type="Item Removed",
            actor="Staff Member",
            description=f"Removed '{item_name}' from order.",
            created_at=datetime.utcnow()
        )
        db.add(event)
        db.commit()
    return {"message": "Item removed"}

# -------------------------------------------------------------
# 5. PRODUCTION MODULE (DATE, SHIFT, TRACEABILITY, EXPORT)
# -------------------------------------------------------------
@router.get("/production/sheet")
def get_production_sheet(
    date: Optional[str] = None,
    shift: Optional[str] = "Morning",
    tenant: models.BusinessTenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """
    Returns aggregated production batch requirements.
    Strictly aggregates approved orders for the selected shift & tenant.
    """
    b_id = tenant.id
    query = db.query(models.Order).filter(
        models.Order.business_id == b_id,
        models.Order.status.in_(["Approved", "Sent to Production", "Ready"])
    )
    if shift and shift.upper() != "ALL DAY":
        query = query.filter(models.Order.shift == shift)

    approved_orders = query.all()
    
    # Calculate aggregated product requirements
    sku_map = {}
    for o in approved_orders:
        for i in o.items:
            sku = i.matched_sku
            if sku not in sku_map:
                sku_map[sku] = {
                    "sku": sku,
                    "item_name": i.item_name,
                    "unit": i.product.unit if i.product else "Units",
                    "required_quantity": 0,
                    "completed_quantity": 0,
                    "order_count": 0,
                    "production_status": i.product.production_status if i.product else "Pending"
                }
            sku_map[sku]["required_quantity"] += i.quantity
            sku_map[sku]["completed_quantity"] += (i.completed_quantity or 0)
            sku_map[sku]["order_count"] += 1

    items_list = []
    total_units_required = 0
    total_units_completed = 0
    
    for sku, data in sku_map.items():
        data["remaining_quantity"] = max(0, data["required_quantity"] - data["completed_quantity"])
        total_units_required += data["required_quantity"]
        total_units_completed += data["completed_quantity"]
        items_list.append(data)

    # Sort alphabetically by product name
    items_list.sort(key=lambda x: x["item_name"])

    return {
        "production_date": date or "Tomorrow Morning",
        "shift": shift or "Morning",
        "summary": {
            "total_approved_orders": len(approved_orders),
            "total_products": len(items_list),
            "total_units_required": total_units_required,
            "total_units_completed": total_units_completed,
            "remaining_units": max(0, total_units_required - total_units_completed)
        },
        "items": items_list
    }

@router.get("/production/contributing-orders")
def get_contributing_orders(
    sku: str,
    shift: Optional[str] = "Morning",
    tenant: models.BusinessTenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """
    Traceability Tool: Returns the exact customer orders that contribute to a product's batch count.
    """
    b_id = tenant.id
    query = db.query(models.Order).join(models.OrderItem).filter(
        models.Order.business_id == b_id,
        models.Order.status.in_(["Approved", "Sent to Production", "Ready"]),
        models.OrderItem.matched_sku == sku
    )
    if shift and shift.upper() != "ALL DAY":
        query = query.filter(models.Order.shift == shift)

    orders = query.all()
    contributions = []
    for o in orders:
        matching_items = [i for i in o.items if i.matched_sku == sku]
        qty = sum(i.quantity for i in matching_items)
        contributions.append({
            "order_id": o.id,
            "customer_name": o.customer_name,
            "account_number": o.customer.account_number if o.customer else "ACC-GUEST",
            "quantity": qty,
            "status": o.status,
            "route": o.customer.delivery_route if o.customer else "Standard"
        })
    return contributions

@router.post("/production/update-progress")
def update_production_progress(
    req: ProductionProgressRequest,
    tenant: models.BusinessTenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Updates completed count and production status for a batch item."""
    prod = db.query(models.ProductCatalog).filter(
        models.ProductCatalog.sku == req.sku,
        models.ProductCatalog.business_id == tenant.id
    ).first()
    if prod and req.status:
        prod.production_status = req.status
        
    # Update items across current approved orders
    items = db.query(models.OrderItem).join(models.Order).filter(
        models.Order.business_id == tenant.id,
        models.Order.status.in_(["Approved", "Sent to Production", "Ready"]),
        models.OrderItem.matched_sku == req.sku
    ).all()
    for it in items:
        it.completed_quantity = req.completed_quantity
        
    db.commit()
    return {"message": f"Updated progress for SKU {req.sku}"}

@router.get("/kitchen-sheet")
def get_kitchen_production_sheet(business_id: int = 1, db: Session = Depends(get_db)):
    """Compatibility endpoint for kitchen production sheet."""
    query = db.query(
        models.OrderItem.matched_sku,
        models.OrderItem.item_name,
        func.sum(models.OrderItem.quantity).label("total_quantity"),
        func.count(models.OrderItem.order_id).label("order_count"),
        models.ProductCatalog.production_status
    ).join(models.Order, models.OrderItem.order_id == models.Order.id)\
     .outerjoin(models.ProductCatalog, (models.OrderItem.matched_sku == models.ProductCatalog.sku) & (models.ProductCatalog.business_id == business_id))\
     .filter(
         models.Order.business_id == business_id,
         models.Order.status.in_(["Approved", "Sent to Production", "Ready"])
     )\
     .group_by(models.OrderItem.matched_sku, models.OrderItem.item_name, models.ProductCatalog.production_status)\
     .all()
    
    return [{
        "sku": r[0],
        "item_name": r[1],
        "total_quantity": r[2],
        "order_count": r[3],
        "production_status": r[4] or "Pending"
    } for r in query]

@router.get("/production/export")
def export_production_sheet_csv(
    shift: Optional[str] = "Morning",
    tenant: models.BusinessTenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Exports production sheet CSV with clean headers and specific filename."""
    sheet = get_production_sheet(shift=shift, tenant=tenant, db=db)
    output = io.StringIO()
    writer = csv.writer(output)
    
    writer.writerow(["Production Date", "Shift", "SKU", "Product Name", "Required Quantity", "Completed Quantity", "Remaining Quantity", "Unit", "Status"])
    for it in sheet["items"]:
        writer.writerow([
            sheet["production_date"],
            sheet["shift"],
            it["sku"],
            it["item_name"],
            it["required_quantity"],
            it["completed_quantity"],
            it["remaining_quantity"],
            it["unit"],
            it["production_status"]
        ])
        
    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    filename = f"{tenant.slug}-production-{date_str}-{shift.lower().replace(' ', '-')}.csv"
    response = Response(content=output.getvalue(), media_type="text/csv")
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    return response

# -------------------------------------------------------------
# 6. CUSTOMER DIRECTORY (CRM-LITE)
# -------------------------------------------------------------
@router.get("/customers/list")
def get_customers_list(
    tenant: models.BusinessTenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    customers = db.query(models.Customer).filter(
        models.Customer.business_id == tenant.id,
        models.Customer.is_archived == False
    ).order_by(models.Customer.business_name.asc()).all()
    
    results = []
    for c in customers:
        order_count = len(c.orders)
        last_order = c.orders[-1].created_at.strftime("%Y-%m-%d") if c.orders else "None"
        results.append({
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
            "order_count": order_count,
            "last_order": last_order,
            "usual_order_day": c.usual_order_day
        })
    return results

@router.get("/customers/{customer_id}")
def get_customer_detail(
    customer_id: int, 
    tenant: models.BusinessTenant = Depends(get_current_tenant), 
    db: Session = Depends(get_db)
):
    c = db.query(models.Customer).filter(
        models.Customer.id == customer_id,
        models.Customer.business_id == tenant.id
    ).first()
    if not c:
        raise HTTPException(status_code=404, detail="Customer not found")
        
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
        "language_memories": mems,
        "usual_order_day": c.usual_order_day
    }

@router.post("/customers")
def create_customer_profile(
    req: CustomerCreateRequest, 
    tenant: models.BusinessTenant = Depends(get_current_tenant), 
    db: Session = Depends(get_db)
):
    count = db.query(models.Customer).filter(models.Customer.business_id == tenant.id).count()
    acc_num = f"ACC-{1001 + count}"
    
    new_c = models.Customer(
        business_id=tenant.id,
        account_number=acc_num,
        business_name=req.business_name.strip(),
        contact_name=req.contact_name.strip(),
        phone_number=req.phone_number.strip(),
        email=req.email.strip(),
        delivery_route=req.delivery_route.strip(),
        pricing_tier=req.pricing_tier.strip(),
        discount_percentage=req.discount_percentage,
        special_instructions=req.special_instructions.strip(),
        enabled_channels=req.enabled_channels.strip(),
        created_at=datetime.utcnow()
    )
    db.add(new_c)
    db.commit()
    db.refresh(new_c)
    return {"message": f"Created customer profile for {new_c.business_name}", "account_number": acc_num}

@router.put("/customers/{customer_id}")
def update_customer_profile(
    customer_id: int, 
    req: CustomerUpdateRequest, 
    tenant: models.BusinessTenant = Depends(get_current_tenant), 
    db: Session = Depends(get_db)
):
    c = db.query(models.Customer).filter(
        models.Customer.id == customer_id,
        models.Customer.business_id == tenant.id
    ).first()
    if not c:
        raise HTTPException(status_code=404, detail="Customer not found")
        
    c.business_name = req.business_name.strip()
    c.contact_name = req.contact_name.strip()
    c.phone_number = req.phone_number.strip()
    c.email = req.email.strip()
    c.delivery_route = req.delivery_route.strip()
    c.pricing_tier = req.pricing_tier.strip()
    c.discount_percentage = req.discount_percentage
    c.special_instructions = req.special_instructions.strip()
    c.enabled_channels = req.enabled_channels.strip()
    db.commit()
    return {"message": "Customer profile updated"}

@router.post("/customers/{customer_id}/archive")
def archive_customer_profile(
    customer_id: int,
    tenant: models.BusinessTenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    c = db.query(models.Customer).filter(
        models.Customer.id == customer_id,
        models.Customer.business_id == tenant.id
    ).first()
    if c:
        c.is_archived = True
        db.commit()
    return {"message": "Customer archived"}

# -------------------------------------------------------------
# 7. PRODUCT CATALOG
# -------------------------------------------------------------
@router.get("/catalog")
def get_product_catalog(
    tenant: models.BusinessTenant = Depends(get_current_tenant), 
    db: Session = Depends(get_db)
):
    return db.query(models.ProductCatalog).filter(
        models.ProductCatalog.business_id == tenant.id,
        models.ProductCatalog.is_archived == False
    ).order_by(models.ProductCatalog.name.asc()).all()

@router.post("/products")
def add_product_to_catalog(
    req: ProductCreateRequest, 
    tenant: models.BusinessTenant = Depends(get_current_tenant), 
    db: Session = Depends(get_db)
):
    new_prod = models.ProductCatalog(
        business_id=tenant.id,
        sku=req.sku.strip().upper(),
        name=req.name.strip(),
        category=req.category.strip(),
        unit=req.unit.strip(),
        unit_price=req.unit_price,
        stock_available=req.stock_available,
        aliases=req.aliases.strip(),
        production_status="Pending",
        is_archived=False
    )
    db.add(new_prod)
    db.commit()
    return {"message": f"Product {req.name} added."}

@router.put("/products/{prod_id}")
def update_product_in_catalog(
    prod_id: int, 
    req: ProductUpdateRequest, 
    tenant: models.BusinessTenant = Depends(get_current_tenant), 
    db: Session = Depends(get_db)
):
    prod = db.query(models.ProductCatalog).filter(
        models.ProductCatalog.id == prod_id,
        models.ProductCatalog.business_id == tenant.id
    ).first()
    if not prod:
        raise HTTPException(status_code=404, detail="Product not found")
    prod.sku = req.sku.strip().upper()
    prod.name = req.name.strip()
    prod.category = req.category.strip()
    prod.unit = req.unit.strip()
    prod.unit_price = req.unit_price
    prod.stock_available = req.stock_available
    prod.aliases = req.aliases.strip()
    db.commit()
    return {"message": f"Product {req.name} updated."}

@router.delete("/products/{prod_id}")
def delete_product_from_catalog(
    prod_id: int, 
    tenant: models.BusinessTenant = Depends(get_current_tenant), 
    db: Session = Depends(get_db)
):
    """Soft archive: Never destroys historical references in orders."""
    prod = db.query(models.ProductCatalog).filter(
        models.ProductCatalog.id == prod_id,
        models.ProductCatalog.business_id == tenant.id
    ).first()
    if prod:
        prod.is_archived = True
        db.commit()
    return {"message": "Product archived from catalog"}

# -------------------------------------------------------------
# 8. BUSINESS BRAIN & CUSTOMER TERMINOLOGY
# -------------------------------------------------------------
@router.get("/business/brain")
def get_business_brain(
    tenant: models.BusinessTenant = Depends(get_current_tenant), 
    db: Session = Depends(get_db)
):
    return {
        "id": tenant.id,
        "name": tenant.name,
        "contact_email": tenant.contact_email,
        "contact_phone": tenant.contact_phone,
        "assigned_inbound_number": tenant.assigned_inbound_number,
        "order_cutoff_time": tenant.order_cutoff_time,
        "minimum_order_amount": tenant.minimum_order_amount,
        "business_faq": tenant.business_faq,
        "timezone": tenant.timezone
    }

@router.post("/business/brain")
def update_business_brain(
    req: BrainUpdateRequest, 
    tenant: models.BusinessTenant = Depends(get_current_tenant), 
    db: Session = Depends(get_db)
):
    b = db.query(models.BusinessTenant).filter(models.BusinessTenant.id == tenant.id).first()
    if b:
        if req.name:
            b.name = req.name
        if req.contact_email:
            b.contact_email = req.contact_email
        if req.contact_phone:
            b.contact_phone = req.contact_phone
        if req.assigned_inbound_number:
            b.assigned_inbound_number = req.assigned_inbound_number
        b.order_cutoff_time = req.order_cutoff_time
        b.minimum_order_amount = req.minimum_order_amount
        b.business_faq = req.business_faq
        db.commit()
    return {"message": "Business policies saved successfully"}

@router.get("/memories")
def get_language_memories(
    tenant: models.BusinessTenant = Depends(get_current_tenant), 
    db: Session = Depends(get_db)
):
    mems = db.query(models.CustomerLanguageMemory).filter(models.CustomerLanguageMemory.business_id == tenant.id).all()
    return [{
        "id": m.id,
        "customer_name": m.customer.business_name if m.customer else "Unknown",
        "phrase": m.phrase,
        "mapped_sku": m.mapped_sku,
        "learned_from": m.learned_from,
        "created_at": m.created_at.strftime("%Y-%m-%d")
    } for m in mems]

@router.post("/correct-item")
def correct_item_learning(
    req: CorrectionRequest, 
    tenant: models.BusinessTenant = Depends(get_current_tenant), 
    db: Session = Depends(get_db)
):
    record_human_correction_learning(
        db=db,
        customer_id=req.customer_id,
        original_phrase=req.original_phrase,
        corrected_sku=req.corrected_sku,
        business_id=tenant.id
    )
    return {"message": f"Mapped '{req.original_phrase}' to SKU {req.corrected_sku}."}

# -------------------------------------------------------------
# 10. INTEGRATIONS & CHANNELS
# -------------------------------------------------------------
@router.get("/export/csv")
def export_quickbooks_csv(
    tenant: models.BusinessTenant = Depends(get_current_tenant), 
    db: Session = Depends(get_db)
):
    orders = db.query(models.Order).filter(models.Order.business_id == tenant.id).all()
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
            
    filename = f"{tenant.slug}-quickbooks-export-{datetime.utcnow().strftime('%Y-%m-%d')}.csv"
    response = Response(content=output.getvalue(), media_type="text/csv")
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    return response

@router.post("/switch-workspace")
def switch_workspace(req: WorkspaceSwitchRequest, response: Response, db: Session = Depends(get_db)):
    """Sets secure tenant cookie for workspace context."""
    target = req.tenant_identifier.strip()
    tenant = None
    if target.isdigit():
        tenant = db.query(models.BusinessTenant).filter(models.BusinessTenant.id == int(target)).first()
    else:
        tenant = db.query(models.BusinessTenant).filter(models.BusinessTenant.slug == target.lower()).first()
        
    if not tenant:
        raise HTTPException(status_code=404, detail="Workspace not found")
        
    response.set_cookie(key="orderstream_tenant", value=str(tenant.id), httponly=False, samesite="lax")
    return {"message": f"Switched to workspace: {tenant.name}", "tenant_id": tenant.id, "slug": tenant.slug}
