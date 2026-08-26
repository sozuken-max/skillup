"""
Stage 3 Course Recommendation System - Modularized
===================================================
Part of the SkillUp course recommendation pipeline.
"""

from typing import List, Optional, Union
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import math
import logging

logger = logging.getLogger(__name__)

# ===========================================================================
# DATA STRUCTURES & SCHEMAS
# ============================================================================

class Modality(Enum):
    """Course delivery modalities"""
    ONLINE = "online"
    ONSITE = "onsite"
    BLENDED = "blended"
    FLEXIBLE = "flexible"


class Schedule(Enum):
    """Course schedule preferences"""
    WEEKDAY = "weekday"
    WEEKEND = "weekend"
    EVENING = "evening"
    FLEXIBLE = "flexible"


@dataclass
class UserProfile:
    """User profile from Stage 1"""
    user_id: str
    current_role: str
    target_role: str
    current_skills: List[str]
    budget: float  # SGD
    available_hours_per_week: float
    preferred_modality: Modality
    preferred_schedule: Schedule
    skillsfuture_eligible: bool = True
    preferred_providers: List[str] = field(default_factory=list)
    preferred_duration_weeks: Optional[int] = None


@dataclass
class SkillGap:
    """Prioritized skill gap from Stage 2"""
    skill: str
    priority: float  # 0.0 - 1.0
    current_level: float  # 0.0 - 1.0
    target_level: float  # 0.0 - 1.0
    gap_size: float  # target - current


@dataclass
class Course:
    """
    Course metadata matching workspace.default.my_skills_future_course_directory schema.
    
    Field mapping from Delta table:
    - coursereferencenumber -> course_id (primary key)
    - coursetitle -> title
    - trainingprovideruen -> provider_uen
    - trainingprovideralias -> provider
    - courseratings_value -> rating_value
    - courseratings_stars -> rating
    - courseratings_noofrespondents -> rating_respondents
    - jobcareer_impact_value -> career_impact_value
    - jobcareer_impact_stars -> career_impact_stars
    - jobcareer_impact_noofrespondents -> career_impact_respondents
    - attendancecount -> enrollment_count
    - full_course_fee -> cost
    - course_fee_after_subsidies -> cost_after_subsidy
    - number_of_hours -> total_hours
    - training_commitment -> training_commitment
    - conducted_in -> conducted_in
    - about_this_course -> description
    - what_you_learn -> skills_covered (unstructured text description)
    - minimum_entry_requirement -> prerequisites (unstructured text description)
    """
    # Primary identifiers
    course_id: str  # coursereferencenumber
    title: str  # coursetitle
    
    # Provider information
    provider: str  # trainingprovideralias
    provider_uen: Optional[str] = None  # trainingprovideruen
    
    # Course ratings
    rating: float = 0.0  # courseratings_stars (0.0-5.0)
    rating_value: Optional[float] = None  # courseratings_value
    rating_respondents: int = 0  # courseratings_noofrespondents
    
    # Career impact metrics
    career_impact_stars: Optional[float] = None  # jobcareer_impact_stars
    career_impact_value: Optional[float] = None  # jobcareer_impact_value
    career_impact_respondents: Optional[int] = None  # jobcareer_impact_noofrespondents
    
    # Enrollment and popularity
    enrollment_count: int = 0  # attendancecount
    
    # Cost and subsidies
    cost: float = 0.0  # full_course_fee (SGD before subsidy)
    cost_after_subsidy: float = 0.0  # course_fee_after_subsidies (SGD after subsidy)
    
    # Duration and commitment
    total_hours: float = 0.0  # number_of_hours
    training_commitment: Optional[str] = None  # training_commitment (e.g., "Full-time", "Part-time")
    
    # Location and format
    conducted_in: Optional[str] = None  # conducted_in (location/format)
    
    # Course content (unstructured text)
    description: Optional[str] = None  # about_this_course
    skills_covered: Optional[str] = None  # what_you_learn (unstructured description)
    prerequisites: Optional[str] = None  # minimum_entry_requirement (unstructured description)
    
    # Inferred fields
    modality: Optional[Union[str, Modality]] = None  # Inferred from training_commitment or conducted_in
    schedule: Optional[Union[str, Schedule]] = None  # Inferred from training_commitment
    skillsfuture_eligible: bool = True  # Assume true if subsidy exists
    
    @property
    def subsidy_rate(self) -> float:
        """Calculate subsidy rate from cost and subsidized cost"""
        if self.cost > 0:
            return (self.cost - self.cost_after_subsidy) / self.cost
        return 0.0
    
    @property
    def duration_weeks(self) -> int:
        """Calculate duration in weeks from total hours (assumes 10 hours/week)"""
        if self.total_hours > 0:
            return max(1, int(math.ceil(self.total_hours / 10.0)))
        return 1
    
    @property
    def hours_per_week(self) -> float:
        """Estimate weekly time commitment based on training commitment"""
        if self.training_commitment:
            commitment_lower = self.training_commitment.lower()
            if 'full-time' in commitment_lower or 'full time' in commitment_lower:
                return 30.0  # Full-time: ~30 hours/week
            elif 'part-time' in commitment_lower or 'part time' in commitment_lower:
                return 10.0  # Part-time: ~10 hours/week
        
        # Fallback: calculate from duration if available
        if self.total_hours > 0 and self.duration_weeks > 0:
            return self.total_hours / self.duration_weeks
        
        return 10.0
    
    def get_searchable_text(self) -> str:
        """
        Get concatenated text for semantic search.
        Combines title, description, skills_covered, and provider into a single searchable string.
        """
        parts = [
            self.title,
            self.description or "",
            self.skills_covered or "",
            self.provider
        ]
        return " ".join(p for p in parts if p)


class FuzzyScores:
    """Fuzzy logic degree-of-satisfaction scores"""

    def __init__(self, **kwargs):
        """Support both naming conventions for backwards compatibility"""
        # Map old names to new names if provided
        if 'budget_score' in kwargs:
            self.budget_fitness = kwargs.pop('budget_score')
        elif 'budget_fitness' in kwargs:
            self.budget_fitness = kwargs.pop('budget_fitness')
        else:
            self.budget_fitness = kwargs.get('budget_fitness', 0.0)

        if 'time_score' in kwargs:
            self.time_fitness = kwargs.pop('time_score')
        elif 'time_fitness' in kwargs:
            self.time_fitness = kwargs.pop('time_fitness')
        else:
            self.time_fitness = kwargs.get('time_fitness', 0.0)

        if 'modality_score' in kwargs:
            self.modality_match = kwargs.pop('modality_score')
        elif 'modality_match' in kwargs:
            self.modality_match = kwargs.pop('modality_match')
        else:
            self.modality_match = kwargs.get('modality_match', 0.0)

        if 'schedule_score' in kwargs:
            self.schedule_match = kwargs.pop('schedule_score')
        elif 'schedule_match' in kwargs:
            self.schedule_match = kwargs.pop('schedule_match')
        else:
            self.schedule_match = kwargs.get('schedule_match', 0.0)

        if 'provider_score' in kwargs:
            self.provider_match = kwargs.pop('provider_score')
        elif 'provider_match' in kwargs:
            self.provider_match = kwargs.pop('provider_match')
        else:
            self.provider_match = kwargs.get('provider_match', 0.0)

        # Handle relevance (new field)
        self.relevance = kwargs.get('relevance', 0.0)

        # Ignore these old names if provided
        if 'total_fuzzy_score' in kwargs:
            kwargs.pop('total_fuzzy_score')


@dataclass
class ScoreBreakdown:
    """Explainable score components"""
    relevance: float  # How well it fills skill gaps
    rating: float  # Course quality (learner ratings)
    constraint_fit: float  # Budget/time/modality fit
    cbr: float  # Similar users' success
    popularity: float  # Market validation


@dataclass
class RecommendedCourse:
    """Course recommendation with scores and metadata"""
    rank: int
    course: Course
    final_score: float
    score_breakdown: ScoreBreakdown
    fuzzy_scores: FuzzyScores
    sequence_position: str  # e.g., "Month 1-2"
    reasoning: str = ""  # Human-readable explanation of why this course was picked
    flags: List[str] = field(default_factory=list)


@dataclass
class LearningPath:
    """Complete learning path recommendation"""
    user_id: str
    courses: List[RecommendedCourse]
    total_duration_weeks: int
    total_cost: float
    total_cost_after_subsidy: float
    trade_offs: List[str]
    cbr_insight: str
    generated_at: datetime = field(default_factory=datetime.now)
    
    @property
    def total_courses(self) -> int:
        return len(self.courses)


@dataclass
class HistoricalCase:
    """Case for CBR case library"""
    case_id: str
    user_profile: UserProfile
    skill_gaps: List[SkillGap]
    completed_courses: List[str]  # Course IDs
    completion_rate: float  # 0.0 - 1.0
    satisfaction_score: float  # 0.0 - 5.0
    total_duration_weeks: int

