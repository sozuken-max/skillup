"""
Pipeline Orchestration Functions
=================================

End-to-end pipeline helper functions that integrate Stage 2 (skill gap analysis)
with Stage 3 (course recommendation). Supports single-role and multi-role workflows.
"""

from typing import List, Dict, Optional, Any
import logging
import os

from .models import UserProfile, LearningPath, Course
from .recommender import CourseRecommender
from .integration import parse_stage2_json, parse_stage2_multi_role_json
from .serialization import save_learning_path_to_json
from .data_loading import _load_course_from_row
from .catalog import CourseCatalog

# ── INTEGRATION ───────────────────────────────────────────────────────────────
from skillgap.skillgap import execute_sql_query, COURSE_TABLE

try:
    from pyspark.sql import SparkSession
except ImportError:
    SparkSession = None

logger = logging.getLogger(__name__)


def run_recommendation_pipeline(
    stage2_json: Dict[str, Any],
    user_profile: UserProfile,
    course_catalog: List[Course] = None,
    output_json_path: Optional[str] = None
) -> LearningPath:
    """
    End-to-end pipeline helper function that integrates Stage 2 → Stage 3.
    
    This is a convenience wrapper that:
    1. Parses Stage 2 JSON output from skillgap.py
    2. Filters candidate courses
    3. Runs the recommender
    4. Optionally saves output to JSON
    
    Args:
        stage2_json: Stage 2 JSON output from skillgap.py (build_json_output)
        user_profile: User profile object
        course_catalog: List of available courses
        output_json_path: Optional path to save JSON output
        
    Returns:
        LearningPath object with course recommendations
    
    Example:
        >>> # Load Stage 2 output from skillgap.py
        >>> with open('stage2_output.json') as f:
        ...     stage2_data = json.load(f)
        >>> 
        >>> # Create user profile
        >>> user = UserProfile(
        ...     user_id="user123",
        ...     current_role="Data Analyst",
        ...     target_role="Data Engineer",
        ...     current_skills=["Python", "SQL"],
        ...     budget=5000.0,
        ...     available_hours_per_week=10.0,
        ...     preferred_modality=Modality.ONLINE,
        ...     preferred_schedule=Schedule.WEEKEND
        ... )
        >>> 
        >>> # Run pipeline
        >>> learning_path = run_recommendation_pipeline(
        ...     stage2_json=stage2_data,
        ...     user_profile=user,
        ...     course_catalog=courses,
        ...     output_json_path='stage3_output.json'
        ... )
    """
    # Parse Stage 2 JSON
    target_role, skill_gaps, candidate_course_ids = parse_stage2_json(stage2_json)

    # Load catalog if not provided
    if not course_catalog:
        course_catalog = CourseCatalog().load_all_courses()
    
    # Filter courses to candidates (if candidate_course_ids is not empty)
    #if candidate_course_ids: #Chad.Rue implement semantic search here. 
    if False:
        candidate_courses = [
            c for c in course_catalog
            if c.course_id in candidate_course_ids
        ]
        logger.info(f"Filtered to {len(candidate_courses)} candidate courses from Stage 2")
    else:
        candidate_courses = course_catalog
        logger.warning(f"No candidate courses specified in Stage 2, using full catalog ({len(course_catalog)} courses)")
    
    
    # Run recommender
    recommender = CourseRecommender()
    learning_path = recommender.recommend(user_profile, skill_gaps, candidate_courses)
    
    # Save to JSON if path provided
    if output_json_path:
        save_learning_path_to_json(learning_path, output_json_path)
    
    return learning_path


def run_multi_role_recommendation_pipeline(
    all_role_results: List[Dict[str, Any]],
    user_profile: UserProfile,
    output_dir: Optional[str] = None
) -> Dict[str, LearningPath]:
    """
    End-to-end multi-role pipeline helper function.
    
    Processes all_role_results from skillgap.py (multiple target roles) and generates
    a learning path recommendation for each role. Loads courses from Delta table
    workspace.default.my_skills_future_course_directory.
    
    Args:
        all_role_results: List of Stage 2 JSON outputs from skillgap.py
        user_profile: User profile object (will be modified for each target role)
        output_dir: Optional directory to save JSON outputs (one file per role)
        
    Returns:
        Dictionary mapping target_role -> LearningPath
        
    Example:
        >>> # Load multi-role results from skillgap.py
        >>> with open('all_roles.json') as f:
        ...     all_role_results = json.load(f)
        >>> 
        >>> # Run multi-role pipeline
        >>> learning_paths = run_multi_role_recommendation_pipeline(
        ...     all_role_results=all_role_results,
        ...     user_profile=user,
        ...     output_dir='./recommendations'
        ... )
        >>> 
        >>> for role, path in learning_paths.items():
        ...     print(f"{role}: {path.total_courses} courses, ${path.total_cost_after_subsidy:.2f}")
    """
    # Check if PySpark is available
    if SparkSession is None:
        raise RuntimeError("PySpark not available. Install pyspark to use multi-role pipeline.")

    # Parse all role results
    role_data_map = parse_stage2_multi_role_json(all_role_results)
    
    logger.info(f"Generating recommendations for {len(role_data_map)} roles")
    
    learning_paths = {}
    
    for target_role, (skill_gaps, candidate_course_ids) in role_data_map.items():
        logger.info(f"Processing: {target_role}")
        
        # Update user profile target role
        role_profile = UserProfile(
            user_id=user_profile.user_id,
            current_role=user_profile.current_role,
            target_role=target_role,  # Update with current role being processed
            current_skills=user_profile.current_skills,
            budget=user_profile.budget,
            available_hours_per_week=user_profile.available_hours_per_week,
            preferred_modality=user_profile.preferred_modality,
            preferred_schedule=user_profile.preferred_schedule,
            skillsfuture_eligible=user_profile.skillsfuture_eligible,
            preferred_providers=user_profile.preferred_providers,
            preferred_duration_weeks=user_profile.preferred_duration_weeks
        )
        
        # Load courses from Delta table
        try:
            if candidate_course_ids:
                # Filter to candidate courses only
                course_id_list = ", ".join([f"'{cid}'" for cid in candidate_course_ids])

                query = f"SELECT * FROM {COURSE_TABLE} WHERE coursereferencenumber IN ({course_id_list})"
                df_pandas = execute_sql_query(query)
                candidate_courses = [_load_course_from_row(row) for _, row in df_pandas.iterrows()]

                logger.info(f"Filtered to {len(candidate_courses)} candidate courses")
            else:
                # Use full course catalog
                query = f"SELECT * FROM {COURSE_TABLE}"
                df_pandas = execute_sql_query(query)
                candidate_courses = [_load_course_from_row(row) for _, row in df_pandas.iterrows()]

                logger.warning(f"Using full catalog ({len(candidate_courses)} courses)")
        except Exception as e:
            logger.warning(f"Failed to load courses from Delta table: {e}")
            candidate_courses = []

        # Run recommender
        recommender = CourseRecommender()
        learning_path = recommender.recommend(role_profile, skill_gaps, candidate_courses)
        
        learning_paths[target_role] = learning_path
        
        # Save to file if output directory provided
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            # Sanitize role name for filename
            safe_role_name = target_role.lower().replace(' ', '_').replace('/', '_')
            output_path = os.path.join(output_dir, f"{safe_role_name}.json")
            save_learning_path_to_json(learning_path, output_path)
        
        logger.info(f"Generated {learning_path.total_courses} course recommendations")
        logger.info(f"Total cost: ${learning_path.total_cost:.2f} → ${learning_path.total_cost_after_subsidy:.2f}")
    
    logger.info(f"Completed recommendations for {len(learning_paths)} roles")

    return learning_paths
