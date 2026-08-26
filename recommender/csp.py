"""
Stage 3 Course Recommendation System - Modularized
===================================================
Part of the SkillUp course recommendation pipeline.
"""

from typing import List, Tuple, Optional
import logging

from .models import UserProfile, Course, Modality, Schedule, SkillGap
from .config import RecommenderConfig
from .utils import expand_skill_with_synonyms

logger = logging.getLogger(__name__)


class ConstraintSolver:
    """
    CSP-based course filtering and validation.
    Handles hard constraints (must-satisfy) and soft constraints (preferences).
    """
    
    def __init__(self, config: RecommenderConfig):
        self.config = config
    
    def filter_courses(
        self,
        candidate_courses: List[Course],
        user_profile: UserProfile,
        skill_gaps: List[SkillGap]
    ) -> Tuple[List[Course], List[str]]:
        """
        Filter courses based on hard constraints.
        Returns: (valid_courses, constraint_violations)
        """
        valid_courses = []
        violations = []
        
        logger.debug(f"CSP filtering {len(candidate_courses)} courses")
        
        for course in candidate_courses:
            # Hard constraint 1: Budget (with tolerance)
            max_budget = user_profile.budget * (1 + self.config.budget_tolerance)
            # Use cost_after_subsidy if available, otherwise use total cost
            course_cost = getattr(course, 'cost_after_subsidy', course.cost)
            if course_cost > max_budget:
                violations.append(
                    f"{course.title}: Exceeds budget limit including tolerance (${course_cost:.0f} > ${max_budget:.0f})"
                )
                continue
            
            # Hard constraint 2: Time availability (with tolerance)

            max_time = user_profile.available_hours_per_week * (1 + self.config.time_tolerance)
            if course.hours_per_week > max_time:
                violations.append(
                    f"{course.title}: Insufficient time including tolerance ({course.hours_per_week:.1f} hrs/week > {max_time:.1f} available)"
                )
                continue

            
            # Hard constraint 3: SkillsFuture eligibility
            if user_profile.skillsfuture_eligible and not course.skillsfuture_eligible:
                violations.append(
                    f"{course.title}: Not SkillsFuture eligible"
                )
                continue
            
            # Hard constraint 4: Relevance — threshold-based check
            relevance_score = self.calculate_relevance(course, skill_gaps)
            if relevance_score < self.config.min_relevance_threshold:
                logger.debug(f"Filter out {course.title}: relevance {relevance_score:.2f} < {self.config.min_relevance_threshold:.2f}")
                violations.append(
                    f"{course.title}: Low relevance ({relevance_score:.2f} < threshold {self.config.min_relevance_threshold:.2f})"
                )
                continue
            
            logger.debug(f"Course passed relevance check: {course.title} (score: {relevance_score:.2f})")
            valid_courses.append(course)
        
        logger.info(f"CSP filtered: {len(valid_courses)} valid courses, {len(violations)} violations")
        return valid_courses, violations
    
    def calculate_relevance(self, course: Course, skill_gaps: List[SkillGap]) -> float:
        """
        Calculate how relevant a course is to the skill gaps.
        
        Returns score in [0, 1] based on:
        - Number of gaps addressed
        - Priority of gaps addressed
        - Coverage quality (using simple text matching)
        """
        if not course.skills_covered:
            return 0.0
        
        skills_text_lower = course.skills_covered.lower()

        total_priority = 0.0
        matched_priority = 0.0

        for gap in skill_gaps:
            total_priority += gap.priority
            skill_variants = expand_skill_with_synonyms(gap.skill)
            if any(v in skills_text_lower for v in skill_variants):
                matched_priority += gap.priority

        if total_priority == 0:
            return 0.0

        return matched_priority / total_priority
    
    def soft_constraint_score(self, course: Course, user_profile: UserProfile) -> float:
        """
        Score based on preference match (modality, schedule, provider).
        Returns score in [0, 1].
        """
        score = 0.0
        weight_per_item = 1.0 / 3.0  # 3 soft constraints
        
        # Modality preference (compare string values)
        if user_profile.preferred_modality == Modality.FLEXIBLE:
            score += weight_per_item
        elif course.modality:
            modality_lower = course.modality.value.lower() if hasattr(course.modality, 'value') else str(course.modality).lower()
            pref_value = user_profile.preferred_modality.value.lower()
            if pref_value in modality_lower or modality_lower in pref_value:
                score += weight_per_item
        
        # Schedule preference (compare string values)
        if user_profile.preferred_schedule == Schedule.FLEXIBLE:
            score += weight_per_item
        elif course.schedule:
            schedule_lower = course.schedule.value.lower() if hasattr(course.schedule, 'value') else str(course.schedule).lower()
            pref_value = user_profile.preferred_schedule.value.lower()
            if pref_value in schedule_lower or schedule_lower in pref_value:
                score += weight_per_item
        
        # Provider preference (if specified)
        if not user_profile.preferred_providers or \
           course.provider in user_profile.preferred_providers:
            score += weight_per_item
        
        return score


# ============================================================================
