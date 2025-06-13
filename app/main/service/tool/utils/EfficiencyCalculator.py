from typing import Optional, Dict, Tuple


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