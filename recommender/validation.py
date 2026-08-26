"""
Stage 3 Course Recommendation System - Modularized
===================================================
Part of the SkillUp course recommendation pipeline.
"""

from typing import List
import logging

from .models import UserProfile, SkillGap, Course

logger = logging.getLogger(__name__)

def validate_user_profile(profile: UserProfile) -> List[str]:
    """
    Validate user profile and return list of errors.
    
    Args:
        profile: UserProfile to validate
        
    Returns:
        List of validation error messages (empty if valid)
    """
    errors = []
    
    if not profile.user_id:
        errors.append("Missing user_id")
    
    if profile.budget <= 0:
        errors.append(f"Invalid budget: {profile.budget} (must be > 0)")
    
    if profile.available_hours_per_week <= 0:
        errors.append(f"Invalid hours per week: {profile.available_hours_per_week} (must be > 0)")
    
    if not profile.current_role:
        errors.append("Missing current_role")
    
    if not profile.target_role:
        errors.append("Missing target_role")
    
    if not isinstance(profile.current_skills, list):
        errors.append("current_skills must be a list")
    
    return errors


def validate_skill_gaps(skill_gaps: List[SkillGap]) -> List[str]:
    """
    Validate skill gaps and return list of errors.
    
    Args:
        skill_gaps: List of SkillGap objects to validate
        
    Returns:
        List of validation error messages (empty if valid)
    """
    errors = []
    
    if not skill_gaps:
        errors.append("No skill gaps provided")
        return errors
    
    for i, gap in enumerate(skill_gaps):
        if not gap.skill:
            errors.append(f"Gap {i}: Missing skill name")
        
        if not (0.0 <= gap.priority <= 1.0):
            errors.append(f"Gap {i} ({gap.skill}): Invalid priority {gap.priority} (must be in [0.0, 1.0])")
        
        if not (0.0 <= gap.current_level <= 1.0):
            errors.append(f"Gap {i} ({gap.skill}): Invalid current_level {gap.current_level} (must be in [0.0, 1.0])")
        
        if not (0.0 <= gap.target_level <= 1.0):
            errors.append(f"Gap {i} ({gap.skill}): Invalid target_level {gap.target_level} (must be in [0.0, 1.0])")
    
    return errors


def validate_courses(courses: List[Course]) -> List[str]:
    """
    Validate course list and return list of errors.
    
    Args:
        courses: List of Course objects to validate
        
    Returns:
        List of validation error messages (empty if valid)
    """
    errors = []
    
    if not courses:
        errors.append("No courses provided")
        return errors
    
    course_ids = set()
    for i, course in enumerate(courses):
        if not course.course_id:
            errors.append(f"Course {i}: Missing course_id")
        elif course.course_id in course_ids:
            errors.append(f"Course {i}: Duplicate course_id {course.course_id}")
        else:
            course_ids.add(course.course_id)
        
        if not course.title:
            errors.append(f"Course {i} ({course.course_id}): Missing title")
        
        if course.cost < 0:
            errors.append(f"Course {i} ({course.course_id}): Invalid cost {course.cost} (must be >= 0)")
    
    return errors


