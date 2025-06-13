from typing import Dict, Any, List

from app.main.service.tool.utils.ToolUtils import ToolUtils


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