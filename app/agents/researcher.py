"""
Researcher Agent - Enhanced with intelligent attribute filtering

FIXES:
- Handles None values safely (no more: 'NoneType' is not iterable)
- Normalizes filter keys and values (lists/None/strings)
- Maps vegan -> SERVES_VEGETARIAN (no SERVES_VEGAN column assumed)
"""

import streamlit as st
import pandas as pd
from models.agent_message import AgentMessage
from utils import display_agent_status


def _ensure_list(value):
    """Convert None/str/list into a clean list[str]."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip().lower() for v in value if str(v).strip()]
    if isinstance(value, str):
        v = value.strip()
        return [v.lower()] if v else []
    # fallback
    return [str(value).strip().lower()]


def _normalize_attribute_filters(attribute_filters: dict | None) -> dict:
    """
    Accepts various shapes coming from LLM/old UI:
      - None
      - keys: service vs service_type, special vs special_needs
      - values: null, [], "outdoor", etc.
    Returns canonical:
      {
        "dietary": [...],
        "meal_time": [...],
        "accessibility": [...],
        "service_type": [...],
        "special_needs": [...]
      }
    """
    if not attribute_filters:
        return {
            "dietary": [],
            "meal_time": [],
            "accessibility": [],
            "service_type": [],
            "special_needs": [],
        }

    # allow older key names too
    service_val = attribute_filters.get("service_type", attribute_filters.get("service"))
    special_val = attribute_filters.get("special_needs", attribute_filters.get("special"))

    normalized = {
        "dietary": _ensure_list(attribute_filters.get("dietary")),
        "meal_time": _ensure_list(attribute_filters.get("meal_time")),
        "accessibility": _ensure_list(attribute_filters.get("accessibility")),
        "service_type": _ensure_list(service_val),
        "special_needs": _ensure_list(special_val),
    }

    # also accept accidental singular keys
    if "service" in attribute_filters and not normalized["service_type"]:
        normalized["service_type"] = _ensure_list(attribute_filters.get("service"))
    if "special" in attribute_filters and not normalized["special_needs"]:
        normalized["special_needs"] = _ensure_list(attribute_filters.get("special"))

    return normalized


def researcher_agent(
    retriever_msg: AgentMessage,
    max_price="Any",
    min_safety=0,
    attribute_filters: dict = None
) -> AgentMessage:
    """
    Applies business rules filters to retrieved restaurants and ranks them.

    NOTE:
    - vegan maps to SERVES_VEGETARIAN
    - handles null/None filters safely
    """
    display_agent_status("Researcher Agent", "running", "Filtering and ranking restaurants...")

    if not retriever_msg or not retriever_msg.is_successful():
        return AgentMessage("Researcher", "failed", None, 0.0, metadata={"reason": "retriever_failed"})

    try:
        results_df = retriever_msg.data.copy()
        if results_df is None or len(results_df) == 0:
            return AgentMessage("Researcher", "failed", None, 0.0, metadata={"reason": "no_rows"})

        initial_count = len(results_df)

        # ----------------------------
        # Price filter
        # ----------------------------
        if max_price != "Any" and "PRICE_LEVEL" in results_df.columns:
            try:
                max_price_int = int(max_price)
                before = len(results_df)
                results_df = results_df[pd.to_numeric(results_df["PRICE_LEVEL"], errors="coerce") <= max_price_int]
                after = len(results_df)
                st.caption(f"💰 Price: {before} → {after} (≤ {'$' * max_price_int})")
            except Exception:
                pass

        # ----------------------------
        # Safety filter
        # ----------------------------
        if min_safety and min_safety > 0 and "SAFETY_SCORE" in results_df.columns:
            before = len(results_df)
            results_df = results_df[pd.to_numeric(results_df["SAFETY_SCORE"], errors="coerce") >= float(min_safety)]
            after = len(results_df)
            st.caption(f"🛡️ Safety: {before} → {after} (≥ {min_safety})")

        # ----------------------------
        # Attribute filters (robust)
        # ----------------------------
        f = _normalize_attribute_filters(attribute_filters)

        # DIETARY
        dietary = f["dietary"]
        if ("vegetarian" in dietary) or ("vegan" in dietary):
            if "SERVES_VEGETARIAN" in results_df.columns:
                before = len(results_df)
                results_df = results_df[results_df["SERVES_VEGETARIAN"] == True]
                after = len(results_df)
                st.caption(f"🥗 Vegetarian/Vegan: {before} → {after} (using SERVES_VEGETARIAN)")

        # MEAL TIME
        meal = f["meal_time"]
        if "breakfast" in meal and "SERVES_BREAKFAST" in results_df.columns:
            before = len(results_df)
            results_df = results_df[results_df["SERVES_BREAKFAST"] == True]
            st.caption(f"🍳 Breakfast: {before} → {len(results_df)}")
        if "lunch" in meal and "SERVES_LUNCH" in results_df.columns:
            before = len(results_df)
            results_df = results_df[results_df["SERVES_LUNCH"] == True]
            st.caption(f"🥪 Lunch: {before} → {len(results_df)}")
        if "dinner" in meal and "SERVES_DINNER" in results_df.columns:
            before = len(results_df)
            results_df = results_df[results_df["SERVES_DINNER"] == True]
            st.caption(f"🍽️ Dinner: {before} → {len(results_df)}")

        # ACCESSIBILITY / GROUPS
        acc = f["accessibility"]
        if "wheelchair" in acc and "IS_WHEELCHAIR_ACCESSIBLE" in results_df.columns:
            before = len(results_df)
            results_df = results_df[results_df["IS_WHEELCHAIR_ACCESSIBLE"] == True]
            st.caption(f"♿ Wheelchair: {before} → {len(results_df)}")
        if ("groups" in acc or "group" in acc) and "GOOD_FOR_GROUPS" in results_df.columns:
            before = len(results_df)
            results_df = results_df[results_df["GOOD_FOR_GROUPS"] == True]
            st.caption(f"👥 Groups: {before} → {len(results_df)}")
        if ("children" in acc or "kids" in acc or "family" in acc) and "GOOD_FOR_CHILDREN" in results_df.columns:
            before = len(results_df)
            results_df = results_df[results_df["GOOD_FOR_CHILDREN"] == True]
            st.caption(f"👶 Kids/Family: {before} → {len(results_df)}")

        # SERVICE TYPE
        svc = f["service_type"]
        if "outdoor" in svc and "OUTDOOR_SEATING" in results_df.columns:
            before = len(results_df)
            results_df = results_df[results_df["OUTDOOR_SEATING"] == True]
            st.caption(f"🌳 Outdoor: {before} → {len(results_df)}")
        if "takeout" in svc and "TAKEOUT" in results_df.columns:
            before = len(results_df)
            results_df = results_df[results_df["TAKEOUT"] == True]
            st.caption(f"🥡 Takeout: {before} → {len(results_df)}")
        if "delivery" in svc and "DELIVERY" in results_df.columns:
            before = len(results_df)
            results_df = results_df[results_df["DELIVERY"] == True]
            st.caption(f"🚚 Delivery: {before} → {len(results_df)}")
        if ("reservations" in svc or "reservable" in svc) and "RESERVABLE" in results_df.columns:
            before = len(results_df)
            results_df = results_df[results_df["RESERVABLE"] == True]
            st.caption(f"📅 Reservations: {before} → {len(results_df)}")

        # SPECIAL NEEDS
        sp = f["special_needs"]
        if ("coffee_shop" in sp or "cafe" in sp) and "SERVES_COFFEE" in results_df.columns:
            before = len(results_df)
            results_df = results_df[results_df["SERVES_COFFEE"] == True]
            st.caption(f"☕ Coffee: {before} → {len(results_df)}")

        if ("pet_friendly" in sp or "dogs" in sp) and "ALLOWS_DOGS" in results_df.columns:
            before = len(results_df)
            results_df = results_df[results_df["ALLOWS_DOGS"] == True]
            st.caption(f"🐕 Pet-friendly: {before} → {len(results_df)}")

        if "live_music" in sp and "LIVE_MUSIC" in results_df.columns:
            before = len(results_df)
            results_df = results_df[results_df["LIVE_MUSIC"] == True]
            st.caption(f"🎵 Live music: {before} → {len(results_df)}")

        # ----------------------------
        # Rank / return
        # ----------------------------
        if len(results_df) == 0:
            display_agent_status("Researcher Agent", "warning", "No restaurants passed filters")
            return AgentMessage(
                agent_name="Researcher",
                status="partial",
                data=None,  # ✅ FIXED: Return None, not unfiltered data!
                confidence=0.0,  # ✅ FIXED: 0 confidence when no matches
                metadata={
                    "filters_too_strict": True,
                    "initial_count": initial_count,
                    "normalized_filters": f,
                    "num_results": 0  # ✅ FIXED: Explicit count
                }
            )

        if "OVERALL_SCORE" in results_df.columns:
            results_df = results_df.sort_values("OVERALL_SCORE", ascending=False)

        display_agent_status("Researcher Agent", "success", f"Filtered to {len(results_df)} restaurants (from {initial_count})")

        with st.expander("📊 View Filtered Results"):
            display_cols = ["RESTAURANT_NAME", "PRIMARY_CUISINE", "NEIGHBORHOOD", "OVERALL_SCORE", "SAFETY_SCORE", "RECOMMENDATION_TIER"]
            available_cols = [c for c in display_cols if c in results_df.columns]
            st.dataframe(results_df[available_cols].head(20))

        return AgentMessage(
            agent_name="Researcher",
            status="success",
            data=results_df,
            confidence=0.9,
            metadata={
                "num_results": len(results_df),
                "initial_count": initial_count,
                "normalized_filters": f
            }
        )

    except Exception as e:
        st.error(f"Researcher error: {e}")
        return AgentMessage("Researcher", "failed", None, 0.0, metadata={"exception": str(e)})