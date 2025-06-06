"""Base class for tool executors"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session


class ToolExecutor(ABC):
    """Abstract base class for all tool executors"""

    def __init__(self, db: Session, tool_config: Dict[str, Any] = None):
        self.db = db
        self.config = tool_config or {}

    @abstractmethod
    def execute(
        self,
        baby_ids: List[int],
        user_id: int,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute the tool logic"""
        pass

    @abstractmethod
    def validate_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and normalize input parameters"""
        pass

    def get_config_value(self, key: str, default: Any = None) -> Any:
        """Get configuration value with fallback to default"""
        keys = key.split('.')
        value = self.config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value