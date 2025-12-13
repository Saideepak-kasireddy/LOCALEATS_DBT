"""
Restaurant Name Search Utility
Separated from query_processor since we're using analyst now
"""
import streamlit as st
from snowflake.snowpark.context import get_active_session

def search_restaurant_by_name(restaurant_name: str):
    """
    Search for specific restaurant by name with fuzzy matching
    Used when user asks for a specific place like "find Giulia"
    """
    try:
        session = get_active_session()
        
        search_query = f"""
        SELECT
            RESTAURANT_ID,
            RESTAURANT_NAME,
            CITY,
            NEIGHBORHOOD,
            PRIMARY_CUISINE,
            PRICE_LEVEL,
            OVERALL_SCORE,
            SAFETY_SCORE,
            YELP_RATING,
            STREET_ADDRESS,
            PHONE,
            YELP_URL,
            LATITUDE,
            LONGITUDE
        FROM LOCEATS_DB.DBT_SKASIREDDY_MARTS.RESTAURANTS_MASTER
        WHERE RESTAURANT_NAME ILIKE '%{restaurant_name.replace("'", "''")}%'
        ORDER BY
            CASE
                WHEN UPPER(RESTAURANT_NAME) = UPPER('{restaurant_name.replace("'", "''")}') THEN 1
                WHEN RESTAURANT_NAME ILIKE '{restaurant_name.replace("'", "''")}%' THEN 2
                ELSE 3
            END,
            OVERALL_SCORE DESC
        LIMIT 5
        """
        
        results = session.sql(search_query).to_pandas()
        return results
        
    except Exception as e:
        st.error(f"Name search error: {str(e)}")
        return None