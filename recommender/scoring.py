"""
Stage 3 Course Recommendation System - Modularized
===================================================
Part of the SkillUp course recommendation pipeline.
"""

from typing import List, Optional, Tuple, Dict
import logging

from .models import Course, FuzzyScores, ScoreBreakdown, SkillGap
from .config import RecommenderConfig
from .utils import normalize_score

logger = logging.getLogger(__name__)


class ScoreFusion:
    """
    Combines multiple scoring dimensions into final ranking.
    Uses weighted linear combination with normalization.
    """
    
    def __init__(self, config: RecommenderConfig):
        self.config = config
    
    def calculate_final_scores(
        self,
        courses: List[Course],
        relevance_scores: Dict[str, float],
        cbr_scores: Dict[str, float],
        fuzzy_scores_map: Dict[str, FuzzyScores],
        soft_constraint_scores: Dict[str, float]
    ) -> List[Tuple[Course, float, ScoreBreakdown, FuzzyScores]]:
        """
        Calculate final scores for all courses.
        
        Returns: List of (course, final_score, score_breakdown, fuzzy_scores) tuples
        """
        results = []

        # Pre-compute max_enrollment once (avoid O(n²) max() inside loop)
        max_enrollment = max((c.enrollment_count for c in courses), default=1) or 1

        for course in courses:
            cid = course.course_id

            # Component scores
            relevance = relevance_scores.get(cid, 0.0)
            rating_norm = normalize_score(course.rating, 0.0, 5.0)
            constraint_fit = soft_constraint_scores.get(cid, 0.5)
            cbr_score = cbr_scores.get(cid, 0.5)  # Default 0.5 if no CBR data

            # Popularity (enrollment-based)
            popularity = normalize_score(course.enrollment_count, 0, max_enrollment)
            
            # Weighted fusion
            final_score = (
                self.config.weight_relevance * relevance +
                self.config.weight_rating * rating_norm +
                self.config.weight_constraints * constraint_fit +
                self.config.weight_cbr * cbr_score +
                self.config.weight_popularity * popularity
            )
            
            breakdown = ScoreBreakdown(
                relevance=relevance,
                rating=rating_norm,
                constraint_fit=constraint_fit,
                cbr=cbr_score,
                popularity=popularity
            )
            
            fuzzy = fuzzy_scores_map[cid]
            
            results.append((course, final_score, breakdown, fuzzy))
        
        # Sort by final score descending
        results.sort(key=lambda x: x[1], reverse=True)
        
        return results


# ============================================================================
