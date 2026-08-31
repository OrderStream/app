from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    account_number = Column(String(50), unique=True, index=True)
    business_name = Column(String(200), index=True)
    contact_name = Column(String(100), nullable=True)
    phone_number = Column(String(50), unique=True, index=True)
    delivery_route = Column(String(100), default="Downtown / Central")
    pricing_tier = Column(String(50), default="Wholesale Standard")
    created_at = Column(DateTime, default=datetime.utcnow)

    orders = relationship("Order", back_populates="customer")

class ProductCatalog(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    sku = Column(String(50), unique=True, index=True)
    name = Column(String(200), index=True)
    category = Column(String(100), default="Bakery")
    unit = Column(String(50), default="Each") # Each, Dozen, Loaf, Bag
    unit_price = Column(Float, default=0.0)
    aliases = Column(Text, default="") # Comma-separated search aliases (e.g. "sourdough, sourdough loaf, country bread")

    order_items = relationship("OrderItem", back_populates="product")

class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)
    customer_phone = Column(String(50), index=True)
    customer_name = Column(String(100), default="Unknown Customer")
    raw_message = Column(Text)
    status = Column(String(50), default="Ready") # Ready, Needs Review, Exported, Cancelled
    confirmation_status = Column(String(50), default="Confirmed") # Confirmed, Pending SMS, Manual Approved
    confidence_score = Column(Integer, default=95) # 0 to 100%
    delivery_date = Column(String(50), default="Tomorrow Morning")
    created_at = Column(DateTime, default=datetime.utcnow)

    customer = relationship("Customer", back_populates="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")

class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"))
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    matched_sku = Column(String(50), default="MISC-001")
    item_name = Column(String(200))
    quantity = Column(Integer)
    unit_price = Column(Float, default=0.0)
    line_total = Column(Float, default=0.0)

    order = relationship("Order", back_populates="items")
    product = relationship("ProductCatalog", back_populates="order_items")
