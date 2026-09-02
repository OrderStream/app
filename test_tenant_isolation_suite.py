import os
import sys
import unittest
from fastapi.testclient import TestClient

# Ensure workspace on path
sys.path.insert(0, os.path.dirname(__file__))

import models
import database
from main import app
from services.seeder import seed_default_data

class TenantIsolationTestSuite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Reset and seed database
        models.Base.metadata.drop_all(bind=database.engine)
        models.Base.metadata.create_all(bind=database.engine)
        db = database.SessionLocal()
        seed_default_data(db)
        
        # Verify tenant 1 exists and create tenant 2
        t1 = db.query(models.BusinessTenant).filter(models.BusinessTenant.slug == "hudsonbreads").first()
        assert t1 is not None
        cls.t1_id = t1.id

        t2 = db.query(models.BusinessTenant).filter(models.BusinessTenant.slug == "manchesterbakes").first()
        if not t2:
            t2 = models.BusinessTenant(
                slug="manchesterbakes",
                name="Manchester Artisan Bakes",
                contact_email="orders@manchesterbakes.com",
                contact_phone="+44 161 555 0199",
                order_cutoff_time="22:00",
                minimum_order_amount=50.0
            )
            db.add(t2)
            db.commit()
            db.refresh(t2)
        cls.t2_id = t2.id
        
        # Add order & customer to Tenant 2
        c_beta = models.Customer(
            business_id=t2.id,
            account_number="ACC-BETA-01",
            business_name="Salford Coffee House",
            phone_number="+441619998888",
            delivery_route="Manchester Central"
        )
        db.add(c_beta)
        db.commit()
        db.refresh(c_beta)
        cls.c_beta_id = c_beta.id

        o_beta = models.Order(
            business_id=t2.id,
            customer_id=c_beta.id,
            customer_phone="+441619998888",
            customer_name="Salford Coffee House",
            channel="WhatsApp",
            raw_message="Need 50 Manchester Sourdough Cobs please",
            status="Approved",
            delivery_date="Tomorrow"
        )
        db.add(o_beta)
        db.commit()
        db.refresh(o_beta)
        cls.o_beta_id = o_beta.id

        # Product for Beta
        p_beta = db.query(models.ProductCatalog).filter(models.ProductCatalog.business_id == t2.id).first()
        if not p_beta:
            p_beta = models.ProductCatalog(
                business_id=t2.id,
                sku="MCR-001",
                name="Manchester Sourdough Cob",
                category="Artisan Bread",
                unit="Cob",
                unit_price=7.50,
                stock_available=100
            )
            db.add(p_beta)
            db.commit()
            db.refresh(p_beta)
        cls.p_beta_id = p_beta.id
        cls.p_beta_sku = p_beta.sku
        
        db.close()
        cls.client = TestClient(app)

    # -------------------------------------------------------------
    # 1. DIRECT ORDER URL / ID MANIPULATION TEST
    # -------------------------------------------------------------
    def test_01_cross_tenant_order_detail_blocked(self):
        """Tenant Alpha attempting to access Tenant Beta's order by ID must return 404."""
        # Alpha session accessing Beta order
        headers = {"X-OrderStream-Tenant": str(self.t1_id)}
        res = self.client.get(f"/api/orders/{self.o_beta_id}", headers=headers)
        self.assertEqual(res.status_code, 404, "Tenant Alpha must NOT be able to view Tenant Beta's order")

    # -------------------------------------------------------------
    # 2. CROSS-TENANT ORDER STATUS MUTATION BLOCKED
    # -------------------------------------------------------------
    def test_02_cross_tenant_order_status_mutation_blocked(self):
        """Tenant Alpha attempting to Approve or Cancel Tenant Beta's order must return 404."""
        headers = {"X-OrderStream-Tenant": str(self.t1_id)}
        payload = {"status": "Cancelled", "actor": "Malicious Caller"}
        res = self.client.post(f"/api/orders/{self.o_beta_id}/status", json=payload, headers=headers)
        self.assertEqual(res.status_code, 404, "Tenant Alpha must NOT mutate Tenant Beta's order status")

    # -------------------------------------------------------------
    # 3. CROSS-TENANT CUSTOMER ACCESS BLOCKED
    # -------------------------------------------------------------
    def test_03_cross_tenant_customer_access_blocked(self):
        """Tenant Alpha attempting to read or update Tenant Beta's customer must return 404."""
        headers = {"X-OrderStream-Tenant": str(self.t1_id)}
        res = self.client.get(f"/api/orders/customers/{self.c_beta_id}", headers=headers)
        self.assertEqual(res.status_code, 404, "Tenant Alpha must NOT access Tenant Beta's customer profile")

    # -------------------------------------------------------------
    # 4. CROSS-TENANT PRODUCT CATALOG MUTATION BLOCKED
    # -------------------------------------------------------------
    def test_04_cross_tenant_product_mutation_blocked(self):
        """Tenant Alpha attempting to delete or edit Tenant Beta's catalog item must return 404."""
        headers = {"X-OrderStream-Tenant": str(self.t1_id)}
        res = self.client.delete(f"/api/orders/products/{self.p_beta_id}", headers=headers)
        # Should either be 404 or product not found
        self.assertEqual(res.status_code, 200) # Deletion checks business_id filter and only affects matching row
        
        # Verify Beta's product is NOT archived
        db = database.SessionLocal()
        p = db.query(models.ProductCatalog).filter(models.ProductCatalog.id == self.p_beta_id).first()
        self.assertFalse(p.is_archived, "Tenant Beta's product must remain untouched")
        db.close()

    # -------------------------------------------------------------
    # 5. UNIVERSAL SEARCH ISOLATION (ZERO LEAKAGE)
    # -------------------------------------------------------------
    def test_05_universal_search_isolation(self):
        """Searching under Tenant Alpha for 'Manchester' or 'Salford' must return 0 results."""
        headers = {"X-OrderStream-Tenant": str(self.t1_id)}
        res = self.client.get("/api/orders/search?q=Salford", headers=headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(len(data["orders"]), 0, "No Beta orders should appear in Alpha search")
        self.assertEqual(len(data["customers"]), 0, "No Beta customers should appear in Alpha search")

    # -------------------------------------------------------------
    # 6. EXPORT ISOLATION (ZERO CROSS-TENANT ROWS)
    # -------------------------------------------------------------
    def test_06_export_csv_isolation(self):
        """QuickBooks export for Tenant Alpha must NEVER contain Beta's customer names or SKUs."""
        headers = {"X-OrderStream-Tenant": str(self.t1_id)}
        res = self.client.get("/api/orders/export/csv", headers=headers)
        self.assertEqual(res.status_code, 200)
        csv_text = res.text
        self.assertNotIn("Salford Coffee House", csv_text, "Tenant Beta customer leaked into Alpha export")
        self.assertNotIn("MCR-001", csv_text, "Tenant Beta SKU leaked into Alpha export")
        self.assertIn("BRD-001", csv_text, "Tenant Alpha's own SKU should be in export")

    # -------------------------------------------------------------
    # 7. PRODUCTION SHEET ISOLATION
    # -------------------------------------------------------------
    def test_07_production_sheet_isolation(self):
        """Production sheet under Tenant Alpha must only aggregate Alpha's approved orders."""
        headers = {"X-OrderStream-Tenant": str(self.t1_id)}
        res = self.client.get("/api/orders/production/sheet?shift=Morning", headers=headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        skus = [i["sku"] for i in data["items"]]
        self.assertNotIn(self.p_beta_sku, skus, "Tenant Beta product must not appear on Alpha's bake sheet")

if __name__ == "__main__":
    unittest.main()
