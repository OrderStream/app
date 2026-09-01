import re
from sqlalchemy.orm import Session
import models

def match_or_create_customer(db: Session, phone: str, extracted_name: str = None, business_id: int = 1) -> models.Customer:
    """
    Look up customer by phone number within the business tenant.
    """
    clean_phone = re.sub(r"[^\d+]", "", phone.strip())
    customer = db.query(models.Customer).filter(
        models.Customer.business_id == business_id,
        models.Customer.phone_number == clean_phone
    ).first()
    
    if not customer:
        count = db.query(models.Customer).filter(models.Customer.business_id == business_id).count() + 1001
        acc_num = f"ACC-{count}"
        name = extracted_name if (extracted_name and extracted_name != "Unknown Customer") else f"Client {clean_phone[-4:]}"
        
        customer = models.Customer(
            business_id=business_id,
            account_number=acc_num,
            business_name=name,
            contact_name=extracted_name or "Manager",
            phone_number=clean_phone,
            delivery_route="Route A - Downtown Core",
            pricing_tier="Wholesale Standard",
            avg_order_volume=18.0
        )
        db.add(customer)
        db.commit()
        db.refresh(customer)
    elif extracted_name and customer.business_name.startswith("Client ") and extracted_name != "Unknown Customer":
        customer.business_name = extracted_name
        db.commit()
        db.refresh(customer)
        
    return customer

def match_product_sku(db: Session, raw_item_name: str, business_id: int = 1):
    """
    Fuzzy match natural language item name to the business's official Product Catalog & SKU.
    """
    raw_lower = raw_item_name.lower().strip()
    products = db.query(models.ProductCatalog).filter(models.ProductCatalog.business_id == business_id).all()
    
    best_match = None
    highest_score = 0
    
    for prod in products:
        prod_name_lower = prod.name.lower()
        aliases = [a.strip().lower() for a in (prod.aliases or "").split(",") if a.strip()]
        all_terms = [prod_name_lower, prod.sku.lower()] + aliases
        
        if raw_lower in all_terms or any(term == raw_lower for term in all_terms):
            return prod, 98
            
        for term in all_terms:
            if term and (term in raw_lower or raw_lower in term):
                score = 85
                if score > highest_score:
                    highest_score = score
                    best_match = prod
                    
        raw_words = set(re.findall(r"\w+", raw_lower))
        for term in all_terms:
            term_words = set(re.findall(r"\w+", term))
            overlap = raw_words.intersection(term_words)
            if overlap:
                score = 70 + (len(overlap) * 5)
                if score > highest_score:
                    highest_score = score
                    best_match = prod

    if best_match and highest_score >= 70:
        return best_match, min(highest_score, 95)
        
    return None, 40

def generate_confirmation_sms(customer_name: str, items: list, total_amount: float = 0.0) -> str:
    """
    Generates structured two-way SMS confirmation text.
    """
    item_summary = ", ".join([f"{item['quantity']}x {item['item_name']}" for item in items])
    if total_amount > 0:
        return f"OrderStream: Received order for {customer_name}: [{item_summary}]. Total: ${total_amount:.2f}. Reply YES to confirm."
    return f"OrderStream: Received order for {customer_name}: [{item_summary}]. Reply YES to confirm."
