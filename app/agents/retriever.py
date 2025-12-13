"""
Retriever Agent - CLEAN VERSION
Uses analyst_data as single source of truth
No duplicate query parsing!
"""
import streamlit as st
import pandas as pd
from snowflake.snowpark.context import get_active_session
from models.agent_message import AgentMessage
from utils import display_agent_status, calculate_haversine_distance
from config import GOLD_RESTAURANT_EMBEDDINGS, GOLD_RESTAURANTS_MASTER

def get_session():
    return get_active_session()

def retriever_agent(
    user_query: str,
    analyst_data: dict,
    user_location: dict = None,
    search_area: dict = None,  # ← NEW: Override location from search_area
    top_k: int = 20
) -> AgentMessage:
    """
    Clean retriever that uses analyst + search_area
    
    Args:
        user_query: For semantic search
        analyst_data: Analyst's full output
        user_location: User's actual location (for distance)
        search_area: Where to search (from analyst or smart handler)
    """
    display_agent_status("Retriever Agent", "running", "Performing search...")
    
    try:
        session = get_session()
        
        # Extract from analyst
        cuisine = analyst_data.get('cuisine')
        
        # Use search_area if provided (overrides analyst location)
        if search_area:
            location_name = search_area.get('name')
            location_mode = search_area.get('mode', 'none')
            radius_miles = search_area.get('radius_miles', 1.5)
        else:
            # Fall back to analyst location
            location_info = analyst_data.get('location', {})
            location_name = location_info.get('name')
            location_mode = location_info.get('mode', 'none')
            radius_miles = location_info.get('radius_miles', 1.5)
        
        # Build SQL conditions
        cuisine_condition = ""
        neighborhood_condition = ""
        
        # CUISINE FILTER (from analyst!)
        if cuisine:
            cuisine_condition = f"AND PRIMARY_CUISINE = '{cuisine}'"
            st.info(f"🎯 Cuisine: {cuisine}")
        
        # LOCATION FILTER (CITY vs NEIGHBORHOOD)
        if location_name:
            loc = location_name.replace("'", "''").strip()
            loc_title = loc.title()
            city_exact = f"CITY ILIKE '{loc_title}'"
            neighborhood_like = f"NEIGHBORHOOD ILIKE '{loc_title}%'"
        
            if location_mode == "include_strict":
                # "in Boston" should match CITY, "in Fenway" should match NEIGHBORHOOD
                neighborhood_condition = f"AND ({city_exact} OR {neighborhood_like})"
                st.info(f"📍 Strict: IN {loc_title} (city OR neighborhood)")
        
            elif location_mode == "exclude":
                neighborhood_condition = f"AND NOT ({city_exact} OR {neighborhood_like})"
                st.info(f"🚫 Excluding: {loc_title} (city OR neighborhood)")
        
            elif location_mode == "include_nearby":
                st.info(f"🌍 Nearby: {loc_title} (within {radius_miles} mi)")

        
        # SEMANTIC SEARCH QUERY
        embed_expr = f"""
        VECTOR_COSINE_SIMILARITY(
            DESCRIPTION_EMBEDDING,
            SNOWFLAKE.CORTEX.EMBED_TEXT_768('snowflake-arctic-embed-m', '{user_query.replace("'", "''")}')
        )
        """
        
        search_query = f"""
        SELECT 
            RESTAURANT_ID, RESTAURANT_NAME, CITY, NEIGHBORHOOD,
            PRIMARY_CUISINE, PRICE_LEVEL, OVERALL_SCORE,
            RECOMMENDATION_TIER, SAFETY_SCORE, HEALTH_RISK_LEVEL,
            NEAREST_STOP_DISTANCE_M, SERVES_VEGETARIAN,
            IS_WHEELCHAIR_ACCESSIBLE, GOOD_FOR_GROUPS, IS_CURRENTLY_OPEN,
            {embed_expr} as SIMILARITY_SCORE
        FROM {GOLD_RESTAURANT_EMBEDDINGS}
        WHERE DESCRIPTION_EMBEDDING IS NOT NULL
          {cuisine_condition}
          {neighborhood_condition}
        AND SIMILARITY_SCORE > 0.3
        ORDER BY SIMILARITY_SCORE DESC
        LIMIT {top_k}
        """

        
        results_df = session.sql(search_query).to_pandas()
        
        if len(results_df) == 0:
            st.error("❌ No restaurants found")
            return AgentMessage("Retriever", "failed", None, 0.0)
        
        # ENRICH WITH MASTER TABLE
        restaurant_ids = results_df['RESTAURANT_ID'].tolist()
        restaurant_context = ", ".join([f"'{id}'" for id in restaurant_ids])
        
        detail_query = f"""
        SELECT 
            RESTAURANT_ID, STREET_ADDRESS, PHONE, YELP_RATING, CITY,
            LATITUDE, LONGITUDE, YELP_URL,
            SERVES_BREAKFAST, SERVES_LUNCH, SERVES_DINNER, SERVES_COFFEE,
            GOOD_FOR_CHILDREN, OUTDOOR_SEATING, TAKEOUT, DELIVERY,
            ALLOWS_DOGS, LIVE_MUSIC, OPEN_NOW
        FROM {GOLD_RESTAURANTS_MASTER}
        WHERE RESTAURANT_ID IN ({restaurant_context})
        """
        
        try:
            detail_df = session.sql(detail_query).to_pandas()
            results_df = results_df.merge(detail_df, on='RESTAURANT_ID', how='left')
            st.caption(f"✅ Enriched with {len(detail_df.columns)-1} attributes")
        except Exception as e:
            st.warning(f"Enrichment failed: {str(e)}")
        
        # DISTANCE CALCULATIONS
        # Priority: Use search area location if "near", otherwise user_location
        
        if location_mode == "include_nearby" and location_name:
            # Calculate distance from search location, then filter by radius
            # We'd need coordinates for the location_name - for now, skip this
            # and just sort by similarity
            st.caption(f"ℹ️ Distance filtering for 'nearby' mode - coordinates needed")
        
        elif user_location and 'latitude' in user_location:
            # Calculate distance from user's location
            if 'LATITUDE' in results_df.columns:
                results_df['DISTANCE_FROM_USER_M'] = results_df.apply(
                    lambda row: calculate_haversine_distance(
                        user_location['latitude'], user_location['longitude'],
                        row['LATITUDE'], row['LONGITUDE']
                    ) if pd.notna(row['LATITUDE']) else None,
                    axis=1
                )
                results_df['DISTANCE_FROM_USER_MI'] = results_df['DISTANCE_FROM_USER_M'] / 1609.34
                results_df = results_df.sort_values('DISTANCE_FROM_USER_MI')
                st.success(f"📍 Sorted by distance from {user_location.get('name', 'your location')}")
        
        display_agent_status("Retriever Agent", "success", f"Retrieved {len(results_df)} restaurants")
        
        with st.expander("🔎 View Retrieved Restaurants"):
            display_cols = ['RESTAURANT_NAME', 'PRIMARY_CUISINE', 'NEIGHBORHOOD', 'SIMILARITY_SCORE']
            if 'DISTANCE_FROM_USER_MI' in results_df.columns:
                display_cols.append('DISTANCE_FROM_USER_MI')
            st.dataframe(results_df[display_cols].head(10))
        
        return AgentMessage(
            agent_name="Retriever",
            status="success",
            data=results_df,
            confidence=0.9,
            metadata={
                "num_results": len(results_df),
                "cuisine_filter": cuisine,
                "location_mode": location_mode,
                "has_full_attributes": 'ALLOWS_DOGS' in results_df.columns
            }
        )
            
    except Exception as e:
        st.error(f"Retriever error: {str(e)}")
        import traceback
        st.code(traceback.format_exc())
        return AgentMessage("Retriever", "failed", None, 0.0)