"""
Review Summarization Agent
Fetches Google Places reviews and creates intelligent summaries
Uses Cortex SUMMARIZE for concise, actionable insights
"""
import streamlit as st
import pandas as pd
from snowflake.snowpark.context import get_active_session
from utils.cortex_helper import call_cortex

REVIEW_TABLE = "LOCEATS_DB.DBT_SKASIREDDY_MARTS.BRONZE_RESTAURANT_REVIEWS"

def get_restaurant_reviews(restaurant_id: str, limit: int = 5) -> pd.DataFrame:
    """
    Fetch reviews for a specific restaurant
    
    Args:
        restaurant_id: Restaurant ID to fetch reviews for
        limit: Max number of reviews (default 5)
    
    Returns:
        DataFrame with reviews or None if no reviews
    """
    try:
        session = get_active_session()
        
        query = f"""
        SELECT 
            REVIEW_TEXT,
            RATING,
            REVIEW_DATE,
            USER_NAME
        FROM {REVIEW_TABLE}
        WHERE RESTAURANT_ID = '{restaurant_id}'
          AND REVIEW_TEXT IS NOT NULL
          AND LENGTH(REVIEW_TEXT) > 10
        ORDER BY REVIEW_DATE DESC
        LIMIT {limit}
        """
        
        reviews_df = session.sql(query).to_pandas()
        return reviews_df if len(reviews_df) > 0 else None
        
    except Exception as e:
        return None


def summarize_reviews(reviews_df: pd.DataFrame, restaurant_name: str) -> dict:
    """
    Use LLM to intelligently summarize reviews
    
    Returns:
    {
        "summary": "2-3 sentence overview",
        "pros": ["Great service", "Authentic flavors"],
        "cons": ["Can be crowded", "Limited parking"],
        "num_reviews": 5
    }
    """
    if reviews_df is None or len(reviews_df) == 0:
        return {
            "summary": "No reviews available yet",
            "pros": [],
            "cons": [],
            "num_reviews": 0
        }
    
    # Combine all review texts
    all_reviews = "\n\n".join([
        f"Rating {row['RATING']}/5: {row['REVIEW_TEXT']}" 
        for _, row in reviews_df.iterrows()
    ])
    
    # Use LLM to analyze and summarize
    summary_prompt = f"""Analyze these Google Places reviews for {restaurant_name} and provide insights.

Reviews:
{all_reviews}

Your task:
1. Write a 2-3 sentence summary highlighting key themes
2. Extract 2-3 main PROS (what customers love)
3. Extract 1-2 main CONS (what could be better)

Focus on: food quality, service, atmosphere, value, authenticity.

Respond in EXACT JSON format:
{{
    "summary": "2-3 sentence overview",
    "pros": ["specific pro 1", "specific pro 2", "specific pro 3"],
    "cons": ["specific con 1", "specific con 2"]
}}

Be specific and concise. JSON only."""
    
    result = call_cortex(summary_prompt, temperature=0.3)
    
    if not result:
        # Fallback: simple summary
        avg_rating = reviews_df['RATING'].mean()
        return {
            "summary": f"Based on {len(reviews_df)} reviews with average rating of {avg_rating:.1f}/5",
            "pros": [],
            "cons": [],
            "num_reviews": len(reviews_df)
        }
    
    try:
        import json
        # Clean JSON
        result_clean = result.strip()
        if "```json" in result_clean:
            result_clean = result_clean.split("```json")[1].split("```")[0]
        elif "```" in result_clean:
            result_clean = result_clean.split("```")[1].split("```")[0]
        
        parsed = json.loads(result_clean)
        parsed["num_reviews"] = len(reviews_df)
        return parsed
        
    except Exception as e:
        # Fallback
        avg_rating = reviews_df['RATING'].mean()
        return {
            "summary": f"Based on {len(reviews_df)} Google reviews (avg: {avg_rating:.1f}/5)",
            "pros": [],
            "cons": [],
            "num_reviews": len(reviews_df)
        }


def display_review_summary(restaurant_id: str, restaurant_name: str, compact: bool = False):
    """
    Display review summary in UI
    
    Args:
        restaurant_id: Restaurant ID
        restaurant_name: Restaurant name for display
        compact: If True, show condensed version
    """
    
    # Fetch reviews
    reviews_df = get_restaurant_reviews(restaurant_id, limit=5)
    
    if reviews_df is None or len(reviews_df) == 0:
        if not compact:
            st.caption("📝 No reviews available")
        return None
    
    # Summarize
    with st.spinner("Analyzing reviews..."):
        summary = summarize_reviews(reviews_df, restaurant_name)
    
    if compact:
        # Compact version for restaurant cards
        st.caption(f"📝 **Reviews :** {summary['summary']}")
    else:
        # Full version
        st.markdown(f"### 📝 What Customers Say ")
        
        st.write(summary['summary'])
        
        if summary.get('pros'):
            st.markdown("**👍 Highlights:**")
            for pro in summary['pros']:
                st.write(f"✓ {pro}")
        
        if summary.get('cons'):
            st.markdown("**👎 Watch out for:**")
            for con in summary['cons']:
                st.write(f"• {con}")
    
    return summary


def add_review_summaries_to_recommendations(top_restaurants_df: pd.DataFrame) -> pd.DataFrame:
    """
    Batch process: Add review summaries to all recommended restaurants
    
    Args:
        top_restaurants_df: DataFrame with recommended restaurants
    
    Returns:
        Same DataFrame with added REVIEW_SUMMARY column
    """
    
    summaries = []
    
    for _, rest in top_restaurants_df.iterrows():
        reviews_df = get_restaurant_reviews(rest['RESTAURANT_ID'], limit=5)
        
        if reviews_df is not None and len(reviews_df) > 0:
            summary = summarize_reviews(reviews_df, rest['RESTAURANT_NAME'])
            summaries.append(summary['summary'])
        else:
            summaries.append("No reviews available")
    
    top_restaurants_df['REVIEW_SUMMARY'] = summaries
    return top_restaurants_df