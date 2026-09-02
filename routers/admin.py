import os
from fastapi import APIRouter, Depends, HTTPException, Header, Cookie
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.orm import Session
from datetime import datetime
from database import get_db
import models

router = APIRouter()

# Read Master Admin Key from environment (default strong fallback for local dev)
ADMIN_SECRET_KEY = os.environ.get("ADMIN_SECRET_KEY", "OrderStream_MasterAdmin_2026_SecureKey!")

def verify_admin_access(
    x_admin_key: Optional[str] = Header(None),
    admin_token: Optional[str] = Cookie(None)
):
    """
    Security Gate: Rejects any request that doesn't provide the Master Admin Key.
    """
    provided_key = x_admin_key or admin_token
    if not provided_key or provided_key != ADMIN_SECRET_KEY:
        raise HTTPException(
            status_code=401, 
            detail="Unauthorized: Access Denied. Master Super-Admin Key required."
        )
    return True

class AdminLoginRequest(BaseModel):
    password: str

class TenantProvisionRequest(BaseModel):
    name: str
    slug: str
    contact_email: str
    contact_phone: str
    assigned_inbound_number: str
    order_cutoff_time: str = "23:00"
    minimum_order_amount: float = 35.0
    business_faq: str = "Minimum wholesale order is $35. Order cutoff is 11:00 PM for next-day delivery."

# Public Authentication Endpoint for Admin
@router.post("/login")
def admin_login(req: AdminLoginRequest):
    """Verifies Master Password and returns secure session token."""
    if req.password.strip() == ADMIN_SECRET_KEY:
        return {"success": True, "token": ADMIN_SECRET_KEY, "message": "Super-Admin Access Granted"}
    raise HTTPException(status_code=401, detail="Invalid Master Admin Password.")

# PROTECTED ENDPOINT 1: Global Platform Overview
@router.get("/overview")
def get_admin_global_overview(
    db: Session = Depends(get_db),
    authorized: bool = Depends(verify_admin_access)
):
    """Super-Admin Master Metric Overview (Locked behind Admin Auth)."""
    total_tenants = db.query(models.BusinessTenant).count()
    total_orders = db.query(models.Order).count()
    total_customers = db.query(models.Customer).count()
    
    orders = db.query(models.Order).filter(models.Order.status.in_(["Approved", "Sent to Production", "Ready", "Exported"])).all()
    total_revenue_processed = sum(sum(i.line_total for i in o.items) for o in orders)
    total_anomalies = db.query(models.Order).filter(models.Order.is_anomaly == True).count()

    tenants = db.query(models.BusinessTenant).all()
    tenant_list = []
    for t in tenants:
        t_orders_count = db.query(models.Order).filter(models.Order.business_id == t.id).count()
        t_cust_count = db.query(models.Customer).filter(models.Customer.business_id == t.id).count()
        t_prod_count = db.query(models.ProductCatalog).filter(models.ProductCatalog.business_id == t.id).count()
        
        tenant_list.append({
            "id": t.id,
            "name": t.name,
            "slug": t.slug,
            "contact_email": t.contact_email,
            "contact_phone": t.contact_phone,
            "assigned_number": t.assigned_inbound_number or "Pending Twilio Number",
            "cutoff_time": t.order_cutoff_time,
            "minimum_order": t.minimum_order_amount,
            "total_orders": t_orders_count,
            "total_customers": t_cust_count,
            "total_products": t_prod_count,
            "subscription_status": "14-Day Free Pilot Active" if t.id == 1 else "Active Paying ($199/mo)",
            "created_at": t.created_at.strftime("%Y-%m-%d")
        })

    return {
        "total_tenants": total_tenants,
        "total_orders_ingested": total_orders,
        "total_wholesale_buyers": total_customers,
        "total_revenue_processed": total_revenue_processed,
        "total_anomalies_intercepted": total_anomalies,
        "tenants": tenant_list
    }

# PROTECTED ENDPOINT 2: Provision Tenant
@router.post("/provision")
def provision_new_tenant(
    req: TenantProvisionRequest, 
    db: Session = Depends(get_db),
    authorized: bool = Depends(verify_admin_access)
):
    """Super-Admin creates and provisions a new isolated bakery tenant (Locked)."""
    clean_slug = req.slug.strip().lower().replace(" ", "-")
    existing = db.query(models.BusinessTenant).filter(models.BusinessTenant.slug == clean_slug).first()
    if existing:
        raise HTTPException(status_code=400, detail="A business with this slug already exists.")
        
    new_tenant = models.BusinessTenant(
        name=req.name.strip(),
        slug=clean_slug,
        contact_email=req.contact_email.strip(),
        contact_phone=req.contact_phone.strip(),
        assigned_inbound_number=req.assigned_inbound_number.strip(),
        order_cutoff_time=req.order_cutoff_time.strip(),
        minimum_order_amount=req.minimum_order_amount,
        business_faq=req.business_faq.strip(),
        created_at=datetime.utcnow()
    )
    db.add(new_tenant)
    db.commit()
    db.refresh(new_tenant)
    
    starter_skus = [
        models.ProductCatalog(business_id=new_tenant.id, sku="BRD-001", name="Artisan Sourdough Loaf", unit="Loaf", unit_price=6.50, stock_available=100, aliases="sourdough, country loaf"),
        models.ProductCatalog(business_id=new_tenant.id, sku="PST-001", name="Butter Croissant", unit="Each", unit_price=2.80, stock_available=150, aliases="croissant, butter croissant")
    ]
    db.add_all(starter_skus)
    db.commit()
    
    return {"message": f"Successfully provisioned workspace for {new_tenant.name} with Hotline {new_tenant.assigned_inbound_number}."}
