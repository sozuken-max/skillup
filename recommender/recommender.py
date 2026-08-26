"""
Stage 3: Course Recommendation System recommender.py
======================================

A constraint-aware, multi-technique hybrid recommender that combines:
- Constraint Satisfaction Problem (CSP) filtering
- Case-Based Reasoning (CBR) for experience-based recommendations
- Fuzzy Logic for near-miss handling
- Weighted Score Fusion for ranking
- Intelligent Sequencing & Timeline Generation

Architecture aligns with docs/stage3_course_recommendation.md

INTEGRATION WITH STAGE 2 (skillgap.py):
---------------------------------------
This module consumes JSON output from skillgap.py's build_json_output() function.
See parse_stage2_json() and load_stage2_from_* functions in integration module.

MULTI-ROLE SUPPORT:
------------------
When skillgap.py processes multiple target roles, it produces all_role_results.
Use parse_stage2_multi_role_json(all_role_results) to parse all roles at once.

BACKWARDS COMPATIBLE DESIGN:
----------------------------
The recommender can accept pre-filtered candidate_courses from skillgap (Option 1)
OR discover courses internally using semantic search (Option 2).
If candidate_courses=None, semantic search is used automatically.
"""

from typing import List, Tuple, Optional
import logging
import warnings

# MLflow integration
try:
    import mlflow
    MLFLOW_AVAILABLE = True
except ImportError:
    MLFLOW_AVAILABLE = False
    warnings.warn("MLflow not available. Set enable_mlflow=False to suppress this warning.")

# Import from modular components
from .models import UserProfile, SkillGap, Course, LearningPath, HistoricalCase
from .config import RecommenderConfig
from .csp import ConstraintSolver
from .cbr import CaseLibrary
from .fuzzy import FuzzyScorer
from .scoring import ScoreFusion
from .sequencing import CourseSequencer
from .validation import validate_user_profile, validate_skill_gaps, validate_courses
from .mlflow_tracking import MLflowTracker
from .catalog import CourseCatalog

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CourseRecommender:
    """
    Main recommendation engine coordinating all components.
    
    This class orchestrates the multi-technique hybrid recommendation workflow:
    1. Input validation
    2. Course discovery (optional semantic search)
    3. CSP filtering
    4. CBR lookup
    5. Fuzzy scoring
    6. Score fusion
    7. Sequencing
    8. Optional MLflow tracking
    """
    
    def __init__(self, config: Optional[RecommenderConfig] = None):
        """
        Initialize the recommender with all component subsystems.
        
        Args:
            config: Optional configuration object. Uses default config if not provided.
        """
        self.config = config or RecommenderConfig()
        self.csp_solver = ConstraintSolver(self.config)
        self.case_library = CaseLibrary(self.config)
        self.fuzzy_scorer = FuzzyScorer(self.config)
        self.score_fusion = ScoreFusion(self.config)
        self.sequencer = CourseSequencer()
        self.mlflow_tracker = MLflowTracker(self.config) if MLFLOW_AVAILABLE else None
        
        # Initialize course catalog for semantic search
        self.catalog = CourseCatalog(table_name=self.config.course_catalog_table)
    
    def recommend(
        self,
        user_profile: UserProfile,
        skill_gaps: List[SkillGap],
        candidate_courses: Optional[List[Course]] = None
    ) -> LearningPath:
        """
        Generate complete learning path recommendation.
        
        Args:
            user_profile: User profile with preferences and constraints
            skill_gaps: List of skill gaps to address
            candidate_courses: Optional pre-filtered courses from skillgap.
                              If None, uses semantic search to discover courses.
            
        Returns:
            LearningPath object with ranked, sequenced course recommendations
            
        Raises:
            ValueError: If input validation fails
        """
        logger.info(f"Starting recommendation for user_id={user_profile.user_id}, target_role={user_profile.target_role}")
        
        if candidate_courses is not None:
            logger.info(f"Input: {len(skill_gaps)} skill gaps, {len(candidate_courses)} pre-filtered candidate courses")
        else:
            logger.info(f"Input: {len(skill_gaps)} skill gaps, will discover courses via semantic search")
        
        # Input validation
        validation_errors = validate_user_profile(user_profile)
        if validation_errors:
            error_msg = f"Invalid user profile: {'; '.join(validation_errors)}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        gap_errors = validate_skill_gaps(skill_gaps)
        if gap_errors:
            error_msg = f"Invalid skill gaps: {'; '.join(gap_errors)}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Only validate courses if they were provided
        if candidate_courses is not None and len(candidate_courses) > 0:
            course_errors = validate_courses(candidate_courses)
            if course_errors:
                error_msg = f"Invalid courses: {'; '.join(course_errors)}"
                logger.error(error_msg)
                raise ValueError(error_msg)
        
        # Execute recommendation with tracking (MLflow and/or UC Table)
        if (self.config.enable_mlflow or self.config.enable_uc_logging) and self.mlflow_tracker:
            return self.mlflow_tracker.track_recommendation(
                user_profile,
                skill_gaps,
                candidate_courses,
                self._recommend_impl
            )
        else:
            if self.config.enable_mlflow and not MLFLOW_AVAILABLE:
                logger.warning("MLflow tracking requested but MLflow not available. Running without tracking.")
            return self._recommend_impl(user_profile, skill_gaps, candidate_courses)
    
    def _recommend_impl(
        self,
        user_profile: UserProfile,
        skill_gaps: List[SkillGap],
        candidate_courses: Optional[List[Course]] = None
    ) -> LearningPath:
        """
        Core recommendation implementation without MLflow tracking.
        
        Executes the full recommendation pipeline:
        0. Course discovery (if candidate_courses is None)
        1. CSP filtering - Remove courses that violate hard constraints
        2. Relevance scoring - Match courses to skill gaps
        3. CBR recommendations - Leverage historical case library
        4. Fuzzy scoring - Handle near-misses and soft matches
        5. Soft constraint scoring - Evaluate preference fit
        6. Score fusion - Combine all scores with configurable weights
        7. Sequencing - Order courses by prerequisites and difficulty
        
        Args:
            user_profile: User profile with preferences and constraints
            skill_gaps: List of skill gaps to address
            candidate_courses: Optional pre-filtered courses. If None, discovers via semantic search.
            
        Returns:
            LearningPath with ranked and sequenced recommendations
        """
        try:
            # Step 0: Course Discovery (if needed)
            logger.debug("Step 0: Course discovery")
            if candidate_courses is None:
                if self.config.use_semantic_search:
                    # Discover courses via semantic search
                    candidate_courses = self.catalog.semantic_search(
                        skill_gaps,
                        top_k=self.config.semantic_search_top_k
                    )
                    logger.info(f"Semantic search retrieved {len(candidate_courses)} candidate courses")
                else:
                    # Load full catalog
                    candidate_courses = self.catalog.load_all_courses()
                    logger.info(f"Using full catalog: {len(candidate_courses)} courses")
            else:
                # Use pre-filtered courses from skillgap
                logger.info(f"Using {len(candidate_courses)} pre-filtered candidate courses from skillgap")
            
            # Step 1: CSP Filtering
            logger.debug("Step 1: CSP filtering")
            valid_courses, violations = self.csp_solver.filter_courses(
                candidate_courses,
                user_profile,
                skill_gaps
            )
            
            if not valid_courses:
                logger.warning(f"No valid courses found for user_id={user_profile.user_id}")
                # Return empty path with violations
                return LearningPath(
                    user_id=user_profile.user_id,
                    courses=[],
                    total_duration_weeks=0,
                    total_cost=0.0,
                    total_cost_after_subsidy=0.0,
                    trade_offs=violations,
                    cbr_insight="No valid courses found matching constraints."
                )
            
            # Step 2: Calculate relevance scores
            logger.debug("Step 2: Calculating relevance scores")
            relevance_scores = {
                course.course_id: self.csp_solver.calculate_relevance(course, skill_gaps)
                for course in valid_courses
            }
            
            # Step 3: CBR recommendations
            logger.debug("Step 3: CBR recommendations")
            similar_cases = self.case_library.find_similar_cases(
                user_profile,
                skill_gaps,
                top_k=5
            )
            cbr_scores = self.case_library.recommend_from_cases(
                similar_cases,
                valid_courses
            )
            
            # Step 4: Fuzzy scoring
            logger.debug("Step 4: Fuzzy scoring")
            fuzzy_scores_map = {
                course.course_id: self.fuzzy_scorer.calculate_fuzzy_scores(
                    course,
                    user_profile,
                    skill_gaps
                )
                for course in valid_courses
            }
            
            # Step 5: Soft constraint scores
            logger.debug("Step 5: Soft constraint scoring")
            soft_constraint_scores = {
                course.course_id: self.csp_solver.soft_constraint_score(course, user_profile)
                for course in valid_courses
            }
            
            # Step 6: Score fusion
            logger.debug("Step 6: Score fusion and ranking")
            ranked_courses = self.score_fusion.calculate_final_scores(
                valid_courses,
                relevance_scores,
                cbr_scores,
                fuzzy_scores_map,
                soft_constraint_scores
            )
            
            # Step 7: Sequencing
            logger.debug("Step 7: Sequencing")
            sequenced_courses = self.sequencer.sequence_courses(
                ranked_courses,
                max_courses=self.config.max_courses
            )
            
            # Calculate totals
            total_duration = sum(rc.course.duration_weeks for rc in sequenced_courses)
            total_cost = sum(rc.course.cost for rc in sequenced_courses)
            total_cost_after_subsidy = sum(rc.course.cost_after_subsidy for rc in sequenced_courses)
            
            # Generate CBR insight
            cbr_insight = self._generate_cbr_insight(similar_cases)
            
            return LearningPath(
                user_id=user_profile.user_id,
                courses=sequenced_courses,
                total_duration_weeks=total_duration,
                total_cost=total_cost,
                total_cost_after_subsidy=total_cost_after_subsidy,
                trade_offs=violations,
                cbr_insight=cbr_insight
            )
        
        except Exception as e:
            logger.exception(f"Recommendation implementation failed: {e}")
            # Return empty path with error
            return LearningPath(
                user_id=user_profile.user_id,
                courses=[],
                total_duration_weeks=0,
                total_cost=0.0,
                total_cost_after_subsidy=0.0,
                trade_offs=[f"System error: {str(e)}"],
                cbr_insight="Recommendation failed due to system error."
            )
    
    def _generate_cbr_insight(
        self,
        similar_cases: List[Tuple[HistoricalCase, float]]
    ) -> str:
        """
        Generate human-readable CBR insight from similar cases.
        
        Args:
            similar_cases: List of (HistoricalCase, similarity_score) tuples
            
        Returns:
            Human-readable string describing the CBR insight
        """
        if not similar_cases:
            return "No similar historical profiles found."
        
        best_case, similarity = similar_cases[0]
        
        return (
            f"Found {len(similar_cases)} similar profiles. "
            f"Top match: {best_case.user_profile.current_role} -> {best_case.user_profile.target_role} "
            f"(similarity: {similarity:.2f}, success rate: {best_case.completion_rate:.1%})"
        )
