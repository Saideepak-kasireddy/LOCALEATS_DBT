"""
Agent Message class for structured agent-to-agent communication
"""
from datetime import datetime
from typing import Any, Dict, Optional

class AgentMessage:
    """Structured message format for agent communication"""
    
    def __init__(
        self, 
        agent_name: str, 
        status: str, 
        data: Any, 
        confidence: float = 1.0, 
        metadata: Optional[Dict] = None
    ):
        self.agent = agent_name
        self.status = status  # "success", "partial", "failed"
        self.data = data
        self.confidence = confidence
        self.metadata = metadata or {}
        self.timestamp = datetime.now().isoformat()
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "agent": self.agent,
            "status": self.status,
            "data": self.data,
            "confidence": self.confidence,
            "metadata": self.metadata,
            "timestamp": self.timestamp
        }
    
    def is_successful(self) -> bool:
        """Check if agent execution was successful"""
        return self.status == "success" and self.data is not None