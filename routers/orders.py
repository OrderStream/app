from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from database import get_db
import models

router = APIRouter()

class OrderItemSchema(BaseModel):
    id: int
    item_name: str
    quantity: int
    
    class Config:
        from_attributes = True

class OrderSchema(BaseModel):
    id: int
    customer_phone: str
    customer_name: Optional[str]
    raw_message: str
    status: str
    items: List[OrderItemSchema] = []
    
    class Config:
        from_attributes = True

@router.get("/", response_model=List[OrderSchema])
def get_orders(db: Session = Depends(get_db)):
    orders = db.query(models.Order).order_by(models.Order.created_at.desc()).all()
    return orders

@router.put("/{order_id}/status")
def update_status(order_id: int, status: str, db: Session = Depends(get_db)):
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    order.status = status
    db.commit()
    return {"message": "success"}
