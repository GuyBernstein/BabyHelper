import statistics
from collections import defaultdict
from typing import List, Any, Optional, Dict

from app.main.service.tool.utils.MetricAggregator import MetricAggregator


class DataProcessor:
    """Utilities for processing and analyzing data patterns"""

    @staticmethod
    def detect_trend(
        values: List[float],
        threshold: float = 0.1
    ) -> str:
        """
        Detect trend in sequential values.

        Args:
            values: List of values in chronological order
            threshold: Percentage threshold for trend detection

        Returns:
            Trend description (improving, declining, stable, insufficient_data)
        """
        if len(values) < 2:
            return "insufficient_data"

        # Compare first half to second half
        mid_point = len(values) // 2
        first_half = values[:mid_point]
        second_half = values[mid_point:]

        if not first_half or not second_half:
            return "insufficient_data"

        first_avg = statistics.mean(first_half)
        second_avg = statistics.mean(second_half)

        if first_avg == 0:
            return "stable"

        change_ratio = (second_avg - first_avg) / first_avg

        if change_ratio > threshold:
            return "improving"
        elif change_ratio < -threshold:
            return "declining"
        else:
            return "stable"

    @staticmethod
    def calculate_distribution(
        items: List[Any],
        key_extractor,
        total: Optional[int] = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        Calculate distribution of items by a key.

        Args:
            items: List of items to analyze
            key_extractor: Function to extract key from item
            total: Optional total count (defaults to len(items))

        Returns:
            Dictionary with distribution data including counts and percentages
        """
        counts = defaultdict(int)
        for item in items:
            key = key_extractor(item)
            if key is not None:
                counts[key] += 1

        total = total or len(items)
        distribution = {}

        for key, count in counts.items():
            distribution[str(key)] = {
                'count': count,
                'percentage': MetricAggregator.calculate_percentage(count, total)
            }

        return distribution