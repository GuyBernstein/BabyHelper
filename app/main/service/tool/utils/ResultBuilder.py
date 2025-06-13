from typing import Dict, Optional, List, Any


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
