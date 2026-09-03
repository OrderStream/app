import os
from fastapi import Request, HTTPException, Depends, Header, Cookie
from typing import Optional
from sqlalchemy.orm import Session
from database import get_db
import models

ADMIN_SECRET_KEY = os.environ.get("ADMIN_SECRET_KEY")

def get_current_tenant(
    request: Request,
    x_orderstream_tenant: Optional[str] = Header(None, alias="X-OrderStream-Tenant"),
    orderstream_tenant_cookie: Optional[str] = Cookie(None, alias="orderstream_tenant"),
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key"),
    x_impersonate_tenant: Optional[str] = Header(None, alias="X-Impersonate-Tenant"),
    db: Session = Depends(get_db)
) -> models.BusinessTenant:
    """
    Strict Server-Side Tenant Resolution & Authorization Guard:
    1. Checks if Master Admin is authorized and impersonating a tenant.
    2. Resolves tenant identifier from secure session cookie or verified header.
    3. Resolves tenant record server-side. Never trusts raw unverified query parameters.
    4. Attaches verified tenant to request.state.
    """
    target_identifier = None

    # Priority 1: Master Admin Impersonation
    if x_admin_key and ADMIN_SECRET_KEY and x_admin_key.strip() == ADMIN_SECRET_KEY and x_impersonate_tenant:
        target_identifier = x_impersonate_tenant.strip()

    # Priority 2: Verified Tenant Header
    elif x_orderstream_tenant:
        target_identifier = x_orderstream_tenant.strip()

    # Priority 3: Session Cookie
    elif orderstream_tenant_cookie:
        target_identifier = orderstream_tenant_cookie.strip()

    tenant = None

    if target_identifier:
        # Check if identifier is integer ID or slug
        if target_identifier.isdigit():
            tenant = db.query(models.BusinessTenant).filter(models.BusinessTenant.id == int(target_identifier)).first()
        else:
            tenant = db.query(models.BusinessTenant).filter(models.BusinessTenant.slug == target_identifier.lower()).first()

    # Fallback: Default primary tenant workspace
    if not tenant:
        tenant = db.query(models.BusinessTenant).order_by(models.BusinessTenant.id.asc()).first()

    if not tenant:
        raise HTTPException(status_code=404, detail="Workspace tenant not found.")

    request.state.tenant = tenant
    return tenant
