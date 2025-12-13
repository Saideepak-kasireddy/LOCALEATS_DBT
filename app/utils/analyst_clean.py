"""
Unified Query Analyst - Clean Version
Extracts ALL query information in one LLM call
NO conversation history pollution - only analyzes current query
"""
import json
import streamlit as st
from utils.cortex_helper import call_cortex

def _clean_json(text: str) -> str:
    """Remove markdown fences from JSON"""
    if not text:
        return ""
    t = text.strip()
    if "```json" in t:
        t = t.split("```json", 1)[1].split("```", 1)[0]
    elif "```" in t:
        t = t.split("```", 1)[1].split("```", 1)[0]
    return t.strip()


def analyze_query_to_json(user_query: str) -> dict:
    """
    Single LLM call to extract everything from user query
    
    IMPORTANT: Only analyzes CURRENT query, NOT conversation history!
    
    Returns structured data:
    {
        "cuisine": str | null,
        "location": {
            "name": str | null,
            "mode": "include_strict" | "include_nearby" | "exclude" | "none",
            "radius_miles": float | null
        },
        "budget": {
            "max_price_level": 1-4 | null,
            "max_dollars": int | null
        },
        "open_now": bool | null,
        "filters": {
            "dietary": [],
            "meal_time": [],
            "accessibility": [],
            "service_type": [],
            "special_needs": []
        }
    }
    """
    
    prompt = f"""You are a query analyst for a Boston restaurant system.

Analyze ONLY the current query below. Do NOT assume filters from context.

Query: "{user_query}"

Extract structured information. Respond with ONLY valid JSON:

{{
  "cuisine": "Mexican" | "Italian" | "Pizza" | null,
  "location": {{
    "name": "fenway" | "mit" | "harvard" | "roxbury" | null,
    "mode": "include_strict" | "include_nearby" | "exclude" | "none",
    "radius_miles": 1.5 | null
  }},
  "budget": {{
    "max_price_level": 1 | 2 | 3 | 4 | null,
    "max_dollars": number | null
  }},
  "open_now": true | false | null,
  "filters": {{
    "dietary": ["vegetarian", "vegan"],
    "meal_time": ["breakfast", "lunch", "dinner"],
    "accessibility": ["wheelchair", "groups", "children"],
    "service_type": ["outdoor", "takeout", "delivery", "reservations"],
    "special_needs": ["pet_friendly", "coffee_shop", "live_music"]
  }}
}}

RULES:

1) LOCATION MODE (detect from prepositions):
   - "IN fenway" | "AT fenway" → mode: "include_strict"
   - "NEAR fenway" | "AROUND fenway" | "BY fenway" → mode: "include_nearby", radius_miles: 1.5
   - "NOT IN fenway" | "EXCLUDING fenway" → mode: "exclude"
   - No location mentioned → mode: "none"

2) CUISINE:
   - Extract cuisine type if mentioned
   - "mexican", "italian", "pizza", "chinese", etc.
   - null if not specified

3) BUDGET:
   - "cheap" → max_price_level: 2
   - "$" → 1, "$$" → 2, "$$$" → 3, "$$$$" → 4
   - "under $20" → max_dollars: 20
   - "expensive" | "costly" → max_price_level: 4

4) OPEN NOW:
   - "open now" | "currently open" → true
   - Otherwise null

5) FILTERS (extract ONLY if mentioned in THIS query):
   - "vegetarian" | "vegan" → dietary
   - "breakfast" | "lunch" | "dinner" → meal_time
   - "wheelchair" | "accessible" → accessibility: ["wheelchair"]
   - "groups" | "group" → accessibility: ["groups"]
   - "kids" | "children" | "family" → accessibility: ["children"]
   - "outdoor" | "patio" → service_type: ["outdoor"]
   - "takeout" | "to-go" → service_type: ["takeout"]
   - "delivery" → service_type: ["delivery"]
   - "reservations" → service_type: ["reservations"]
   - "pet friendly" | "dog friendly" → special_needs: ["pet_friendly"]
   - "cafe" | "coffee shop" → special_needs: ["coffee_shop"]
   - "live music" → special_needs: ["live_music"]


CRITICAL: Extract filters ONLY from the current query text.
If query says "mexican food", extract cuisine but NO filters.
If query says "mexican food for groups", extract cuisine AND accessibility: ["groups"].

Examples:

"cheap vegetarian mexican near MIT"
→ {{"cuisine": "Mexican", "budget": {{"max_price_level": 2}}, "location": {{"name": "mit", "mode": "include_nearby", "radius_miles": 1.5}}, "filters": {{"dietary": ["vegetarian"]}}}}

"pizza in fenway"
→ {{"cuisine": "Pizza", "location": {{"name": "fenway", "mode": "include_strict"}}, "filters": {{}}}}

"italian NOT in downtown"
→ {{"cuisine": "Italian", "location": {{"name": "downtown", "mode": "exclude"}}, "filters": {{}}}}

"pet friendly cafe"
→ {{"filters": {{"special_needs": ["pet_friendly", "coffee_shop"]}}}}

JSON only. No other text."""
    
    raw = call_cortex(prompt, temperature=0.2)  # Low temp for consistency
    
    if not raw:
        # Return empty structure
        return _get_empty_analysis()
    
    try:
        txt = _clean_json(raw)
        analysis = json.loads(txt)
        
        # Validate and fill defaults
        analysis = _fill_defaults(analysis)
        
        # Show what was extracted
        _display_extraction(analysis)
        
        return analysis
        
    except Exception as e:
        st.warning(f"Could not parse analyst output, using defaults")
        return _get_empty_analysis()


def _get_empty_analysis() -> dict:
    """Return empty analysis structure"""
    return {
        "cuisine": None,
        "location": {
            "name": None,
            "mode": "none",
            "radius_miles": None
        },
        "budget": {
            "max_price_level": None,
            "max_dollars": None
        },
        "open_now": None,
        "filters": {
            "dietary": [],
            "meal_time": [],
            "accessibility": [],
            "service_type": [],
            "special_needs": []
        }
    }


def _fill_defaults(analysis: dict) -> dict:
    """Ensure all required fields exist"""
    analysis.setdefault("cuisine", None)
    
    analysis.setdefault("location", {})
    analysis["location"].setdefault("name", None)
    analysis["location"].setdefault("mode", "none")
    analysis["location"].setdefault("radius_miles", None)
    
    analysis.setdefault("budget", {})
    analysis["budget"].setdefault("max_price_level", None)
    analysis["budget"].setdefault("max_dollars", None)
    
    analysis.setdefault("open_now", None)
    
    analysis.setdefault("filters", {})
    for key in ["dietary", "meal_time", "accessibility", "service_type", "special_needs"]:
        analysis["filters"].setdefault(key, [])
        if analysis["filters"][key] is None:
            analysis["filters"][key] = []
    
    return analysis


def _display_extraction(analysis: dict):
    """Show what analyst extracted"""
    
    # Show cuisine
    if analysis.get("cuisine"):
        st.info(f"🎯 Cuisine: {analysis['cuisine']}")
    
    # Show location
    location_info = analysis.get("location", {})
    if location_info.get("name") and location_info.get("mode") != "none":
        mode_text = {
            "include_strict": "IN (strict)",
            "include_nearby": f"NEAR (within {location_info.get('radius_miles', 1.5)} mi)",
            "exclude": "NOT IN (excluding)"
        }
        mode_display = mode_text.get(location_info["mode"], "")
        st.info(f"📍 Location: {location_info['name'].title()} - {mode_display}")
    
    # Show budget
    budget = analysis.get("budget", {})
    if budget.get("max_price_level"):
        st.info(f"💰 Budget: {'$' * budget['max_price_level']} or less")
    elif budget.get("max_dollars"):
        st.info(f"💰 Budget: Under ${budget['max_dollars']}")
    
    # Show open now
    if analysis.get("open_now"):
        st.info("🕐 Filter: Currently open only")
    
    # Show attribute filters
    filters = analysis.get("filters", {})
    filter_badges = []
    
    if filters.get("dietary"):
        filter_badges.append(f"🥗 {', '.join(filters['dietary'])}")
    if filters.get("accessibility"):
        filter_badges.append(f"♿ {', '.join(filters['accessibility'])}")
    if filters.get("service_type"):
        filter_badges.append(f"🍽️ {', '.join(filters['service_type'])}")
    if filters.get("meal_time"):
        filter_badges.append(f"⏰ {', '.join(filters['meal_time'])}")
    if filters.get("special_needs"):
        filter_badges.append(f"✨ {', '.join(filters['special_needs'])}")
    
    if filter_badges:
        st.info("🔍 **Filters:**")
        for badge in filter_badges:
            st.write(badge)