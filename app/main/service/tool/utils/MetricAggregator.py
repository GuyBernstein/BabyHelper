from collections import defaultdict
from datetime import datetime
from typing import List, Any, Dict


class MetricAggregator:
    """Utilities for aggregating metrics across multiple data sources"""

    @staticmethod
    def calculate_average_with_precision(
        total: float,
        count: int,
        precision_config: Dict[str, Any],
        metric_type: str = 'normal'
    ) -> float:
        """
        Calculate average with appropriate precision based on configuration.

        Args:
            total: Sum of values
            count: Number of values
            precision_config: Precision settings from config
            metric_type: Type of metric for precision rules

        Returns:
            Rounded average value
        """
        if count == 0:
            return 0.0

        avg = total / count

        # Handle small value precision
        if metric_type in ['sleep', 'duration'] and 'small_value_threshold' in precision_config:
            threshold = precision_config['small_value_threshold']
            if avg < threshold:
                return round(avg, precision_config.get('small_value_decimals', 2))

        # Default precision
        return round(avg, precision_config.get('normal_decimals', 1))

    @staticmethod
    def calculate_percentage(
        count: int,
        total: int,
        decimals: int = 1
    ) -> float:
        """Calculate percentage with proper handling of zero division"""
        if total == 0:
            return 0.0
        return round((count / total) * 100, decimals)

    @staticmethod
    def aggregate_by_date(
        items: List[Any],
        date_extractor,
        value_extractor=None
    ) -> Dict[datetime, List[Any]]:
        """
        Aggregate items by date.

        Args:
            items: List of items to aggregate
            date_extractor: Function to extract date from item
            value_extractor: Optional function to extract value (default: return item)

        Returns:
            Dictionary mapping dates to lists of values
        """
        aggregated = defaultdict(list)
        for item in items:
            date_key = date_extractor(item).date()
            value = value_extractor(item) if value_extractor else item
            aggregated[date_key].append(value)
        return dict(aggregated)