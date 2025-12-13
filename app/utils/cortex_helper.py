"""
Snowflake Cortex AI helper functions
"""
import streamlit as st
from snowflake.snowpark.context import get_active_session

def call_cortex(prompt: str, model: str = "mistral-large", temperature: float = 0.7) -> str:
    """Call Snowflake Cortex AI with a prompt"""
    try:
        session = get_active_session()  # Get directly
        safe_prompt = prompt.replace("'", "''")
        query = f"SELECT SNOWFLAKE.CORTEX.COMPLETE('{model}', '{safe_prompt}') as response"
        result = session.sql(query).collect()
        return result[0]['RESPONSE'] if result else None
    except Exception as e:
        st.error(f"❌ Cortex Error: {str(e)}")
        return None

def display_agent_status(agent_name: str, status: str, details: str = ""):
    """Display agent execution status with consistent formatting"""
    if status == "running":
        st.info(f"⚙️ **{agent_name}**: {details}")
    elif status == "success":
        st.success(f"✅ **{agent_name}**: {details}")
    elif status == "warning":
        st.warning(f"⚠️ **{agent_name}**: {details}")
    elif status == "error":
        st.error(f"❌ **{agent_name}**: {details}")