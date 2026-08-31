from sqlalchemy.orm import Session
import models

def seed_default_data(db: Session):
    """
    Populates standard bakery product catalog, customer directory, and language memory.
    """
    # 1. Seed Products
    if db.query(models.ProductCatalog).count() == 0:
        sample_products = [
            models.ProductCatalog(
                sku="BRD-001",
                name="Country Sourdough Loaf 800g",
                category="Artisan Bread",
                unit="Loaf",
                unit_price=6.50,
                aliases="sourdough, country sourdough, sourdough loaf, sour dough, white sourdough",
                stock_available=150
            ),
            models.ProductCatalog(
                sku="BRD-002",
                name="Traditional Seeded Rye Loaf",
                category="Artisan Bread",
                unit="Loaf",
                unit_price=5.75,
                aliases="rye, rye bread, dark rye, seeded rye, caraway rye",
                stock_available=80
            ),
            models.ProductCatalog(
                sku="PST-001",
                name="All-Butter French Croissant",
                category="Pastries",
                unit="Each",
                unit_price=2.80,
                aliases="croissant, croissants, butter croissant, french croissant",
                stock_available=200
            ),
            models.ProductCatalog(
                sku="PST-002",
                name="Blueberry Streusel Muffins (Dozen)",
                category="Pastries",
                unit="Dozen",
                unit_price=28.00,
                aliases="muffins, blueberry muffin, blueberry muffins, blueberry muffins (dozen), muffin, dozen muffins",
                stock_available=40
            ),
            models.ProductCatalog(
                sku="BRD-003",
                name="Traditional Crusty Baguette",
                category="Artisan Bread",
                unit="Each",
                unit_price=3.25,
                aliases="baguette, baguettes, french baguette, stick bread",
                stock_available=120
            ),
            models.ProductCatalog(
                sku="BRD-004",
                name="Whole Wheat Farmhouse Loaf",
                category="Artisan Bread",
                unit="Loaf",
                unit_price=5.50,
                aliases="whole wheat, wheat bread, brown bread, wholemeal, wheat loaf",
                stock_available=90
            ),
        ]
        for p in sample_products:
            db.add(p)
        db.commit()
            
    # 2. Seed Customers
    if db.query(models.Customer).count() == 0:
        c1 = models.Customer(
            account_number="ACC-1001",
            business_name="Cafe Bella",
            contact_name="Marco Rossi",
            phone_number="+15551234",
            email="orders@cafebella.com",
            delivery_route="Route A - Downtown Core",
            pricing_tier="Wholesale Tier 1 (-10%)",
            avg_order_volume=16.0
        )
        c2 = models.Customer(
            account_number="ACC-1002",
            business_name="The Daily Grind Cafe",
            contact_name="Sarah Jenkins",
            phone_number="+15559876",
            email="sarah@dailygrind.com",
            delivery_route="Route B - Uptown / North",
            pricing_tier="Wholesale Standard",
            avg_order_volume=20.0
        )
        c3 = models.Customer(
            account_number="ACC-1003",
            business_name="Harbor View Bistro",
            contact_name="Chef Tony",
            phone_number="+15554321",
            email="kitchen@harborview.com",
            delivery_route="Route A - Downtown Core",
            pricing_tier="Wholesale VIP (-15%)",
            avg_order_volume=12.0
        )
        db.add_all([c1, c2, c3])
        db.commit()

        # 3. Seed Customer Language Memory (Jargon & Nicknames)
        db.add_all([
            models.CustomerLanguageMemory(
                customer_id=c1.id,
                phrase="the big bread",
                mapped_sku="BRD-001",
                confidence_boost=99,
                learned_from="Human Staff Correction"
            ),
            models.CustomerLanguageMemory(
                customer_id=c2.id,
                phrase="brown loaf",
                mapped_sku="BRD-004",
                confidence_boost=98,
                learned_from="Historical Pattern"
            )
        ])
        
        # 4. Seed initial historical order for Cafe Bella to enable "Same as last time" testing
        past_order = models.Order(
            customer_id=c1.id,
            customer_phone="+15551234",
            customer_name="Cafe Bella",
            channel="SMS",
            raw_message="10 sourdough and 6 croissants for Monday - Marco",
            status="Exported",
            confirmation_status="Confirmed via SMS",
            confidence_score=98,
            delivery_date="Yesterday (5:00 AM)"
        )
        db.add(past_order)
        db.commit()
        db.refresh(past_order)
        
        db.add_all([
            models.OrderItem(order_id=past_order.id, product_id=1, matched_sku="BRD-001", item_name="Country Sourdough Loaf 800g", quantity=10, unit_price=6.50, line_total=65.00),
            models.OrderItem(order_id=past_order.id, product_id=3, matched_sku="PST-001", item_name="All-Butter French Croissant", quantity=6, unit_price=2.80, line_total=16.80)
        ])
        db.commit()
