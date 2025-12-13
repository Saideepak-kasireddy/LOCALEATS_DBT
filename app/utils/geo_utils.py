"""
Geographic utilities for distance calculation and geocoding
"""
import math
import pandas as pd
import streamlit as st
from snowflake.snowpark.context import get_active_session  # Import directly here
from config import (
    BOSTON_NEIGHBORHOODS, 
    WALKING_SPEED_M_PER_MIN, 
    DEFAULT_BOSTON_LAT, 
    DEFAULT_BOSTON_LON, 
    BRONZE_MBTA_STOPS, 
    INT_RESTAURANT_TRANSIT
)

def get_session():
    """Get Snowflake session - local function to avoid circular import"""
    return get_active_session()

# ... rest of the file stays the same

def calculate_haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points in meters using Haversine formula"""
    R = 6371000  # Earth's radius in meters
    
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    
    a = math.sin(delta_lat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    
    return R * c

def geocode_location(location_name: str) -> dict:
    """
    Simple geocoding for Boston locations
    Returns dict with latitude, longitude, and name
    """
    location_lower = location_name.lower()
    
    for neighborhood, coords in BOSTON_NEIGHBORHOODS.items():
        if neighborhood in location_lower:
            result = coords.copy()
            result["name"] = location_name
            return result
    
    # Return default Boston coordinates if not found
    return {
        "latitude": DEFAULT_BOSTON_LAT,
        "longitude": DEFAULT_BOSTON_LON,
        "name": location_name
    }

def get_mbta_route(user_location: dict, restaurant_id: str):
    """Calculate MBTA transit route with actual route lookup"""
    try:
        if not user_location or 'latitude' not in user_location:
            return None
        
        session = get_active_session()
        
        # Find nearest T stop to user
        user_stop_query = f"""
        SELECT 
            s.STOP_ID,
            s.STOP_NAME,
            s.PLATFORM_NAME,
            s.LATITUDE,
            s.LONGITUDE,
            6371000 * 2 * ASIN(SQRT(
                POW(SIN(RADIANS(s.LATITUDE - {user_location['latitude']}) / 2), 2) +
                COS(RADIANS({user_location['latitude']})) * 
                COS(RADIANS(s.LATITUDE)) *
                POW(SIN(RADIANS(s.LONGITUDE - {user_location['longitude']}) / 2), 2)
            )) as DISTANCE_M
        FROM {BRONZE_MBTA_STOPS} s
        WHERE s.LATITUDE IS NOT NULL AND s.LONGITUDE IS NOT NULL
          AND s.PLATFORM_NAME IS NOT NULL  -- Only real T stations
        ORDER BY DISTANCE_M
        LIMIT 3  -- Get top 3 to find best route
        """
        
        user_stops_df = session.sql(user_stop_query).to_pandas()
        
        if user_stops_df.empty:
            return None
        
        # Get restaurant's nearest stop
        restaurant_stop_query = f"""
        SELECT 
            STOP_ID,
            STOP_NAME,
            DISTANCE_METERS,
            WALKING_TIME_MINUTES,
            ACCESSIBILITY_CATEGORY
        FROM {INT_RESTAURANT_TRANSIT}
        WHERE RESTAURANT_ID = '{restaurant_id}'
        ORDER BY DISTANCE_METERS
        LIMIT 1
        """
        
        restaurant_stop_df = session.sql(restaurant_stop_query).to_pandas()
        
        if restaurant_stop_df.empty:
            return None
        
        restaurant_stop = restaurant_stop_df.iloc[0]
        
        # Use the closest user stop
        user_stop = user_stops_df.iloc[0]
        walk_to_stop_min = int(user_stop['DISTANCE_M'] / WALKING_SPEED_M_PER_MIN)
        
        # Determine route by analyzing stop names
        origin_name = str(user_stop['STOP_NAME']).lower()
        dest_name = str(restaurant_stop['STOP_NAME']).lower()
        
        # Route detection logic based on Boston T system
        route_name = "MBTA"
        
        # Red Line stations
        red_line_keywords = ['harvard', 'central', 'kendall', 'park street', 'downtown', 'south station', 'broadway', 'andrew', 'jfk']
        # Orange Line stations  
        orange_line_keywords = ['oak grove', 'sullivan', 'community', 'north station', 'haymarket', 'state', 'downtown', 'chinatown', 'tufts', 'back bay', 'massachusetts', 'ruggles', 'roxbury', 'jackson', 'stony brook', 'green street', 'forest hills']
        # Green Line stations
        green_line_keywords = ['government', 'park street', 'boylston', 'arlington', 'copley', 'hynes', 'kenmore', 'fenway']
        # Blue Line stations
        blue_line_keywords = ['wonderland', 'revere', 'beachmont', 'suffolk', 'orient', 'wood island', 'airport', 'maverick', 'aquarium', 'state', 'government']
        
        # Check which line(s) both stops might be on
        if any(kw in origin_name or kw in dest_name for kw in red_line_keywords):
            route_name = "Red Line"
        elif any(kw in origin_name or kw in dest_name for kw in orange_line_keywords):
            route_name = "Orange Line"
        elif any(kw in origin_name or kw in dest_name for kw in green_line_keywords):
            route_name = "Green Line"
        elif any(kw in origin_name or kw in dest_name for kw in blue_line_keywords):
            route_name = "Blue Line"
        
        estimated_transit_time = 10
        total_time = walk_to_stop_min + estimated_transit_time + int(restaurant_stop['WALKING_TIME_MINUTES'])
        
        return {
            "origin_stop": user_stop['STOP_NAME'],
            "origin_platform": user_stop.get('PLATFORM_NAME'),
            "origin_walk_min": walk_to_stop_min,
            "destination_stop": restaurant_stop['STOP_NAME'],
            "destination_walk_min": int(restaurant_stop['WALKING_TIME_MINUTES']),
            "route_name": route_name,
            "total_time_min": total_time,
            "accessibility": restaurant_stop.get('ACCESSIBILITY_CATEGORY', 'Unknown')
        }
        
    except Exception as e:
        st.warning(f"Transit routing: {str(e)}")
        return None

def format_transit_directions(transit_info: dict, user_location_name: str) -> str:
    """Format transit directions as readable text"""
    if not transit_info:
        return None
    
    platform_info = f" ({transit_info['origin_platform']})" if transit_info.get('origin_platform') else ""
    
    directions = f"""🚇 **Transit Directions from {user_location_name}:**

**Step 1:** Walk to **{transit_info['origin_stop']}{platform_info}** (~{transit_info['origin_walk_min']} min)

**Step 2:** Take {transit_info['route_name']}

**Step 3:** Walk from **{transit_info['destination_stop']}** (~{transit_info['destination_walk_min']} min)

**⏱️ Total Transit Time: ~{transit_info['total_time_min']} minutes**

♿ Accessibility: {transit_info['accessibility']}"""
    
    return directions