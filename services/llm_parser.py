import os
import json
import re

def parse_order_text(text: str) -> dict:
    text_clean = text.strip()
    
    # 1. Extract Customer / Sender Name
    customer_name = "Unknown Customer"
    name_patterns = [
        r"(?:this is|it's|its|i'm|im)\s+([A-Za-z0-9\s'&]+?)(?:\s+(?:cafe|bistro|bakery|restaurant|bar|kitchen|diner|grind))?(?:[.,\n]|\s+need|\s+order|\s+can|\s+we)",
        r"(?:from|@)\s+([A-Za-z0-9\s'&]+?)(?:[.,\n]|$)",
        r"-\s*([A-Za-z0-9\s'&]+?)$"
    ]
    for pattern in name_patterns:
        match = re.search(pattern, text_clean, re.IGNORECASE)
        if match:
            candidate = match.group(1).strip()
            if len(candidate) > 1 and candidate.lower() not in ["need", "tony", "order", "please"]:
                customer_name = candidate.title()
                break
                
    if customer_name == "Unknown Customer":
        match = re.search(r"(?:The\s+)?([A-Za-z0-9\s'&]+?\s+(?:Cafe|Bistro|Bakery|Kitchen|Diner|Grind))", text_clean, re.IGNORECASE)
        if match:
            customer_name = match.group(1).strip().title()

    # 2. Extract Corrections (e.g. "actually make it 8", "scratch that make it 5")
    correction_pattern = r"(?:actually|scratch that|make that|make it|change to|instead)\s+(?:make it\s+)?(\d+)"
    corrections = re.findall(correction_pattern, text_clean, re.IGNORECASE)
    
    # 3. Word numbers mapping
    word_nums = {
        "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
        "eleven": 11, "twelve": 12, "dozen": 12, "half dozen": 6, "half-dozen": 6
    }
    
    items = []
    captured_ranges = []
    
    # Check for Dozens (e.g. "2 dozen blueberry muffins")
    dozen_matches = re.finditer(r"(\d+|a|one|two|three|four|five|six)\s+dozen\s+([a-zA-Z\s]+?)(?:[.,;]|\s+and\s+|\s+by\s+|\s+for\s+|$)", text_clean, re.IGNORECASE)
    for m in dozen_matches:
        qty_str = m.group(1).lower()
        multiplier = word_nums.get(qty_str, int(qty_str) if qty_str.isdigit() else 1)
        item_raw = m.group(2).strip()
        item_clean = re.sub(r"\b(loaves|loaf|by|for|at|am|pm|tomorrow|morning)\b", "", item_raw, flags=re.IGNORECASE).strip().title()
        if item_clean:
            items.append({"item_name": f"{item_clean} (Dozen)", "quantity": multiplier})
            captured_ranges.append(m.span())

    # Check for Standard quantities (e.g. "6 sourdough loaves", "10 croissants")
    std_matches = re.finditer(r"(\d+)\s+([a-zA-Z\s]+?)(?:[.,;]|\s+and\s+|\s+actually|\s+scratch|\s+by\s+|\s+for\s+|$)", text_clean, re.IGNORECASE)
    for m in std_matches:
        if any(start <= m.start() <= end for start, end in captured_ranges):
            continue
            
        qty = int(m.group(1))
        item_raw = m.group(2).strip()
        
        # Apply corrections if mentioned nearby
        if "actually" in text_clean[m.end():m.end()+40].lower() or "scratch" in text_clean[m.end():m.end()+40].lower():
            if corrections:
                qty = int(corrections[0])
                
        item_clean = re.sub(r"\b(loaves|loaf|by|for|at|am|pm|tomorrow|morning|actually|scratch|make|it)\b", "", item_raw, flags=re.IGNORECASE).strip().title()
        
        if item_clean and item_clean.lower() not in ["am", "pm", "dozen", "and", "by", "morning", "night"]:
            if not any(i["item_name"].lower() == item_clean.lower() for i in items):
                items.append({"item_name": item_clean, "quantity": qty})

    if not items:
        # Fallback simple extractor
        words = text_clean.replace(",", " ").split()
        for i in range(len(words)-1):
            if words[i].isdigit():
                q = int(words[i])
                it = words[i+1].title()
                if it.lower() not in ["am", "pm", "and", "by"]:
                    items.append({"item_name": it, "quantity": q})

    return {
        "customer_name": customer_name,
        "status": "Parsed" if items else "Needs Review",
        "items": items
    }
