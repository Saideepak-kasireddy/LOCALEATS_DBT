"""
Smart Location Handler
Uses LLM to extract location names, then geocodes them intelligently
No hardcoded location lists - handles ANY Boston area location
"""
import streamlit as st
from typing import Optional, Dict
from utils.cortex_helper import call_cortex

# Fallback coordinates for common areas (only used if geocoding fails)
FALLBACK_COORDS = {
    "boston": (42.3601, -71.0589),
    "cambridge": (42.3736, -71.1097),
    "somerville": (42.3876, -71.0995),
}

def geocode_with_llm(location_name: str) -> Optional[Dict]:
    """
    Use LLM to determine coordinates for Boston-area locations
    Handles neighborhoods, landmarks, universities without hardcoding
    """
    if not location_name:
        return None
    
    # Ask LLM for approximate coordinates
    geocoding_prompt = f"""You are a Boston area geography expert.

Location name: "{location_name}"

If this is a valid Boston/Cambridge/Somerville area location, provide coordinates.

Respond in EXACT JSON:
{{
    "is_valid_boston_location": true|false,
    "latitude": 42.xxxx,
    "longitude": -71.xxxx,
    "normalized_name": "Proper Name",
    "neighborhood": "Neighborhood Name"
}}

Examples:
"roxbury" → {{"is_valid_boston_location": true, "latitude": 42.3299, "longitude": -71.0892, "normalized_name": "Roxbury", "neighborhood": "Roxbury"}}
"boston university" → {{"is_valid_boston_location": true, "latitude": 42.3505, "longitude": -71.1054, "normalized_name": "Boston University", "neighborhood": "Allston"}}
"fenway park" → {{"is_valid_boston_location": true, "latitude": 42.3467, "longitude": -71.0972, "normalized_name": "Fenway Park", "neighborhood": "Fenway"}}
"new york" → {{"is_valid_boston_location": false}}

JSON only:"""
    
    result = call_cortex(geocoding_prompt, temperature=0.1)
    
    if not result:
        # Fallback to simple lookup
        location_lower = location_name.lower().strip()
        for key, coords in FALLBACK_COORDS.items():
            if key in location_lower:
                return {
                    "latitude": coords[0],
                    "longitude": coords[1],
                    "name": location_name,
                    "neighborhood": key.title()
                }
        return None
    
    try:
        import json
        # Clean JSON
        result_clean = result.strip()
        if "```json" in result_clean:
            result_clean = result_clean.split("```json")[1].split("```")[0]
        elif "```" in result_clean:
            result_clean = result_clean.split("```")[1].split("```")[0]
        
        parsed = json.loads(result_clean)
        
        # Verify it's a valid Boston location
        if not parsed.get("is_valid_boston_location"):
            st.warning(f"⚠️ '{location_name}' is not in the Boston area")
            return None
        
        st.caption(f"📍 Geocoded: {parsed.get('normalized_name', location_name)}")
        
        return {
            "latitude": parsed["latitude"],
            "longitude": parsed["longitude"],
            "name": parsed.get("normalized_name", location_name),
            "neighborhood": parsed.get("neighborhood")
        }
        
    except Exception as e:
        # Fallback
        location_lower = location_name.lower().strip()
        for key, coords in FALLBACK_COORDS.items():
            if key in location_lower:
                return {
                    "latitude": coords[0],
                    "longitude": coords[1],
                    "name": location_name,
                    "neighborhood": key.title()
                }
        return None


def resolve_user_location(
    analyst_location: dict,
    user_input_location: dict,
    user_input_text: str
) -> Optional[Dict]:
    """
    Smart location resolution with priority order
    
    Priority:
    1. User manually entered location in input box → Use that as USER location
    2. Query mentions location → Use for SEARCH area, not user location
    3. No location → None
    
    Args:
        analyst_location: Location from analyst.py
        user_input_location: Location from optional input box  
        user_input_text: What user typed in location box
    
    Returns:
        User's actual location (for distance calculations)
    """
    
    # Priority 1: User explicitly entered location in the input box
    if user_input_text and len(user_input_text.strip()) > 0:
        st.info(f"📍 Using YOUR location: {user_input_text}")
        return user_input_location
    
    # Priority 2: Quick location dropdown
    if user_input_location and user_input_location.get("name") != "None":
        st.info(f"📍 Using YOUR location: {user_input_location['name']}")
        return user_input_location
    
    # No explicit user location - don't use query location as user location
    return None


def get_search_area_from_analyst(analyst_data: dict) -> Optional[Dict]:
    """
    Extract SEARCH AREA from analyst (different from user location!)
    
    This is where the user wants to search FOR restaurants,
    not where the user IS located.
    """
    location_info = analyst_data.get("location", {})
    location_name = location_info.get("name")
    mode = location_info.get("mode", "none")
    
    if not location_name or mode == "none":
        return None
    
    # Geocode the search area
    search_area = geocode_with_llm(location_name)
    
    if search_area:
        search_area["mode"] = mode
        search_area["radius_miles"] = location_info.get("radius_miles", 1.5)
        
        if mode == "include_strict":
            st.info(f"🎯 Searching IN: {search_area['name']} only")
        elif mode == "include_nearby":
            st.info(f"🌍 Searching NEAR: {search_area['name']} (within {search_area['radius_miles']} mi)")
        elif mode == "exclude":
            st.info(f"🚫 Excluding: {search_area['name']}")
    
    return search_area