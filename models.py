from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class BusinessTenant(Base):
    """
    Multi-tenant Root: Every bakery or distributor has its own isolated workspace,
    private numbers, custom business brain, and customer directory.
    """
    __tablename__ = "businesses"

    id = Column(Integer, primary_key=True, index=True)
    slug = Column(String(50), unique=True, index=True) # e.g. 'bakehouse24', 'hudsonbreads'
    name = Column(String(200), index=True)
    contact_email = Column(String(100), nullable=True)
    contact_phone = Column(String(50), nullable=True)
    assigned_inbound_number = Column(String(50), unique=True, index=True, nullable=True)
    order_cutoff_time = Column(String(50), default="23:00") # 11:00 PM
    minimum_order_amount = Column(Float, default=0.0)
    business_faq = Column(Text, default="Minimum wholesale order is $30. Delivery window: 4:30 AM - 6:30 AM.")
    created_at = Column(DateTime, default=datetime.utcnow)

    # Isolated Relationships
    customers = relationship("Customer", back_populates="business", cascade="all, delete-orphan")
    products = relationship("ProductCatalog", back_populates="business", cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="business", cascade="all, delete-orphan")
    memories = relationship("CustomerLanguageMemory", back_populates="business", cascade="all, delete-orphan")

class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), index=True, default=1)
    account_number = Column(String(50), index=True)
    business_name = Column(String(200), index=True)
    contact_name = Column(String(100), nullable=True)
    phone_number = Column(String(50), index=True)
    email = Column(String(100), nullable=True)
    delivery_route = Column(String(100), default="Route A - Downtown Core")
    pricing_tier = Column(String(50), default="Wholesale Standard") # Wholesale Standard, Tier 1 (-10%), VIP (-15%)
    discount_percentage = Column(Float, default=0.0)
    special_instructions = Column(Text, default="")
    enabled_channels = Column(String(100), default="SMS, WhatsApp, Email")
    avg_order_volume = Column(Float, default=15.0)
    created_at = Column(DateTime, default=datetime.utcnow)

    business = relationship("BusinessTenant", back_populates="customers")
    orders = relationship("Order", back_populates="customer")
    language_memories = relationship("CustomerLanguageMemory", back_populates="customer", cascade="all, delete-orphan")

class CustomerLanguageMemory(Base):
    """
    Customer Language Memory strictly isolated per Business Tenant.
    """
    __tablename__ = "customer_language_memories"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), index=True, default=1)
    customer_id = Column(Integer, ForeignKey("customers.id"))
    phrase = Column(String(200), index=True)
    mapped_sku = Column(String(50))
    confidence_boost = Column(Integer, default=95)
    learned_from = Column(String(100), default="Human Correction")
    created_at = Column(DateTime, default=datetime.utcnow)

    business = relationship("BusinessTenant", back_populates="memories")
    customer = relationship("Customer", back_populates="language_memories")

class ProductCatalog(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), index=True, default=1)
    sku = Column(String(50), index=True)
    name = Column(String(200), index=True)
    category = Column(String(100), default="Bakery")
    unit = Column(String(50), default="Each")
    unit_price = Column(Float, default=0.0)
    aliases = Column(Text, default="")
    stock_available = Column(Integer, default=100)
    production_status = Column(String(50), default="Pending") # Pending, In Progress, Completed

    business = relationship("BusinessTenant", back_populates="products")
    order_items = relationship("OrderItem", back_populates="product")

class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), index=True, default=1)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)
    customer_phone = Column(String(50), index=True)
    customer_name = Column(String(100), default="Unknown Customer")
    channel = Column(String(50), default="SMS") # SMS, WhatsApp, Email, Voice
    raw_message = Column(Text)
    
    # Human Review Workflow Statuses: New, AI Processed, Needs Review, Approved, Rejected, Sent to Production, Completed
    status = Column(String(50), default="New")
    confirmation_status = Column(String(50), default="Unconfirmed")
    confidence_score = Column(Integer, default=95)
    delivery_date = Column(String(50), default="Tomorrow Morning")
    
    # Intelligence Flags
    is_anomaly = Column(Boolean, default=False)
    anomaly_reason = Column(String(255), nullable=True)
    is_duplicate = Column(Boolean, default=False)
    duplicate_of_id = Column(Integer, nullable=True)
    history_cloned = Column(Boolean, default=False)
    history_note = Column(String(255), nullable=True)
    ai_agent_clarification = Column(Text, nullable=True)
    ai_interpretation_summary = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)

    business = relationship("BusinessTenant", back_populates="orders")
    customer = relationship("Customer", back_populates="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    timeline = relationship("OrderTimelineEvent", back_populates="order", cascade="all, delete-orphan")

class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"))
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    matched_sku = Column(String(50), default="MISC-001")
    item_name = Column(String(200))
    quantity = Column(Integer)
    unit_price = Column(Float, default=0.0)
    customer_price = Column(Float, default=0.0)
    line_total = Column(Float, default=0.0)
    match_confidence = Column(Integer, default=95)

    order = relationship("Order", back_populates="items")
    product = relationship("ProductCatalog", back_populates="order_items")

class OrderTimelineEvent(Base):
    """
    Audit Trail / Timeline for every order action:
    who modified what, when, and automated events.
    """
    __tablename__ = "order_timeline_events"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), index=True)
    event_type = Column(String(100)) # Message Received, AI Processed, Staff Edit, Approved, Rejected, Sent to Production, Completed
    actor = Column(String(100), default="OrderStream AI") # "OrderStream AI", "Staff Member", "Customer"
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    order = relationship("Order", back_populates="timeline")
