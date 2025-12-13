"""
Writer Agent - Generates natural language recommendations
"""
import pandas as pd
from models.agent_message import AgentMessage
from utils import display_agent_status, call_cortex

def writer_agent(researcher_msg: AgentMessage, user_query: str, user_location: dict = None) -> AgentMessage:
    """
    Generates natural language recommendations ONLY from database data
    """
    display_agent_status("Writer Agent", "running", "Generating recommendations...")
    
    if not researcher_msg.is_successful():
        return AgentMessage("Writer", "failed", None, 0.0)
    
    top_restaurants = researcher_msg.data.head(5).to_dict('records')
    
    # Format restaurant data for prompt
    restaurant_summary = ""
    for i, rest in enumerate(top_restaurants, 1):
        yelp = rest.get('YELP_RATING', 'N/A')
        phone = rest.get('PHONE', 'N/A')
        address = rest.get('STREET_ADDRESS', rest['NEIGHBORHOOD'])
        
        distance_info = ""
        if 'DISTANCE_FROM_USER_MI' in rest and pd.notna(rest['DISTANCE_FROM_USER_MI']):
            dist_mi = rest['DISTANCE_FROM_USER_MI']
            distance_info = f"   - 📍 **{dist_mi:.1f} miles from you** (~{int(dist_mi * 20)} min drive)\n"
        
        transit_info = ""
        if pd.notna(rest.get('NEAREST_STOP_DISTANCE_M')):
            transit_m = rest['NEAREST_STOP_DISTANCE_M']
            walk_min = int(transit_m / 80)
            transit_info = f"   - 🚇 Nearest T: {transit_m:.0f}m walk (~{walk_min} min)\n"
        
        restaurant_summary += f"""
{i}. **{rest['RESTAURANT_NAME']}** ({rest['PRIMARY_CUISINE']})
   - Location: {rest['NEIGHBORHOOD']}
   - Address: {address}
   - Phone: {phone}
   - Price: {'$' * int(rest['PRICE_LEVEL'])}
{distance_info}{transit_info}   - Overall: {rest['OVERALL_SCORE']:.1f}/100 | Safety: {rest['SAFETY_SCORE']:.1f}/100
   - Yelp: {yelp if yelp != 'N/A' else 'N/A'} | Tier: {rest['RECOMMENDATION_TIER']}
"""
    
    location_context = ""
    if user_location:
        location_context = f"\n\nUSER LOCATION: {user_location.get('name')}. MENTION distances prominently!"
    
    writer_prompt = f"""You are LocalEats AI for Boston restaurants.

User: {user_query}{location_context}

Restaurants:
{restaurant_summary}

RULES:
1. ONLY recommend from the list above
2. Write 3-4 warm paragraphs
3. Recommend top 3 restaurants
4. Highlight distance (if provided), safety, transit, value
5. Be honest about tradeoffs

Write naturally and enthusiastically."""
    
    recommendation_text = call_cortex(writer_prompt, temperature=0.7)
    
    if recommendation_text:
        display_agent_status("Writer Agent", "success", "Done")
        return AgentMessage(
            agent_name="Writer",
            status="success",
            data={
                "recommendation": recommendation_text,
                "restaurants": top_restaurants[:3],
                "full_data": researcher_msg.data
            },
            confidence=0.85
        )
    else:
        return AgentMessage("Writer", "failed", None, 0.0)