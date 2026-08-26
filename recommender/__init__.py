"""
Stage 3 Course Recommendation System - Package Exports
======================================================
"""

# Core models
from .models import (
    Modality,
    Schedule,
    UserProfile,
    SkillGap,
    Course,
    FuzzyScores,
    ScoreBreakdown,
    RecommendedCourse,
    LearningPath,
    HistoricalCase,
)

# Configuration
from .config import RecommenderConfig

# Main recommender
from .recommender import CourseRecommender

# Pipeline orchestration
from .pipeline import (
    run_recommendation_pipeline,
    run_multi_role_recommendation_pipeline,
)

# Output formatting
from .output import print_learning_path_summary

# MLflow tracking (optional - only used if MLflow is available)
try:
    from .mlflow_tracking import MLflowTracker
    _mlflow_available = True
except ImportError:
    _mlflow_available = False

# Integration utilities
from .integration import (
    parse_stage2_json,
    parse_stage2_multi_role_json,
    load_stage2_from_json_file,
    load_stage2_multi_role_from_json_file,
)

# Serialization utilities
from .serialization import (
    serialize_learning_path_to_json,
    save_learning_path_to_json,
    save_learning_path_to_delta,
)

# Evaluation metrics
from .evaluation import (
    calculate_skill_gap_coverage,
    calculate_weighted_skill_coverage,
    calculate_recommendation_diversity,
    calculate_cost_efficiency,
)

# Validation utilities
from .validation import (
    validate_user_profile,
    validate_skill_gaps,
    validate_courses,
)

__all__ = [
    # Models
    "Modality",
    "Schedule",
    "UserProfile",
    "SkillGap",
    "Course",
    "FuzzyScores",
    "ScoreBreakdown",
    "RecommendedCourse",
    "LearningPath",
    "HistoricalCase",
    # Configuration
    "RecommenderConfig",
    # Main recommender
    "CourseRecommender",
    # Pipeline orchestration
    "run_recommendation_pipeline",
    "run_multi_role_recommendation_pipeline",
    # Output formatting
    "print_learning_path_summary",
    # Integration
    "parse_stage2_json",
    "parse_stage2_multi_role_json",
    "load_stage2_from_json_file",
    "load_stage2_multi_role_from_json_file",
    # Serialization
    "serialize_learning_path_to_json",
    "save_learning_path_to_json",
    "save_learning_path_to_delta",
    # Evaluation
    "calculate_skill_gap_coverage",
    "calculate_weighted_skill_coverage",
    "calculate_recommendation_diversity",
    "calculate_cost_efficiency",
    # Validation
    "validate_user_profile",
    "validate_skill_gaps",
    "validate_courses",
]

# Conditionally add MLflowTracker if available
if _mlflow_available:
    __all__.append("MLflowTracker")
