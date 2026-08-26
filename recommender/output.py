"""
Output Formatting Utilities
============================

Functions for pretty-printing and displaying recommendation results
to the console or other output destinations.
"""

from .models import LearningPath


def print_learning_path_summary(learning_path: LearningPath):
    """
    Pretty-print learning path summary to console.
    
    Args:
        learning_path: LearningPath object to display
    """
    print("=" * 70)
    print("STAGE 3: COURSE RECOMMENDATION SYSTEM - LEARNING PATH")
    print("=" * 70)
    print()
    print(f"User ID: {learning_path.user_id}")
    print(f"Generated: {learning_path.generated_at.strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    print("📊 SUMMARY")
    print(f"  • Total Courses: {learning_path.total_courses}")
    print(f"  • Total Duration: {learning_path.total_duration_weeks} weeks (~{learning_path.total_duration_weeks//4} months)")
    print(f"  • Total Cost: ${learning_path.total_cost:.2f} SGD")
    print(f"  • Cost After Subsidy: ${learning_path.total_cost_after_subsidy:.2f} SGD")
    savings = learning_path.total_cost - learning_path.total_cost_after_subsidy
    savings_pct = (savings / learning_path.total_cost * 100) if learning_path.total_cost > 0 else 0
    print(f"  • Total Savings: ${savings:.2f} SGD ({savings_pct:.1f}%)")
    print()
    
    print("💡 CBR INSIGHT")
    print(f"  {learning_path.cbr_insight}")
    print()
    
    print("📚 RECOMMENDED COURSES")
    print("=" * 70)
    print()
    
    for rc in learning_path.courses:
        print(f"{rc.rank}. {rc.course.title}")
        print(f"   Provider: {rc.course.provider}")
        print(f"   Timeline: {rc.sequence_position}")
        print(f"   Duration: {rc.course.duration_weeks} weeks")
        print(f"   Cost: ${rc.course.cost:.2f} → ${rc.course.cost_after_subsidy:.2f} (save ${rc.course.cost - rc.course.cost_after_subsidy:.2f})")
        print(f"   Modality: {rc.course.modality or 'Flexible'} | Schedule: {rc.course.schedule or 'Flexible'}")
        print(f"   Rating: {rc.course.rating}/5.0 ⭐ ({rc.course.enrollment_count} enrolled)")
        
        # Display skills as text (not a list)
        skills_display = rc.course.skills_covered[:100] + "..." if rc.course.skills_covered and len(rc.course.skills_covered) > 100 else rc.course.skills_covered or "N/A"
        print(f"   Skills: {skills_display}")
        
        # Display prerequisites as text (not a list)
        if rc.course.prerequisites:
            prereq_display = rc.course.prerequisites[:100] + "..." if len(rc.course.prerequisites) > 100 else rc.course.prerequisites
            print(f"   Prerequisites: {prereq_display}")
        print()
        
        print(f"   📈 SCORES")
        print(f"      Final Score: {rc.final_score:.3f}")
        print(f"      ├─ Relevance: {rc.score_breakdown.relevance:.3f}")
        print(f"      ├─ Rating: {rc.score_breakdown.rating:.3f}")
        print(f"      ├─ Constraints: {rc.score_breakdown.constraint_fit:.3f}")
        print(f"      ├─ CBR: {rc.score_breakdown.cbr:.3f}")
        print(f"      └─ Popularity: {rc.score_breakdown.popularity:.3f}")
        print("   " + "-" * 68)
        print()
    
    print("=" * 70)
    print()
