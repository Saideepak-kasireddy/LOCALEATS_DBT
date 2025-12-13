"""
Reviewer Agent - Evaluates recommendation quality

FIXES:
- Signature compatible with orchestrator: reviewer_agent(writer_msg, user_query=None, iteration=1)
- Defensive access to writer_msg.data (dict vs string)
- Robust score parsing (handles "OVERALL: 8", "Overall 8/10", etc.)
- Returns: (AgentMessage, score, feedback, raw_eval) exactly as orchestrator expects
"""

import re
import streamlit as st
from models.agent_message import AgentMessage
from utils import display_agent_status, call_cortex


def _extract_text(writer_msg: AgentMessage) -> str:
    """Safely extract recommendation text from writer agent output."""
    if not writer_msg or not writer_msg.is_successful():
        return ""

    data = writer_msg.data
    if data is None:
        return ""

    # Most common: dict with "recommendation"
    if isinstance(data, dict) and "recommendation" in data:
        return str(data.get("recommendation") or "").strip()

    # Sometimes people return raw string
    return str(data).strip()


def _parse_score(evaluation_text: str) -> int:
    """
    Extract a 1-10 score from evaluation text.
    Accepts formats like:
      - OVERALL: 8
      - OVERALL: 8/10
      - Overall 8
      - Score: 7
    Defaults to 7 if parsing fails.
    """
    if not evaluation_text:
        return 7

    text = evaluation_text.strip()

    # Prefer explicit OVERALL pattern
    m = re.search(r"OVERALL\s*[:\-]\s*(\d{1,2})", text, re.IGNORECASE)
    if m:
        val = int(m.group(1))
        return max(1, min(10, val))

    # Try "x/10"
    m = re.search(r"(\d{1,2})\s*/\s*10", text)
    if m:
        val = int(m.group(1))
        return max(1, min(10, val))

    # Fallback: first standalone number 1-10
    m = re.search(r"\b(10|[1-9])\b", text)
    if m:
        val = int(m.group(1))
        return max(1, min(10, val))

    return 7


def reviewer_agent(writer_msg: AgentMessage, user_query: str = None, iteration: int = 1):
    """
    Evaluates recommendation quality and provides structured feedback.

    Returns:
      review_msg: AgentMessage
      score: int (1-10)
      feedback: str (short improvement guidance)
      raw_eval: str (raw LLM output)
    """
    display_agent_status("Reviewer Agent", "running", f"Evaluating (Iteration {iteration})...")

    if not writer_msg or not writer_msg.is_successful():
        return AgentMessage("Reviewer", "failed", None, 0.0), 0, "Writer output missing.", ""

    recommendation_text = _extract_text(writer_msg)
    if not recommendation_text:
        return AgentMessage("Reviewer", "failed", None, 0.0), 0, "Empty recommendation text.", ""

    uq = (user_query or "").strip()
    if not uq:
        # If user_query isn't provided, still evaluate based on general quality
        uq = "N/A (not provided)"

    review_prompt = f"""You are a strict QA reviewer for restaurant recommendations.

USER QUERY:
{uq}

RECOMMENDATION:
{recommendation_text}

Score each dimension from 1 to 10:
- RELEVANCE (matches query + filters)
- SPECIFICITY (uses concrete restaurant details)
- CLARITY (easy to read)
- HONESTY (mentions tradeoffs/uncertainty)
- ACTIONABILITY (helps user decide)

Return in this format ONLY:

RELEVANCE: x
SPECIFICITY: x
CLARITY: x
HONESTY: x
ACTIONABILITY: x
OVERALL: x
FEEDBACK: <one short paragraph of improvements>
"""

    raw_eval = call_cortex(review_prompt, temperature=0.2)

    score = _parse_score(raw_eval)
    feedback = ""

    if raw_eval:
        m = re.search(r"FEEDBACK\s*:\s*(.*)", raw_eval, re.IGNORECASE | re.DOTALL)
        if m:
            feedback = m.group(1).strip()

    # Display metric in UI
    st.metric("Quality Score", f"{score}/10")

    if score >= 8:
        display_agent_status("Reviewer Agent", "success", f"Approved ({score}/10)")
        status = "success"
        conf = 0.9
    else:
        display_agent_status("Reviewer Agent", "warning", f"Below threshold ({score}/10)")
        status = "partial"
        conf = 0.7

    review_msg = AgentMessage(
        agent_name="Reviewer",
        status=status,
        data={
            "score": score,
            "feedback": feedback,
            "raw_evaluation": raw_eval
        },
        confidence=conf
    )

    return review_msg, score, feedback, raw_eval