"""
Stage 3 Course Recommendation System - Modularized
===================================================
Part of the SkillUp course recommendation pipeline.
"""

from typing import List, Tuple
from datetime import datetime, timedelta
import logging

from .models import Course, FuzzyScores, RecommendedCourse, ScoreBreakdown, SkillGap

logger = logging.getLogger(__name__)


class CourseSequencer:
    """
    Generates optimal course sequence considering:
    - Prerequisites
    - Skill progression
    - Timeline optimization
    """
    
    def sequence_courses(
        self,
        ranked_courses: List[Tuple[Course, float, ScoreBreakdown, FuzzyScores]],
        max_courses: int = 10
    ) -> List[RecommendedCourse]:
        """
        Create sequenced learning path with timeline.
        
        Returns: List of RecommendedCourse with sequence_position set
        """
        # Limit to top N courses
        top_courses = ranked_courses[:max_courses]
        
        # Since prerequisites are unstructured text, we'll use simple sequential ordering
        # based on the ranking scores
        sequenced = []
        current_week = 0

        for rank, (course, score, breakdown, fuzzy) in enumerate(top_courses, 1):
            # Calculate timeline position
            start_week = current_week
            end_week = current_week + course.duration_weeks  # Use the property, not raw calc
            position = self._format_timeline(start_week, end_week)

            # --- Generate human-readable reasoning and flags ---
            flags = []
            reasoning_parts = []
            
            # 1. Relevance reasoning
            if breakdown.relevance > 0.7:
                reasoning_parts.append(f"Highly relevant: Directly addresses your primary skill gaps.")
            elif breakdown.relevance > 0.4:
                reasoning_parts.append(f"Good match: Covers several important skills for your target role.")
            else:
                reasoning_parts.append(f"Supplemental: Builds foundational knowledge relevant to your goal.")

            # 2. Constraint/Fuzzy reasoning
            if fuzzy.budget_fitness < 1.0:
                reasoning_parts.append(f"Note: This course is slightly above your budget (${course.cost_after_subsidy:.0f}), but offers high value.")
                flags.append("⚠️ Slightly over budget — consider using SkillsFuture credits")
            
            if fuzzy.time_fitness < 1.0:
                reasoning_parts.append(f"Commitment: Requires {course.hours_per_week:.1f} hrs/week, which is slightly above your preferred availability.")
                flags.append(f"⚠️ Time commitment ({course.hours_per_week:.1f} hrs/week) is a stretch")

            # 3. CBR/Social proof
            if breakdown.cbr > 0.7:
                reasoning_parts.append("Peer Success: Frequently chosen by users with similar career paths.")
            
            # 4. Quality/Rating
            if course.rating >= 4.5:
                reasoning_parts.append(f"High Quality: Top-rated course ({course.rating:.1f}/5.0) with strong learner feedback.")

            # Modality mismatch (this CAN be <1.0 since modality is a soft constraint)
            if fuzzy.modality_match < 0.7:
                course_modality = course.modality or "unknown format"
                flags.append(
                    f"⚠️ Course modality ({course_modality}) differs from your preference"
                )
            elif 0.7 <= fuzzy.modality_match < 1.0:
                flags.append("ℹ️ Blended/hybrid format — partially matches your modality preference")

            # Partial skill coverage
            if breakdown.relevance < 0.4:
                flags.append(
                    "⚠️ Partial skill coverage — addresses some but not all of your skill gaps"
                )

            recommended = RecommendedCourse(
                rank=rank,
                course=course,
                final_score=score,
                score_breakdown=breakdown,
                fuzzy_scores=fuzzy,
                sequence_position=position,
                reasoning=" ".join(reasoning_parts),
                flags=flags,
            )

            sequenced.append(recommended)
            current_week = end_week

        return sequenced
    
    def _format_timeline(self, start_week: int, end_week: int) -> str:
        """Format timeline position (e.g., 'Month 1-2')"""
        start_month = (start_week // 4) + 1
        end_month = ((end_week - 1) // 4) + 1
        
        if start_month == end_month:
            return f"Month {start_month}"
        else:
            return f"Month {start_month}-{end_month}"


# ============================================================================
