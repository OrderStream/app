import os
import sys
import unittest
from datetime import datetime, timedelta

# Ensure workspace is on sys.path
sys.path.insert(0, os.path.dirname(__file__))

import models
from database import SessionLocal, engine
from services.seeder import seed_default_data
from services.llm_parser import parse_order_text
from services.matcher import match_or_create_customer, match_product_sku
from services.intelligence import process_order_intelligence, record_human_correction_learning

class OrderStreamPilotTestSuite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["ORDERSTREAM_TEST_ENV"] = "true"
        # Reset and seed test database
        models.Base.metadata.drop_all(bind=engine)
        models.Base.metadata.create_all(bind=engine)
        db = SessionLocal()
        seed_default_data(db)
        db.close()

        from fastapi.testclient import TestClient
        from main import app
        cls.client = TestClient(app)

    def setUp(self):
        self.db = SessionLocal()
        self.business = self.db.query(models.BusinessTenant).filter(models.BusinessTenant.id == 1).first()

    def tearDown(self):
        self.db.close()

    # -------------------------------------------------------------
    # 1. NORMAL CLEAR ORDER PARSING & SKU MATCHING
    # -------------------------------------------------------------
    def test_01_normal_order_parsing(self):
        msg = "Need 10 sourdough loaves and 6 baguettes for Cafe Bella"
        parsed = parse_order_text(msg)
        self.assertEqual(len(parsed["items"]), 2)
        
        customer = match_or_create_customer(self.db, "+15551234", "Cafe Bella", business_id=1)
        intel = process_order_intelligence(self.db, self.business, customer, msg, parsed["items"])
        
        self.assertEqual(len(intel["items"]), 2)
        skus = [i["matched_sku"] for i in intel["items"]]
        self.assertIn("BRD-001", skus) # Country Sourdough
        self.assertIn("BRD-003", skus) # Traditional Baguette
        self.assertFalse(intel["is_anomaly"])
        self.assertGreaterEqual(intel["confidence_score"], 80)

    # -------------------------------------------------------------
    # 2. "SAME AS LAST WEEK" ORDER MEMORY CLONING
    # -------------------------------------------------------------
    def test_02_repeat_order_memory_cloning(self):
        customer = self.db.query(models.Customer).filter(models.Customer.phone_number == "+15551234").first()
        msg = "Same as last week + 4 baguettes please"
        parsed = parse_order_text(msg)
        intel = process_order_intelligence(self.db, self.business, customer, msg, parsed["items"])
        
        self.assertTrue(intel["history_cloned"])
        self.assertIn("Auto-cloned", intel["history_note"])
        self.assertGreater(len(intel["items"]), 0)

    # -------------------------------------------------------------
    # 3. CUSTOMER JARGON / NICKNAME ("THE BIG BREAD")
    # -------------------------------------------------------------
    def test_03_customer_jargon_mapping(self):
        customer = self.db.query(models.Customer).filter(models.Customer.phone_number == "+15551234").first()
        msg = "Send 8 of the big bread please"
        parsed = parse_order_text(msg)
        intel = process_order_intelligence(self.db, self.business, customer, msg, parsed["items"])
        
        matched_item = next((i for i in intel["items"] if i["matched_sku"] == "BRD-001"), None)
        self.assertIsNotNone(matched_item)
        self.assertEqual(matched_item["matched_sku"], "BRD-001")
        self.assertEqual(matched_item["match_confidence"], 99)

    # -------------------------------------------------------------
    # 4. UNKNOWN PRODUCT HANDLING (ROUTED TO REVIEW)
    # -------------------------------------------------------------
    def test_04_unknown_product_safety(self):
        customer = self.db.query(models.Customer).filter(models.Customer.phone_number == "+15551234").first()
        msg = "Need 15 alien spaceship cakes"
        parsed = parse_order_text(msg)
        intel = process_order_intelligence(self.db, self.business, customer, msg, parsed["items"])
        
        self.assertTrue(intel["is_anomaly"])
        self.assertEqual(intel["status"], "Needs Review")
        self.assertLess(intel["confidence_score"], 70)

    # -------------------------------------------------------------
    # 5. BUSINESS BRAIN FAQ INQUIRIES (NO FAKE ORDER)
    # -------------------------------------------------------------
    def test_05_faq_inquiry_handler(self):
        customer = self.db.query(models.Customer).filter(models.Customer.phone_number == "+15551234").first()
        msg = "What is your order cutoff time tonight?"
        parsed = parse_order_text(msg)
        intel = process_order_intelligence(self.db, self.business, customer, msg, parsed["items"])
        
        self.assertTrue(intel["is_inquiry"])
        self.assertIn("cutoff", intel["ai_clarification"].lower())
        self.assertEqual(len(intel["items"]), 0)

    # -------------------------------------------------------------
    # 6. 500X QUANTITY ANOMALY PROTECTION
    # -------------------------------------------------------------
    def test_06_500x_anomaly_detection(self):
        customer = self.db.query(models.Customer).filter(models.Customer.phone_number == "+15554321").first() # avg: 14 units
        msg = "Need 500 sourdough loaves for morning"
        parsed = parse_order_text(msg)
        intel = process_order_intelligence(self.db, self.business, customer, msg, parsed["items"])
        
        self.assertTrue(intel["is_anomaly"])
        self.assertIn("Volume Spike", intel["anomaly_reason"])
        self.assertEqual(intel["status"], "Needs Review")

    # -------------------------------------------------------------
    # 7. DUPLICATE ORDER INTERCEPTOR
    # -------------------------------------------------------------
    def test_07_duplicate_order_detection(self):
        customer = self.db.query(models.Customer).filter(models.Customer.phone_number == "+15551234").first()
        msg = "12 sourdough loaves and 2 dozen croissants"
        parsed = parse_order_text(msg)
        intel = process_order_intelligence(self.db, self.business, customer, msg, parsed["items"])
        
        # O1 in seeder has identical SKUs for Cafe Bella within last 60 mins
        self.assertTrue(intel["is_duplicate"])
        self.assertEqual(intel["status"], "Needs Review")

    # -------------------------------------------------------------
    # 8. CUSTOMER-SPECIFIC PRICING DISCOUNTS
    # -------------------------------------------------------------
    def test_08_customer_pricing_discounts(self):
        c1 = self.db.query(models.Customer).filter(models.Customer.business_name == "Cafe Bella").first()
        self.assertEqual(c1.discount_percentage, 10.0) # 10% off
        
        c3 = self.db.query(models.Customer).filter(models.Customer.business_name == "Harbor View Bistro").first()
        self.assertEqual(c3.discount_percentage, 15.0) # 15% off VIP

    # -------------------------------------------------------------
    # 9. KITCHEN BAKE SHEET AGGREGATION (APPROVED ONLY)
    # -------------------------------------------------------------
    def test_09_kitchen_sheet_aggregation(self):
        from routers.orders import get_kitchen_production_sheet
        sheet = get_kitchen_production_sheet(business_id=1, db=self.db)
        
        self.assertGreater(len(sheet), 0)
        for row in sheet:
            self.assertIn("sku", row)
            self.assertIn("total_quantity", row)
            self.assertGreater(row["total_quantity"], 0)

    # -------------------------------------------------------------
    # 10. MULTI-TENANT DATA ISOLATION (BUSINESS A vs BUSINESS B)
    # -------------------------------------------------------------
    def test_10_multi_tenant_isolation(self):
        # Create Business B
        b2 = models.BusinessTenant(
            slug="manchesterbakes",
            name="Manchester Artisan Bakes",
            order_cutoff_time="22:00",
            minimum_order_amount=50.0
        )
        self.db.add(b2)
        self.db.commit()
        self.db.refresh(b2)
        
        # Add Product to Business B
        p2 = models.ProductCatalog(
            business_id=b2.id,
            sku="MCR-001",
            name="Manchester Sourdough",
            unit_price=7.00
        )
        self.db.add(p2)
        self.db.commit()
        
        # Query Business A catalog - MCR-001 MUST NOT appear
        b1_products = self.db.query(models.ProductCatalog).filter(models.ProductCatalog.business_id == 1).all()
        b1_skus = [p.sku for p in b1_products]
        self.assertNotIn("MCR-001", b1_skus)
        
        # Query Business B catalog - Only MCR-001 appears
        b2_products = self.db.query(models.ProductCatalog).filter(models.ProductCatalog.business_id == b2.id).all()
        b2_skus = [p.sku for p in b2_products]
        self.assertIn("MCR-001", b2_skus)
        self.assertNotIn("BRD-001", b2_skus)

    def test_11_duplicate_webhook_integrity(self):
        """Phase 5: Prevent duplicate order processing on identical webhooks."""
        payload = {
            "From": "+15551234",
            "Body": "Need 5 loaves of sourdough",
            "To": "+18885550000",
            "MessageSid": "SM_INTEGRITY_TEST_1",
            "Channel": "SMS"
        }

        # Disable Twilio signature check for this test
        os.environ.pop("TWILIO_AUTH_TOKEN", None)

        # First request should succeed and create the order
        res1 = self.client.post("/api/webhook/twilio", data=payload)
        self.assertEqual(res1.status_code, 200)

        initial_order_count = self.db.query(models.Order).count()

        # Second request with same MessageSid should be caught by idempotency
        res2 = self.client.post("/api/webhook/twilio", data=payload)
        self.assertEqual(res2.status_code, 200)
        self.assertIn(b"already received", res2.content)

        # Order count should NOT increase
        final_order_count = self.db.query(models.Order).count()
        self.assertEqual(initial_order_count, final_order_count)

    def test_12_ai_failure_fallback(self):
        """Phase 3: Ensure AI parsing failure doesn't silently drop the inbound message."""
        payload = {
            "From": "+15551234",
            "Body": "Fail the AI please",
            "To": "+18885550000",
            "MessageSid": "SM_FAIL_TEST_1",
            "Channel": "SMS"
        }

        os.environ.pop("TWILIO_AUTH_TOKEN", None)

        # Force the parse function to fail by patching it or passing bad data
        # We simulate this by having the AI throw an exception, let's mock it
        from unittest.mock import patch
        with patch('routers.webhook.parse_order_text', side_effect=Exception("Mocked AI Timeout")):
            res = self.client.post("/api/webhook/twilio", data=payload)

        self.assertEqual(res.status_code, 200)

        # Verify order was still created in Needs Review state
        order = self.db.query(models.Order).filter(models.Order.raw_message == "Fail the AI please").first()
        self.assertIsNotNone(order)
        self.assertEqual(order.status, "Needs Review")
        self.assertTrue(order.is_anomaly)
        self.assertEqual(order.confidence_score, 0)
        self.assertIn("Mocked AI Timeout", order.timeline[0].description)

if __name__ == "__main__":
    unittest.main()
