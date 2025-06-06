"""Sleep Pattern Analyzer Tool Executor"""
from typing import Dict, Any, List, Optional

from app.main.model.tool import ToolType
from app.main.service.sleep_service import get_sleep_patterns
from app.main.service.tool.base.executor import ToolExecutor
from app.main.service.tool.base.registry import ToolRegistry


@ToolRegistry.register(ToolType.SLEEP_PATTERN_ANALYZER)
class SleepAnalyzer(ToolExecutor):
    """Analyzes sleep patterns for specified babies"""

    def validate_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Validate sleep analyzer parameters"""
        config = self.config.get('configuration', {})
        defaults = config.get('defaults', {})
        validation = config.get('validation', {})

        # Extract and process parameters
        timeframe = parameters.get('timeframe', defaults.get('timeframe', 7))
        timeframe_bounds = validation.get('timeframe_bounds', {})
        min_days = timeframe_bounds.get('min', 1)
        max_days = timeframe_bounds.get('max', 365)

        # Validate timeframe
        if isinstance(timeframe, int):
            days = max(min_days, min(timeframe, max_days))
        else:
            days = defaults.get('timeframe', 7)

        # Extract other parameters
        include_details = parameters.get('include_details', defaults.get('include_details', True))

        # Extract metrics parameter - default to all metrics if not specified
        default_metrics = defaults.get('metrics', ['total_sleep', 'night_sleep', 'naps', 'quality'])
        requested_metrics = parameters.get('metrics', default_metrics)
        if not isinstance(requested_metrics, list):
            requested_metrics = default_metrics

        # Validate metrics
        valid_metrics = set(validation.get('allowed_metrics', ['total_sleep', 'night_sleep', 'naps', 'quality']))
        requested_metrics = [m for m in requested_metrics if m in valid_metrics]

        # Extract and validate calculation_method
        calculation_method = parameters.get('calculation_method', None)

        # Define valid calculation methods
        valid_calculation_methods = set(validation.get('allowed_calculation_methods', ['PSQI', 'custom']))
        default_calc_method = defaults.get('calculation_method', 'custom')

        if calculation_method is not None:
            if calculation_method not in valid_calculation_methods:
                calculation_method = default_calc_method

            if 'quality' not in requested_metrics:
                calculation_method = None
        else:
            if 'quality' in requested_metrics:
                calculation_method = default_calc_method

        # If no valid metrics specified, default to all
        if not requested_metrics:
            requested_metrics = list(valid_metrics)
            calculation_method = defaults.get('calculation_method', 'custom')

        return {
            'days': days,
            'include_details': include_details,
            'requested_metrics': requested_metrics,
            'calculation_method': calculation_method
        }

    def execute(
            self,
            baby_ids: List[int],
            user_id: int,
            parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute sleep pattern analysis"""
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

        # If no successful data, return empty result
        if not successful_babies:
            return self._create_empty_result(
                params['days'],
                params['requested_metrics'],
                params['calculation_method']
            )

        # Aggregate only requested metrics
        aggregated_data = self._aggregate_metrics(
            all_patterns,
            successful_babies,
            params['requested_metrics']
        )

        # Build summary based on requested metrics
        summary = {
            "analysis_period_days": params['days'],
            "babies_analyzed": len(successful_babies),
            "metrics_analyzed": params['requested_metrics']
        }

        # Add calculation_method to summary if quality was analyzed
        if 'quality' in params['requested_metrics'] and params['calculation_method']:
            summary["calculation_method_used"] = params['calculation_method']

        # Add metric-specific results
        if 'total_sleep' in params['requested_metrics']:
            summary["avg_total_sleep_hours"] = aggregated_data['avg_total_sleep_hours']

        if 'night_sleep' in params['requested_metrics']:
            summary["avg_night_sleep_hours"] = aggregated_data['avg_night_sleep_hours']

        if 'naps' in params['requested_metrics']:
            summary["avg_naps_per_day"] = aggregated_data['avg_naps_per_day']

        if 'quality' in params['requested_metrics']:
            summary["sleep_quality_score"] = aggregated_data['sleep_quality_score']
            summary["sleep_quality_rating"] = aggregated_data['sleep_quality_rating']
            summary["sleep_quality_explanation"] = aggregated_data['sleep_quality_explanation']
            summary["calculation_method"] = aggregated_data['calculation_method']

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

    def _aggregate_metrics(
            self,
            all_patterns: Dict[int, Dict[str, Any]],
            successful_babies: List[int],
            requested_metrics: List[str]
    ) -> Dict[str, Any]:
        """Aggregate only the requested metrics across all babies"""
        # Get configuration values
        config = self.config.get('configuration', {})
        defaults = config.get('defaults', {})
        messages = config.get('messages', {
            'no_data_rating': 'No Data',
            'no_quality_data': 'No sleep quality data available',
            'calculation_method_na': 'N/A'
        })

        # Initialize aggregation variables only for requested metrics
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

        # Collect data for requested metrics only
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
                    if quality_score > 0:  # Valid score (not "No Data")
                        aggregated['total_quality_scores'] += float(quality_score)
                        aggregated['babies_with_valid_scores'] += 1

                        # Collect explanations, ratings, and methods for reference
                        if 'sleep_quality_explanation' in summary:
                            aggregated['quality_explanations'].append(summary['sleep_quality_explanation'])
                        if 'sleep_quality_rating' in summary:
                            aggregated['quality_ratings'].append(summary['sleep_quality_rating'])
                        if 'calculation_method' in summary:
                            aggregated['calculation_methods'].add(summary['calculation_method'])

        # Calculate averages with better precision handling
        result = {}

        # Get precision settings from config
        precision_settings = config.get('precision', {
            'small_value_threshold': 0.1,
            'small_value_decimals': 2,
            'normal_decimals': 1
        })

        if 'total_sleep' in requested_metrics:
            avg_sleep = aggregated['total_sleep_hours'] / baby_count
            # Use more precision for very small values, otherwise round to 1 decimal
            threshold = precision_settings['small_value_threshold']
            small_decimals = precision_settings['small_value_decimals']
            normal_decimals = precision_settings['normal_decimals']
            result['avg_total_sleep_hours'] = round(avg_sleep, small_decimals) if avg_sleep < threshold else round(
                avg_sleep, normal_decimals)

        if 'night_sleep' in requested_metrics:
            avg_night = aggregated['total_night_sleep_hours'] / baby_count
            threshold = precision_settings['small_value_threshold']
            small_decimals = precision_settings['small_value_decimals']
            normal_decimals = precision_settings['normal_decimals']
            result['avg_night_sleep_hours'] = round(avg_night, small_decimals) if avg_night < threshold else round(
                avg_night, normal_decimals)

        if 'naps' in requested_metrics:
            result['avg_naps_per_day'] = round(aggregated['total_naps'] / baby_count,
                                               precision_settings['normal_decimals'])

        if 'quality' in requested_metrics:
            if aggregated['babies_with_valid_scores'] > 0:
                avg_quality_score = aggregated['total_quality_scores'] / aggregated['babies_with_valid_scores']
                result['sleep_quality_score'] = round(avg_quality_score, precision_settings['normal_decimals'])

                # Handle rating based on number of babies
                if aggregated['babies_with_valid_scores'] == 1:
                    # For single baby, use the original rating
                    result['sleep_quality_rating'] = aggregated['quality_ratings'][0] if aggregated[
                        'quality_ratings'] else messages['no_data_rating']
                else:
                    # For multiple babies, aggregate the ratings
                    # Count occurrences of each rating
                    rating_counts = {}
                    for rating in aggregated['quality_ratings']:
                        rating_counts[rating] = rating_counts.get(rating, 0) + 1

                    # Use the most common rating, or if tied, use the one that corresponds to the average score
                    most_common_rating = max(rating_counts.items(), key=lambda x: x[1])[0]
                    result['sleep_quality_rating'] = most_common_rating

                # Handle explanation based on number of babies
                methods_used = list(aggregated['calculation_methods'])
                method_str = methods_used[0] if len(methods_used) == 1 else "Mixed"

                if aggregated['babies_with_valid_scores'] == 1:
                    # For single baby, use the original detailed explanation
                    result['sleep_quality_explanation'] = aggregated['quality_explanations'][0] if aggregated[
                        'quality_explanations'] else f"{method_str} Score: {result['sleep_quality_score']}/100"
                else:
                    # For multiple babies, create aggregated explanation
                    result[
                        'sleep_quality_explanation'] = f"Average {method_str} Score: {result['sleep_quality_score']}/100 across {aggregated['babies_with_valid_scores']} babies"

                result['calculation_method'] = method_str
            else:
                result['sleep_quality_score'] = 0
                result['sleep_quality_rating'] = messages['no_data_rating']
                result['sleep_quality_explanation'] = messages['no_quality_data']
                result['calculation_method'] = messages['calculation_method_na']

        return result

    def _filter_pattern_by_metrics(
            self,
            pattern: Dict[str, Any],
            requested_metrics: List[str]
    ) -> Dict[str, Any]:
        """Filter pattern data to include only requested metrics and avoid redundancy with summary"""
        filtered = {}

        if 'summary' in pattern:
            filtered_summary = {}
            summary = pattern['summary']

            # Always include these meta fields
            filtered_summary['total_days_analyzed'] = summary.get('total_days_analyzed')
            filtered_summary['days_with_sleep_data'] = summary.get('days_with_sleep_data')

            # For detailed patterns, include more granular data (minutes) but not the redundant hour calculations
            if 'total_sleep' in requested_metrics:
                filtered_summary['avg_total_sleep_minutes'] = summary.get('avg_total_sleep_minutes')

            if 'night_sleep' in requested_metrics:
                filtered_summary['avg_night_sleep_minutes'] = summary.get('avg_night_sleep_minutes')

            if 'naps' in requested_metrics:
                filtered_summary['avg_naps_per_day'] = summary.get('avg_naps_per_day')
                filtered_summary['avg_nap_duration_minutes'] = summary.get('avg_nap_duration_minutes')

            if 'quality' in requested_metrics:
                # Quality metrics are already in the summary level, no need to duplicate
                pass

            filtered['summary'] = filtered_summary

        # Include additional details based on metrics
        if (
                'total_sleep' in requested_metrics or 'night_sleep' in requested_metrics or 'naps' in requested_metrics) and 'daily_sleep' in pattern:
            filtered['daily_sleep'] = pattern['daily_sleep']

        if 'total_sleep' in requested_metrics and 'by_location' in pattern:
            filtered['by_location'] = pattern['by_location']

        return filtered

    def _create_empty_result(
            self,
            days: int,
            requested_metrics: List[str],
            calculation_method: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create an empty result with appropriate structure based on requested metrics"""
        # Get configuration values
        config = self.config.get('configuration', {})
        messages = config.get('messages', {
            'no_data_available': 'No sleep data available for the specified timeframe',
            'no_data_rating': 'No Data',
            'no_quality_data': 'No sleep quality data available',
            'calculation_method_na': 'N/A'
        })

        precision_settings = config.get('precision', {
            'normal_decimals': 1
        })

        summary = {
            "analysis_period_days": days,
            "babies_analyzed": 0,
            "metrics_analyzed": requested_metrics,
            "message": messages['no_data_available']
        }

        # Add zeros/defaults for requested metrics with consistent precision
        if 'total_sleep' in requested_metrics:
            summary["avg_total_sleep_hours"] = 0.0

        if 'night_sleep' in requested_metrics:
            summary["avg_night_sleep_hours"] = 0.0

        if 'naps' in requested_metrics:
            summary["avg_naps_per_day"] = 0.0

        if 'quality' in requested_metrics:
            summary["sleep_quality_score"] = 0
            summary["sleep_quality_rating"] = messages['no_data_rating']
            summary["sleep_quality_explanation"] = messages['no_quality_data']
            summary["calculation_method"] = calculation_method if calculation_method else messages[
                'calculation_method_na']
            if calculation_method:
                summary["calculation_method_used"] = calculation_method

        return {"summary": summary}