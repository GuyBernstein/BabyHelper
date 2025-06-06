"""Tool registry for managing tool executors"""
from typing import Dict, Type
from app.main.model.tool import ToolType
from .executor import ToolExecutor


class ToolRegistry:
    """Registry for tool executors"""
    _executors: Dict[ToolType, Type[ToolExecutor]] = {}

    @classmethod
    def register(cls, tool_type: ToolType):
        """Decorator to register tool executors"""
        def decorator(executor_class: Type[ToolExecutor]):
            cls._executors[tool_type] = executor_class
            return executor_class
        return decorator

    @classmethod
    def get_executor(cls, tool_type: ToolType) -> Type[ToolExecutor]:
        """Get executor class for tool type"""
        if tool_type not in cls._executors:
            raise ValueError(f"No executor registered for tool type: {tool_type}")
        return cls._executors[tool_type]

    @classmethod
    def get_all_executors(cls) -> Dict[ToolType, Type[ToolExecutor]]:
        """Get all registered executors"""
        return cls._executors.copy()