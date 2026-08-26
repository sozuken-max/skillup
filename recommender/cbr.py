"""
Stage 3 Course Recommendation System - Modularized
===================================================
Part of the SkillUp course recommendation pipeline.
"""

from typing import List, Optional, Tuple, Dict
from collections import defaultdict
import logging

from .models import UserProfile, HistoricalCase, SkillGap, Course
from .utils import jaccard_similarity, semantic_similarity
from .config import RecommenderConfig

logger = logging.getLogger(__name__)


class CaseLibrary:
    """
    Case-based reasoning engine using historical user data.
    Finds similar users and recommends courses that worked for them.
    """
    
    def __init__(self, config: RecommenderConfig):
        self.config = config
        self.cases: List[HistoricalCase] = []
    
    def add_case(self, case: HistoricalCase):
        """Add a historical case to the library"""
        self.cases.append(case)
    
    def find_similar_cases(
        self,
        query_profile: UserProfile,
        query_gaps: List[SkillGap],
        top_k: int = 5
    ) -> List[Tuple[HistoricalCase, float]]:
        """
        Find k most similar historical cases.
        Returns: List of (case, similarity_score) tuples.
        """
        similarities = []
        
        for case in self.cases:
            similarity = self._calculate_case_similarity(
                query_profile,
                query_gaps,
                case.user_profile,
                case.skill_gaps
            )
            similarities.append((case, similarity))
        
        # Sort by similarity descending
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        return similarities[:top_k]
    
    def _calculate_case_similarity(
        self,
        query_profile: UserProfile,
        query_gaps: List[SkillGap],
        case_profile: UserProfile,
        case_gaps: List[SkillGap]
    ) -> float:
        """
        Calculate weighted similarity between query and case.
        """
        # Role similarity (current and target)
        current_role_sim = semantic_similarity(
            query_profile.current_role,
            case_profile.current_role
        )
        target_role_sim = semantic_similarity(
            query_profile.target_role,
            case_profile.target_role
        )
        
        # Skill gap overlap
        query_skill_set = set(g.skill.lower() for g in query_gaps)
        case_skill_set = set(g.skill.lower() for g in case_gaps)
        skill_overlap = jaccard_similarity(query_skill_set, case_skill_set)
        
        # Budget similarity
        budget_diff = abs(query_profile.budget - case_profile.budget)
        budget_max = max(query_profile.budget, case_profile.budget)
        budget_sim = 1.0 - (budget_diff / budget_max) if budget_max > 0 else 1.0
        
        # Time availability similarity
        time_diff = abs(query_profile.available_hours_per_week - case_profile.available_hours_per_week)
        time_max = max(query_profile.available_hours_per_week, case_profile.available_hours_per_week)
        time_sim = 1.0 - (time_diff / time_max) if time_max > 0 else 1.0
        
        # Weighted combination
        similarity = (
            self.config.cbr_weight_current_role * current_role_sim +
            self.config.cbr_weight_target_role * target_role_sim +
            self.config.cbr_weight_skill_overlap * skill_overlap +
            self.config.cbr_weight_budget * budget_sim +
            self.config.cbr_weight_time * time_sim
        )
        
        return similarity
    
    def recommend_from_cases(
        self,
        similar_cases: List[Tuple[HistoricalCase, float]],
        candidate_courses: List[Course]
    ) -> Dict[str, float]:
        """
        Generate course recommendations based on similar cases.
        Returns: Dict mapping course_id -> CBR score [0, 1]
        """
        course_scores = defaultdict(float)
        total_weight = 0.0
        
        for case, similarity in similar_cases:
            # Weight by case similarity and success metrics
            case_weight = similarity * case.completion_rate * (case.satisfaction_score / 5.0)
            
            for course_id in case.completed_courses:
                course_scores[course_id] += case_weight
            
            total_weight += case_weight
        
        # Normalize scores
        if total_weight > 0:
            course_scores = {
                cid: score / total_weight
                for cid, score in course_scores.items()
            }
        
        return dict(course_scores)


# ============================================================================
