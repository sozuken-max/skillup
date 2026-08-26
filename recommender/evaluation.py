"""
Stage 3 Course Recommendation System - Modularized
===================================================
Part of the SkillUp course recommendation pipeline.
"""

from typing import List, Dict
import logging

from .models import LearningPath, SkillGap, RecommendedCourse
from .utils import expand_skill_with_synonyms

logger = logging.getLogger(__name__)

def calculate_skill_gap_coverage(learning_path: LearningPath, skill_gaps: List[SkillGap]) -> float:
    """
    Calculate percentage of skill gaps covered by recommendations.
    
    Args:
        learning_path: Generated learning path with recommended courses
        skill_gaps: List of skill gaps to address
        
    Returns:
        Coverage ratio [0.0, 1.0] representing fraction of gaps covered
    """
    if not skill_gaps:
        return 1.0
    
    covered_skills = set()
    for rc in learning_path.courses:
        if rc.course.skills_covered:
            skills_text = rc.course.skills_covered.lower()
            for gap in skill_gaps:
                skill_variants = expand_skill_with_synonyms(gap.skill)
                if any(v in skills_text for v in skill_variants):
                    covered_skills.add(gap.skill.lower())
    
    coverage = len(covered_skills) / len(skill_gaps)
    logger.debug(f"Skill gap coverage: {coverage:.2%} ({len(covered_skills)}/{len(skill_gaps)} skills)")
    return coverage


def calculate_weighted_skill_coverage(learning_path: LearningPath, skill_gaps: List[SkillGap]) -> float:
    """
    Calculate priority-weighted skill coverage.
    
    Accounts for skill gap priorities - covering high-priority gaps is more valuable
    than covering low-priority gaps.
    
    Args:
        learning_path: Generated learning path with recommended courses
        skill_gaps: List of skill gaps with priorities
        
    Returns:
        Weighted coverage ratio [0.0, 1.0]
    """
    if not skill_gaps:
        return 1.0
    
    total_priority = sum(gap.priority for gap in skill_gaps)
    if total_priority == 0:
        return 0.0
    
    covered_priority = 0.0
    
    for gap in skill_gaps:
        skill_variants = expand_skill_with_synonyms(gap.skill)
        gap_covered = False
        for rc in learning_path.courses:
            if rc.course.skills_covered:
                skills_text = rc.course.skills_covered.lower()
                if any(v in skills_text for v in skill_variants):
                    gap_covered = True
                    break
        
        if gap_covered:
            covered_priority += gap.priority
    
    weighted_coverage = covered_priority / total_priority
    logger.debug(f"Weighted skill coverage: {weighted_coverage:.2%} (priority-adjusted)")
    return weighted_coverage


def calculate_recommendation_diversity(learning_path: LearningPath) -> Dict[str, float]:
    """
    Calculate diversity metrics for recommendations.
    
    Measures:
    - Provider diversity: Ratio of unique providers to total courses
    - Modality diversity: Ratio of unique modalities to total courses
    - Average course rating: Mean quality score
    
    Args:
        learning_path: Generated learning path with recommended courses
        
    Returns:
        Dictionary with diversity metrics
    """
    if not learning_path.courses:
        return {
            "provider_diversity": 0.0,
            "modality_diversity": 0.0,
            "avg_course_rating": 0.0
        }
    
    providers = set(rc.course.provider for rc in learning_path.courses)
    modalities = set(rc.course.modality for rc in learning_path.courses if rc.course.modality)
    ratings = [rc.course.rating for rc in learning_path.courses if rc.course.rating > 0]
    
    provider_diversity = len(providers) / len(learning_path.courses)
    modality_diversity = len(modalities) / len(learning_path.courses) if modalities else 0.0
    avg_rating = sum(ratings) / len(ratings) if ratings else 0.0
    
    metrics = {
        "provider_diversity": provider_diversity,
        "modality_diversity": modality_diversity,
        "avg_course_rating": avg_rating
    }
    
    logger.debug(f"Diversity metrics: {metrics}")
    return metrics


def calculate_cost_efficiency(learning_path: LearningPath, skill_gaps: List[SkillGap]) -> float:
    """
    Calculate cost efficiency: skills covered per $1000 SGD.
    
    Measures value-for-money by dividing weighted skill coverage by cost.
    
    Args:
        learning_path: Generated learning path with recommended courses
        skill_gaps: List of skill gaps to address
        
    Returns:
        Skills per $1000 SGD (higher is better)
    """
    coverage = calculate_weighted_skill_coverage(learning_path, skill_gaps)
    cost = learning_path.total_cost_after_subsidy
    
    if cost == 0:
        return 0.0
    
    # Skills covered per $1000 SGD
    efficiency = (coverage * len(skill_gaps)) / (cost / 1000.0)
    
    logger.debug(f"Cost efficiency: {efficiency:.2f} skills/$1000")
    return efficiency


