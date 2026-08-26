"""
Stage 3 Course Recommendation System - Modularized data_loading.py
===================================================
Part of the SkillUp course recommendation pipeline.
"""

from typing import Any
import logging

from .models import Course

logger = logging.getLogger(__name__)

def _load_course_from_row(row) -> Course:
    """
    Helper function to create a Course object from a Delta table row.
    Maps workspace.default.my_skills_future_course_directory schema to Course dataclass.
    
    Args:
        row: PySpark Row object from my_skills_future_course_directory table
        
    Returns:
        Course object with all fields mapped from table schema
    """
    # Direct field mappings
    course_id = row['coursereferencenumber']
    title = row['coursetitle']
    provider = row['trainingprovideralias']
    provider_uen = row.get('trainingprovideruen')
    
    # Ratings and impact
    rating = float(row['courseratings_stars']) if row['courseratings_stars'] is not None else 0.0
    rating_value = float(row['courseratings_value']) if row.get('courseratings_value') is not None else None
    rating_respondents = int(row['courseratings_noofrespondents']) if row['courseratings_noofrespondents'] is not None else 0
    
    career_impact_stars = float(row['jobcareer_impact_stars']) if row.get('jobcareer_impact_stars') is not None else None
    career_impact_value = float(row['jobcareer_impact_value']) if row.get('jobcareer_impact_value') is not None else None
    career_impact_respondents = int(row['jobcareer_impact_noofrespondents']) if row.get('jobcareer_impact_noofrespondents') is not None else None
    
    # Enrollment and costs
    enrollment_count = int(row['attendancecount']) if row['attendancecount'] is not None else 0
    cost = float(row['full_course_fee']) if row['full_course_fee'] is not None else 0.0
    cost_after_subsidy = float(row['course_fee_after_subsidies']) if row['course_fee_after_subsidies'] is not None else cost
    
    # Duration and commitment
    total_hours = float(row['number_of_hours']) if row['number_of_hours'] is not None else 0.0
    training_commitment = row.get('training_commitment')
    conducted_in = row.get('conducted_in')
    
    # Content fields
    description = row.get('about_this_course')
    skills_covered = row.get('what_you_learn')
    prerequisites = row.get('minimum_entry_requirement')
    
    # Infer modality from conducted_in or training_commitment
    modality = None
    if conducted_in:
        conducted_lower = str(conducted_in).lower()
        if 'online' in conducted_lower:
            modality = 'online'
        elif 'classroom' in conducted_lower or 'onsite' in conducted_lower:
            modality = 'onsite'
        elif 'blended' in conducted_lower or 'hybrid' in conducted_lower:
            modality = 'blended'
    
    # Infer schedule from training_commitment
    schedule = None
    if training_commitment:
        commitment_lower = str(training_commitment).lower()
        if 'weekday' in commitment_lower:
            schedule = 'weekday'
        elif 'weekend' in commitment_lower:
            schedule = 'weekend'
        elif 'evening' in commitment_lower:
            schedule = 'evening'
    
    # Determine SkillsFuture eligibility (has subsidy if cost differs)
    skillsfuture_eligible = (cost > cost_after_subsidy) if cost > 0 else True
    
    return Course(
        course_id=course_id,
        title=title,
        provider=provider,
        provider_uen=provider_uen,
        rating=rating,
        rating_value=rating_value,
        rating_respondents=rating_respondents,
        career_impact_stars=career_impact_stars,
        career_impact_value=career_impact_value,
        career_impact_respondents=career_impact_respondents,
        enrollment_count=enrollment_count,
        cost=cost,
        cost_after_subsidy=cost_after_subsidy,
        total_hours=total_hours,
        training_commitment=training_commitment,
        conducted_in=conducted_in,
        description=description,
        skills_covered=skills_covered,
        prerequisites=prerequisites,
        modality=modality,
        schedule=schedule,
        skillsfuture_eligible=skillsfuture_eligible
    )


# ============================================================================
