"""
Input Validation Agent - WITH LLM INTENT VERIFICATION
Uses LLM to verify query is actually about restaurants
Prevents hallucination on off-topic queries
"""
from models.agent_message import AgentMessage
from utils import display_agent_status
from utils.cortex_helper import call_cortex
from config import INVALID_LOCATIONS, RESTAURANT_KEYWORDS

def input_validation_agent(user_query: str) -> AgentMessage:
    """
    Validates user input with LLM-powered restaurant intent verification
    
    Two-stage validation:
    1. Basic checks (length, geography)
    2. LLM verification (is this about restaurants?)
    """
    display_agent_status("Input Validator", "running", "Validating query...")

    # STAGE 1: Basic validation
    if len(user_query.strip()) < 2:
        return AgentMessage(
            "InputValidator", "failed", None, 0.0,
            metadata={"error": "Query too short", "suggestion": "Please describe what you're looking for"}
        )

    if len(user_query) > 500:
        return AgentMessage(
            "InputValidator", "failed", None, 0.0,
            metadata={"error": "Query too long", "suggestion": "Keep under 500 characters"}
        )

    query_lower = user_query.lower()

    # Geographic validation (expanded for international locations)
    # Add common non-Boston locations
    expanded_invalid = INVALID_LOCATIONS + [
        'cambodia', 'thailand', 'vietnam', 'china', 'japan', 'korea',
        'france', 'italy', 'spain', 'mexico', 'canada',
        'new york', 'nyc', 'san francisco', 'los angeles', 'chicago',
        'seattle', 'miami', 'austin', 'denver'
    ]
    
    for location in expanded_invalid:
        if f" {location} " in f" {query_lower} " or query_lower.startswith(f"{location} ") or query_lower.endswith(f" {location}"):
            # Exception: If it's a cuisine type, allow it (e.g., "cambodian restaurant")
            if location in ['cambodia', 'thailand', 'vietnam', 'china', 'japan', 'korea', 'france', 'italy', 'spain', 'mexico']:
                cuisine_words = ['restaurant', 'food', 'cuisine', 'place', 'spot']
                if any(word in query_lower for word in cuisine_words):
                    # It's asking for cuisine type, not location - allow it
                    continue
            
            return AgentMessage(
                "InputValidator", "failed", None, 0.0,
                metadata={
                    "error": "Geographic restriction",
                    "suggestion": "LocalEats AI only covers Boston/Cambridge/Somerville"
                }
            )
    
    # STAGE 2: LLM-Powered Restaurant Intent Verification
    # This prevents non-food queries from passing through
    
    intent_check_prompt = f"""Is this query about finding, recommending, or discussing RESTAURANTS or FOOD?

Query: "{user_query}"

Answer with ONLY "YES" or "NO".

Examples:
"cheap mexican food" → YES
"pizza near MIT" → YES  
"vegetarian restaurants" → YES
"president of cambodia" → NO
"best hotels in boston" → NO
"weather in boston" → NO
"how to cook pasta" → NO (about cooking, not finding restaurants)

Answer (YES or NO only):"""
    
    result = call_cortex(intent_check_prompt, temperature=0.1)
    
    if result:
        answer = result.strip().upper()
        
        if "NO" in answer or "NOT" in answer:
            return AgentMessage(
                "InputValidator", "failed", None, 0.0,
                metadata={
                    "error": "Not a restaurant query",
                    "suggestion": "LocalEats AI helps you find restaurants in Boston. Try: 'cheap Mexican food' or 'coffee shop near MIT'"
                }
            )
    
    # If LLM call fails, fall back to keyword check
    else:
        restaurant_keywords = RESTAURANT_KEYWORDS + [
            'cafe', 'caffe', 'coffee', 'cofee', 'cofe',
            'food', 'foosd', 'fo0d', 'fod',
            'restaurant', 'resturant', 'restarant',
            'friendly', 'place', 'spot', 'eat', 'eating',
            'mexican', 'meican', 'italian', 'chinese', 'thai', 'pizza', 'burger',
            'near', 'in', 'at', 'around'
        ]
        
        has_keyword = any(kw in query_lower for kw in restaurant_keywords)
        
        if not has_keyword:
            return AgentMessage(
                "InputValidator", "failed", None, 0.0,
                metadata={
                    "error": "No restaurant keywords",
                    "suggestion": "Try: 'Italian restaurant', 'coffee shop', or 'cheap Mexican food'"
                }
            )

    display_agent_status("Input Validator", "success", "Query validated")
    return AgentMessage("InputValidator", "success", {"original_query": user_query}, 0.95)