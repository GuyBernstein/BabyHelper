from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict
import statistics


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


class ParameterValidator:
    """Validates and normalizes tool parameters using configuration"""

    @staticmethod
    def validate_base_parameters(
        parameters: Dict[str, Any],
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate common parameters that most tools share.

        Args:
            parameters: Input parameters from user
            config: Tool configuration containing defaults and validation rules

        Returns:
            Dict with validated parameters including:
                - days: Validated timeframe in days
                - include_details: Whether to include detailed patterns
                - requested_metrics: List of validated metric names
        """
        defaults = config.get('defaults', {})
        validation = config.get('validation', {})

        # Validate timeframe
        timeframe = parameters.get('timeframe', defaults.get('timeframe', 7))
        timeframe_bounds = validation.get('timeframe_bounds', {})
        days = ToolUtils.validate_timeframe(
            timeframe,
            timeframe_bounds.get('min', 1),
            timeframe_bounds.get('max', 365),
            defaults.get('timeframe', 7)
        )

        # Extract include_details
        include_details = parameters.get('include_details', defaults.get('include_details', True))

        # Validate metrics
        default_metrics = defaults.get('metrics', [])
        requested_metrics = parameters.get('metrics', default_metrics)
        if not isinstance(requested_metrics, list):
            requested_metrics = default_metrics

        # Filter valid metrics
        allowed_metrics = set(validation.get('allowed_metrics', default_metrics))
        requested_metrics = [m for m in requested_metrics if m in allowed_metrics]

        # Default to all metrics if none valid
        if not requested_metrics:
            requested_metrics = list(allowed_metrics)

        return {
            'days': days,
            'include_details': include_details,
            'requested_metrics': requested_metrics
        }

    @staticmethod
    def validate_filter_parameter(
        parameter_name: str,
        parameter_value: Any,
        allowed_values: List[str],
        default_value: str = 'all'
    ) -> str:
        """
        Validate a filter parameter against allowed values.

        Args:
            parameter_name: Name of the parameter (for documentation)
            parameter_value: Value to validate
            allowed_values: List of allowed values
            default_value: Default value if validation fails

        Returns:
            Validated parameter value
        """
        if parameter_value not in allowed_values:
            return default_value
        return parameter_value


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


class ResultBuilder:
    """Utilities for building standardized results"""

    @staticmethod
    def create_empty_analysis_result(
        days: int,
        requested_metrics: List[str],
        config: Dict[str, Any],
        additional_filters: Optional[Dict[str, Any]] = None,
        metric_defaults: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a standardized empty result for analysis tools.

        Args:
            days: Analysis period in days
            requested_metrics: List of metrics that were requested
            config: Tool configuration for messages
            additional_filters: Any additional filters applied
            metric_defaults: Default values for specific metrics

        Returns:
            Standardized empty result structure
        """
        messages = config.get('messages', {})

        summary = {
            "analysis_period_days": days,
            "babies_analyzed": 0,
            "metrics_analyzed": requested_metrics,
            "message": messages.get('no_data_available', 'No data available for the specified timeframe')
        }

        # Add filter information if provided
        if additional_filters:
            summary["filters_applied"] = additional_filters

        # Add metric-specific defaults
        if metric_defaults:
            for metric, default_value in metric_defaults.items():
                if metric in requested_metrics:
                    summary[metric] = default_value

        return {"summary": summary}

    @staticmethod
    def build_summary_with_metrics(
        base_summary: Dict[str, Any],
        metrics_data: Dict[str, Any],
        requested_metrics: List[str],
        metric_mapping: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Build a summary by adding metric data based on requested metrics.

        Args:
            base_summary: Base summary dict with metadata
            metrics_data: Dictionary containing calculated metric values
            requested_metrics: List of metrics to include
            metric_mapping: Optional mapping of metric names to summary keys

        Returns:
            Complete summary with metric data
        """
        summary = base_summary.copy()

        # Use provided mapping or assume direct mapping
        mapping = metric_mapping or {m: m for m in requested_metrics}

        for metric in requested_metrics:
            if metric in mapping and mapping[metric] in metrics_data:
                summary[mapping[metric]] = metrics_data[mapping[metric]]

        return summary


class DateTimeUtils:
    """Utilities for date and time operations"""

    @staticmethod
    def get_date_range(days: int) -> Tuple[datetime, datetime]:
        """
        Get date range for analysis.

        Args:
            days: Number of days to look back

        Returns:
            Tuple of (start_date, end_date)
        """
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        return start_date, end_date

    @staticmethod
    def calculate_intervals(
        timestamps: List[datetime],
        unit: str = 'hours'
    ) -> List[float]:
        """
        Calculate intervals between consecutive timestamps.

        Args:
            timestamps: List of datetime objects
            unit: Unit for intervals ('hours', 'minutes', 'seconds')

        Returns:
            List of intervals in specified unit
        """
        if len(timestamps) < 2:
            return []

        sorted_times = sorted(timestamps)
        intervals = []

        divisor = {
            'hours': 3600,
            'minutes': 60,
            'seconds': 1
        }.get(unit, 3600)

        for i in range(1, len(sorted_times)):
            interval = (sorted_times[i] - sorted_times[i-1]).total_seconds() / divisor
            intervals.append(interval)

        return intervals

    @staticmethod
    def get_time_period(hour: int) -> str:
        """
        Get time period name for given hour.

        Args:
            hour: Hour of day (0-23)

        Returns:
            Time period name (morning, afternoon, evening, night)
        """
        if 0 <= hour < 6:
            return 'night'
        elif 6 <= hour < 12:
            return 'morning'
        elif 12 <= hour < 18:
            return 'afternoon'
        else:
            return 'evening'

    @staticmethod
    def filter_by_time_period(
        items: List[Any],
        time_extractor,
        period: str,
        time_config: Optional[Dict[str, Dict[str, str]]] = None
    ) -> List[Any]:
        """
        Filter items by time period.

        Args:
            items: List of items to filter
            time_extractor: Function to extract datetime from item
            period: Time period to filter by
            time_config: Optional custom time period configuration

        Returns:
            Filtered list of items
        """
        if period == 'all':
            return items

        # Default time periods
        default_periods = {
            'morning': {'start': '06:00', 'end': '12:00'},
            'afternoon': {'start': '12:00', 'end': '18:00'},
            'evening': {'start': '18:00', 'end': '00:00'},
            'night': {'start': '00:00', 'end': '06:00'}
        }

        periods = time_config or default_periods

        if period not in periods:
            return items

        period_config = periods[period]
        start_hour = int(period_config['start'].split(':')[0])
        end_hour = int(period_config['end'].split(':')[0])

        filtered = []
        for item in items:
            hour = time_extractor(item).hour

            # Handle day boundary
            if start_hour <= end_hour:
                if start_hour <= hour < end_hour:
                    filtered.append(item)
            else:  # Crosses midnight
                if hour >= start_hour or hour < end_hour:
                    filtered.append(item)

        return filtered


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


class ValidationUtils:
    """Additional validation utilities"""

    @staticmethod
    def validate_enum_parameter(
            parameter_value: Any,
            enum_class: Any,
            default_value: Any
    ) -> Any:
        """
        Validate parameter against enum values.

        Args:
            parameter_value: Value to validate
            enum_class: Enum class to validate against
            default_value: Default enum value

        Returns:
            Valid enum value
        """
        try:
            return enum_class(parameter_value)
        except (ValueError, KeyError):
            return default_value

    @staticmethod
    def validate_numeric_parameter(
            value: Any,
            min_value: Optional[float] = None,
            max_value: Optional[float] = None,
            default: float = 0
    ) -> float:
        """
        Validate numeric parameter within bounds.

        Args:
            value: Value to validate
            min_value: Minimum allowed value
            max_value: Maximum allowed value
            default: Default value if validation fails

        Returns:
            Validated numeric value
        """
        try:
            num_value = float(value)
            if min_value is not None and num_value < min_value:
                return min_value
            if max_value is not None and num_value > max_value:
                return max_value
            return num_value
        except (TypeError, ValueError):
            return default

    @staticmethod
    def validate_list_parameter(
            parameter_value: Any,
            allowed_values: List[str],
            default_value: List[str]
    ) -> List[str]:
        """
        Validate a list parameter against allowed values.

        Args:
            parameter_value: Value to validate (can be list or single value)
            allowed_values: List of allowed values
            default_value: Default list if validation fails

        Returns:
            Validated list of values
        """
        if not isinstance(parameter_value, list):
            parameter_value = default_value

        # Filter valid values
        valid_set = set(allowed_values)
        validated = [v for v in parameter_value if v in valid_set]

        # Return default if no valid values
        return validated if validated else default_value


class ClusterDetector:
    """Utilities for detecting clusters in time-series data"""

    @staticmethod
    def detect_time_clusters(
            items: List[Any],
            time_extractor,
            window_minutes: int = 60,
            min_cluster_size: int = 2
    ) -> List[List[Any]]:
        """
        Detect clusters of items based on time proximity.

        Args:
            items: List of items to analyze
            time_extractor: Function to extract datetime from item
            window_minutes: Maximum minutes between items in a cluster
            min_cluster_size: Minimum items to consider a cluster

        Returns:
            List of clusters (each cluster is a list of items)
        """
        if len(items) < min_cluster_size:
            return []

        # Sort items by time
        sorted_items = sorted(items, key=time_extractor)
        clusters = []
        current_cluster = [sorted_items[0]]

        for i in range(1, len(sorted_items)):
            time_diff = (time_extractor(sorted_items[i]) -
                         time_extractor(current_cluster[-1])).total_seconds() / 60

            if time_diff <= window_minutes:
                current_cluster.append(sorted_items[i])
            else:
                if len(current_cluster) >= min_cluster_size:
                    clusters.append(current_cluster)
                current_cluster = [sorted_items[i]]

        # Don't forget the last cluster
        if len(current_cluster) >= min_cluster_size:
            clusters.append(current_cluster)

        return clusters


class EfficiencyCalculator:
    """Utilities for calculating efficiency metrics"""

    @staticmethod
    def calculate_rate(
            amount: Optional[float],
            duration: Optional[float],
            precision: int = 2
    ) -> Optional[float]:
        """
        Calculate rate (amount per time unit).

        Args:
            amount: Amount value
            duration: Duration value
            precision: Decimal places for rounding

        Returns:
            Rate value or None if calculation not possible
        """
        if amount is None or duration is None or duration <= 0:
            return None
        return round(amount / duration, precision)

    @staticmethod
    def interpret_efficiency_context(
            rate: float,
            context_thresholds: Dict[str, Tuple[float, float]],
            default_message: str = "Within normal range"
    ) -> str:
        """
        Provide context interpretation for efficiency values.

        Args:
            rate: The efficiency rate
            context_thresholds: Dict mapping context names to (min, max) tuples
            default_message: Default message if no threshold matches

        Returns:
            Context interpretation string
        """
        for context, (min_val, max_val) in context_thresholds.items():
            if min_val <= rate < max_val:
                return context
        return default_message