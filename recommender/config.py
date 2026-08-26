"""
Stage 3 Course Recommendation System - Modularized
===================================================
Part of the SkillUp course recommendation pipeline.
"""

from typing import Optional
from dataclasses import dataclass, field


@dataclass
class RecommenderConfig:
    """Configuration for recommendation weights and thresholds"""
    
    # Score fusion weights (must sum to 1.0)
    weight_relevance: float = 0.35
    weight_rating: float = 0.20
    weight_constraints: float = 0.20
    weight_cbr: float = 0.15
    weight_popularity: float = 0.10
    
    # CBR similarity weights (must sum to 1.0)
    cbr_weight_current_role: float = 0.20
    cbr_weight_target_role: float = 0.25
    cbr_weight_skill_overlap: float = 0.25
    cbr_weight_budget: float = 0.15
    cbr_weight_time: float = 0.15
    
    # Fuzzy logic thresholds
    budget_tolerance: float = 0.15  # 15% overage allowed
    time_tolerance: float = 0.20  # 20% stretch allowed
    
    # CSP parameters
    max_courses: int = 10
    min_relevance_threshold: float = 0.4
    
    # Semantic search parameters
    use_semantic_search: bool = True  # Enable/disable semantic search
    semantic_search_top_k: int = 100  # Number of courses to retrieve via semantic search
    course_catalog_table: str = "workspace.default.my_skills_future_course_directory"
    
    # MLflow configuration
    enable_mlflow: bool = True
    mlflow_experiment_name: Optional[str] = None  # If None, uses default

    # Databricks UC Logging configuration
    enable_uc_logging: bool = True
    uc_log_table: str = "workspace.default.recommendation_log"

    # CBR case library fixture (relative to project root or absolute path)
    # If None, auto-detects data/cbr_cases_fixtures.json
    cbr_fixture_path: Optional[str] = None

