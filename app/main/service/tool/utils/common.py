"""Common utilities for tool execution"""
from typing import Dict, List, Any, Optional
from datetime import datetime


class ToolUtils:
    """Utility functions for tool execution"""

    @staticmethod
    def create_empty_result(
        timeframe: Any = None,
        message: str = "No data available",
        **kwargs
    ) -> Dict[str, Any]:
        """Create a standardized empty result"""
        result = {
            "summary": {
                "message": message,
                **kwargs
            },
            "data": []
        }
        if timeframe is not None:
            result["summary"]["timeframe"] = timeframe
        return result

    @staticmethod
    def format_timestamp(dt: Optional[datetime]) -> Optional[str]:
        """Format datetime to ISO string"""
        return dt.isoformat() if dt else None

    @staticmethod
    def aggregate_counts(items: List[Dict[str, Any]], key: str) -> Dict[str, int]:
        """Aggregate counts by a specific key"""
        counts = {}
        for item in items:
            value = item.get(key)
            if value:
                counts[value] = counts.get(value, 0) + 1
        return counts

    @staticmethod
    def validate_timeframe(
        timeframe: Any,
        min_days: int = 1,
        max_days: int = 365,
        default: int = 7
    ) -> int:
        """Validate and normalize timeframe parameter"""
        if isinstance(timeframe, int):
            return max(min_days, min(timeframe, max_days))
        elif isinstance(timeframe, str) and timeframe.isdigit():
            return max(min_days, min(int(timeframe), max_days))
        return default

    @staticmethod
    def filter_by_metrics(
        data: Dict[str, Any],
        requested_metrics: List[str],
        metric_mapping: Dict[str, List[str]]
    ) -> Dict[str, Any]:
        """Filter data to include only requested metrics"""
        filtered = {}

        for metric in requested_metrics:
            if metric in metric_mapping:
                for field in metric_mapping[metric]:
                    if field in data:
                        filtered[field] = data[field]

        return filtered