from datetime import datetime, timedelta
from sqlalchemy.orm import Session
import models

def seed_default_data(db: Session):
    """
    Seeds a rich, realistic wholesale bakery operations workspace (Hudson Artisan Wholesale)
    along with an isolated second business (Manchester Breads) for strict multi-tenant isolation.
    """
    # =============================================================
    # 1. TENANT 1: HUDSON ARTISAN WHOLESALE (PRIMARY DEMO WORKSPACE)
    # =============================================================
    t1 = db.query(models.BusinessTenant).filter(models.BusinessTenant.slug == "hudsonbreads").first()
    if not t1:
        t1 = models.BusinessTenant(
            slug="hudsonbreads",
            name="Hudson Artisan Wholesale",
            contact_email="orders@hudsonbreads.com",
            contact_phone="+1 (555) 839-2011",
            assigned_inbound_number="+1 (555) 839-2011",
            order_cutoff_time="23:00",
            minimum_order_amount=35.0,
            business_faq="Minimum wholesale order is $35. Order cutoff is 11:00 PM for next-day 4:30 AM delivery. Organic sourdough and pastries baked fresh nightly.",
            timezone="America/New_York",
            shifts_config="Morning,Afternoon,Evening,All Day",
            api_key="hudson_live_api_key_2026"
        )
        db.add(t1)
        db.commit()
        db.refresh(t1)

    # Seed Tenant 1 Products (Artisan Sourdough & Viennoiserie)
    if db.query(models.ProductCatalog).filter(models.ProductCatalog.business_id == t1.id).count() == 0:
        products_t1 = [
            models.ProductCatalog(business_id=t1.id, sku="BRD-001", name="Country Sourdough Loaf 800g", category="Artisan Bread", unit="Loaf", unit_price=6.50, aliases="sourdough, country sourdough, sourdough loaf, sour dough, big bread, white sourdough", stock_available=180, production_status="Pending"),
            models.ProductCatalog(business_id=t1.id, sku="BRD-002", name="Traditional Seeded Rye Loaf", category="Artisan Bread", unit="Loaf", unit_price=5.75, aliases="rye, rye bread, dark rye, seeded rye, caraway rye", stock_available=95, production_status="Pending"),
            models.ProductCatalog(business_id=t1.id, sku="BRD-003", name="Crusty French Baguette 400g", category="Artisan Bread", unit="Each", unit_price=3.25, aliases="baguette, baguettes, french baguette, stick bread, french stick", stock_available=140, production_status="Pending"),
            models.ProductCatalog(business_id=t1.id, sku="BRD-004", name="Whole Wheat Farmhouse Loaf", category="Artisan Bread", unit="Loaf", unit_price=5.50, aliases="whole wheat, wheat bread, brown bread, wholemeal, brown loaf, wheat loaf", stock_available=85, production_status="Pending"),
            models.ProductCatalog(business_id=t1.id, sku="BRD-005", name="Rosemary Sea Salt Focaccia", category="Artisan Bread", unit="Sheet", unit_price=14.00, aliases="focaccia, rosemary focaccia, herb bread, sheet bread", stock_available=30, production_status="Pending"),
            models.ProductCatalog(business_id=t1.id, sku="BRD-006", name="Artisan Ciabatta Sandwich Rolls (6pk)", category="Artisan Bread", unit="Pack", unit_price=7.20, aliases="ciabatta, ciabatta rolls, sandwich rolls", stock_available=60, production_status="Pending"),
            models.ProductCatalog(business_id=t1.id, sku="PST-001", name="All-Butter French Croissant", category="Pastries", unit="Each", unit_price=2.80, aliases="croissant, croissants, butter croissant, french croissant", stock_available=250, production_status="In Progress"),
            models.ProductCatalog(business_id=t1.id, sku="PST-002", name="Blueberry Streusel Muffins (Dozen)", category="Pastries", unit="Dozen", unit_price=28.00, aliases="muffins, blueberry muffin, blueberry muffins, dozen muffins", stock_available=45, production_status="Pending"),
            models.ProductCatalog(business_id=t1.id, sku="PST-003", name="Pain au Chocolat (Dark Chocolate)", category="Pastries", unit="Each", unit_price=3.40, aliases="chocolate croissant, pain au chocolat, choc croissant", stock_available=120, production_status="Pending"),
            models.ProductCatalog(business_id=t1.id, sku="PST-004", name="Almond Frangipane Croissant", category="Pastries", unit="Each", unit_price=3.90, aliases="almond croissant, frangipane", stock_available=80, production_status="Pending"),
            models.ProductCatalog(business_id=t1.id, sku="PST-005", name="Cardamom Morning Buns", category="Pastries", unit="Each", unit_price=3.20, aliases="morning bun, cardamom bun, morning buns, cinnamon bun", stock_available=90, production_status="Pending")
        ]
        db.add_all(products_t1)
        db.commit()

    # Seed Tenant 1 Customers
    if db.query(models.Customer).filter(models.Customer.business_id == t1.id).count() == 0:
        c1 = models.Customer(business_id=t1.id, account_number="ACC-1001", business_name="Cafe Bella", contact_name="Marco Rossi", phone_number="+15551234", email="orders@cafebella.com", delivery_route="Route A - Downtown Core", pricing_tier="Wholesale Tier 1 (-10%)", discount_percentage=10.0, special_instructions="Side door delivery before 5 AM. Gate code: 4421.", enabled_channels="SMS", avg_order_volume=18.0, usual_order_day="Tuesday, Thursday, Saturday")
        c2 = models.Customer(business_id=t1.id, account_number="ACC-1002", business_name="The Daily Grind Cafe", contact_name="Sarah Jenkins", phone_number="+15559876", email="sarah@dailygrind.com", delivery_route="Route B - Uptown / North", pricing_tier="Wholesale Standard", discount_percentage=0.0, special_instructions="Leave delivery on front counter tray.", enabled_channels="SMS, Email", avg_order_volume=22.0, usual_order_day="Monday, Wednesday, Friday")
        c3 = models.Customer(business_id=t1.id, account_number="ACC-1003", business_name="Harbor View Bistro", contact_name="Chef Tony", phone_number="+15554321", email="kitchen@harborview.com", delivery_route="Route A - Downtown Core", pricing_tier="Wholesale VIP (-15%)", discount_percentage=15.0, special_instructions="Chef signature required for delivery receipt.", enabled_channels="SMS, Email", avg_order_volume=14.0, usual_order_day="Tuesday, Friday")
        c4 = models.Customer(business_id=t1.id, account_number="ACC-1004", business_name="Greenwood Espresso Bar", contact_name="David Kim", phone_number="+15556789", email="dave@greenwoodcoffee.com", delivery_route="Route C - Westside Suburbs", pricing_tier="Wholesale Standard", discount_percentage=0.0, special_instructions="Deliver directly to kitchen prep table.", enabled_channels="SMS", avg_order_volume=28.0, usual_order_day="Daily (Mon–Sat)")
        c5 = models.Customer(business_id=t1.id, account_number="ACC-1005", business_name="SoHo Grand Bistro", contact_name="Claire Laurent", phone_number="+15557711", email="purchasing@sohogrand.com", delivery_route="Route A - Downtown Core", pricing_tier="Wholesale VIP (-15%)", discount_percentage=15.0, special_instructions="Service elevator to 2nd floor prep kitchen.", enabled_channels="Email", avg_order_volume=35.0, usual_order_day="Tuesday, Thursday, Saturday")
        c6 = models.Customer(business_id=t1.id, account_number="ACC-1006", business_name="Tribeca Morning Kitchen", contact_name="Paul Miller", phone_number="+15558822", email="paul@tribecakitchen.com", delivery_route="Route A - Downtown Core", pricing_tier="Wholesale Tier 1 (-10%)", discount_percentage=10.0, special_instructions="Leave crates inside vestibule.", enabled_channels="SMS, Email", avg_order_volume=20.0, usual_order_day="Daily")
        db.add_all([c1, c2, c3, c4, c5, c6])
        db.commit()

        # Seed Customer Jargon Memories
        db.add_all([
            models.CustomerLanguageMemory(business_id=t1.id, customer_id=c1.id, phrase="the big bread", mapped_sku="BRD-001", confidence_boost=99, learned_from="Staff Confirmation"),
            models.CustomerLanguageMemory(business_id=t1.id, customer_id=c2.id, phrase="brown loaf", mapped_sku="BRD-004", confidence_boost=98, learned_from="Historical Pattern"),
            models.CustomerLanguageMemory(business_id=t1.id, customer_id=c4.id, phrase="morning rolls", mapped_sku="BRD-006", confidence_boost=97, learned_from="Staff Confirmation")
        ])
        db.commit()

        # Seed Orders with Grounded Operational Scenarios
        now = datetime.utcnow()
        o1 = models.Order(
            business_id=t1.id,
            customer_id=c1.id,
            customer_phone="+15551234",
            customer_name="Cafe Bella",
            channel="SMS",
            raw_message="Hey Tony, need 12 sourdough loaves and 2 dozen croissants for 5am please - Marco",
            status="Approved",
            confirmation_status="Confirmed via SMS",
            confidence_score=98,
            delivery_date="Tomorrow Morning",
            shift="Morning",
            ai_interpretation_summary="Parsed: 12x Country Sourdough Loaf (BRD-001), 24x French Croissant (PST-001). Customer recognized as Cafe Bella with 10% Tier 1 wholesale discount applied.",
            reviewed_by="Alex (Operations)",
            reviewed_at=now - timedelta(minutes=35),
            created_at=now - timedelta(minutes=42)
        )
        o2 = models.Order(
            business_id=t1.id,
            customer_id=c2.id,
            customer_phone="+15559876",
            customer_name="The Daily Grind Cafe",
            channel="SMS",
            raw_message="Same as last Tuesday + 4 baguettes. Thanks! - Sarah",
            status="Sent to Production",
            confirmation_status="Confirmed via SMS",
            confidence_score=96,
            delivery_date="Tomorrow Morning",
            shift="Morning",
            history_cloned=True,
            history_note="Cloned 14 items from previous Tuesday + 4 Baguettes",
            ai_interpretation_summary="Order Memory Activated: Cloned recurring Tuesday batch (10x Sourdough, 4x Seeded Rye) and added +4x French Baguette (BRD-003).",
            reviewed_by="OrderStream Automated Rule",
            reviewed_at=now - timedelta(minutes=20),
            created_at=now - timedelta(minutes=25)
        )
        o3 = models.Order(
            business_id=t1.id,
            customer_id=c3.id,
            customer_phone="+15554321",
            customer_name="Harbor View Bistro",
            channel="Email",
            raw_message="Emergency update: We need 450 sourdough loaves for the harbor festival tomorrow morning.",
            status="Needs Review",
            confirmation_status="Pending Staff Review",
            confidence_score=48,
            delivery_date="Tomorrow Morning",
            shift="Morning",
            is_anomaly=True,
            anomaly_reason="Volume Spike: 450 units is 32x higher than client's average (14 units)",
            ai_interpretation_summary="Unusual Quantity Flag: Parsed 450x Sourdough. 32x volume spike above customer baseline (14 units). Paused for human confirmation.",
            created_at=now - timedelta(minutes=10)
        )
        o4 = models.Order(
            business_id=t1.id,
            customer_id=c5.id,
            customer_phone="+15557711",
            customer_name="SoHo Grand Bistro",
            channel="Email",
            raw_message="PO #8841: 30 French Croissants and 20 Pain au Chocolat for Thursday morning service.",
            status="Approved",
            confirmation_status="Confirmed via Email",
            confidence_score=99,
            delivery_date="Tomorrow Morning",
            shift="Morning",
            ai_interpretation_summary="Parsed: 30x French Croissant (PST-001), 20x Pain au Chocolat (PST-003). VIP 15% discount applied.",
            reviewed_by="Alex (Operations)",
            reviewed_at=now - timedelta(minutes=5),
            created_at=now - timedelta(minutes=8)
        )
        db.add_all([o1, o2, o3, o4])
        db.commit()
        db.refresh(o1); db.refresh(o2); db.refresh(o3); db.refresh(o4)

        # Order Items with Line Totals & Completed Units
        db.add_all([
            # Order 1 (Cafe Bella - 10% off)
            models.OrderItem(order_id=o1.id, product_id=1, matched_sku="BRD-001", item_name="Country Sourdough Loaf 800g", quantity=12, completed_quantity=6, unit_price=6.50, customer_price=5.85, line_total=70.20, match_confidence=98),
            models.OrderItem(order_id=o1.id, product_id=7, matched_sku="PST-001", item_name="All-Butter French Croissant", quantity=24, completed_quantity=24, unit_price=2.80, customer_price=2.52, line_total=60.48, match_confidence=98),
            # Order 2 (Daily Grind - Standard price)
            models.OrderItem(order_id=o2.id, product_id=1, matched_sku="BRD-001", item_name="Country Sourdough Loaf 800g", quantity=10, completed_quantity=10, unit_price=6.50, customer_price=6.50, line_total=65.00, match_confidence=96),
            models.OrderItem(order_id=o2.id, product_id=2, matched_sku="BRD-002", item_name="Traditional Seeded Rye Loaf", quantity=4, completed_quantity=0, unit_price=5.75, customer_price=5.75, line_total=23.00, match_confidence=96),
            models.OrderItem(order_id=o2.id, product_id=3, matched_sku="BRD-003", item_name="Crusty French Baguette 400g", quantity=4, completed_quantity=0, unit_price=3.25, customer_price=3.25, line_total=13.00, match_confidence=98),
            # Order 3 (Harbor View Bistro - VIP 15% off)
            models.OrderItem(order_id=o3.id, product_id=1, matched_sku="BRD-001", item_name="Country Sourdough Loaf 800g", quantity=450, completed_quantity=0, unit_price=6.50, customer_price=5.52, line_total=2484.00, match_confidence=95),
            # Order 4 (SoHo Grand Bistro - VIP 15% off)
            models.OrderItem(order_id=o4.id, product_id=7, matched_sku="PST-001", item_name="All-Butter French Croissant", quantity=30, completed_quantity=15, unit_price=2.80, customer_price=2.38, line_total=71.40, match_confidence=99),
            models.OrderItem(order_id=o4.id, product_id=9, matched_sku="PST-003", item_name="Pain au Chocolat (Dark Chocolate)", quantity=20, completed_quantity=10, unit_price=3.40, customer_price=2.89, line_total=57.80, match_confidence=99)
        ])
        db.commit()

        # Seed Timeline Events
        db.add_all([
            models.OrderTimelineEvent(order_id=o1.id, event_type="Message Received", actor="Customer via SMS", description="Inbound SMS received from +15551234", created_at=o1.created_at),
            models.OrderTimelineEvent(order_id=o1.id, event_type="Customer Identified", actor="OrderStream", description="Matched phone ID to ACC-1001 (Cafe Bella). Applied Tier 1 discount (-10%).", created_at=o1.created_at + timedelta(seconds=2)),
            models.OrderTimelineEvent(order_id=o1.id, event_type="Approved", actor="Staff (Alex)", description="Order reviewed and approved for morning route.", created_at=o1.created_at + timedelta(minutes=5)),
            
            models.OrderTimelineEvent(order_id=o2.id, event_type="Message Received", actor="Customer via SMS", description="Inbound SMS message received from +15559876", created_at=o2.created_at),
            models.OrderTimelineEvent(order_id=o2.id, event_type="Order Memory Activated", actor="OrderStream", description="Recognized 'Same as last Tuesday'. Auto-cloned 14 items from previous batch and added 4x Baguettes.", created_at=o2.created_at + timedelta(seconds=2)),
            models.OrderTimelineEvent(order_id=o2.id, event_type="Sent to Production", actor="OrderStream", description="High confidence recurring order (96%) automatically queued for 3 AM bake.", created_at=o2.created_at + timedelta(minutes=5)),

            models.OrderTimelineEvent(order_id=o3.id, event_type="Message Received", actor="Customer via Email", description="Inbound Email PO received from kitchen@harborview.com", created_at=o3.created_at),
            models.OrderTimelineEvent(order_id=o3.id, event_type="Anomaly Intercepted", actor="OrderStream", description="Volume Spike Anomaly: 450 units is 32x higher than historical average (14 units). Routed to 'Needs Review' queue.", created_at=o3.created_at + timedelta(seconds=3)),

            models.OrderTimelineEvent(order_id=o4.id, event_type="Message Received", actor="Customer via Email", description="Inbound Email received from purchasing@sohogrand.com", created_at=o4.created_at),
            models.OrderTimelineEvent(order_id=o4.id, event_type="Approved", actor="Staff (Alex)", description="Approved for morning bake and delivery Route A.", created_at=o4.created_at + timedelta(minutes=3))
        ])
        db.commit()


