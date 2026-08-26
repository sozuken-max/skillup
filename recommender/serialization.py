"""
Stage 3 Course Recommendation System - Modularized
===================================================
Part of the SkillUp course recommendation pipeline.
"""

from typing import Dict, Any
import json
import logging

from .models import LearningPath, RecommendedCourse

logger = logging.getLogger(__name__)

def serialize_learning_path_to_json(learning_path: LearningPath) -> Dict[str, Any]:
    """
    Serialize LearningPath to JSON format for downstream consumption.
    
    Args:
        learning_path: LearningPath object from recommender
        
    Returns:
        JSON-serializable dict
    """
    return {
        "user_id": learning_path.user_id,
        "generated_at": learning_path.generated_at.isoformat(),
        "summary": {
            "total_courses": learning_path.total_courses,
            "total_duration_weeks": learning_path.total_duration_weeks,
            "total_cost_sgd": learning_path.total_cost,
            "total_cost_after_subsidy_sgd": learning_path.total_cost_after_subsidy,
            "total_savings_sgd": learning_path.total_cost - learning_path.total_cost_after_subsidy,
            "subsidy_rate": (
                (learning_path.total_cost - learning_path.total_cost_after_subsidy) / learning_path.total_cost
                if learning_path.total_cost > 0 else 0.0
            )
        },
        "cbr_insight": learning_path.cbr_insight,
        "trade_offs": learning_path.trade_offs,
        "recommended_courses": [
            _serialize_recommended_course(rc)
            for rc in learning_path.courses
        ]
    }


def _serialize_recommended_course(rc: RecommendedCourse) -> Dict[str, Any]:
    """Serialize a single RecommendedCourse"""
    # Helper to extract enum value
    def get_enum_value(obj):
        if obj is None:
            return "flexible"
        if hasattr(obj, 'value'):
            return obj.value
        return str(obj)
    
    return {
        "rank": rc.rank,
        "sequence_position": rc.sequence_position,
        "course": {
            "course_id": rc.course.course_id,
            "title": rc.course.title,
            "provider": rc.course.provider,
            "duration_weeks": rc.course.duration_weeks,
            "cost_sgd": rc.course.cost,
            "cost_after_subsidy_sgd": rc.course.cost_after_subsidy,
            "subsidy_rate": rc.course.subsidy_rate,
            "savings_sgd": rc.course.cost - rc.course.cost_after_subsidy,
            "modality": get_enum_value(rc.course.modality),
            "schedule": get_enum_value(rc.course.schedule),
            "skills_covered": rc.course.skills_covered or "",
            "prerequisites": rc.course.prerequisites or "",
            "rating": rc.course.rating,
            "enrollment_count": rc.course.enrollment_count,
            "skillsfuture_eligible": rc.course.skillsfuture_eligible,
            "estimated_hours_per_week": rc.course.hours_per_week
        },
        "scores": {
            "final_score": rc.final_score,
            "score_breakdown": {
                "relevance": rc.score_breakdown.relevance,
                "rating": rc.score_breakdown.rating,
                "constraint_fit": rc.score_breakdown.constraint_fit,
                "cbr_similarity": rc.score_breakdown.cbr,
                "popularity": rc.score_breakdown.popularity
            },
            "fuzzy_logic_scores": {
                "budget_fitness": rc.fuzzy_scores.budget_fitness,
                "time_fitness": rc.fuzzy_scores.time_fitness,
                "skill_relevance": rc.fuzzy_scores.relevance,
                "modality_match": rc.fuzzy_scores.modality_match
            }
        },
        "warnings": rc.flags
    }


def save_learning_path_to_json(learning_path: LearningPath, filepath: str):
    """
    Save LearningPath to JSON file.
    
    Args:
        learning_path: LearningPath object
        filepath: Output file path
    """
    data = serialize_learning_path_to_json(learning_path)
    
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)
    
    logger.info(f"Saved learning path to: {filepath}")


def save_learning_path_to_delta(learning_path: LearningPath, table_name: str):
    """
    Save LearningPath to Delta table.
    
    Requires PySpark in Databricks environment.
    
    Args:
        learning_path: LearningPath object
        table_name: Fully qualified Delta table name
    """
    try:
        from pyspark.sql import SparkSession
        from datetime import timezone
        
        spark = SparkSession.builder.getOrCreate()
        
        data = serialize_learning_path_to_json(learning_path)
        json_str = json.dumps(data)
        
        row = {
            "user_id": learning_path.user_id,
            "recommendation_json": json_str,
            "generated_at": learning_path.generated_at.replace(tzinfo=timezone.utc)
        }
        
        df = spark.createDataFrame([row])
        df.write.format("delta").mode("append").saveAsTable(table_name)
        
        logger.info(f"Saved learning path to Delta: {table_name}")
    
    except ImportError:
        raise RuntimeError("PySpark not available. Use save_learning_path_to_json() instead.")


# ============================================================================
