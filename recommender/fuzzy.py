"""
Stage 3 Course Recommendation System - Modularized
===================================================
Part of the SkillUp course recommendation pipeline.
"""

from typing import List
import logging

from .models import UserProfile, Course, FuzzyScores, SkillGap, Modality
from .config import RecommenderConfig
from .utils import expand_skill_with_synonyms

logger = logging.getLogger(__name__)


class FuzzyScorer:
    """
    Fuzzy logic system for handling near-miss constraints.
    Provides graceful degradation instead of hard binary filtering.
    """
    
    def __init__(self, config: RecommenderConfig):
        self.config = config
    
    def calculate_fuzzy_scores(
        self,
        course: Course,
        user_profile: UserProfile,
        skill_gaps: List[SkillGap]
    ) -> FuzzyScores:
        """
        Calculate fuzzy membership degrees for all criteria.
        """
        budget_fit = self._budget_membership(course, user_profile)
        time_fit = self._time_membership(course, user_profile)
        relevance = self._relevance_membership(course, skill_gaps)
        modality_fit = self._modality_membership(course, user_profile)
        
        return FuzzyScores(
            budget_fitness=budget_fit,
            time_fitness=time_fit,
            modality_match=modality_fit,
            schedule_match=0.0,
            provider_match=0.0
        )
    
    def _budget_membership(self, course: Course, user_profile: UserProfile) -> float:
        """
        Fuzzy membership for budget constraint.
        
        - 1.0 if cost <= budget
        - Linear decay from 1.0 to 0.0 in tolerance range
        - 0.0 if cost > budget * (1 + tolerance)
        """
        cost = course.cost_after_subsidy
        budget = user_profile.budget
        tolerance = self.config.budget_tolerance
        
        if cost <= budget:
            return 1.0
        
        max_acceptable = budget * (1 + tolerance)
        if cost >= max_acceptable:
            return 0.0
        
        # Linear decay in tolerance range
        return 1.0 - ((cost - budget) / (max_acceptable - budget))
    
    def _time_membership(self, course: Course, user_profile: UserProfile) -> float:
        """
        Fuzzy membership for time availability constraint.
        """
        required = course.hours_per_week
        available = user_profile.available_hours_per_week
        tolerance = self.config.time_tolerance
        
        if required <= available:
            return 1.0
        
        max_acceptable = available * (1 + tolerance)
        if required >= max_acceptable:
            return 0.0
        
        return 1.0 - ((required - available) / (max_acceptable - available))
    
    def _relevance_membership(self, course: Course, skill_gaps: List[SkillGap]) -> float:
        """
        Fuzzy relevance based on skill coverage and priority.
        """
        if not course.skills_covered:
            return 0.0

        skills_text_lower = course.skills_covered.lower()

        matched_priority = 0.0
        total_priority = 0.0

        for gap in skill_gaps:
            total_priority += gap.priority
            skill_variants = expand_skill_with_synonyms(gap.skill)
            if any(v in skills_text_lower for v in skill_variants):
                matched_priority += gap.priority

        if total_priority == 0:
            return 0.0

        return matched_priority / total_priority
    
    def _modality_membership(self, course: Course, user_profile: UserProfile) -> float:
        """
        Fuzzy membership for modality preference.
        """
        if user_profile.preferred_modality == Modality.FLEXIBLE:
            return 1.0
        
        if not course.modality:
            return 0.8  # Unknown modality gets partial credit
        
        modality_lower = course.modality.value.lower() if hasattr(course.modality, 'value') else str(course.modality).lower()
        pref_value = user_profile.preferred_modality.value.lower()
        
        # Exact match
        if pref_value in modality_lower or modality_lower in pref_value:
            return 1.0
        
        # Partial match for blended (between online and onsite)
        if 'blended' in modality_lower or 'hybrid' in modality_lower:
            return 0.7
        
        # Different modality but not zero
        return 0.3


# ============================================================================
