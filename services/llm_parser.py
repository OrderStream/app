import os
import json
from dotenv import dotenv_values

# Force explicit path to .env
env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
env_vars = dotenv_values(env_path)

try:
    import google.generativeai as genai
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False

def parse_order_text(text: str) -> dict:
    api_key = env_vars.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")
    
    if not HAS_GENAI or not api_key:
        debug_info = f"Mock Fallback (GenAI: {HAS_GENAI}, Key: {'Present' if api_key else 'Missing'})"
        print(f"WARNING: GEMINI_API_KEY not found or google-generativeai not installed. {debug_info}")
        mock_result = mock_parse_order_text(text)
        mock_result["customer_name"] = debug_info
        return mock_result
        
    genai.configure(api_key=api_key)

    system_instruction = """
    You are an AI order extraction assistant for a B2B wholesale bakery/roaster. 
    Your job is to read messy SMS text messages from chefs/buyers and extract the order into a strict JSON format.
    
    Rules:
    1. Identify the 'customer_name' (usually at the end, e.g., 'from Cafe Bella' or '- Tony'). If unknown, use 'Unknown'.
    2. Extract each item requested and its exact numerical quantity.
    3. Determine a 'status': use 'Parsed' if you are confident in the extraction, use 'Needs Review' if the text is confusing, ambiguous, or lacks quantities.
    
    Output EXACTLY this JSON schema:
    {
        "customer_name": "string",
        "status": "Parsed" | "Needs Review",
        "items": [
            {"item_name": "string", "quantity": integer}
        ]
    }
    """
    
    try:
        model = genai.GenerativeModel(
            model_name="gemini-3.6-flash",
            system_instruction=system_instruction,
            generation_config={"response_mime_type": "application/json"}
        )

        
        response = model.generate_content(text)
        parsed_data = json.loads(response.text)
        return parsed_data
        
    except Exception as e:
        print(f"LLM Parsing Error: {e}")
        return {
            "customer_name": "Parsing Failed",
            "status": "Needs Review",
            "items": []
        }

def mock_parse_order_text(text: str) -> dict:
    """Original mock parser for testing without an API key."""
    text_lower = text.lower()
    items = []
    customer_name = "Unknown Customer"
    
    if "-" in text:
        parts = text.split("-")
        customer_name = parts[-1].strip().title()
        order_part = parts[0]
    else:
        order_part = text
        
    words = order_part.replace(",", " ").split()
    for i in range(len(words)-1):
        if words[i].isdigit():
            qty = int(words[i])
            item = words[i+1]
            items.append({"item_name": item.title(), "quantity": qty})
            
    if not items:
        return {
            "customer_name": "Cafe Mock",
            "items": [
                {"item_name": "Sourdough Loaf", "quantity": 5},
                {"item_name": "Rye Bread", "quantity": 2}
            ],
            "status": "Needs Review"
        }
        
    return {
        "customer_name": customer_name,
        "items": items,
        "status": "Parsed"
    }
