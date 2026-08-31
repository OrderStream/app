from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import get_db
import models
import csv
import io

router = APIRouter()

@router.get("/")
def get_all_orders(db: Session = Depends(get_db)):
    """
    Returns list of orders with items, SKU details, customer accounts, and confirmation states.
    """
    orders = db.query(models.Order).order_by(models.Order.created_at.desc()).all()
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
                "line_total": i.line_total
            })
            
        results.append({
            "id": o.id,
            "account_number": o.customer.account_number if o.customer else "ACC-GUEST",
            "customer_name": o.customer_name,
            "customer_phone": o.customer_phone,
            "delivery_route": o.customer.delivery_route if o.customer else "Standard",
            "raw_message": o.raw_message,
            "status": o.status,
            "confirmation_status": o.confirmation_status,
            "confidence_score": o.confidence_score,
            "delivery_date": o.delivery_date,
            "order_total": order_total,
            "created_at": o.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "items": items_data
        })
    return results

@router.get("/kitchen-sheet")
def get_kitchen_production_sheet(db: Session = Depends(get_db)):
    """
    Aggregates all line items across all ready/confirmed orders into a single
    Production & Bake Batch Sheet for 3 AM Kitchen staff.
    """
    # Group by matched SKU and item_name
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
    
    production_list = []
    for row in query:
        production_list.append({
            "sku": row[0],
            "item_name": row[1],
            "total_quantity": row[2]
        })
    return production_list

@router.get("/catalog")
def get_product_catalog(db: Session = Depends(get_db)):
    """Returns active Product Catalog & SKUs."""
    return db.query(models.ProductCatalog).all()

@router.get("/customers")
def get_customers(db: Session = Depends(get_db)):
    """Returns customer directory."""
    return db.query(models.Customer).all()

@router.post("/{order_id}/confirm")
def manual_confirm_order(order_id: int, db: Session = Depends(get_db)):
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    order.confirmation_status = "Manual Approved"
    order.status = "Ready"
    db.commit()
    return {"message": "Order approved"}

@router.get("/export/csv")
def export_quickbooks_csv(db: Session = Depends(get_db)):
    """
    Exports clean, SKU-matched orders formatted for QuickBooks Invoicing.
    """
    orders = db.query(models.Order).all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header formatted for QuickBooks B2B Invoice Batch Import
    writer.writerow([
        "Invoice_Date", 
        "Account_Number", 
        "Customer_Name", 
        "Phone_Number", 
        "Delivery_Route", 
        "Item_SKU", 
        "Item_Description", 
        "Quantity", 
        "Unit_Price", 
        "Line_Total", 
        "Confidence", 
        "Confirmation"
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
