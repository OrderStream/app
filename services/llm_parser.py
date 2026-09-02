import os
import json
import re
from dotenv import dotenv_values

# Explicit path to .env
env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
env_vars = dotenv_values(env_path)
api_key = env_vars.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")

gemini_model = None
if api_key:
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        for model_name in ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-flash-latest"]:
            try:
                gemini_model = genai.GenerativeModel(model_name)
                break
            except Exception:
                continue
    except Exception:
        gemini_model = None

def parse_with_gemini(text: str) -> dict:
    """Uses Google Gemini API to extract complex customer orders, corrections, and slang."""
    if not gemini_model:
        return None
        
    prompt = f"""You are an expert AI order clerk for wholesale bakeries.
Extract the customer name and ordered line items from this inbound text message.
Handle natural language corrections (e.g., 'actually make it 8', 'scratch that'), dozen conversions (1 dozen = 12), and customer nicknames.

Inbound Text:
"{text}"

Return ONLY a valid JSON object with this exact structure:
{{
  "customer_name": "Extracted Name or Unknown Customer",
  "status": "Parsed",
  "items": [
    {{"item_name": "Item Description", "quantity": 10}}
  ]
}}"""

    try:
        response = gemini_model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        data = json.loads(response.text)
        if "items" in data and len(data["items"]) > 0:
            return data
    except Exception as e:
        print(f"Gemini API Notice: {e}. Falling back to local NLP engine.")
    return None

def parse_order_text(text: str) -> dict:
    """
    Dual-Engine Order Parser:
    1. Tries Google Gemini API for deep reasoning and complex context if API key is active.
    2. Uses high-speed local NLP engine (0ms, $0 cost) for instant resilient parsing.
    """
    text_clean = text.strip()
    
    # 1. Try Gemini API first if configured
    if gemini_model:
        gemini_result = parse_with_gemini(text_clean)
        if gemini_result:
            return gemini_result

    # 2. Resilient High-Speed Local NLP Engine
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

    correction_pattern = r"(?:actually|scratch that|make that|make it|change to|instead)\s+(?:make it\s+)?(\d+)"
    corrections = re.findall(correction_pattern, text_clean, re.IGNORECASE)
    
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
        
        if "actually" in text_clean[m.end():m.end()+40].lower() or "scratch" in text_clean[m.end():m.end()+40].lower():
            if corrections:
                qty = int(corrections[0])
                
        item_clean = re.sub(r"\b(loaves|loaf|by|for|at|am|pm|tomorrow|morning|actually|scratch|make|it)\b", "", item_raw, flags=re.IGNORECASE).strip().title()
        
        if item_clean and item_clean.lower() not in ["am", "pm", "dozen", "and", "by", "morning", "night"]:
            if not any(i["item_name"].lower() == item_clean.lower() for i in items):
                items.append({"item_name": item_clean, "quantity": qty})

    if not items:
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
