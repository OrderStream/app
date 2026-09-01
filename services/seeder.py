from datetime import datetime, timedelta
from sqlalchemy.orm import Session
import models

def seed_default_data(db: Session):
    """
    Seeds a rich, realistic wholesale bakery dataset so the app feels alive immediately.
    """
    # 1. Seed Business Tenant
    business = db.query(models.BusinessTenant).first()
    if not business:
        business = models.BusinessTenant(
            slug="bakehouse24",
            name="Bakehouse 24 Artisan Wholesale",
            contact_email="orders@bakehouse24.com",
            contact_phone="+1 (555) 019-2834",
            assigned_inbound_number="+1 (555) 839-2011",
            order_cutoff_time="23:00",
            minimum_order_amount=35.0,
            business_faq="Minimum wholesale order is $35. Order cutoff is 11:00 PM for next-day 4:30 AM delivery. Organic sourdough and pastries baked fresh nightly."
        )
        db.add(business)
        db.commit()
        db.refresh(business)

    # 2. Seed Products
    if db.query(models.ProductCatalog).count() == 0:
        sample_products = [
            models.ProductCatalog(
                business_id=business.id,
                sku="BRD-001",
                name="Country Sourdough Loaf 800g",
                category="Artisan Bread",
                unit="Loaf",
                unit_price=6.50,
                aliases="sourdough, country sourdough, sourdough loaf, sour dough, big bread, white sourdough",
                stock_available=180
            ),
            models.ProductCatalog(
                business_id=business.id,
                sku="BRD-002",
                name="Traditional Seeded Rye Loaf",
                category="Artisan Bread",
                unit="Loaf",
                unit_price=5.75,
                aliases="rye, rye bread, dark rye, seeded rye, caraway rye",
                stock_available=95
            ),
            models.ProductCatalog(
                business_id=business.id,
                sku="PST-001",
                name="All-Butter French Croissant",
                category="Pastries",
                unit="Each",
                unit_price=2.80,
                aliases="croissant, croissants, butter croissant, french croissant",
                stock_available=250
            ),
            models.ProductCatalog(
                business_id=business.id,
                sku="PST-002",
                name="Blueberry Streusel Muffins (Dozen)",
                category="Pastries",
                unit="Dozen",
                unit_price=28.00,
                aliases="muffins, blueberry muffin, blueberry muffins, blueberry muffins (dozen), muffin, dozen muffins",
                stock_available=45
            ),
            models.ProductCatalog(
                business_id=business.id,
                sku="BRD-003",
                name="Traditional Crusty Baguette",
                category="Artisan Bread",
                unit="Each",
                unit_price=3.25,
                aliases="baguette, baguettes, french baguette, stick bread",
                stock_available=140
            ),
            models.ProductCatalog(
                business_id=business.id,
                sku="BRD-004",
                name="Whole Wheat Farmhouse Loaf",
                category="Artisan Bread",
                unit="Loaf",
                unit_price=5.50,
                aliases="whole wheat, wheat bread, brown bread, wholemeal, brown loaf, wheat loaf",
                stock_available=85
            ),
        ]
        for p in sample_products:
            db.add(p)
        db.commit()

    # 3. Seed Customers
    if db.query(models.Customer).count() == 0:
        c1 = models.Customer(
            business_id=business.id,
            account_number="ACC-1001",
            business_name="Cafe Bella",
            contact_name="Marco Rossi",
            phone_number="+15551234",
            email="orders@cafebella.com",
            delivery_route="Route A - Downtown Core",
            pricing_tier="Wholesale Tier 1 (-10%)",
            avg_order_volume=18.0
        )
        c2 = models.Customer(
            business_id=business.id,
            account_number="ACC-1002",
            business_name="The Daily Grind Cafe",
            contact_name="Sarah Jenkins",
            phone_number="+15559876",
            email="sarah@dailygrind.com",
            delivery_route="Route B - Uptown / North",
            pricing_tier="Wholesale Standard",
            avg_order_volume=22.0
        )
        c3 = models.Customer(
            business_id=business.id,
            account_number="ACC-1003",
            business_name="Harbor View Bistro",
            contact_name="Chef Tony",
            phone_number="+15554321",
            email="kitchen@harborview.com",
            delivery_route="Route A - Downtown Core",
            pricing_tier="Wholesale VIP (-15%)",
            avg_order_volume=14.0
        )
        c4 = models.Customer(
            business_id=business.id,
            account_number="ACC-1004",
            business_name="Greenwood Espresso Bar",
            contact_name="David Kim",
            phone_number="+15556789",
            email="dave@greenwoodcoffee.com",
            delivery_route="Route C - Westside Suburbs",
            pricing_tier="Wholesale Standard",
            avg_order_volume=28.0
        )
        db.add_all([c1, c2, c3, c4])
        db.commit()

        # Seed Customer Jargon Memories
        db.add_all([
            models.CustomerLanguageMemory(
                business_id=business.id,
                customer_id=c1.id,
                phrase="the big bread",
                mapped_sku="BRD-001",
                confidence_boost=99,
                learned_from="Human Staff Correction"
            ),
            models.CustomerLanguageMemory(
                business_id=business.id,
                customer_id=c2.id,
                phrase="brown loaf",
                mapped_sku="BRD-004",
                confidence_boost=98,
                learned_from="Historical Pattern"
            )
        ])
        db.commit()

        # Seed Realistic Orders (Confirmed, Needs Review, Historical)
        now = datetime.utcnow()
        o1 = models.Order(
            business_id=business.id,
            customer_id=c1.id,
            customer_phone="+15551234",
            customer_name="Cafe Bella",
            channel="SMS",
            raw_message="Hey Tony, need 12 sourdough loaves and 2 dozen croissants for 5am please - Marco",
            status="Ready",
            confirmation_status="Confirmed via SMS",
            confidence_score=98,
            delivery_date="Tomorrow (4:30 AM)",
            created_at=now - timedelta(minutes=42)
        )
        o2 = models.Order(
            business_id=business.id,
            customer_id=c2.id,
            customer_phone="+15559876",
            customer_name="The Daily Grind Cafe",
            channel="WhatsApp",
            raw_message="Same as last Tuesday + 4 baguettes. Thanks! - Sarah",
            status="Ready",
            confirmation_status="Confirmed via WhatsApp",
            confidence_score=96,
            delivery_date="Tomorrow (5:00 AM)",
            history_cloned=True,
            history_note="Cloned 14 items from previous Tuesday + 4 Baguettes",
            created_at=now - timedelta(minutes=25)
        )
        o3 = models.Order(
            business_id=business.id,
            customer_id=c3.id,
            customer_phone="+15554321",
            customer_name="Harbor View Bistro",
            channel="Email",
            raw_message="Emergency update: We need 450 sourdough loaves for the harbor festival tomorrow morning.",
            status="Needs Review",
            confirmation_status="Pending Staff Review",
            confidence_score=55,
            delivery_date="Tomorrow (6:00 AM)",
            is_anomaly=True,
            anomaly_reason="Volume Spike: 450 units is 32x higher than client's average (14 units)",
            created_at=now - timedelta(minutes=10)
        )
        db.add_all([o1, o2, o3])
        db.commit()
        db.refresh(o1)
        db.refresh(o2)
        db.refresh(o3)

        # Add Order Items
        db.add_all([
            # Cafe Bella
            models.OrderItem(order_id=o1.id, product_id=1, matched_sku="BRD-001", item_name="Country Sourdough Loaf 800g", quantity=12, unit_price=6.50, line_total=78.00, match_confidence=98),
            models.OrderItem(order_id=o1.id, product_id=3, matched_sku="PST-001", item_name="All-Butter French Croissant", quantity=24, unit_price=2.80, line_total=67.20, match_confidence=98),
            # Daily Grind
            models.OrderItem(order_id=o2.id, product_id=1, matched_sku="BRD-001", item_name="Country Sourdough Loaf 800g", quantity=10, unit_price=6.50, line_total=65.00, match_confidence=96),
            models.OrderItem(order_id=o2.id, product_id=2, matched_sku="BRD-002", item_name="Traditional Seeded Rye Loaf", quantity=4, unit_price=5.75, line_total=23.00, match_confidence=96),
            models.OrderItem(order_id=o2.id, product_id=5, matched_sku="BRD-003", item_name="Traditional Crusty Baguette", quantity=4, unit_price=3.25, line_total=13.00, match_confidence=98),
            # Harbor Bistro Anomaly
            models.OrderItem(order_id=o3.id, product_id=1, matched_sku="BRD-001", item_name="Country Sourdough Loaf 800g", quantity=450, unit_price=6.50, line_total=2925.00, match_confidence=95)
        ])
        db.commit()
