"""Feeding Tracker Tool Executor"""
from collections import defaultdict
from datetime import datetime
from statistics import mean, stdev
from typing import Dict, Any, List

from app.main.model.feeding import FeedingType
from app.main.model.tool import ToolType
from app.main.service.feeding_service import get_feedings_for_baby
from app.main.service.tool.base.executor import ToolExecutor
from app.main.service.tool.base.registry import ToolRegistry
from app.main.service.tool.utils.EfficiencyCalculator import EfficiencyCalculator
from app.main.service.tool.utils.ParameterValidator import ParameterValidator
from app.main.service.tool.utils.DateTimeUtils import DateTimeUtils
from app.main.service.tool.utils.DataProcessor import DataProcessor
from app.main.service.tool.utils.ResultBuilder import ResultBuilder
from app.main.service.tool.utils.MetricAggregator import MetricAggregator
from app.main.service.tool.utils.ClusterDetector import ClusterDetector


@ToolRegistry.register(ToolType.FEEDING_TRACKER)
class FeedingTracker(ToolExecutor):
    """Enhanced feeding analyzer with nutrition, cluster detection, and efficiency tracking"""

    # Nutrition constants (calories per ml)
    NUTRITION_CONSTANTS = {
        'breast_milk': 0.67,  # ~20 cal/oz
        'formula': 0.67,      # ~20 cal/oz
        'mixed': 0.67,        # Average of breast milk and formula
        'solids': {           # Approximate calories per gram for common baby foods
            'cereals': 3.5,
            'fruits': 0.6,
            'vegetables': 0.4,
            'proteins': 1.5,
            'default': 1.0    # Default for unspecified solids
        }
    }

    # Efficiency context thresholds
    EFFICIENCY_THRESHOLDS = {
        "Below typical range - may indicate slow feeding or latching difficulties": (0, 1.0),
        "Typical for newborns (0-3 months)": (1.0, 2.0),
        "Typical for infants (3-6 months)": (2.0, 4.0),
        "Typical for older infants (6+ months)": (4.0, 6.0),
        "Above typical range - very efficient feeding": (6.0, float('inf'))
    }

    def validate_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Validate feeding tracker parameters using common validators"""
        config = self.config

        # Use common parameter validator for base parameters
        base_params = ParameterValidator.validate_base_parameters(parameters, config)

        # Validate feeding-specific parameters
        defaults = config.get('defaults', {})
        validation = config.get('validation', {})

        # Validate feeding types filter
        feeding_types_filter = ParameterValidator.validate_filter_parameter(
            'feeding_types_filter',
            parameters.get('feeding_types_filter', defaults.get('feeding_types_filter', 'all')),
            validation.get('allowed_feeding_types', ['all']),
            'all'
        )

        # Validate time of day filter
        time_of_day_filter = ParameterValidator.validate_filter_parameter(
            'time_of_day_filter',
            parameters.get('time_of_day_filter', defaults.get('time_of_day_filter', 'all')),
            ['morning', 'afternoon', 'evening', 'night', 'all'],
            'all'
        )

        # Additional parameters
        include_trends = parameters.get('include_trends', True)
        nutrition_detail_level = parameters.get('nutrition_detail_level', 'summary')

        return {
            **base_params,
            'feeding_types_filter': feeding_types_filter,
            'time_of_day_filter': time_of_day_filter,
            'include_trends': include_trends,
            'nutrition_detail_level': nutrition_detail_level
        }

    def execute(
            self,
            baby_ids: List[int],
            user_id: int,
            parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute enhanced feeding pattern analysis"""
        # Validate parameters
        params = self.validate_parameters(parameters)

        # Use common date range utility
        start_date, end_date = DateTimeUtils.get_date_range(params['days'])

        # Collect feeding data from all babies
        all_feedings: Dict[int, List[Any]] = {}
        successful_babies: List[int] = []

        for baby_id in baby_ids:
            feedings = get_feedings_for_baby(
                self.db,
                baby_id,
                user_id,
                skip=0,
                limit=None,
                start_date=start_date,
                end_date=end_date
            )

            # Check if we got valid data
            if isinstance(feedings, list) and len(feedings) > 0:
                # Apply filters
                filtered_feedings = self._apply_filters(
                    feedings,
                    params['feeding_types_filter'],
                    params['time_of_day_filter']
                )

                if filtered_feedings:
                    all_feedings[baby_id] = filtered_feedings
                    successful_babies.append(baby_id)

        # If no successful data, return empty result
        if not successful_babies:
            return self._create_empty_result(params)

        # Process feeding data for requested metrics
        processed_data = self._process_feeding_data(
            all_feedings,
            successful_babies,
            params['requested_metrics'],
            params['days']
        )

        # Build summary using common result builder
        summary = {
            "analysis_period_days": params['days'],
            "babies_analyzed": len(successful_babies),
            "metrics_analyzed": params['requested_metrics'],
            "filters_applied": {
                "feeding_types": params['feeding_types_filter'],
                "time_of_day": params['time_of_day_filter']
            }
        }

        # Add metric-specific results to summary
        summary.update(processed_data['summary'])

        result = {"summary": summary}

        # Add detailed patterns if requested
        if params['include_details']:
            detailed_patterns = {}

            for baby_id in successful_babies:
                if baby_id in all_feedings:
                    baby_patterns = self._analyze_baby_patterns(
                        all_feedings[baby_id],
                        params['requested_metrics'],
                        params['days']
                    )
                    detailed_patterns[baby_id] = baby_patterns

            result["detailed_patterns"] = detailed_patterns

        # Add trends if requested
        if params['include_trends'] and len(successful_babies) > 0:
            trends = self._analyze_trends(
                all_feedings,
                params['requested_metrics'],
                params['days']
            )
            result["trends"] = trends

        return result

    def _calculate_calories(self, feeding: Any) -> float:
        """Calculate calories for a feeding based on type and volume"""
        calories = 0.0

        if feeding.feeding_type in [FeedingType.BREAST_LEFT, FeedingType.BREAST_RIGHT,
                                   FeedingType.BREAST_BOTH]:
            # Breast feeding calories
            if feeding.amount:
                calories = feeding.amount * self.NUTRITION_CONSTANTS['breast_milk']

        elif feeding.feeding_type == FeedingType.BOTTLE:
            # Bottle feeding calories based on content type
            if feeding.amount and feeding.bottle_content_type:
                cal_per_ml = self.NUTRITION_CONSTANTS.get(
                    feeding.bottle_content_type,
                    self.NUTRITION_CONSTANTS['mixed']
                )
                calories = feeding.amount * cal_per_ml

        elif feeding.feeding_type == FeedingType.FORMULA:
            # Formula feeding calories
            if feeding.amount:
                calories = feeding.amount * self.NUTRITION_CONSTANTS['formula']

        elif feeding.feeding_type == FeedingType.SOLIDS:
            # Solids calories (simplified - could be enhanced with food type tracking)
            if feeding.amount:
                # Assume amount is in grams for solids
                calories = feeding.amount * self.NUTRITION_CONSTANTS['solids']['default']

        return round(calories, 1)

    def _apply_filters(
            self,
            feedings: List[Any],
            feeding_types_filter: str,
            time_of_day_filter: str
    ) -> List[Any]:
        """Apply feeding type and time of day filters using common utilities"""
        filtered = feedings

        # Apply feeding type filter
        if feeding_types_filter != 'all':
            filtered = [f for f in filtered if f.feeding_type == feeding_types_filter]

        # Apply time of day filter using common utility
        if time_of_day_filter != 'all':
            time_config = self.config.get('configuration', {}).get('validation', {}).get('time_periods')
            filtered = DateTimeUtils.filter_by_time_period(
                filtered,
                lambda f: f.start_time,
                time_of_day_filter,
                time_config
            )

        return filtered

    def _process_feeding_data(
            self,
            all_feedings: Dict[int, List[Any]],
            successful_babies: List[int],
            requested_metrics: List[str],
            days: int
    ) -> Dict[str, Any]:
        """Process feeding data for requested metrics including enhanced features"""
        config = self.config.get('configuration', {})
        precision = config.get('precision', {})
        thresholds = config.get('thresholds', {})

        # Initialize aggregation containers
        aggregated = {
            'summary': {},
            'total_feedings': 0,
            'total_volume': 0.0,
            'total_duration': 0.0,
            'total_calories': 0.0,
            'feeding_types': defaultdict(int),
            'bottle_contents': defaultdict(int),
            'pumping_volume': 0.0,
            'pumping_sessions': 0,
            'feeding_times': [],
            'babies_with_volume': 0,
            'babies_with_duration': 0,
            'all_clusters': [],
            'efficiency_data': [],
            'nutrition_by_type': defaultdict(float),
            'feedings_by_date': defaultdict(list),
            'feedings_with_efficiency': 0,
            'feedings_by_date_with_efficiency': defaultdict(int)
        }

        # Process each baby's data
        for baby_id in successful_babies:
            feedings = all_feedings.get(baby_id, [])
            baby_has_volume = False
            baby_has_duration = False

            # Use common cluster detector
            if 'clusters' in requested_metrics:
                cluster_window = thresholds.get('cluster_feeding_window_minutes', 60)
                baby_clusters = ClusterDetector.detect_time_clusters(
                    feedings,
                    lambda f: f.start_time,
                    cluster_window
                )
                aggregated['all_clusters'].extend(baby_clusters)

            for feeding in feedings:
                aggregated['total_feedings'] += 1
                aggregated['feeding_types'][feeding.feeding_type] += 1

                # Organize by date for trend analysis
                date_key = feeding.start_time.date()
                aggregated['feedings_by_date'][date_key].append(feeding)

                # Collect feeding times for schedule analysis
                aggregated['feeding_times'].append(feeding.start_time)

                # Calculate nutrition
                if 'nutrition' in requested_metrics:
                    calories = self._calculate_calories(feeding)
                    aggregated['total_calories'] += calories
                    aggregated['nutrition_by_type'][feeding.feeding_type] += calories

                # Use common efficiency calculator
                if 'efficiency' in requested_metrics:
                    efficiency = EfficiencyCalculator.calculate_rate(
                        feeding.amount,
                        feeding.duration
                    )
                    if efficiency is not None:
                        aggregated['feedings_with_efficiency'] += 1
                        aggregated['feedings_by_date_with_efficiency'][date_key] += 1
                        aggregated['efficiency_data'].append({
                            'efficiency': efficiency,
                            'type': feeding.feeding_type,
                            'timestamp': feeding.start_time,
                            'volume': feeding.amount,
                            'duration': feeding.duration
                        })

                # Volume metrics
                if feeding.amount is not None and feeding.amount > 0:
                    aggregated['total_volume'] += feeding.amount
                    baby_has_volume = True

                    # Track bottle content types
                    if feeding.feeding_type == FeedingType.BOTTLE and feeding.bottle_content_type:
                        aggregated['bottle_contents'][feeding.bottle_content_type] += 1

                # Duration metrics
                if feeding.duration is not None and feeding.duration > 0:
                    aggregated['total_duration'] += feeding.duration
                    baby_has_duration = True

                # Pumping metrics
                if feeding.feeding_type == FeedingType.PUMPING:
                    aggregated['pumping_sessions'] += 1
                    if feeding.pumped_volume_left:
                        aggregated['pumping_volume'] += feeding.pumped_volume_left
                    if feeding.pumped_volume_right:
                        aggregated['pumping_volume'] += feeding.pumped_volume_right

            if baby_has_volume:
                aggregated['babies_with_volume'] += 1
            if baby_has_duration:
                aggregated['babies_with_duration'] += 1

        # Calculate summary metrics
        summary = self._calculate_summary_metrics(
            aggregated, requested_metrics, successful_babies, days, precision, thresholds
        )

        return {'summary': summary}

    def _calculate_summary_metrics(
            self,
            aggregated: Dict[str, Any],
            requested_metrics: List[str],
            successful_babies: List[int],
            days: int,
            precision: Dict[str, Any],
            thresholds: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate all summary metrics including enhanced features"""
        summary = {}
        config = self.config.get('configuration', {})

        if 'frequency' in requested_metrics:
            total_feedings = aggregated['total_feedings']
            avg_daily_feedings = total_feedings / days / len(successful_babies)
            summary['avg_daily_feedings'] = round(avg_daily_feedings, precision.get('frequency_decimals', 2))
            summary['total_feedings_analyzed'] = total_feedings

            # Use common interval calculator
            if len(aggregated['feeding_times']) >= thresholds.get('min_feedings_for_pattern', 3):
                intervals = DateTimeUtils.calculate_intervals(aggregated['feeding_times'], 'hours')
                if intervals:
                    avg_interval = sum(intervals) / len(intervals)
                    summary['avg_hours_between_feedings'] = round(avg_interval, precision.get('duration_decimals', 1))

        if 'volume' in requested_metrics:
            if aggregated['babies_with_volume'] > 0:
                avg_volume_per_feeding = aggregated['total_volume'] / aggregated['total_feedings']
                total_daily_volume = aggregated['total_volume'] / days
                summary['avg_volume_per_feeding_ml'] = round(avg_volume_per_feeding, precision.get('volume_decimals', 1))
                summary['avg_daily_volume_ml'] = round(total_daily_volume, precision.get('volume_decimals', 1))
            else:
                summary['volume_data'] = config.get('messages', {}).get('no_volume_data', 'Volume data not available')

        if 'duration' in requested_metrics:
            if aggregated['babies_with_duration'] > 0:
                # Use common average calculator with precision
                avg_duration = MetricAggregator.calculate_average_with_precision(
                    aggregated['total_duration'],
                    aggregated['total_feedings'],
                    precision,
                    'duration'
                )
                summary['avg_feeding_duration_minutes'] = avg_duration
            else:
                summary['duration_data'] = config.get('messages', {}).get('no_duration_data', 'Duration data not available')

        if 'types' in requested_metrics:
            # Use common distribution calculator
            type_distribution = DataProcessor.calculate_distribution(
                [{'type': t} for t, count in aggregated['feeding_types'].items() for _ in range(count)],
                lambda x: x['type'],
                aggregated['total_feedings']
            )
            summary['feeding_type_distribution'] = type_distribution

            # Add bottle content distribution if applicable
            if aggregated['bottle_contents']:
                bottle_distribution = DataProcessor.calculate_distribution(
                    [{'content': c} for c, count in aggregated['bottle_contents'].items() for _ in range(count)],
                    lambda x: x['content'],
                    sum(aggregated['bottle_contents'].values())
                )
                summary['bottle_content_distribution'] = bottle_distribution

        if 'nutrition' in requested_metrics:
            total_calories = aggregated['total_calories']
            if total_calories > 0:
                avg_daily_calories = total_calories / days / len(successful_babies)
                summary['nutrition_metrics'] = {
                    'total_calories': round(total_calories, 1),
                    'avg_daily_calories': round(avg_daily_calories, 1),
                    'avg_calories_per_feeding': round(total_calories / aggregated['total_feedings'], 1)
                }

                # Nutrition breakdown by type
                nutrition_breakdown = {}
                for feeding_type, calories in aggregated['nutrition_by_type'].items():
                    percentage = MetricAggregator.calculate_percentage(
                        calories,
                        total_calories,
                        1
                    )
                    nutrition_breakdown[feeding_type] = {
                        'calories': round(calories, 1),
                        'percentage': percentage
                    }
                summary['nutrition_metrics']['breakdown_by_type'] = nutrition_breakdown

        if 'pumping' in requested_metrics:
            if aggregated['pumping_sessions'] > 0:
                avg_pumping_volume = aggregated['pumping_volume'] / aggregated['pumping_sessions']
                summary['pumping_sessions'] = aggregated['pumping_sessions']
                summary['avg_pumping_volume_ml'] = round(avg_pumping_volume, precision.get('volume_decimals', 1))
                summary['total_pumped_ml'] = round(aggregated['pumping_volume'], precision.get('volume_decimals', 1))

        if 'schedule' in requested_metrics:
            if len(aggregated['feeding_times']) >= thresholds.get('min_feedings_for_pattern', 3):
                schedule_analysis = self._analyze_schedule_patterns(aggregated['feeding_times'])
                summary['schedule_analysis'] = schedule_analysis

        if 'clusters' in requested_metrics:
            cluster_count = len(aggregated['all_clusters'])
            if cluster_count > 0:
                avg_cluster_size = sum(len(c) for c in aggregated['all_clusters']) / cluster_count
                summary['cluster_feeding_analysis'] = {
                    'total_clusters_detected': cluster_count,
                    'avg_feedings_per_cluster': round(avg_cluster_size, 1),
                    'cluster_frequency': round(cluster_count / days, 1),
                    'message': f"Detected {cluster_count} cluster feeding episodes"
                }
            else:
                summary['cluster_feeding_analysis'] = {
                    'total_clusters_detected': 0,
                    'message': "No cluster feeding patterns detected"
                }

        if 'efficiency' in requested_metrics and aggregated['efficiency_data']:
            efficiencies = [d['efficiency'] for d in aggregated['efficiency_data']]
            avg_efficiency = mean(efficiencies)

            # Use common efficiency context interpreter
            efficiency_context = EfficiencyCalculator.interpret_efficiency_context(
                avg_efficiency,
                self.EFFICIENCY_THRESHOLDS
            )

            efficiency_metrics = {
                'avg_feeding_rate_ml_per_min': round(avg_efficiency, 2),
                'efficiency_interpretation': efficiency_context,
                'min_rate_ml_per_min': round(min(efficiencies), 2),
                'max_rate_ml_per_min': round(max(efficiencies), 2),
                'feedings_with_valid_data': aggregated['feedings_with_efficiency'],
                'total_feedings': aggregated['total_feedings'],
                'data_coverage_percentage': MetricAggregator.calculate_percentage(
                    aggregated['feedings_with_efficiency'],
                    aggregated['total_feedings']
                )
            }

            # Calculate standard deviation if enough data
            if len(efficiencies) > 1:
                efficiency_metrics['rate_variability_std_dev'] = round(stdev(efficiencies), 2)

            # Efficiency by feeding type
            efficiency_by_type = defaultdict(list)
            for data in aggregated['efficiency_data']:
                efficiency_by_type[data['type']].append(data['efficiency'])

            type_efficiency = {}
            for ftype, values in efficiency_by_type.items():
                if values:
                    type_efficiency[ftype] = {
                        'avg_rate_ml_per_min': round(mean(values), 2),
                        'sample_count': len(values)
                    }

            efficiency_metrics['rate_by_feeding_type'] = type_efficiency

            # Add helpful explanation
            efficiency_metrics['explanation'] = (
                "Feeding rate (efficiency) measures how quickly baby consumes milk/formula in ml per minute. "
                "Higher rates indicate faster feeding. Rates typically increase as babies grow and become more efficient feeders."
            )

            summary['feeding_efficiency'] = efficiency_metrics
        elif 'efficiency' in requested_metrics:
            summary['feeding_efficiency'] = {
                'message': "No efficiency data available - requires both volume and duration data for calculation",
                'explanation': "Feeding efficiency measures ml consumed per minute during feeding sessions"
            }

        return summary

    def _analyze_trends(
            self,
            all_feedings: Dict[int, List[Any]],
            requested_metrics: List[str],
            days: int
    ) -> Dict[str, Any]:
        """Analyze trends over time for various metrics"""
        trends = {}

        # Use common aggregation utility
        feedings_by_date = defaultdict(list)
        for baby_id, feedings in all_feedings.items():
            for feeding in feedings:
                date_key = feeding.start_time.date()
                feedings_by_date[date_key].append(feeding)

        # Sort dates
        sorted_dates = sorted(feedings_by_date.keys())

        if 'volume' in requested_metrics:
            volume_trend = []
            for date in sorted_dates:
                daily_feedings = feedings_by_date[date]
                daily_volume = sum(f.amount for f in daily_feedings if f.amount)
                volume_trend.append({
                    'date': date.isoformat(),
                    'total_volume_ml': round(daily_volume, 1),
                    'feeding_count': len(daily_feedings)
                })
            trends['volume_trend'] = volume_trend

        if 'efficiency' in requested_metrics:
            efficiency_trend = []
            for date in sorted_dates:
                daily_feedings = feedings_by_date[date]
                daily_efficiencies = []

                total_daily_feedings = len(daily_feedings)

                for f in daily_feedings:
                    eff = EfficiencyCalculator.calculate_rate(f.amount, f.duration)
                    if eff is not None:
                        daily_efficiencies.append(eff)

                if daily_efficiencies:
                    efficiency_trend.append({
                        'date': date.isoformat(),
                        'avg_feeding_rate_ml_per_min': round(mean(daily_efficiencies), 2),
                        'min_rate': round(min(daily_efficiencies), 2),
                        'max_rate': round(max(daily_efficiencies), 2),
                        'feedings_with_efficiency_data': len(daily_efficiencies),
                        'total_feedings': total_daily_feedings,
                        'data_coverage_percentage': MetricAggregator.calculate_percentage(
                            len(daily_efficiencies),
                            total_daily_feedings
                        )
                    })

            if efficiency_trend:
                trends['efficiency_trend'] = {
                    'daily_data': efficiency_trend,
                    'explanation': "Shows daily average feeding rates (ml/min) with data coverage information"
                }

        if 'nutrition' in requested_metrics:
            nutrition_trend = []
            for date in sorted_dates:
                daily_feedings = feedings_by_date[date]
                daily_calories = sum(self._calculate_calories(f) for f in daily_feedings)
                nutrition_trend.append({
                    'date': date.isoformat(),
                    'total_calories': round(daily_calories, 1),
                    'feeding_count': len(daily_feedings)
                })
            trends['nutrition_trend'] = nutrition_trend

        return trends

    def _analyze_schedule_patterns(self, feeding_times: List[datetime]) -> Dict[str, Any]:
        """Analyze feeding schedule patterns using common utilities"""
        precision = self.config.get('configuration', {}).get('precision', {})

        # Count feedings by time period
        period_counts = {
            'morning': 0,
            'afternoon': 0,
            'evening': 0,
            'night': 0
        }

        for feeding_time in feeding_times:
            period = DateTimeUtils.get_time_period(feeding_time.hour)
            period_counts[period] += 1

        # Use common distribution calculator
        schedule_distribution = DataProcessor.calculate_distribution(
            [{'period': p} for p, count in period_counts.items() for _ in range(count)],
            lambda x: x['period'],
            sum(period_counts.values())
        )

        # Identify peak feeding times
        total = sum(period_counts.values())
        peak_period = max(period_counts.items(), key=lambda x: x[1])[0] if total > 0 else None

        # Calculate most common feeding hours
        hour_counts = defaultdict(int)
        for feeding_time in feeding_times:
            hour_counts[feeding_time.hour] += 1

        top_hours = sorted(hour_counts.items(), key=lambda x: x[1], reverse=True)[:3]

        return {
            'distribution_by_time': schedule_distribution,
            'peak_feeding_period': peak_period,
            'most_common_hours': [{'hour': h, 'count': c} for h, c in top_hours],
            'total_feedings': total
        }

    def _analyze_baby_patterns(
            self,
            feedings: List[Any],
            requested_metrics: List[str],
            days: int
    ) -> Dict[str, Any]:
        """Analyze feeding patterns for individual baby with enhanced metrics"""
        precision = self.config.get('configuration', {}).get('precision', {})
        thresholds = self.config.get('configuration', {}).get('thresholds', {})
        patterns = {}

        # Basic stats
        patterns['total_feedings'] = len(feedings)
        patterns['analysis_days'] = days

        if 'frequency' in requested_metrics:
            patterns['daily_feeding_frequency'] = round(len(feedings) / days, precision.get('frequency_decimals', 2))

            # Use common aggregation by date
            daily_data = MetricAggregator.aggregate_by_date(
                feedings,
                lambda f: f.start_time
            )

            patterns['daily_feeding_counts'] = [
                {
                    'date': date.isoformat(),
                    'count': len(feeds)
                }
                for date, feeds in sorted(daily_data.items())
            ]

        if 'volume' in requested_metrics:
            volumes = [f.amount for f in feedings if f.amount is not None and f.amount > 0]
            if volumes:
                patterns['avg_volume_ml'] = round(sum(volumes) / len(volumes), precision.get('volume_decimals', 1))
                patterns['total_volume_ml'] = round(sum(volumes), precision.get('volume_decimals', 1))
                patterns['min_volume_ml'] = round(min(volumes), precision.get('volume_decimals', 1))
                patterns['max_volume_ml'] = round(max(volumes), precision.get('volume_decimals', 1))

        if 'duration' in requested_metrics:
            durations = [f.duration for f in feedings if f.duration is not None and f.duration > 0]
            if durations:
                patterns['avg_duration_minutes'] = round(sum(durations) / len(durations), precision.get('duration_decimals', 1))
                patterns['min_duration_minutes'] = round(min(durations), precision.get('duration_decimals', 1))
                patterns['max_duration_minutes'] = round(max(durations), precision.get('duration_decimals', 1))

        if 'types' in requested_metrics:
            type_counts = defaultdict(int)
            for feeding in feedings:
                type_counts[feeding.feeding_type] += 1

            patterns['feeding_types'] = dict(type_counts)

        if 'nutrition' in requested_metrics:
            total_calories = sum(self._calculate_calories(f) for f in feedings)
            patterns['nutrition'] = {
                'total_calories': round(total_calories, 1),
                'avg_calories_per_feeding': round(total_calories / len(feedings), 1) if feedings else 0,
                'daily_average_calories': round(total_calories / days, 1)
            }

        if 'clusters' in requested_metrics:
            cluster_window = thresholds.get('cluster_feeding_window_minutes', 60)
            clusters = ClusterDetector.detect_time_clusters(
                feedings,
                lambda f: f.start_time,
                cluster_window
            )
            patterns['cluster_analysis'] = {
                'clusters_detected': len(clusters),
                'largest_cluster_size': max(len(c) for c in clusters) if clusters else 0,
                'cluster_dates': [
                    {
                        'date': clusters[i][0].start_time.date().isoformat(),
                        'size': len(clusters[i]),
                        'duration_minutes': round(
                            (clusters[i][-1].start_time - clusters[i][0].start_time).total_seconds() / 60, 1
                        )
                    }
                    for i in range(len(clusters))
                ]
            }

        if 'efficiency' in requested_metrics:
            efficiencies = []
            feedings_with_efficiency = 0

            for feeding in feedings:
                eff = EfficiencyCalculator.calculate_rate(feeding.amount, feeding.duration)
                if eff is not None:
                    efficiencies.append({
                        'value': eff,
                        'timestamp': feeding.start_time,
                        'volume': feeding.amount,
                        'duration': feeding.duration
                    })
                    feedings_with_efficiency += 1

            if efficiencies:
                efficiency_values = [e['value'] for e in efficiencies]
                avg_efficiency = mean(efficiency_values)

                patterns['efficiency_analysis'] = {
                    'avg_feeding_rate_ml_per_min': round(avg_efficiency, 2),
                    'rate_interpretation': EfficiencyCalculator.interpret_efficiency_context(
                        avg_efficiency,
                        self.EFFICIENCY_THRESHOLDS
                    ),
                    'improving_trend': self._detect_efficiency_trend(feedings),
                    'feedings_with_complete_data': feedings_with_efficiency,
                    'total_feedings': len(feedings),
                    'data_completeness_percentage': MetricAggregator.calculate_percentage(
                        feedings_with_efficiency,
                        len(feedings)
                    ),
                    'rate_range': {
                        'min_ml_per_min': round(min(efficiency_values), 2),
                        'max_ml_per_min': round(max(efficiency_values), 2)
                    }
                }

                # Add variability if enough data
                if len(efficiency_values) > 1:
                    patterns['efficiency_analysis']['rate_consistency_std_dev'] = round(stdev(efficiency_values), 2)
            else:
                patterns['efficiency_analysis'] = {
                    'message': "No feedings with both volume and duration data available for efficiency calculation"
                }

        return patterns

    def _detect_efficiency_trend(self, feedings: List[Any]) -> str:
        """Detect if feeding efficiency is improving over time using common trend detector"""
        # Group by week and calculate average efficiency
        weekly_efficiencies = defaultdict(list)

        for feeding in feedings:
            eff = EfficiencyCalculator.calculate_rate(feeding.amount, feeding.duration)
            if eff is not None:
                week_key = feeding.start_time.isocalendar()[1]  # Week number
                weekly_efficiencies[week_key].append(eff)

        if len(weekly_efficiencies) < 2:
            return "insufficient_data"

        # Calculate weekly averages
        sorted_weeks = sorted(weekly_efficiencies.keys())
        weekly_avgs = [mean(weekly_efficiencies[week]) for week in sorted_weeks]

        # Use common trend detector
        trend = DataProcessor.detect_trend(weekly_avgs, threshold=0.1)

        trend_messages = {
            "improving": "improving - feeding rate increasing over time",
            "declining": "declining - feeding rate decreasing over time",
            "stable": "stable - consistent feeding rate",
            "insufficient_data": "insufficient_data"
        }

        return trend_messages.get(trend, "stable - consistent feeding rate")

    def _create_empty_result(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Create an empty result using common result builder"""
        config = self.config.get('configuration', {})

        # Define metric defaults
        metric_defaults = {}

        if 'frequency' in params['requested_metrics']:
            metric_defaults['avg_daily_feedings'] = 0.0
            metric_defaults['total_feedings_analyzed'] = 0

        if 'volume' in params['requested_metrics']:
            messages = config.get('messages', {})
            metric_defaults['volume_data'] = messages.get('no_volume_data', 'Volume data not available')

        if 'duration' in params['requested_metrics']:
            messages = config.get('messages', {})
            metric_defaults['duration_data'] = messages.get('no_duration_data', 'Duration data not available')

        if 'types' in params['requested_metrics']:
            metric_defaults['feeding_type_distribution'] = {}

        if 'nutrition' in params['requested_metrics']:
            messages = config.get('messages', {})
            metric_defaults['nutrition_metrics'] = {
                "message": messages.get('no_data_available', 'No nutrition data available')
            }

        if 'pumping' in params['requested_metrics']:
            metric_defaults['pumping_sessions'] = 0

        if 'schedule' in params['requested_metrics']:
            messages = config.get('messages', {})
            metric_defaults['schedule_analysis'] = {
                "message": messages.get('insufficient_data', 'Insufficient data for pattern analysis')
            }

        if 'clusters' in params['requested_metrics']:
            metric_defaults['cluster_feeding_analysis'] = {
                "total_clusters_detected": 0,
                "message": "No data available for cluster analysis"
            }

        if 'efficiency' in params['requested_metrics']:
            metric_defaults['feeding_efficiency'] = {
                "message": "No efficiency data available",
                "explanation": "Feeding efficiency measures ml consumed per minute during feeding sessions"
            }

        # Use common result builder
        result = ResultBuilder.create_empty_analysis_result(
            days=params['days'],
            requested_metrics=params['requested_metrics'],
            config=config,
            additional_filters={
                "feeding_types": params['feeding_types_filter'],
                "time_of_day": params['time_of_day_filter']
            },
            metric_defaults=metric_defaults
        )

        return result