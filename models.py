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
    business_faq = Column(Text, default="Minimum wholesale order is $35. Order cutoff is 11:00 PM for next-day morning delivery.")
    timezone = Column(String(50), default="America/New_York")
    shifts_config = Column(String(200), default="Morning,Afternoon,Evening,All Day")
    api_key = Column(String(100), unique=True, index=True, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Isolated Relationships
    customers = relationship("Customer", back_populates="business", cascade="all, delete-orphan")
    products = relationship("ProductCatalog", back_populates="business", cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="business", cascade="all, delete-orphan")
    memories = relationship("CustomerLanguageMemory", back_populates="business", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="business", cascade="all, delete-orphan")
    webhook_events = relationship("InboundWebhookEvent", back_populates="business", cascade="all, delete-orphan")

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
    usual_order_day = Column(String(100), default="Tuesday, Thursday, Saturday")
    is_archived = Column(Boolean, default=False)
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
    learned_from = Column(String(100), default="Human Staff Correction")
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
    min_order_qty = Column(Integer, default=1)
    is_archived = Column(Boolean, default=False)

    business = relationship("BusinessTenant", back_populates="products")
    order_items = relationship("OrderItem", back_populates="product")

class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), index=True, default=1)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)
    customer_phone = Column(String(50), index=True)
    customer_name = Column(String(100), default="Unknown Customer")
    channel = Column(String(50), default="SMS") # SMS, WhatsApp, Email, Voice, Manual
    raw_message = Column(Text)
    
    # Human Review Workflow Statuses: Received, Processing, Needs Review, Ready, Approved, Sent to Production, Completed, Cancelled
    status = Column(String(50), default="New")
    confirmation_status = Column(String(50), default="Unconfirmed")
    confidence_score = Column(Integer, default=95)
    delivery_date = Column(String(50), default="Tomorrow Morning")
    shift = Column(String(50), default="Morning") # Morning, Afternoon, Evening, All Day
    
    # Intelligence Flags
    is_anomaly = Column(Boolean, default=False)
    anomaly_reason = Column(String(255), nullable=True)
    is_duplicate = Column(Boolean, default=False)
    duplicate_of_id = Column(Integer, nullable=True)
    history_cloned = Column(Boolean, default=False)
    history_note = Column(String(255), nullable=True)
    ai_agent_clarification = Column(Text, nullable=True)
    ai_interpretation_summary = Column(Text, nullable=True)
    
    # Operational Reviewer Attribution
    reviewed_by = Column(String(100), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
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
    completed_quantity = Column(Integer, default=0) # Units completed on kitchen floor
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
    event_type = Column(String(100)) # Message Received, Customer Identified, Products Matched, Anomaly Intercepted, Staff Edit, Approved, Rejected, Sent to Production, Clarification Sent
    actor = Column(String(100), default="OrderStream") # "OrderStream", "Staff Member", "Customer"
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    order = relationship("Order", back_populates="timeline")

class InboundWebhookEvent(Base):
    """
    Idempotency & Inbound Pipeline Audit:
    Every inbound provider message is recorded once with unique message ID.
    Prevents duplicate orders and tracks delivery health.
    """
    __tablename__ = "inbound_webhook_events"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), index=True)
    provider = Column(String(50), default="twilio_sms") # twilio_sms, twilio_whatsapp, email, manual
    provider_message_id = Column(String(100), index=True, nullable=True) # e.g. Twilio MessageSid
    sender = Column(String(100))
    recipient = Column(String(100), nullable=True)
    payload = Column(Text)
    status = Column(String(50), default="processed") # received, processed, duplicate, failed
    error_message = Column(Text, nullable=True)
    received_at = Column(DateTime, default=datetime.utcnow)

    business = relationship("BusinessTenant", back_populates="webhook_events")

class Notification(Base):
    """
    Lightweight, tenant-scoped operational notifications.
    """
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True)
    title = Column(String(200))
    message = Column(Text)
    category = Column(String(50), default="review_required") # review_required, anomaly, customer_confirmed, channel_alert
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    business = relationship("BusinessTenant", back_populates="notifications")
