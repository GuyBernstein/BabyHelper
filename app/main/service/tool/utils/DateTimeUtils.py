from datetime import datetime, timedelta
from typing import List, Any, Optional, Dict, Tuple


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