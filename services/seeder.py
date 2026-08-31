from sqlalchemy.orm import Session
import models

def seed_default_data(db: Session):
    """
    Populates standard bakery product catalog and demo customer directory if empty.
    """
    # Seed Products
    if db.query(models.ProductCatalog).count() == 0:
        sample_products = [
            models.ProductCatalog(
                sku="BRD-001",
                name="Country Sourdough Loaf 800g",
                category="Artisan Bread",
                unit="Loaf",
                unit_price=6.50,
                aliases="sourdough, country sourdough, sourdough loaf, sour dough, white sourdough"
            ),
            models.ProductCatalog(
                sku="BRD-002",
                name="Traditional Seeded Rye Loaf",
                category="Artisan Bread",
                unit="Loaf",
                unit_price=5.75,
                aliases="rye, rye bread, dark rye, seeded rye, caraway rye"
            ),
            models.ProductCatalog(
                sku="PST-001",
                name="All-Butter French Croissant",
                category="Pastries",
                unit="Each",
                unit_price=2.80,
                aliases="croissant, croissants, butter croissant, french croissant"
            ),
            models.ProductCatalog(
                sku="PST-002",
                name="Blueberry Streusel Muffins (Dozen)",
                category="Pastries",
                unit="Dozen",
                unit_price=28.00,
                aliases="muffins, blueberry muffin, blueberry muffins, blueberry muffins (dozen), muffin, dozen muffins"
            ),
            models.ProductCatalog(
                sku="BRD-003",
                name="Traditional Crusty Baguette",
                category="Artisan Bread",
                unit="Each",
                unit_price=3.25,
                aliases="baguette, baguettes, french baguette, stick bread"
            ),
            models.ProductCatalog(
                sku="BRD-004",
                name="Whole Wheat Farmhouse Loaf",
                category="Artisan Bread",
                unit="Loaf",
                unit_price=5.50,
                aliases="whole wheat, wheat bread, brown bread, wholemeal, wheat loaf"
            ),
        ]
        for p in sample_products:
            db.add(p)
            
    # Seed Demo Customers
    if db.query(models.Customer).count() == 0:
        sample_customers = [
            models.Customer(
                account_number="ACC-1001",
                business_name="Cafe Bella",
                contact_name="Marco Rossi",
                phone_number="+15551234",
                delivery_route="Route A - Downtown Core",
                pricing_tier="Wholesale Tier 1 (-10%)"
            ),
            models.Customer(
                account_number="ACC-1002",
                business_name="The Daily Grind Cafe",
                contact_name="Sarah Jenkins",
                phone_number="+15559876",
                delivery_route="Route B - Uptown / North",
                pricing_tier="Wholesale Standard"
            ),
            models.Customer(
                account_number="ACC-1003",
                business_name="Harbor View Bistro",
                contact_name="Chef Tony",
                phone_number="+15554321",
                delivery_route="Route A - Downtown Core",
                pricing_tier="Wholesale VIP (-15%)"
            )
        ]
        for c in sample_customers:
            db.add(c)
            
    db.commit()
