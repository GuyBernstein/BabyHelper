from collections import defaultdict
from typing import Dict, Any, List, Optional

from app.main.model.tool import ToolType
from app.main.service.sleep_service import get_sleep_patterns
from app.main.service.tool.base.executor import ToolExecutor
from app.main.service.tool.base.registry import ToolRegistry
from app.main.service.tool.utils.ParameterValidator import ParameterValidator
from app.main.service.tool.utils.MetricAggregator import MetricAggregator
from app.main.service.tool.utils.ResultBuilder import ResultBuilder


@ToolRegistry.register(ToolType.SLEEP_PATTERN_ANALYZER)
class SleepAnalyzer(ToolExecutor):
    """Analyzes sleep patterns for specified babies using common utilities"""

    def validate_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate sleep analyzer parameters using common validator.

        Leverages ParameterValidator for standard parameter validation,
        then adds tool-specific validation for calculation_method.
        """
        config = self.config

        # Use common validator for base parameters
        base_params = ParameterValidator.validate_base_parameters(parameters, config)

        # validation for calculation_method
        calculation_method = self._validate_calculation_method(
            parameters.get('calculation_method'),
            base_params['requested_metrics'],
            config
        )

        # Merge base and specific parameters
        return {
            **base_params,
            'calculation_method': calculation_method
        }

    def _validate_calculation_method(
        self,
        calculation_method: Optional[str],
        requested_metrics: List[str],
        config: Dict[str, Any]
    ) -> Optional[str]:
        """
        Validate calculation method parameter specific to sleep analysis.

        Args:
            calculation_method: Method requested by user
            requested_metrics: List of requested metrics
            config: Tool configuration

        Returns:
            Validated calculation method or None
        """
        validation = config.get('validation', {})
        defaults = config.get('defaults', {})

        # Get allowed methods from config
        allowed_methods = validation.get('allowed_calculation_methods', ['PSQI', 'custom'])
        default_method = defaults.get('calculation_method', 'custom')

        # Only validate if quality metric is requested
        if 'quality' not in requested_metrics:
            return None

        # Validate the method using common validator
        if calculation_method is not None:
            return ParameterValidator.validate_filter_parameter(
                'calculation_method',
                calculation_method,
                allowed_methods,
                default_method
            )
        else:
            return default_method

    def execute(
            self,
            baby_ids: List[int],
            user_id: int,
            parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute sleep pattern analysis using common data processing utilities"""
        # Validate parameters
        params = self.validate_parameters(parameters)

        # Collect data from all babies
        all_patterns: Dict[int, Dict[str, Any]] = {}
        successful_babies: List[int] = []

        for baby_id in baby_ids:
            result = get_sleep_patterns(
                self.db,
                baby_id,
                user_id,
                params['days'],
                params['calculation_method']
            )
            if isinstance(result, dict) and result.get('status') == 'success':
                all_patterns[baby_id] = result['patterns']
                successful_babies.append(baby_id)

        # If no successful data, use common result builder
        if not successful_babies:
            return self._create_empty_result_using_common(
                params['days'],
                params['requested_metrics'],
                params['calculation_method']
            )

        # Aggregate only requested metrics
        aggregated_data = self._aggregate_metrics_using_common(
            all_patterns,
            successful_babies,
            params['requested_metrics']
        )

        # Build summary using common builder
        base_summary = {
            "analysis_period_days": params['days'],
            "babies_analyzed": len(successful_babies),
            "metrics_analyzed": params['requested_metrics']
        }

        # Add calculation method if quality was analyzed
        if 'quality' in params['requested_metrics'] and params['calculation_method']:
            base_summary["calculation_method_used"] = params['calculation_method']

        # Define metric mapping for summary builder
        metric_mapping = {
            'total_sleep': 'avg_total_sleep_hours',
            'night_sleep': 'avg_night_sleep_hours',
            'naps': 'avg_naps_per_day',
            'quality': None  # Special handling below
        }

        # Build summary with standard metrics
        summary = ResultBuilder.build_summary_with_metrics(
            base_summary,
            aggregated_data,
            params['requested_metrics'],
            metric_mapping
        )

        # Handle quality metrics separately due to multiple fields
        if 'quality' in params['requested_metrics']:
            for quality_field in ['sleep_quality_score', 'sleep_quality_rating',
                                'sleep_quality_explanation', 'calculation_method']:
                if quality_field in aggregated_data:
                    summary[quality_field] = aggregated_data[quality_field]

        result = {"summary": summary}

        # Add detailed patterns if requested
        if params['include_details']:
            detailed_patterns: Dict[int, Dict[str, Any]] = {}

            for baby_id in successful_babies:
                if baby_id in all_patterns:
                    # Filter patterns based on requested metrics
                    filtered_pattern = self._filter_pattern_by_metrics(
                        all_patterns[baby_id],
                        params['requested_metrics']
                    )
                    detailed_patterns[baby_id] = filtered_pattern

            result["detailed_patterns"] = detailed_patterns

        return result

    def _aggregate_metrics_using_common(
            self,
            all_patterns: Dict[int, Dict[str, Any]],
            successful_babies: List[int],
            requested_metrics: List[str]
    ) -> Dict[str, Any]:
        """
        Aggregate metrics using common aggregation utilities.

        This method demonstrates how to use MetricAggregator for calculations
        while maintaining tool-specific logic for quality score aggregation.
        """
        # FIX: self.config IS the configuration
        config = self.config
        messages = config.get('messages', {})
        precision_config = config.get('precision', {})

        # Initialize aggregation containers for requested metrics only
        aggregated = {}
        baby_count = len(successful_babies)

        if 'total_sleep' in requested_metrics:
            aggregated['total_sleep_hours'] = 0.0

        if 'night_sleep' in requested_metrics:
            aggregated['total_night_sleep_hours'] = 0.0

        if 'naps' in requested_metrics:
            aggregated['total_naps'] = 0.0

        if 'quality' in requested_metrics:
            aggregated['total_quality_scores'] = 0.0
            aggregated['babies_with_valid_scores'] = 0
            aggregated['quality_explanations'] = []
            aggregated['quality_ratings'] = []
            aggregated['calculation_methods'] = set()

        # Collect data for requested metrics
        for baby_id in successful_babies:
            patterns = all_patterns.get(baby_id, {})
            if patterns and 'summary' in patterns:
                summary = patterns['summary']

                if 'total_sleep' in requested_metrics:
                    aggregated['total_sleep_hours'] += float(summary.get('avg_total_sleep_hours', 0))

                if 'night_sleep' in requested_metrics:
                    aggregated['total_night_sleep_hours'] += float(summary.get('avg_night_sleep_hours', 0))

                if 'naps' in requested_metrics:
                    aggregated['total_naps'] += float(summary.get('avg_naps_per_day', 0))

                if 'quality' in requested_metrics:
                    quality_score = summary.get('sleep_quality_score', 0)
                    if quality_score > 0:
                        aggregated['total_quality_scores'] += float(quality_score)
                        aggregated['babies_with_valid_scores'] += 1

                        # Collect additional quality data
                        if 'sleep_quality_explanation' in summary:
                            aggregated['quality_explanations'].append(summary['sleep_quality_explanation'])
                        if 'sleep_quality_rating' in summary:
                            aggregated['quality_ratings'].append(summary['sleep_quality_rating'])
                        if 'calculation_method' in summary:
                            aggregated['calculation_methods'].add(summary['calculation_method'])

        # Calculate averages using common aggregator
        result = {}

        if 'total_sleep' in requested_metrics:
            result['avg_total_sleep_hours'] = MetricAggregator.calculate_average_with_precision(
                aggregated['total_sleep_hours'],
                baby_count,
                precision_config,
                'sleep'
            )

        if 'night_sleep' in requested_metrics:
            result['avg_night_sleep_hours'] = MetricAggregator.calculate_average_with_precision(
                aggregated['total_night_sleep_hours'],
                baby_count,
                precision_config,
                'sleep'
            )

        if 'naps' in requested_metrics:
            result['avg_naps_per_day'] = MetricAggregator.calculate_average_with_precision(
                aggregated['total_naps'],
                baby_count,
                precision_config,
                'normal'
            )

        if 'quality' in requested_metrics:
            result.update(self._aggregate_quality_metrics(
                aggregated,
                precision_config,
                messages
            ))

        return result

    def _aggregate_quality_metrics(
            self,
            aggregated: Dict[str, Any],
            precision_config: Dict[str, Any],
            messages: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Aggregate quality metrics with special handling for ratings and explanations.

        This method demonstrates tool-specific aggregation logic that works
        alongside common utilities.
        """
        result = {}

        if aggregated['babies_with_valid_scores'] > 0:
            # Calculate average quality score
            avg_quality_score = (aggregated['total_quality_scores'] /
                               aggregated['babies_with_valid_scores'])
            result['sleep_quality_score'] = round(
                avg_quality_score,
                precision_config.get('normal_decimals', 1)
            )

            # Handle rating aggregation
            if aggregated['babies_with_valid_scores'] == 1:
                # Single baby - use original rating
                result['sleep_quality_rating'] = (
                    aggregated['quality_ratings'][0]
                    if aggregated['quality_ratings']
                    else messages.get('no_data_rating', 'No Data')
                )
            else:
                # Multiple babies - use most common rating
                rating_counts = defaultdict(int)
                for rating in aggregated['quality_ratings']:
                    rating_counts[rating] += 1

                most_common_rating = max(rating_counts.items(), key=lambda x: x[1])[0]
                result['sleep_quality_rating'] = most_common_rating

            # Handle explanation aggregation
            methods_used = list(aggregated['calculation_methods'])
            method_str = methods_used[0] if len(methods_used) == 1 else "Mixed"

            if aggregated['babies_with_valid_scores'] == 1:
                # Single baby - use original explanation
                result['sleep_quality_explanation'] = (
                    aggregated['quality_explanations'][0]
                    if aggregated['quality_explanations']
                    else f"{method_str} Score: {result['sleep_quality_score']}/100"
                )
            else:
                # Multiple babies - create summary explanation
                result['sleep_quality_explanation'] = (
                    f"Average {method_str} Score: {result['sleep_quality_score']}/100 "
                    f"across {aggregated['babies_with_valid_scores']} babies"
                )

            result['calculation_method'] = method_str
        else:
            # No valid scores - use default messages
            result['sleep_quality_score'] = 0
            result['sleep_quality_rating'] = messages.get('no_data_rating', 'No Data')
            result['sleep_quality_explanation'] = messages.get('no_quality_data',
                                                             'No sleep quality data available')
            result['calculation_method'] = messages.get('calculation_method_na', 'N/A')

        return result

    def _filter_pattern_by_metrics(
            self,
            pattern: Dict[str, Any],
            requested_metrics: List[str]
    ) -> Dict[str, Any]:
        """
        Filter pattern data to include only requested metrics.

        This method shows how tool-specific filtering logic can work alongside
        common utilities for more complex filtering scenarios.
        """
        filtered = {}

        if 'summary' in pattern:
            filtered_summary = {}
            summary = pattern['summary']

            # Always include meta fields
            filtered_summary['total_days_analyzed'] = summary.get('total_days_analyzed')
            filtered_summary['days_with_sleep_data'] = summary.get('days_with_sleep_data')

            # Include metric-specific fields (granular data for details)
            if 'total_sleep' in requested_metrics:
                filtered_summary['avg_total_sleep_minutes'] = summary.get('avg_total_sleep_minutes')

            if 'night_sleep' in requested_metrics:
                filtered_summary['avg_night_sleep_minutes'] = summary.get('avg_night_sleep_minutes')

            if 'naps' in requested_metrics:
                filtered_summary['avg_naps_per_day'] = summary.get('avg_naps_per_day')
                filtered_summary['avg_nap_duration_minutes'] = summary.get('avg_nap_duration_minutes')

            filtered['summary'] = filtered_summary

        # Include additional detail sections based on metrics
        detail_mapping = {
            'total_sleep': ['daily_sleep', 'by_location'],
            'night_sleep': ['daily_sleep'],
            'naps': ['daily_sleep']
        }

        for metric in requested_metrics:
            if metric in detail_mapping:
                for detail_section in detail_mapping[metric]:
                    if detail_section in pattern and detail_section not in filtered:
                        filtered[detail_section] = pattern[detail_section]

        return filtered

    def _create_empty_result_using_common(
            self,
            days: int,
            requested_metrics: List[str],
            calculation_method: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create empty result using common ResultBuilder.

        This method demonstrates how to use the common empty result builder
        with tool-specific metric defaults.
        """
        # FIX: self.config IS the configuration
        config = self.config
        messages = config.get('messages', {})

        # Define metric-specific default values
        metric_defaults = {}

        if 'total_sleep' in requested_metrics:
            metric_defaults['avg_total_sleep_hours'] = 0.0

        if 'night_sleep' in requested_metrics:
            metric_defaults['avg_night_sleep_hours'] = 0.0

        if 'naps' in requested_metrics:
            metric_defaults['avg_naps_per_day'] = 0.0

        if 'quality' in requested_metrics:
            metric_defaults['sleep_quality_score'] = 0
            metric_defaults['sleep_quality_rating'] = messages.get('no_data_rating', 'No Data')
            metric_defaults['sleep_quality_explanation'] = messages.get('no_quality_data',
                                                                      'No sleep quality data available')
            metric_defaults['calculation_method'] = (
                calculation_method if calculation_method
                else messages.get('calculation_method_na', 'N/A')
            )
            if calculation_method:
                metric_defaults['calculation_method_used'] = calculation_method

        # Use common result builder
        return ResultBuilder.create_empty_analysis_result(
            days=days,
            requested_metrics=requested_metrics,
            config=config,
            metric_defaults=metric_defaults
        )