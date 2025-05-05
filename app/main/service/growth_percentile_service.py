from typing import Dict, Any, Optional

# WHO growth charts data (simplified for this example)
# These are the 50th percentile values by age in months
WHO_WEIGHT_BOYS = {0: 3.3, 1: 4.5, 2: 5.6, 3: 6.4, 6: 7.9, 9: 8.9, 12: 9.6, 18: 11.1, 24: 12.2}
WHO_HEIGHT_BOYS = {0: 49.9, 1: 54.7, 2: 58.4, 3: 61.4, 6: 67.6, 9: 72.3, 12: 75.7, 18: 82.3, 24: 87.8}
WHO_HEAD_BOYS = {0: 34.5, 1: 37.3, 2: 39.1, 3: 40.5, 6: 43.3, 9: 45.2, 12: 46.1, 18: 47.4, 24: 48.3}

WHO_WEIGHT_GIRLS = {0: 3.2, 1: 4.2, 2: 5.1, 3: 5.8, 6: 7.3, 9: 8.2, 12: 8.9, 18: 10.2, 24: 11.5}
WHO_HEIGHT_GIRLS = {0: 49.1, 1: 53.7, 2: 57.1, 3: 59.8, 6: 65.7, 9: 70.4, 12: 74.0, 18: 80.7, 24: 86.4}
WHO_HEAD_GIRLS = {0: 33.9, 1: 36.5, 2: 38.3, 3: 39.5, 6: 42.2, 9: 44.1, 12: 45.2, 18: 46.7, 24: 47.7}


def calculate_growth_percentile(baby_data: Dict[str, Any], measurement_data: Dict[str, Any]) -> Dict[
    str, Any]:
    """Calculate growth percentiles against WHO standards"""
    from datetime import datetime

    # Extract baby information
    birthdate = baby_data.get('birthdate')
    if not birthdate:
        return {
            'status': 'fail',
            'message': 'Baby birthdate not available'
        }

    # Calculate age in months
    today = datetime.utcnow()
    age_days = (today - birthdate).days
    age_months = age_days // 30  # Approximate months

    # Get gender (simplified - in real app we'd store this in the baby model)
    gender = "male"  # Default to male for this example

    # Get measurement values
    weight = measurement_data.get('weight')
    height = measurement_data.get('height')
    head_circumference = measurement_data.get('head_circumference')

    # Initialize results
    percentiles = {}

    # Check weight percentile
    if weight:
        if gender == "male":
            ref_weights = WHO_WEIGHT_BOYS
        else:
            ref_weights = WHO_WEIGHT_GIRLS

        # Find closest age bracket
        closest_age = min(ref_weights.keys(), key=lambda x: abs(x - age_months))
        standard_weight = ref_weights[closest_age]

        # Calculate simple percentile (actual/standard * 100)
        percentiles['weight'] = {
            'value': weight,
            'standard': standard_weight,
            'percentage': round((weight / standard_weight) * 100, 1),
            'age_months': age_months,
            'reference_age_months': closest_age
        }

    # Similar logic for height and head circumference
    # (Code omitted for brevity but would follow same pattern)

    return {
        'status': 'success',
        'percentiles': percentiles,
        'baby_age_months': age_months
    }