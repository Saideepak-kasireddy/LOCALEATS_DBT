"""
Intent Understanding and Execution Agent
Enhanced with rich attribute detection from user's schema
"""
import streamlit as st
import pandas as pd
import json
from utils.cortex_helper import call_cortex
from utils.geo_utils import geocode_location, calculate_haversine_distance

def intent_understanding_agent(user_query: str, previous_results=None) -> dict:
    """
    LLM-powered agent that understands user intent and extracts structured filters
    
    NOW ENHANCED with schema awareness - knows about:
    - SERVES_VEGETARIAN, SERVES_COFFEE, SERVES_BREAKFAST/LUNCH/DINNER
    - OUTDOOR_SEATING, ALLOWS_DOGS, LIVE_MUSIC
    - GOOD_FOR_GROUPS, GOOD_FOR_CHILDREN
    - IS_WHEELCHAIR_ACCESSIBLE
    - TAKEOUT, DELIVERY, RESERVABLE
    """
    
    context = ""
    if previous_results is not None:
        num_results = len(previous_results) if isinstance(previous_results, pd.DataFrame) else len(previous_results.get('researcher_data', []))
        context = f"""
Available previous search results: {num_results} restaurants
"""
    
    # SCHEMA AWARENESS - Tell LLM what columns exist
    schema_context = """
Available restaurant attributes you can filter by:
DIETARY & FOOD:
- SERVES_VEGETARIAN (boolean) - has vegetarian options
- SERVES_BREAKFAST, SERVES_LUNCH, SERVES_DINNER (boolean) - meal times
- SERVES_COFFEE, SERVES_DESSERT, SERVES_BEER, SERVES_WINE (boolean)

ACCESSIBILITY & GROUPS:
- IS_WHEELCHAIR_ACCESSIBLE (boolean) - wheelchair friendly
- GOOD_FOR_GROUPS (boolean) - suitable for groups
- GOOD_FOR_CHILDREN (boolean) - family/kid-friendly
- ALLOWS_DOGS (boolean) - pet-friendly

SERVICE OPTIONS:
- OUTDOOR_SEATING (boolean) - outdoor dining available
- TAKEOUT (boolean) - takeout available
- DELIVERY (boolean) - delivery available  
- RESERVABLE (boolean) - accepts reservations
- DINE_IN (boolean) - dine-in available

OTHER:
- LIVE_MUSIC (boolean) - has live music
- IS_CURRENTLY_OPEN (boolean) - currently open
"""
    
    intent_prompt = f"""You are an intent understanding agent for a Boston restaurant system.

{schema_context}

{context}

User Query: "{user_query}"

Your job: Extract ALL relevant filters from the query, mapping to the available attributes above.

Respond in EXACT JSON format:
{{
    "intent_type": "find_closest" | "find_cheapest" | "find_safest" | "filter_by_attribute" | "new_search",
    "target_location": "Harvard" (extract location if mentioned, null otherwise),
    "cuisine_preference": "Mexican" | "Italian" etc. (null if not specified),
    "filter_criteria": {{
        "max_price": 1-4 (null if not specified),
        "min_safety": 0-100 (null if not specified),
        "dietary": ["vegetarian", "vegan"] (extract if mentioned),
        "meal_time": ["breakfast", "lunch", "dinner"] (extract if mentioned),
        "accessibility": ["wheelchair", "groups", "children"] (extract if mentioned),
        "service_type": ["outdoor", "takeout", "delivery", "reservations"] (extract if mentioned),
        "special_needs": ["coffee_shop", "pet_friendly", "live_music"] (extract if mentioned)
    }},
    "sort_by": "distance" | "price" | "safety" | "rating",
    "interpreted_intent": "clear explanation",
    "requires_new_search": true | false
}}

Mapping examples:
- "vegetarian" → dietary: ["vegetarian"]
- "coffee shop" or "cafe" → special_needs: ["coffee_shop"]
- "good for groups" → accessibility: ["groups"]
- "pet friendly" or "dog friendly" → special_needs: ["pet_friendly"]
- "outdoor seating" or "patio" → service_type: ["outdoor"]
- "breakfast spot" → meal_time: ["breakfast"]
- "wheelchair accessible" → accessibility: ["wheelchair"]
- "family friendly" or "kid friendly" → accessibility: ["children"]
- "takeout" or "to go" → service_type: ["takeout"]
- "delivery" → service_type: ["delivery"]
- "live music" → special_needs: ["live_music"]

Query examples:

"vegetarian italian restaurant"
→ {{"cuisine_preference": "Italian", "filter_criteria": {{"dietary": ["vegetarian"]}}, "interpreted_intent": "Find Italian restaurants with vegetarian options"}}

"pet friendly cafe with outdoor seating"
→ {{"filter_criteria": {{"special_needs": ["pet_friendly", "coffee_shop"], "service_type": ["outdoor"]}}, "interpreted_intent": "Find pet-friendly coffee shops with outdoor seating"}}

"good breakfast spot for kids near MIT"
→ {{"target_location": "MIT", "filter_criteria": {{"meal_time": ["breakfast"], "accessibility": ["children"]}}, "interpreted_intent": "Find kid-friendly breakfast restaurants near MIT"}}

"wheelchair accessible italian with groups"
→ {{"cuisine_preference": "Italian", "filter_criteria": {{"accessibility": ["wheelchair", "groups"]}}, "interpreted_intent": "Find wheelchair accessible Italian restaurants good for groups"}}

Handle typos naturally. Extract ALL relevant attributes. JSON only."""
    
    result = call_cortex(intent_prompt, temperature=0.3)
    
    if not result:
        return {
            "intent_type": "new_search",
            "interpreted_intent": user_query,
            "requires_new_search": False
        }
    
    try:
        # Clean JSON
        result_clean = result.strip()
        if "```json" in result_clean:
            result_clean = result_clean.split("```json")[1].split("```")[0]
        elif "```" in result_clean:
            result_clean = result_clean.split("```")[1].split("```")[0]
        
        parsed = json.loads(result_clean)
        
        # Show what we understood
        st.success(f"🧠 Understood: {parsed.get('interpreted_intent', user_query)}")
        
        # Show extracted filters
        filters = parsed.get('filter_criteria', {})
        if filters:
            filter_summary = []
            if filters.get('dietary'):
                filter_summary.append(f"🥗 {', '.join(filters['dietary'])}")
            if filters.get('accessibility'):
                filter_summary.append(f"♿ {', '.join(filters['accessibility'])}")
            if filters.get('service_type'):
                filter_summary.append(f"🍽️ {', '.join(filters['service_type'])}")
            if filters.get('special_needs'):
                filter_summary.append(f"✨ {', '.join(filters['special_needs'])}")
            if filters.get('meal_time'):
                filter_summary.append(f"⏰ {', '.join(filters['meal_time'])}")
            
            if filter_summary:
                st.info(f"📋 Filters detected: {' | '.join(filter_summary)}")
        
        return parsed
        
    except Exception as e:
        st.warning(f"Could not parse intent")
        return {
            "intent_type": "new_search",
            "interpreted_intent": user_query,
            "requires_new_search": False
        }


def execute_intent(intent: dict, previous_results, user_location: dict = None) -> dict:
    """
    Execute the understood intent using REAL data operations
    (Keep existing execute_intent code - no changes needed here)
    """
    
    # Extract DataFrame properly
    if isinstance(previous_results, dict):
        if 'researcher_data' in previous_results:
            results_df = previous_results['researcher_data']
        elif 'recommendation' in previous_results:
            if 'full_data' in previous_results['recommendation']:
                results_df = previous_results['recommendation']['full_data']
            else:
                return {"error": "Cannot extract data"}
        else:
            return {"error": "Invalid format"}
    elif isinstance(previous_results, pd.DataFrame):
        results_df = previous_results
    else:
        return {"error": f"Unexpected type: {type(previous_results)}"}
    
    intent_type = intent.get('intent_type')
    
    # FIND CLOSEST
    if intent_type == "find_closest":
        target_loc_name = intent.get('target_location')
        
        if target_loc_name:
            target_lower = target_loc_name.lower()
            
            if 'harvard' in target_lower:
                target_coords = {"latitude": 42.3736, "longitude": -71.1197, "name": "Harvard"}
            elif 'mit' in target_lower:
                target_coords = {"latitude": 42.3601, "longitude": -71.0942, "name": "MIT"}
            elif 'downtown' in target_lower:
                target_coords = {"latitude": 42.3601, "longitude": -71.0589, "name": "Downtown"}
            else:
                target_coords = geocode_location(target_loc_name)
        elif user_location:
            target_coords = user_location
        else:
            return {"error": "No location specified"}
        
        st.info(f"📍 Calculating distances from {target_coords['name']}...")
        
        results = results_df.copy()
        
        if 'LATITUDE' in results.columns and 'LONGITUDE' in results.columns:
            results['CALC_DIST_M'] = results.apply(
                lambda r: calculate_haversine_distance(
                    target_coords['latitude'], target_coords['longitude'],
                    r['LATITUDE'], r['LONGITUDE']
                ) if pd.notna(r['LATITUDE']) and pd.notna(r['LONGITUDE']) else 999999,
                axis=1
            )
            results['CALC_DIST_MI'] = results['CALC_DIST_M'] / 1609.34
            results = results.sort_values('CALC_DIST_MI')
            
            return {
                "results": results.head(3),
                "action": "show_closest",
                "location": target_coords['name']
            }
        else:
            return {"error": "No coordinates"}
    
    # FIND CHEAPEST
    elif intent_type == "find_cheapest" or intent.get('sort_by') == 'price':
        st.info("💰 Finding most affordable...")
        results = results_df.copy()
        results = results.sort_values('PRICE_LEVEL')
        return {"results": results.head(5), "action": "show_cheapest"}
    
    # FIND SAFEST
    elif intent_type == "find_safest" or intent.get('sort_by') == 'safety':
        st.info("🛡️ Finding safest...")
        results = results_df.copy()
        results = results.sort_values('SAFETY_SCORE', ascending=False)
        return {"results": results.head(5), "action": "show_safest"}
    
    # FILTER BY ATTRIBUTES
    elif intent_type == "filter_by_attribute":
        st.info("🔍 Filtering...")
        
        results = results_df.copy()
        criteria = intent.get('filter_criteria', {})
        
        # Apply filters (researcher already did this, so just sort)
        sort_by = intent.get('sort_by', 'OVERALL_SCORE')
        if sort_by == 'safety':
            results = results.sort_values('SAFETY_SCORE', ascending=False)
        elif sort_by == 'price':
            results = results.sort_values('PRICE_LEVEL')
        else:
            results = results.sort_values('OVERALL_SCORE', ascending=False)
        
        return {"results": results.head(5), "action": "show_filtered"}
    
    # NEW SEARCH
    elif intent.get('requires_new_search'):
        return {
            "action": "trigger_new_search",
            "message": "Please use search box above"
        }
    
    # UNKNOWN
    else:
        return {
            "action": "unknown",
            "message": "Try: 'which is closest?', 'cheapest?', 'good for groups?'"
        }