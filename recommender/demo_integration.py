"""
Stage 2 → Stage 3 Integration Demo
===================================

Demonstrates the complete pipeline from skillgap.py output to course recommendations.

This script shows:
1. Sample Stage 2 JSON output (from skillgap.py)
2. Parsing Stage 2 data
3. Creating user profile
4. Running recommender
5. Producing Stage 3 JSON output
6. Displaying results

Usage:
    python demo_integration.py
"""

import json
from datetime import datetime
from pathlib import Path

# Import from recommender module
from recommender import (
    UserProfile,
    Course,
    SkillGap,
    Modality,
    Schedule,
    CourseRecommender,
    RecommenderConfig,
    parse_stage2_json,
    serialize_learning_path_to_json,
    save_learning_path_to_json,
    print_learning_path_summary
)


# ============================================================================
# SAMPLE DATA
# ============================================================================

def create_sample_stage2_output():
    """Create sample Stage 2 JSON output (from skillgap.py)"""
    return {
        "skill_gaps": {
            "target_role": "Machine Learning Engineer",
            "total_gaps": 5,
            "gaps": [
                {
                    "skill": "deep learning",
                    "category": "Technical",
                    "gap_weight": 0.75,
                    "user_skill_proficiency": 0.25,
                    "demand_score": 0.85,
                    "peer_score": 0.88,
                    "graph_distance": 2,
                    "priority": "critical",
                    "rationale": "Required in 85% of ML Engineer postings; present in 88% of peer CVs. Core competency for modern ML roles."
                },
                {
                    "skill": "tensorflow",
                    "category": "Technical",
                    "gap_weight": 0.68,
                    "user_skill_proficiency": 0.15,
                    "demand_score": 0.78,
                    "peer_score": 0.82,
                    "graph_distance": 3,
                    "priority": "high",
                    "rationale": "Required in 78% of postings; present in 82% of peer CVs. Industry-standard framework."
                },
                {
                    "skill": "mlops",
                    "category": "Technical",
                    "gap_weight": 0.62,
                    "user_skill_proficiency": 0.10,
                    "demand_score": 0.72,
                    "peer_score": 0.75,
                    "graph_distance": 4,
                    "priority": "high",
                    "rationale": "Growing demand for production ML deployment expertise."
                },
                {
                    "skill": "computer vision",
                    "category": "Technical",
                    "gap_weight": 0.55,
                    "user_skill_proficiency": 0.20,
                    "demand_score": 0.65,
                    "peer_score": 0.68,
                    "graph_distance": 3,
                    "priority": "medium",
                    "rationale": "Required in 65% of postings; specialized skill for CV roles."
                },
                {
                    "skill": "natural language processing",
                    "category": "Technical",
                    "gap_weight": 0.50,
                    "user_skill_proficiency": 0.18,
                    "demand_score": 0.62,
                    "peer_score": 0.65,
                    "graph_distance": 3,
                    "priority": "medium",
                    "rationale": "Required in 62% of postings; specialized skill for NLP roles."
                }
            ],
            "candidate_courses": [
                {
                    "course_id": "SF-DL-001",
                    "covers_skills": ["deep learning", "tensorflow"],
                    "pre_constraint": True
                },
                {
                    "course_id": "SF-CV-002",
                    "covers_skills": ["computer vision", "deep learning"],
                    "pre_constraint": True
                },
                {
                    "course_id": "SF-NLP-003",
                    "covers_skills": ["natural language processing", "tensorflow"],
                    "pre_constraint": True
                },
                {
                    "course_id": "SF-MLOPS-004",
                    "covers_skills": ["mlops", "tensorflow"],
                    "pre_constraint": False
                }
            ]
        }
    }


def create_sample_user_profile():
    """Create sample user profile (from Stage 1)"""
    return UserProfile(
        user_id="user_12345",
        current_role="Software Developer",
        target_role="Machine Learning Engineer",
        current_skills=["Python", "SQL", "Git", "REST APIs"],
        budget=5000.0,  # SGD
        available_hours_per_week=12.0,
        preferred_modality=Modality.ONLINE,
        preferred_schedule=Schedule.EVENING,
        skillsfuture_eligible=True,
        preferred_providers=["National University of Singapore", "Coursera"],
        preferred_duration_weeks=24
    )


def create_sample_course_catalog():
    """Create sample course catalog"""
    return [
        Course(
            course_id="SF-DL-001",
            title="Deep Learning Fundamentals with TensorFlow",
            provider="National University of Singapore",
            total_hours=120.0,  # 12 weeks × 10 hrs/week
            cost=2800.0,
            cost_after_subsidy=840.0,  # 70% subsidy
            modality=Modality.ONLINE,
            schedule=Schedule.EVENING,
            skills_covered="deep learning; tensorflow; neural networks",
            prerequisites="",
            rating=4.8,
            enrollment_count=1250,
            skillsfuture_eligible=True
        ),
        Course(
            course_id="SF-CV-002",
            title="Computer Vision with Deep Learning",
            provider="National University of Singapore",
            total_hours=100.0,  # 10 weeks × 10 hrs/week
            cost=2400.0,
            cost_after_subsidy=720.0,  # 70% subsidy
            modality=Modality.ONLINE,
            schedule=Schedule.EVENING,
            skills_covered="computer vision; deep learning; opencv",
            prerequisites="SF-DL-001",  # Requires DL fundamentals
            rating=4.7,
            enrollment_count=890,
            skillsfuture_eligible=True
        ),
        Course(
            course_id="SF-NLP-003",
            title="Natural Language Processing with Transformers",
            provider="Coursera",
            total_hours=80.0,  # 8 weeks × 10 hrs/week
            cost=2000.0,
            cost_after_subsidy=800.0,  # 60% subsidy
            modality=Modality.ONLINE,
            schedule=Schedule.FLEXIBLE,
            skills_covered="natural language processing; tensorflow; transformers",
            prerequisites="SF-DL-001",
            rating=4.6,
            enrollment_count=750,
            skillsfuture_eligible=True
        ),
        Course(
            course_id="SF-MLOPS-004",
            title="MLOps: Production Machine Learning",
            provider="Coursera",
            total_hours=60.0,  # 6 weeks × 10 hrs/week
            cost=1800.0,
            cost_after_subsidy=720.0,  # 60% subsidy
            modality=Modality.ONLINE,
            schedule=Schedule.WEEKEND,
            skills_covered="mlops; kubernetes; tensorflow; docker",
            prerequisites="SF-DL-001",
            rating=4.5,
            enrollment_count=620,
            skillsfuture_eligible=True
        ),
        Course(
            course_id="GEN-ML-005",
            title="Machine Learning A-Z",
            provider="Udemy",
            total_hours=80.0,  # 8 weeks × 10 hrs/week
            cost=500.0,
            cost_after_subsidy=500.0,  # No subsidy
            modality=Modality.ONLINE,
            schedule=Schedule.FLEXIBLE,
            skills_covered="machine learning; python",
            prerequisites="",
            rating=4.3,
            enrollment_count=5000,
            skillsfuture_eligible=False
        )
    ]


# ============================================================================
# DEMO PIPELINE
# ============================================================================

def run_demo():
    """Run complete integration demo"""
    
    print("="*80)
    print("Stage 2 → Stage 3 Integration Demo")
    print("="*80)
    print()
    
    # ========================================================================
    # STEP 1: Create sample Stage 2 output
    # ========================================================================
    print("STEP 1: Creating sample Stage 2 JSON output (from skillgap.py)")
    print("-" * 80)
    stage2_output = create_sample_stage2_output()
    print(f"✓ Target Role: {stage2_output['skill_gaps']['target_role']}")
    print(f"✓ Total Gaps: {stage2_output['skill_gaps']['total_gaps']}")
    print(f"✓ Candidate Courses: {len(stage2_output['skill_gaps']['candidate_courses'])}")
    print()
    
    # Save Stage 2 output to file for reference
    stage2_file = Path("stage2_output_sample.json")
    with open(stage2_file, 'w') as f:
        json.dump(stage2_output, f, indent=2)
    print(f"✓ Saved Stage 2 output to: {stage2_file}")
    print()
    
    # ========================================================================
    # STEP 2: Parse Stage 2 output
    # ========================================================================
    print("STEP 2: Parsing Stage 2 JSON using integration functions")
    print("-" * 80)
    target_role, skill_gaps, candidate_course_ids = parse_stage2_json(stage2_output)
    
    print(f"✓ Parsed target role: {target_role}")
    print(f"✓ Parsed {len(skill_gaps)} skill gaps:")
    for gap in skill_gaps:
        print(f"  - {gap.skill}: priority={gap.priority:.2f}, gap_size={gap.gap_size:.2f}")
    print(f"✓ Candidate course IDs: {candidate_course_ids}")
    print()
    
    # ========================================================================
    # STEP 3: Create user profile
    # ========================================================================
    print("STEP 3: Creating user profile (from Stage 1)")
    print("-" * 80)
    user_profile = create_sample_user_profile()
    print(f"✓ User ID: {user_profile.user_id}")
    print(f"✓ Current Role: {user_profile.current_role}")
    print(f"✓ Target Role: {user_profile.target_role}")
    print(f"✓ Budget: ${user_profile.budget:.2f} SGD")
    print(f"✓ Available Time: {user_profile.available_hours_per_week} hrs/week")
    print(f"✓ Preferred Modality: {user_profile.preferred_modality.value}")
    print(f"✓ SkillsFuture Eligible: {user_profile.skillsfuture_eligible}")
    print()
    
    # ========================================================================
    # STEP 4: Create course catalog
    # ========================================================================
    print("STEP 4: Loading course catalog")
    print("-" * 80)
    courses = create_sample_course_catalog()
    print(f"✓ Loaded {len(courses)} courses")
    for course in courses:
        subsidy_str = f"({course.subsidy_rate*100:.0f}% subsidy)" if course.subsidy_rate > 0 else "(no subsidy)"
        print(f"  - {course.course_id}: {course.title} - ${course.cost:.0f} {subsidy_str}")
    print()
    
    # ========================================================================
    # STEP 5: Run recommender
    # ========================================================================
    print("STEP 5: Running course recommender (Stage 3)")
    print("-" * 80)
    
    # Create recommender with default config
    config = RecommenderConfig()
    recommender = CourseRecommender(config)
    
    
    # Generate recommendations
    print("⚙ Applying constraint satisfaction...")
    print("⚙ Computing relevance scores...")
    print("⚙ Running case-based reasoning...")
    print("⚙ Applying fuzzy logic...")
    print("⚙ Fusing scores...")
    print("⚙ Sequencing courses...")
    
    learning_path = recommender.recommend(user_profile, skill_gaps, courses)
    
    print(f"✓ Generated learning path with {learning_path.total_courses} courses")
    print()
    
    # ========================================================================
    # STEP 6: Display results
    # ========================================================================
    print("STEP 6: Learning Path Summary")
    print("-" * 80)
    print_learning_path_summary(learning_path)
    print()
    
    # ========================================================================
    # STEP 7: Generate Stage 3 JSON output
    # ========================================================================
    print("STEP 7: Generating Stage 3 JSON output")
    print("-" * 80)
    
    # Convert to JSON
    stage3_json = serialize_learning_path_to_json(learning_path)
    
    # Save to file
    stage3_file = Path("stage3_output_sample.json")
    save_learning_path_to_json(learning_path, str(stage3_file))
    
    print(f"✓ Generated Stage 3 JSON output")
    print(f"✓ Saved to: {stage3_file}")
    print()
    
    # Display summary of JSON structure
    print("Stage 3 JSON Structure:")
    print(f"  - user_id: {stage3_json['user_id']}")
    print(f"  - generated_at: {stage3_json['generated_at']}")
    print(f"  - summary:")
    for key, value in stage3_json['summary'].items():
        print(f"      {key}: {value}")
    print(f"  - recommended_courses: {len(stage3_json['recommended_courses'])} courses")
    print(f"  - cbr_insight: {stage3_json['cbr_insight'][:80]}...")
    print()
    
    # ========================================================================
    # STEP 8: Display detailed recommendations
    # ========================================================================
    print("STEP 8: Detailed Course Recommendations")
    print("-" * 80)
    
    for rec_course in learning_path.courses:
        print(f"\n{rec_course.rank}. {rec_course.course.title}")
        print(f"   Provider: {rec_course.course.provider}")
        print(f"   Duration: {rec_course.course.duration_weeks:.1f} weeks ({rec_course.course.total_hours:.0f} hours)")
        print(f"   Cost: ${rec_course.course.cost:.2f} → ${rec_course.course.cost_after_subsidy:.2f} (after subsidy)")
        print(f"   Skills: {rec_course.course.skills_covered}")
        print(f"   Final Score: {rec_course.final_score:.3f}")
        print(f"   Sequence: {rec_course.sequence_position}")
        if rec_course.flags:
            print(f"   ⚠ Warnings: {', '.join(rec_course.flags)}")
    
    print()
    print("="*80)
    print("✓ Integration Demo Complete!")
    print("="*80)
    print()
    print(f"Generated Files:")
    print(f"  - {stage2_file} (Stage 2 JSON input)")
    print(f"  - {stage3_file} (Stage 3 JSON output)")
    print()


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    run_demo()
