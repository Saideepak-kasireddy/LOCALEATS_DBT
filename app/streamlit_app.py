"""
LocalEats AI - Restaurant Recommendation System
Main Streamlit Application
"""
import streamlit as st
import pandas as pd
from streamlit_folium import folium_static
from snowflake.snowpark.context import get_active_session

# Import from config first
from config import QUICK_LOCATIONS, BOSTON_NEIGHBORHOODS
from agents.review_agent import display_review_summary

# Import utils functions
from utils import (
    call_cortex,
    display_agent_status,
    geocode_location,
    calculate_haversine_distance,
    format_transit_directions
)

# Import analyst (UNIFIED QUERY UNDERSTANDING)
from utils.analyst_clean import analyze_query_to_json
from utils.restaurant_search import search_restaurant_by_name
from utils.smart_location_handler import (
    geocode_with_llm,
    resolve_user_location,
    get_search_area_from_analyst
)

# Import MBTA function
from utils.geo_utils import get_mbta_route

# Import orchestrator and intent agents
from agents import orchestrator_agent
from agents.intent_agent import intent_understanding_agent, execute_intent

# =====================================================================
#                       SESSION & CONFIG
# =====================================================================

st.set_page_config(
    page_title="LocalEats AI",
    page_icon="🍽️",
    layout="wide"
)

if "conversation_history" not in st.session_state:
    st.session_state.conversation_history = []
if "last_search_results" not in st.session_state:
    st.session_state.last_search_results = None
if "last_effective_query" not in st.session_state:
    st.session_state.last_effective_query = ""

# =====================================================================
#                       MAIN UI
# =====================================================================

st.markdown("""
<style>
    .main-header {
        text-align: center;
        font-size: 3rem;
        font-weight: bold;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        padding: 1rem;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<h1 class="main-header">🍽️ LocalEats AI</h1>', unsafe_allow_html=True)
st.markdown("### Powered by Multi-Agent Architecture")
st.markdown("---")

# Connection status
try:
    session = get_active_session()
    session.sql("SELECT 1").collect()
    st.success("✅ Connected to Snowflake")
except Exception as e:
    st.error(f"❌ Connection Error: {str(e)}")
    st.stop()

st.header("🔍 What are you looking for?")

# Location input
with st.expander("📍 Add Your Location (Optional - for distance calculation)"):
    col_loc1, col_loc2 = st.columns(2)
    with col_loc1:
        location_name = st.text_input("Location Name", placeholder="e.g., MIT, Harvard Square")
    with col_loc2:
        quick_loc = st.selectbox("Or choose known location", ["None"] + list(QUICK_LOCATIONS.keys()))

user_location = None

# Process user location from input box (with smart geocoding!)
user_input_location = None
user_input_text = ""

if location_name and quick_loc == "None":
    # User typed a location - use LLM geocoding (handles ANY location!)
    user_input_location = geocode_with_llm(location_name)
    user_input_text = location_name
    if user_input_location:
        st.success(f"📍 Your location: {location_name}")
elif quick_loc != "None":
    user_input_location = QUICK_LOCATIONS[quick_loc].copy()
    user_input_location["name"] = quick_loc
    user_input_text = quick_loc
    st.info(f"📍 Your location: {quick_loc}")

# Main query input
user_query = st.text_area(
    "Describe your ideal restaurant:",
    placeholder="Example: cheap Mexican food near MIT",
    height=100
)

# Filters
col1, col2 = st.columns(2)
with col1:
    max_price = st.selectbox("Max Price", ["Any", 1, 2, 3, 4], index=0)
with col2:
    max_iterations = st.selectbox("Max Iterations", [1, 2, 3], index=1)

min_safety = 0

# Search button
search_clicked = st.button("🚀 Find Restaurants", type="primary", use_container_width=True)

if search_clicked:
    base_query = user_query.strip()
    
    if not base_query:
        st.warning("⚠️ Please enter a restaurant query.")
    else:
        st.markdown("---")
        st.subheader("🧠 Understanding Your Request")
        
        # ✅ USE ANALYST (NO conversation history parameter!)
        analyst_data = analyze_query_to_json(base_query)
        
        # ✅ SMART LOCATION RESOLUTION
        # Separate: User's location (input box) vs Search area (query)
        final_user_location = resolve_user_location(
            analyst_location=analyst_data.get('location', {}),
            user_input_location=user_input_location,
            user_input_text=user_input_text
        )
        
        # Get search area from analyst (different from user location!)
        search_area = get_search_area_from_analyst(analyst_data)
        
        with st.expander("🔍 Query Analysis (Debug)", expanded=False):
            st.json(analyst_data)
        
        st.session_state.conversation_history.append(("user", base_query))
        
        # Extract filters from analyst
        extracted_filters = analyst_data.get('filters', {}) or {}
        
        # Extract budget from analyst
        budget_info = analyst_data.get('budget', {})
        if budget_info.get('max_price_level') and max_price == "Any":
            max_price = budget_info['max_price_level']
            st.info(f"💡 Detected price: {'$' * int(max_price)}")
        
        # Execute orchestrator with analyst_data
        results = orchestrator_agent(
            user_query=base_query,
            analyst_data=analyst_data,
            user_location=final_user_location,  # ← Where USER is
            search_area=search_area,  # ← Where to SEARCH (NEW!)
            max_price=max_price,
            min_safety=0,
            max_iterations=max_iterations,
            quality_threshold=8,
            filters=extracted_filters
        )
        
        if results:
            st.session_state.last_search_results = results
            st.session_state.conversation_history.append(
                ("assistant", results['recommendation']['recommendation'][:200])
            )
            
            st.markdown("---")
            st.header("🎯 Your Personalized Recommendations")
            st.markdown(results['recommendation']['recommendation'])
            
            st.markdown("---")
            st.subheader("📋 Top Restaurants")
            
            top_restaurants = results['researcher_data'].head(10)
            
            for idx, (_, rest) in enumerate(top_restaurants.iterrows(), 1):
                with st.expander(f"{idx}. 🍴 {rest['RESTAURANT_NAME']} - {rest['PRIMARY_CUISINE']}", expanded=(idx <= 3)):
                    c1, c2, c3 = st.columns(3)
                    
                    with c1:
                        st.write(f"**📍 Location:** {rest.get('NEIGHBORHOOD', 'N/A')}")
                        if pd.notna(rest.get('PRICE_LEVEL')):
                            st.write(f"**💰 Price:** {'$' * int(rest['PRICE_LEVEL'])}")
                        if rest.get('YELP_RATING') not in [None, 'N/A']:
                            st.write(f"**⭐ Yelp:** {rest['YELP_RATING']}")
                    
                    with c2:
                        if pd.notna(rest.get('OVERALL_SCORE')):
                            st.metric("Overall Score", f"{rest['OVERALL_SCORE']:.1f}/100")
                        if pd.notna(rest.get('SAFETY_SCORE')):
                            st.metric("Safety Score", f"{rest['SAFETY_SCORE']:.1f}/100")
                    
                    with c3:
                        attributes = []
                        if rest.get('SERVES_VEGETARIAN'):
                            attributes.append("🥗 Vegetarian")
                        if rest.get('IS_WHEELCHAIR_ACCESSIBLE'):
                            attributes.append("♿ Accessible")
                        if rest.get('GOOD_FOR_GROUPS'):
                            attributes.append("👥 Groups")
                        if rest.get('ALLOWS_DOGS'):
                            attributes.append("🐕 Pet-friendly")
                        if rest.get('OUTDOOR_SEATING'):
                            attributes.append("🌳 Outdoor")
                        
                        if attributes:
                            st.write("**Features:**")
                            for attr in attributes:
                                st.write(attr)
                    
                    st.markdown("---")
                    with st.expander("📝 Customer Reviews", expanded=False):
                        display_review_summary(
                            rest['RESTAURANT_ID'],
                            rest['RESTAURANT_NAME']
                        )
                    
                    if rest.get('YELP_URL'):
                        st.markdown(f"[🔗 View on Yelp →]({rest['YELP_URL']})")

# Conversation history
st.markdown("---")
if len(st.session_state.conversation_history) > 0:
    with st.expander("💬 Conversation History"):
        for role, msg in st.session_state.conversation_history:
            if role == "user":
                st.info(f"**You:** {msg}")
            else:
                st.success(f"**Assistant:** {msg[:150]}...")

# Conversational chat
st.markdown("---")
st.header("💬 Continue the Conversation")
st.caption("Ask follow-up questions - I'll understand what you mean!")

if st.session_state.last_search_results:
    chat_input = st.text_input(
        "Ask anything about the results:",
        placeholder="e.g., 'which is closest to Harvard?', 'cheapest one?'"
    )
    
    if st.button("💬 Ask", use_container_width=True):
        if chat_input:
            st.markdown("---")
            
            intent = intent_understanding_agent(
                chat_input,
                st.session_state.last_search_results
            )
            
            execution_result = execute_intent(
                intent,
                st.session_state.last_search_results,
                user_location
            )
            
            if "error" in execution_result:
                st.error(f"❌ {execution_result['error']}")
            elif execution_result.get('action') == 'trigger_new_search':
                st.info("🔍 " + execution_result['message'])
            elif execution_result.get('action') == 'unknown':
                st.warning("⚠️ " + execution_result['message'])
            elif 'results' in execution_result:
                results_df = execution_result['results']
                action = execution_result['action']
                
                if action == "show_closest":
                    st.success(f"✅ Closest to {execution_result['location']}:")
                    for i, (_, r) in enumerate(results_df.iterrows(), 1):
                        dist_mi = r.get('CALC_DIST_MI', 0)
                        st.markdown(f"**{i}. {r['RESTAURANT_NAME']}** - {dist_mi:.2f} mi")
                
                elif action == "show_cheapest":
                    st.success("✅ Most affordable:")
                    for i, (_, r) in enumerate(results_df.iterrows(), 1):
                        st.markdown(f"**{i}. {r['RESTAURANT_NAME']}** - {'$' * int(r['PRICE_LEVEL'])}")
                
                elif action == "show_safest":
                    st.success("✅ Safest:")
                    for i, (_, r) in enumerate(results_df.iterrows(), 1):
                        st.markdown(f"**{i}. {r['RESTAURANT_NAME']}** - Safety: {r['SAFETY_SCORE']:.1f}")
                
                st.session_state.conversation_history.append(("user", chat_input))
                st.session_state.conversation_history.append(("assistant", f"Found {len(results_df)} results"))
else:
    st.info("💡 Make a search first, then ask follow-up questions!")

st.markdown("---")
st.caption("LocalEats AI - Boston/Cambridge/Somerville | Powered by Snowflake Cortex & Multi-Agent Architecture")