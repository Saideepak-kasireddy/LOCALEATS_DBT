"""
Orchestrator Agent - CLEAN VERSION
Passes analyst_data to retriever (single source of truth!)
"""

import streamlit as st
from models.agent_message import AgentMessage
from utils import display_agent_status

from agents.input_validator import input_validation_agent
from agents.retriever import retriever_agent
from agents.researcher import researcher_agent
from agents.writer import writer_agent
from agents.reviewer import reviewer_agent


def _ensure_list(x):
    if x is None:
        return []
    if isinstance(x, list):
        return [str(v).strip().lower() for v in x if str(v).strip()]
    if isinstance(x, str):
        s = x.strip()
        return [s.lower()] if s else []
    return [str(x).strip().lower()]


def _normalize_filters(filters: dict | None) -> dict:
    """Normalize filters"""
    filters = filters or {}
    service_val = filters.get("service_type", filters.get("service"))
    special_val = filters.get("special_needs", filters.get("special"))
    
    return {
        "dietary": _ensure_list(filters.get("dietary")),
        "meal_time": _ensure_list(filters.get("meal_time")),
        "accessibility": _ensure_list(filters.get("accessibility")),
        "service_type": _ensure_list(service_val),
        "special_needs": _ensure_list(special_val),
    }


def _safe_len(df) -> int:
    try:
        return len(df) if df is not None else 0
    except Exception:
        return 0


def orchestrator_agent(
    user_query: str,
    analyst_data: dict,
    user_location: dict = None,
    search_area: dict = None,  # ← NEW: Where to search
    max_price="Any",
    min_safety: int = 0,
    max_iterations: int = 2,
    quality_threshold: int = 8,
    filters: dict = None
) -> dict | None:
    """
    Orchestrator that uses analyst_data as single source of truth
    
    Args:
        user_query: Original query text
        analyst_data: Full analyst output (cuisine, location, budget, filters)
        user_location: User's actual location (from input box)
        max_price: UI-selected max price (analyst can override)
        filters: Extracted filters from analyst
    """
    
    # Normalize filters
    norm_filters = _normalize_filters(filters)
    
    st.subheader("🤖 Multi-Agent System Execution")
    st.caption(f"Max Iterations: {max_iterations} | Quality Threshold: {quality_threshold}/10")
    
    # ==========================
    # 1) INPUT VALIDATION
    # ==========================
    validator_msg: AgentMessage = input_validation_agent(user_query)
    if not validator_msg or not validator_msg.is_successful():
        err = (validator_msg.metadata or {}).get("error", "Invalid input") if validator_msg else "Invalid input"
        display_agent_status("Input Validator", "warning", err)
        suggestion = (validator_msg.metadata or {}).get("suggestion") if validator_msg else None
        if suggestion:
            st.info(f"💡 Try: {suggestion}")
        return None
    
    # ==========================
    # 2) RETRIEVER (with analyst_data and search_area!)
    # ==========================
    retriever_msg: AgentMessage = retriever_agent(
        user_query=user_query,
        analyst_data=analyst_data,
        user_location=user_location,  # User's actual location
        search_area=search_area,  # ← NEW: Where to search
        top_k=20
    )
    
    if not retriever_msg or not retriever_msg.is_successful() or _safe_len(retriever_msg.data) == 0:
        display_agent_status("Retriever Agent", "failed", "No restaurants retrieved")
        return None
    
    initial_count = _safe_len(retriever_msg.data)
    
    # ==========================
    # 3) RESEARCHER
    # ==========================
    # Use budget from analyst if available
    budget_info = analyst_data.get('budget', {})
    if budget_info.get('max_price_level') and max_price == "Any":
        max_price = budget_info['max_price_level']
    
    researcher_msg: AgentMessage = researcher_agent(
        retriever_msg=retriever_msg,
        max_price=max_price,
        min_safety=min_safety,
        attribute_filters=norm_filters
    )
    
    researcher_df = researcher_msg.data if researcher_msg else None
    num_results = _safe_len(researcher_df)
    
    # ==========================
    # 4) HANDLE ZERO RESULTS
    # ==========================
    if num_results == 0:
        st.markdown("---")
        st.warning("⚠️ **No restaurants match your criteria**")
        
        active_filters = []
        if norm_filters.get('dietary'):
            active_filters.append(f"🥗 {', '.join(norm_filters['dietary'])}")
        if norm_filters.get('accessibility'):
            active_filters.append(f"♿ {', '.join(norm_filters['accessibility'])}")
        if norm_filters.get('service_type'):
            active_filters.append(f"🍽️ {', '.join(norm_filters['service_type'])}")
        if norm_filters.get('special_needs'):
            active_filters.append(f"✨ {', '.join(norm_filters['special_needs'])}")
        
        if analyst_data.get('cuisine'):
            st.info(f"**Your search:** {analyst_data['cuisine']} cuisine")
        
        if active_filters:
            st.info("**With filters:**\n" + "\n".join(f"- {f}" for f in active_filters))
        
        st.markdown("### 💡 **Suggestions:**")
        st.write("- Try a different cuisine")
        st.write("- Remove some filters")
        st.write("- Search in a broader area")
        
        return None
    
    # ==========================
    # 5) WRITER/REVIEWER LOOP
    # ==========================
    best_writer_msg = None
    best_score = -1
    
    for i in range(int(max_iterations)):
        st.markdown(f"### 🔁 Iteration {i+1}/{max_iterations}")
        
        writer_msg: AgentMessage = writer_agent(
            researcher_msg=researcher_msg,
            user_query=user_query,
            user_location=user_location
        )
        
        if not writer_msg or not writer_msg.is_successful():
            display_agent_status("Writer Agent", "failed", "No output")
            continue
        
        review_msg, score, feedback, raw_eval = reviewer_agent(
            writer_msg,
            user_query=user_query,
            iteration=i + 1
        )
        
        st.caption(f"🧪 Reviewer score: {score}/10")
        if feedback:
            st.caption(f"📝 Feedback: {feedback}")
        
        if score > best_score:
            best_score = score
            best_writer_msg = writer_msg
        
        if score >= quality_threshold:
            display_agent_status("Reviewer Agent", "success", f"Passed ({score}/10)")
            break
    
    if not best_writer_msg:
        return None
    
    # ==========================
    # 6) RETURN RESULTS
    # ==========================
    recommendation_text = (best_writer_msg.data or {}).get("recommendation", "")
    
    return {
        "recommendation": {"recommendation": str(recommendation_text)},
        "researcher_data": researcher_df,
        "retriever_data": retriever_msg.data,
        "quality_score": best_score,
        "analyst_data": analyst_data  # Include analyst data for reference
    }