"""
WHO Growth Percentile Service - Enhanced Implementation

This module provides functions for calculating child growth percentiles and z-scores
based on the World Health Organization (WHO) Child Growth Standards.

The WHO standards are the international standard for assessing children's growth and
development, providing a robust tool for monitoring health and nutrition status.

References:
- WHO Child Growth Standards: https://www.who.int/tools/child-growth-standards
- WHO Anthro Software: https://www.who.int/tools/child-growth-standards/software
"""

from typing import Dict, Any, Optional, Tuple, List, Union, Literal
from datetime import datetime
import math
import bisect
import json
import os
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Measurement types
MeasurementType = Literal['weight', 'height', 'head', 'bmi', 'weight-for-length']
Sex = Literal['male', 'female']

# Z-score boundaries for standard percentiles
Z_SCORE_FOR_PERCENTILE = {
    1: -2.326,
    3: -1.881,
    5: -1.645,
    10: -1.282,
    15: -1.036,
    25: -0.674,
    50: 0.0,
    75: 0.674,
    85: 1.036,
    90: 1.282,
    95: 1.645,
    97: 1.881,
    99: 2.326
}

# Reverse mapping from z-score to percentile
PERCENTILE_FOR_Z_SCORE = {v: k for k, v in Z_SCORE_FOR_PERCENTILE.items()}

# Path to WHO data files
DATA_DIR = Path(__file__).parent / "who_data"

# LMS data for WHO growth standards (Lambda, Mu, Sigma method)
# This is a critical improvement, as WHO uses the LMS method for growth standards
# In a production environment, these would be loaded from comprehensive data files

# Sample LMS data for demonstration
# Each age has: l (Box-Cox transformation power), m (median), s (coefficient of variation)
LMS_WEIGHT_BOYS = {
    0: {'l': 0.3485, 'm': 3.3464, 's': 0.1460},
    1: {'l': 0.2508, 'm': 4.4709, 's': 0.1356},
    2: {'l': 0.1458, 'm': 5.5675, 's': 0.1277},
    3: {'l': 0.0498, 'm': 6.3762, 's': 0.1220},
    4: {'l': -0.0322, 'm': 7.0023, 's': 0.1179},
    5: {'l': -0.1042, 'm': 7.5105, 's': 0.1147},
    6: {'l': -0.1656, 'm': 7.9340, 's': 0.1123},
    9: {'l': -0.2658, 'm': 8.9021, 's': 0.1079},
    12: {'l': -0.3069, 'm': 9.6481, 's': 0.1060},
    15: {'l': -0.3114, 'm': 10.2966, 's': 0.1062},
    18: {'l': -0.2853, 'm': 10.9029, 's': 0.1076},
    21: {'l': -0.2328, 'm': 11.4678, 's': 0.1097},
    24: {'l': -0.1612, 'm': 12.0008, 's': 0.1123}
}

LMS_WEIGHT_GIRLS = {
    0: {'l': 0.3809, 'm': 3.2322, 's': 0.1382},
    1: {'l': 0.1714, 'm': 4.1873, 's': 0.1309},
    2: {'l': -0.0329, 'm': 5.1282, 's': 0.1261},
    3: {'l': -0.1835, 'm': 5.8458, 's': 0.1229},
    4: {'l': -0.2795, 'm': 6.4237, 's': 0.1209},
    5: {'l': -0.3458, 'm': 6.8985, 's': 0.1195},
    6: {'l': -0.3932, 'm': 7.2970, 's': 0.1187},
    9: {'l': -0.4694, 'm': 8.1351, 's': 0.1177},
    12: {'l': -0.4994, 'm': 8.9471, 's': 0.1175},
    15: {'l': -0.4999, 'm': 9.7365, 's': 0.1181},
    18: {'l': -0.4864, 'm': 10.4740, 's': 0.1190},
    21: {'l': -0.4653, 'm': 11.1449, 's': 0.1200},
    24: {'l': -0.4391, 'm': 11.7979, 's': 0.1209}
}

LMS_HEIGHT_BOYS = {
    0: {'l': 1.0000, 'm': 49.8842, 's': 0.0379},
    1: {'l': 1.0000, 'm': 54.7244, 's': 0.0364},
    2: {'l': 1.0000, 'm': 58.4249, 's': 0.0352},
    3: {'l': 1.0000, 'm': 61.4292, 's': 0.0342},
    4: {'l': 1.0000, 'm': 63.8860, 's': 0.0335},
    5: {'l': 1.0000, 'm': 65.9026, 's': 0.0329},
    6: {'l': 1.0000, 'm': 67.6236, 's': 0.0325},
    9: {'l': 1.0000, 'm': 72.0440, 's': 0.0318},
    12: {'l': 1.0000, 'm': 75.7488, 's': 0.0315},
    15: {'l': 1.0000, 'm': 78.9155, 's': 0.0313},
    18: {'l': 1.0000, 'm': 81.8244, 's': 0.0313},
    21: {'l': 1.0000, 'm': 84.4778, 's': 0.0314},
    24: {'l': 1.0000, 'm': 86.8465, 's': 0.0315}
}

LMS_HEIGHT_GIRLS = {
    0: {'l': 1.0000, 'm': 49.1477, 's': 0.0379},
    1: {'l': 1.0000, 'm': 53.6872, 's': 0.0364},
    2: {'l': 1.0000, 'm': 57.0673, 's': 0.0357},
    3: {'l': 1.0000, 'm': 59.8029, 's': 0.0351},
    4: {'l': 1.0000, 'm': 62.0899, 's': 0.0346},
    5: {'l': 1.0000, 'm': 64.0301, 's': 0.0342},
    6: {'l': 1.0000, 'm': 65.7311, 's': 0.0338},
    9: {'l': 1.0000, 'm': 70.2315, 's': 0.0330},
    12: {'l': 1.0000, 'm': 74.0148, 's': 0.0327},
    15: {'l': 1.0000, 'm': 77.2341, 's': 0.0325},
    18: {'l': 1.0000, 'm': 80.0693, 's': 0.0324},
    21: {'l': 1.0000, 'm': 82.5583, 's': 0.0324},
    24: {'l': 1.0000, 'm': 84.7549, 's': 0.0324}
}

LMS_HEAD_BOYS = {
    0: {'l': 1.0000, 'm': 34.4618, 's': 0.0371},
    1: {'l': 1.0000, 'm': 37.2759, 's': 0.0348},
    2: {'l': 1.0000, 'm': 39.1286, 's': 0.0332},
    3: {'l': 1.0000, 'm': 40.5135, 's': 0.0320},
    4: {'l': 1.0000, 'm': 41.6334, 's': 0.0312},
    5: {'l': 1.0000, 'm': 42.5542, 's': 0.0307},
    6: {'l': 1.0000, 'm': 43.3088, 's': 0.0303},
    9: {'l': 1.0000, 'm': 44.8504, 's': 0.0296},
    12: {'l': 1.0000, 'm': 45.8140, 's': 0.0293},
    15: {'l': 1.0000, 'm': 46.5361, 's': 0.0292},
    18: {'l': 1.0000, 'm': 47.1203, 's': 0.0292},
    21: {'l': 1.0000, 'm': 47.5911, 's': 0.0293},
    24: {'l': 1.0000, 'm': 47.9793, 's': 0.0294}
}

LMS_HEAD_GIRLS = {
    0: {'l': 1.0000, 'm': 33.8787, 's': 0.0339},
    1: {'l': 1.0000, 'm': 36.5463, 's': 0.0333},
    2: {'l': 1.0000, 'm': 38.2521, 's': 0.0327},
    3: {'l': 1.0000, 'm': 39.5330, 's': 0.0322},
    4: {'l': 1.0000, 'm': 40.5817, 's': 0.0317},
    5: {'l': 1.0000, 'm': 41.4508, 's': 0.0313},
    6: {'l': 1.0000, 'm': 42.1866, 's': 0.0310},
    9: {'l': 1.0000, 'm': 43.6153, 's': 0.0303},
    12: {'l': 1.0000, 'm': 44.5855, 's': 0.0300},
    15: {'l': 1.0000, 'm': 45.2991, 's': 0.0298},
    18: {'l': 1.0000, 'm': 45.8392, 's': 0.0297},
    21: {'l': 1.0000, 'm': 46.2588, 's': 0.0297},
    24: {'l': 1.0000, 'm': 46.5977, 's': 0.0297}
}

# For BMI calculations
LMS_BMI_BOYS = {
    0: {'l': -0.3521, 'm': 13.4327, 's': 0.0938},
    1: {'l': -0.5128, 'm': 16.5714, 's': 0.0895},
    2: {'l': -0.6098, 'm': 16.4004, 's': 0.0887},
    3: {'l': -0.6753, 'm': 16.1753, 's': 0.0886},
    4: {'l': -0.7195, 'm': 15.9923, 's': 0.0891},
    5: {'l': -0.7478, 'm': 15.8465, 's': 0.0898},
    6: {'l': -0.7648, 'm': 15.7388, 's': 0.0907},
    9: {'l': -0.7690, 'm': 15.6066, 's': 0.0939},
    12: {'l': -0.7223, 'm': 15.5922, 's': 0.0978},
    15: {'l': -0.6429, 'm': 15.6696, 's': 0.1020},
    18: {'l': -0.5449, 'm': 15.8086, 's': 0.1063},
    21: {'l': -0.4352, 'm': 15.9800, 's': 0.1105},
    24: {'l': -0.3187, 'm': 16.1676, 's': 0.1147}
}

LMS_BMI_GIRLS = {
    0: {'l': -0.3833, 'm': 13.3374, 's': 0.0943},
    1: {'l': -0.5141, 'm': 16.0085, 's': 0.0906},
    2: {'l': -0.5865, 'm': 15.7642, 's': 0.0898},
    3: {'l': -0.6307, 'm': 15.5670, 's': 0.0900},
    4: {'l': -0.6570, 'm': 15.4157, 's': 0.0906},
    5: {'l': -0.6709, 'm': 15.3023, 's': 0.0914},
    6: {'l': -0.6759, 'm': 15.2201, 's': 0.0925},
    9: {'l': -0.6511, 'm': 15.1409, 's': 0.0962},
    12: {'l': -0.5916, 'm': 15.1691, 's': 0.1002},
    15: {'l': -0.5171, 'm': 15.2686, 's': 0.1041},
    18: {'l': -0.4376, 'm': 15.4145, 's': 0.1079},
    21: {'l': -0.3597, 'm': 15.5905, 's': 0.1114},
    24: {'l': -0.2853, 'm': 15.7818, 's': 0.1147}
}

# Compile all LMS data into a structured dictionary for easy access
WHO_LMS_DATA = {
    'male': {
        'weight': LMS_WEIGHT_BOYS,
        'height': LMS_HEIGHT_BOYS,
        'head': LMS_HEAD_BOYS,
        'bmi': LMS_BMI_BOYS
    },
    'female': {
        'weight': LMS_WEIGHT_GIRLS,
        'height': LMS_HEIGHT_GIRLS,
        'head': LMS_HEAD_GIRLS,
        'bmi': LMS_BMI_GIRLS
    }
}

# Legacy data for backward compatibility - these are the original data tables from the code
# BOYS - Weight-for-age (kg)
WHO_WEIGHT_BOYS = {
    # Percentiles [3rd, 15th, 50th, 85th, 97th]
    0: [2.5, 2.9, 3.3, 3.7, 4.0],
    1: [3.4, 3.9, 4.5, 5.1, 5.5],
    2: [4.3, 4.9, 5.6, 6.3, 6.8],
    3: [5.0, 5.7, 6.4, 7.2, 7.8],
    4: [5.6, 6.2, 7.0, 7.8, 8.4],
    5: [6.0, 6.7, 7.5, 8.4, 9.0],
    6: [6.4, 7.1, 7.9, 8.8, 9.5],
    9: [7.1, 7.9, 8.9, 9.9, 10.7],
    12: [7.8, 8.6, 9.6, 10.8, 11.8],
    15: [8.3, 9.2, 10.3, 11.5, 12.6],
    18: [8.8, 9.8, 10.9, 12.2, 13.4],
    21: [9.2, 10.2, 11.5, 12.8, 14.1],
    24: [9.7, 10.6, 12.2, 13.6, 14.8]
}

# BOYS - Length/Height-for-age (cm)
WHO_HEIGHT_BOYS = {
    # Percentiles [3rd, 15th, 50th, 85th, 97th]
    0: [46.3, 48.0, 49.9, 51.8, 53.4],
    1: [50.8, 52.5, 54.7, 56.7, 58.4],
    2: [54.4, 56.2, 58.4, 60.6, 62.4],
    3: [57.3, 59.1, 61.4, 63.7, 65.5],
    4: [59.7, 61.6, 63.9, 66.2, 68.0],
    5: [61.7, 63.6, 65.9, 68.2, 70.1],
    6: [63.3, 65.3, 67.6, 70.0, 71.9],
    9: [67.5, 69.5, 72.0, 74.5, 76.5],
    12: [70.6, 72.7, 75.7, 78.4, 80.5],
    15: [73.0, 75.2, 78.2, 81.2, 83.6],
    18: [75.2, 77.4, 80.7, 83.8, 86.3],
    21: [77.1, 79.4, 82.9, 86.0, 88.7],
    24: [78.9, 81.2, 84.8, 88.0, 90.9]
}

# BOYS - Head circumference-for-age (cm)
WHO_HEAD_BOYS = {
    # Percentiles [3rd, 15th, 50th, 85th, 97th]
    0: [32.4, 33.4, 34.5, 35.7, 36.6],
    1: [35.1, 36.1, 37.3, 38.4, 39.5],
    2: [36.9, 37.9, 39.1, 40.3, 41.3],
    3: [38.3, 39.3, 40.5, 41.7, 42.7],
    4: [39.4, 40.4, 41.6, 42.8, 43.8],
    5: [40.3, 41.3, 42.6, 43.8, 44.8],
    6: [41.0, 42.1, 43.3, 44.6, 45.6],
    9: [42.6, 43.5, 44.9, 46.1, 47.1],
    12: [43.5, 44.6, 45.8, 47.0, 48.0],
    15: [44.3, 45.3, 46.6, 47.8, 48.8],
    18: [44.9, 45.9, 47.1, 48.4, 49.3],
    21: [45.3, 46.3, 47.5, 48.8, 49.7],
    24: [45.7, 46.7, 47.9, 49.1, 50.0]
}

# GIRLS - Weight-for-age (kg)
WHO_WEIGHT_GIRLS = {
    # Percentiles [3rd, 15th, 50th, 85th, 97th]
    0: [2.4, 2.8, 3.2, 3.6, 4.0],
    1: [3.2, 3.6, 4.2, 4.8, 5.2],
    2: [3.9, 4.5, 5.1, 5.8, 6.3],
    3: [4.5, 5.1, 5.8, 6.6, 7.2],
    4: [5.0, 5.6, 6.4, 7.2, 7.8],
    5: [5.4, 6.1, 6.9, 7.7, 8.4],
    6: [5.7, 6.4, 7.3, 8.2, 8.9],
    9: [6.5, 7.3, 8.2, 9.3, 10.1],
    12: [7.1, 7.9, 8.9, 10.1, 11.0],
    15: [7.6, 8.5, 9.6, 10.8, 11.9],
    18: [8.1, 9.0, 10.2, 11.5, 12.6],
    21: [8.6, 9.5, 10.8, 12.2, 13.3],
    24: [8.9, 10.0, 11.5, 12.9, 14.1]
}

# GIRLS - Length/Height-for-age (cm)
WHO_HEIGHT_GIRLS = {
    # Percentiles [3rd, 15th, 50th, 85th, 97th]
    0: [45.6, 47.2, 49.1, 51.0, 52.7],
    1: [49.8, 51.5, 53.7, 55.6, 57.4],
    2: [53.0, 54.6, 57.1, 59.1, 61.0],
    3: [55.6, 57.2, 59.8, 62.0, 63.9],
    4: [57.8, 59.5, 62.1, 64.3, 66.2],
    5: [59.6, 61.4, 64.0, 66.2, 68.2],
    6: [61.2, 63.0, 65.7, 68.0, 70.0],
    9: [65.0, 66.9, 69.8, 72.2, 74.2],
    12: [68.0, 70.0, 73.0, 75.6, 77.8],
    15: [70.5, 72.6, 75.7, 78.5, 80.9],
    18: [72.7, 74.9, 78.1, 81.2, 83.6],
    21: [74.6, 76.9, 80.3, 83.5, 86.1],
    24: [76.5, 78.8, 82.5, 85.7, 88.5]
}

# GIRLS - Head circumference-for-age (cm)
WHO_HEAD_GIRLS = {
    # Percentiles [3rd, 15th, 50th, 85th, 97th]
    0: [31.9, 32.9, 33.9, 35.1, 36.1],
    1: [34.3, 35.3, 36.5, 37.7, 38.7],
    2: [35.8, 36.9, 38.1, 39.4, 40.5],
    3: [37.0, 38.1, 39.3, 40.6, 41.7],
    4: [37.9, 39.0, 40.3, 41.6, 42.7],
    5: [38.7, 39.8, 41.1, 42.5, 43.6],
    6: [39.3, 40.4, 41.7, 43.1, 44.3],
    9: [40.7, 41.8, 43.0, 44.4, 45.7],
    12: [41.8, 42.9, 44.1, 45.6, 46.8],
    15: [42.6, 43.7, 44.9, 46.3, 47.5],
    18: [43.3, 44.3, 45.6, 47.0, 48.1],
    21: [43.9, 44.9, 46.2, 47.5, 48.7],
    24: [44.4, 45.4, 46.6, 48.0, 49.1]
}

# Percentile index reference
PERCENTILE_VALUES = [3, 15, 50, 85, 97]


def get_lms_parameters(age_months: float, sex: Sex, measurement_type: MeasurementType) -> Dict[str, float]:
    """
    Get the LMS parameters for a specific age, sex, and measurement type.

    The LMS parameters are used in the WHO method to calculate z-scores:
    - L: the Box-Cox transformation power
    - M: the median (50th percentile)
    - S: the coefficient of variation

    Args:
        age_months: Age in months
        sex: 'male' or 'female'
        measurement_type: 'weight', 'height', 'head', 'bmi', or 'weight-for-length'

    Returns:
        Dictionary with L, M, and S parameters
    """
    try:
        # Get data for this sex and measurement type
        if sex.lower() not in WHO_LMS_DATA or measurement_type.lower() not in WHO_LMS_DATA[sex.lower()]:
            logger.warning(f"No LMS data available for sex={sex}, measurement_type={measurement_type}")
            # Return default values if data not available
            return {'l': 1.0, 'm': 0.0, 's': 0.1}

        data = WHO_LMS_DATA[sex.lower()][measurement_type.lower()]

        # Get all available ages
        ages = sorted(data.keys())

        # Handle edge cases
        if age_months <= ages[0]:
            return data[ages[0]]
        elif age_months >= ages[-1]:
            return data[ages[-1]]

        # Find the two ages that our target age falls between
        lower_age_idx = bisect.bisect_right(ages, age_months) - 1
        upper_age_idx = lower_age_idx + 1

        lower_age = ages[lower_age_idx]
        upper_age = ages[upper_age_idx]

        # Interpolate parameters
        lower_params = data[lower_age]
        upper_params = data[upper_age]

        # Linear interpolation for each parameter
        interpolated_params = {}
        for param in ['l', 'm', 's']:
            lower_value = lower_params[param]
            upper_value = upper_params[param]
            interpolated_params[param] = lower_value + (age_months - lower_age) * (upper_value - lower_value) / (upper_age - lower_age)

        return interpolated_params

    except Exception as e:
        logger.error(f"Error getting LMS parameters: {e}")
        # Return default values if there's an error
        return {'l': 1.0, 'm': 0.0, 's': 0.1}


def calculate_z_score(value: float, age_months: float, sex: Sex, measurement_type: MeasurementType) -> float:
    """
    Calculate the z-score for a measurement using the LMS method.

    The LMS method accounts for the skewness of the reference data:
    Z = [(Value/M)^L - 1] / (L*S)  if L ≠ 0
    Z = log(Value/M) / S           if L = 0

    Args:
        value: The measurement value
        age_months: Age in months
        sex: 'male' or 'female'
        measurement_type: 'weight', 'height', 'head', 'bmi', or 'weight-for-length'

    Returns:
        Z-score value
    """
    try:
        lms_params = get_lms_parameters(age_months, sex, measurement_type)
        l = lms_params['l']
        m = lms_params['m']
        s = lms_params['s']

        # Safety check to avoid division by zero
        if m <= 0 or s <= 0:
            logger.warning(f"Invalid LMS parameters: L={l}, M={m}, S={s}")
            return 0.0

        # Apply the LMS formula
        if abs(l) < 0.01:  # L is close to 0
            z = math.log(value / m) / s
        else:
            z = ((value / m) ** l - 1) / (l * s)

        return round(z, 2)

    except Exception as e:
        logger.error(f"Error calculating z-score: {e}")
        return 0.0


def z_score_to_percentile(z: float) -> float:
    """
    Convert a z-score to a percentile using the normal distribution.

    Args:
        z: Z-score value

    Returns:
        Percentile value (0-100)
    """
    try:
        # For z-scores beyond ±4, clamp to avoid extreme values
        z = max(-4, min(4, z))

        # Calculate using the error function (normal distribution CDF)
        percentile = 50 * (1 + math.erf(z / math.sqrt(2)))
        return round(percentile, 1)

    except Exception as e:
        logger.error(f"Error converting z-score to percentile: {e}")
        return 50.0  # Default to 50th percentile in case of error


def interpolate_measurement(age_months: float, measurement_data: Dict[int, List[float]],
                            percentile_index: int) -> float:
    """
    Interpolate a measurement value at a specific age and percentile.

    Args:
        age_months: Baby's age in months
        measurement_data: Dictionary with age (months) as keys and lists of percentile values
        percentile_index: Index in the percentile list (0-4 for 3rd, 15th, 50th, 85th, 97th)

    Returns:
        Interpolated measurement value
    """
    try:
        # Get all available ages
        ages = sorted(measurement_data.keys())

        # Handle edge cases
        if age_months <= ages[0]:
            return measurement_data[ages[0]][percentile_index]
        elif age_months >= ages[-1]:
            return measurement_data[ages[-1]][percentile_index]

        # Find the two ages that our target age falls between
        lower_age_idx = bisect.bisect_right(ages, age_months) - 1
        upper_age_idx = lower_age_idx + 1

        lower_age = ages[lower_age_idx]
        upper_age = ages[upper_age_idx]

        # Linear interpolation formula: y = y1 + (x - x1) * (y2 - y1) / (x2 - x1)
        lower_value = measurement_data[lower_age][percentile_index]
        upper_value = measurement_data[upper_age][percentile_index]

        interpolated_value = lower_value + (age_months - lower_age) * (upper_value - lower_value) / (upper_age - lower_age)
        return round(interpolated_value, 2)
    except Exception as e:
        logger.error(f"Error in interpolate_measurement: {e}")
        # Return a safe default
        return 0.0


def find_percentile_range(value: float, age_months: float, sex: Sex, measurement_type: MeasurementType) -> Tuple[
    int, int, float]:
    """
    Find which percentile range a measurement falls into and calculate exact percentile.

    Args:
        value: Actual measurement value
        age_months: Baby's age in months
        sex: 'male' or 'female'
        measurement_type: 'weight', 'height', 'head', 'bmi', or 'weight-for-length'

    Returns:
        Tuple containing (lower_percentile, upper_percentile, exact_percentile)
    """
    try:
        # Calculate z-score
        z_score = calculate_z_score(value, age_months, sex, measurement_type)

        # Convert z-score to percentile
        exact_percentile = z_score_to_percentile(z_score)

        # Find the standard percentile range
        if exact_percentile <= 3:
            return (0, 3, exact_percentile)
        elif exact_percentile >= 97:
            return (97, 100, exact_percentile)

        # Find which percentile range it falls into
        for i in range(len(PERCENTILE_VALUES) - 1):
            if PERCENTILE_VALUES[i] <= exact_percentile <= PERCENTILE_VALUES[i + 1]:
                return (PERCENTILE_VALUES[i], PERCENTILE_VALUES[i + 1], exact_percentile)

        # Fallback in case of unexpected values
        return (50, 50, 50.0)

    except Exception as e:
        logger.error(f"Error in find_percentile_range: {e}")
        # Return a safe default
        return (50, 50, 50.0)


def get_measurement_data(sex: str, measurement_type: str) -> Dict[int, List[float]]:
    """
    Get the appropriate WHO measurement data based on sex and measurement type.

    Args:
        sex: 'male' or 'female'
        measurement_type: 'weight', 'height', or 'head'

    Returns:
        Dictionary of WHO measurement data
    """
    try:
        if sex.lower() == 'male':
            if measurement_type == 'weight':
                return WHO_WEIGHT_BOYS
            elif measurement_type == 'height':
                return WHO_HEIGHT_BOYS
            elif measurement_type == 'head':
                return WHO_HEAD_BOYS
        elif sex.lower() == 'female':
            if measurement_type == 'weight':
                return WHO_WEIGHT_GIRLS
            elif measurement_type == 'height':
                return WHO_HEIGHT_GIRLS
            elif measurement_type == 'head':
                return WHO_HEAD_GIRLS

        raise ValueError(f"Invalid parameters: sex={sex}, measurement_type={measurement_type}")
    except Exception as e:
        logger.error(f"Error in get_measurement_data: {e}")
        raise


def validate_baby_data(baby_data: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Validate the baby data input.

    Args:
        baby_data: Dictionary containing baby information

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(baby_data, dict):
        return False, "Baby data must be a dictionary"

    if 'birthdate' not in baby_data:
        return False, "Baby birthdate is required"

    if 'sex' not in baby_data:
        return False, "Baby sex is required"

    # Validate birthdate
    birthdate = baby_data.get('birthdate')
    if not isinstance(birthdate, datetime):
        return False, "Birthdate must be a datetime object"

    # Validate sex
    sex = baby_data.get('sex')
    if isinstance(sex, dict) and 'value' in sex:
        sex = sex['value']

    if sex.lower() not in ['male', 'female']:
        return False, "Sex must be 'male' or 'female'"

    return True, ""


def validate_measurement_data(measurement_data: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Validate the measurement data input.

    Args:
        measurement_data: Dictionary containing measurements

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(measurement_data, dict):
        return False, "Measurement data must be a dictionary"

    # At least one measurement should be present
    if not any(key in measurement_data for key in ['weight', 'height', 'head_circumference']):
        return False, "At least one measurement (weight, height, or head_circumference) is required"

    # Validate measurement values
    for key in ['weight', 'height', 'head_circumference']:
        if key in measurement_data:
            value = measurement_data[key]
            if not isinstance(value, (int, float)) or value <= 0:
                return False, f"{key} must be a positive number"

    return True, ""


def calculate_bmi(weight_kg: float, height_cm: float) -> float:
    """
    Calculate Body Mass Index (BMI).

    BMI = weight(kg) / height(m)²

    Args:
        weight_kg: Weight in kilograms
        height_cm: Height in centimeters

    Returns:
        BMI value
    """
    try:
        if weight_kg <= 0 or height_cm <= 0:
            return 0.0

        # Convert height from cm to m
        height_m = height_cm / 100.0

        # Calculate BMI
        bmi = weight_kg / (height_m * height_m)

        return round(bmi, 1)
    except Exception as e:
        logger.error(f"Error calculating BMI: {e}")
        return 0.0


def get_age_in_months(birthdate: datetime, measurement_date: Optional[datetime] = None) -> float:
    """
    Calculate age in months from birthdate to measurement date.

    Args:
        birthdate: Baby's date of birth
        measurement_date: Date of measurement (defaults to current date)

    Returns:
        Age in months
    """
    if measurement_date is None:
        measurement_date = datetime.utcnow()

    # Calculate age in days
    age_days = (measurement_date - birthdate).days

    # Convert to months (using average of 30.44 days per month)
    age_months = age_days / 30.44

    return round(age_months, 2)


def get_clinical_interpretation(z_score: float, measurement_type: str) -> str:
    """
    Get clinical interpretation of the z-score.

    Args:
        z_score: Z-score value
        measurement_type: Type of measurement

    Returns:
        Clinical interpretation as a string
    """
    if measurement_type == 'weight':
        if z_score < -3:
            return "Severely underweight"
        elif z_score < -2:
            return "Underweight"
        elif z_score > 3:
            return "Severely overweight"
        elif z_score > 2:
            return "Overweight"
        else:
            return "Normal weight"

    elif measurement_type == 'height':
        if z_score < -3:
            return "Severely stunted"
        elif z_score < -2:
            return "Stunted"
        elif z_score > 3:
            return "Very tall"
        elif z_score > 2:
            return "Tall"
        else:
            return "Normal height"

    elif measurement_type == 'head':
        if z_score < -3:
            return "Severely small head circumference"
        elif z_score < -2:
            return "Small head circumference"
        elif z_score > 3:
            return "Severely large head circumference"
        elif z_score > 2:
            return "Large head circumference"
        else:
            return "Normal head circumference"

    elif measurement_type == 'bmi':
        if z_score < -3:
            return "Severely wasted"
        elif z_score < -2:
            return "Wasted"
        elif z_score > 3:
            return "Severely obese"
        elif z_score > 2:
            return "Obese"
        elif z_score > 1:
            return "Overweight"
        else:
            return "Normal BMI"

    else:
        return "Normal"


def calculate_growth_percentile(baby_data: Dict[str, Any], measurement_data: Dict[str, Any],
                               measurement_date: Optional[datetime] = None) -> Dict[str, Any]:
    """
    Calculate growth percentiles and z-scores against WHO standards.

    Args:
        baby_data: Dictionary containing baby information (birthdate, sex)
        measurement_data: Dictionary containing measurements (weight, height, head_circumference)
        measurement_date: Date of measurement (defaults to current date)

    Returns:
        Dictionary containing percentile and z-score results for each measurement
    """
    try:
        # Validate inputs
        is_valid_baby, baby_error = validate_baby_data(baby_data)
        if not is_valid_baby:
            return {
                'status': 'fail',
                'message': f'Invalid baby data: {baby_error}'
            }

        is_valid_measurements, measurements_error = validate_measurement_data(measurement_data)
        if not is_valid_measurements:
            return {
                'status': 'fail',
                'message': f'Invalid measurement data: {measurements_error}'
            }

        # Extract baby information
        birthdate = baby_data.get('birthdate')

        # Get sex (defaulting to male if not specified for backward compatibility)
        sex = baby_data.get('sex', 'male')
        if isinstance(sex, dict) and 'value' in sex:  # Handle enum objects
            sex = sex['value']

        # Calculate age in months
        if measurement_date is None:
            measurement_date = datetime.utcnow()

        age_months = get_age_in_months(birthdate, measurement_date)

        # Get measurement values
        weight = measurement_data.get('weight')
        height = measurement_data.get('height')
        head_circumference = measurement_data.get('head_circumference')

        # Initialize results
        percentiles = {}

        # Calculate BMI if both weight and height are available
        bmi = None
        if weight and height:
            bmi = calculate_bmi(weight, height)

        # Calculate results for each measurement
        measurements_to_process = [
            ('weight', weight, 'weight'),
            ('height', height, 'height'),
            ('head_circumference', head_circumference, 'head'),
            ('bmi', bmi, 'bmi')
        ]

        for key, value, measurement_type in measurements_to_process:
            if value:
                # Calculate z-score
                z_score = calculate_z_score(value, age_months, sex, measurement_type)

                # Convert z-score to percentile
                percentile = z_score_to_percentile(z_score)

                # Find percentile range
                lower_percentile, upper_percentile, exact_percentile = find_percentile_range(
                    value, age_months, sex, measurement_type)

                # Get standard (median) value
                standard_value = get_lms_parameters(age_months, sex, measurement_type)['m']

                # Get clinical interpretation
                interpretation = get_clinical_interpretation(z_score, measurement_type)

                percentiles[key] = {
                    'value': value,
                    'standard': round(standard_value, 2),
                    'percentage': round((value / standard_value) * 100, 1) if standard_value > 0 else 0,
                    'percentile': round(percentile, 1),
                    'percentile_range': f"{lower_percentile}-{upper_percentile}" if lower_percentile != upper_percentile else str(lower_percentile),
                    'z_score': z_score,
                    'interpretation': interpretation,
                    'age_months': round(age_months, 1)
                }

        return {
            'status': 'success',
            'percentiles': percentiles,
            'baby_age_months': round(age_months, 1),
            'baby_sex': sex,
            'measurement_date': measurement_date.isoformat()
        }

    except Exception as e:
        logger.error(f"Error in calculate_growth_percentile: {str(e)}")
        return {
            'status': 'fail',
            'message': f'Error calculating growth percentiles: {str(e)}'
        }
