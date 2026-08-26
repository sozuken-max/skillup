"""
Stage 3 Course Recommendation System - Modularized integration.py
===================================================
Part of the SkillUp course recommendation pipeline.
"""

from typing import Dict, List, Tuple, Any, Optional
import json
import logging
import os
import sys
from pathlib import Path

from .models import SkillGap

# ── INTEGRATION ───────────────────────────────────────────────────────────────
from skillgap.skillgap import execute_sql_query

logger = logging.getLogger(__name__)

def parse_stage2_json(stage2_output: Dict[str, Any]) -> Tuple[str, List[SkillGap], List[str]]:
    """
    Parse Stage 2 JSON output (from skillgap.py) into Stage 3 data structures.
    
    This function parses a SINGLE role's output from build_json_output().
    For multi-role outputs (all_role_results list), use parse_stage2_multi_role_json().
    
    Expected Input Format from skillgap.py build_json_output():
    {
        "skill_gaps": {
            "target_role": str,
            "total_gaps": int,
            "gaps": [
                {
                    "skill": str,
                    "category": str,
                    "gap_weight": float (0.0-1.0),
                    "user_skill_proficiency": float (0.0-1.0),
                    "demand_score": float,
                    "peer_score": float,
                    "graph_distance": int,
                    "priority": str ("critical"|"high"|"medium"|"low"),
                    "rationale": str
                }
            ],
            "candidate_courses": [
                {
                    "course_id": str,
                    "covers_skills": [str],
                    "pre_constraint": bool
                }
            ]
        }
    }
    
    Args:
        stage2_output: JSON dict from skillgap.py build_json_output()
        
    Returns:
        (target_role, skill_gaps, candidate_course_ids)
        
    Raises:
        KeyError: If required fields are missing
        ValueError: If data validation fails
    """
    # Validate top-level structure
    if "skill_gaps" not in stage2_output:
        raise KeyError("Missing required field 'skill_gaps' in Stage 2 JSON output")
    
    skill_gaps_data = stage2_output["skill_gaps"]
    
    # Extract target role
    if "target_role" not in skill_gaps_data:
        raise KeyError("Missing required field 'target_role' in skill_gaps")
    target_role = skill_gaps_data["target_role"]
    
    # Parse skill gaps
    if "gaps" not in skill_gaps_data:
        raise KeyError("Missing required field 'gaps' in skill_gaps")
    
    skill_gaps = []
    for i, gap_data in enumerate(skill_gaps_data["gaps"]):
        try:
            # Extract required fields
            skill_name = gap_data.get("skill")
            if not skill_name:
                raise ValueError(f"Gap {i}: Missing 'skill' field")
            
            # Convert priority string to float (0.0-1.0)
            priority_str = gap_data.get("priority", "medium")
            priority_value = _priority_to_float(priority_str)
            
            # Extract proficiency levels
            current_level = float(gap_data.get("user_skill_proficiency", 0.0))
            gap_weight = float(gap_data.get("gap_weight", 0.5))
            
            # Calculate target level from gap weight
            # gap_weight = target - current, so target = current + gap_weight
            target_level = min(1.0, current_level + gap_weight)
            
            # Validate ranges
            if not (0.0 <= current_level <= 1.0):
                raise ValueError(f"Gap {i}: user_skill_proficiency must be in [0.0, 1.0], got {current_level}")
            if not (0.0 <= gap_weight <= 1.0):
                raise ValueError(f"Gap {i}: gap_weight must be in [0.0, 1.0], got {gap_weight}")
            
            gap = SkillGap(
                skill=skill_name,
                priority=priority_value,
                current_level=current_level,
                target_level=target_level,
                gap_size=gap_weight
            )
            skill_gaps.append(gap)
            
        except (KeyError, ValueError, TypeError) as e:
            # Log warning but continue processing other gaps
            logger.warning(f"Skipping gap {i} due to error: {e}")
            continue
    
    if not skill_gaps:
        raise ValueError("No valid skill gaps found in Stage 2 JSON output")
    
    # Extract candidate course IDs
    candidate_courses_data = skill_gaps_data.get("candidate_courses", [])
    candidate_course_ids = []
    
    for course_data in candidate_courses_data:
        course_id = course_data.get("course_id")
        if course_id:
            candidate_course_ids.append(course_id)
        else:
            logger.warning("Skipping candidate course with missing course_id")
    
    # Metadata for debugging
    logger.info(f"Parsed Stage 2 JSON: target_role={target_role}, {len(skill_gaps)} skill gaps, {len(candidate_course_ids)} candidate courses")
    
    return target_role, skill_gaps, candidate_course_ids


def parse_stage2_multi_role_json(
    all_role_results: List[Dict[str, Any]]
) -> Dict[str, Tuple[List[SkillGap], List[str]]]:
    """
    Parse Stage 2 multi-role JSON output (from skillgap.py) into Stage 3 data structures.
    
    This function parses the all_role_results list produced by skillgap.py when 
    analyzing multiple target roles:
    
        all_role_results = []
        for target_role in target_roles:
            prioritised = arbitrate_skill_gaps(...)
            final_json = build_json_output(target_role, prioritised, course_skills_map)
            all_role_results.append(final_json)
    
    Expected Input Format:
    [
        {
            "skill_gaps": {
                "target_role": "Data Engineer",
                "total_gaps": int,
                "gaps": [...],
                "candidate_courses": [...]
            }
        },
        {
            "skill_gaps": {
                "target_role": "Machine Learning Engineer",
                "total_gaps": int,
                "gaps": [...],
                "candidate_courses": [...]
            }
        },
        ...
    ]
    
    Args:
        all_role_results: List of JSON dicts from skillgap.py build_json_output()
        
    Returns:
        Dictionary mapping target_role -> (skill_gaps, candidate_course_ids)
        
    Raises:
        ValueError: If input is not a list or contains invalid data
        
    Example:
        >>> # In skillgap.py:
        >>> all_role_results = []
        >>> for role in ["Data Engineer", "ML Engineer"]:
        ...     final_json = build_json_output(role, gaps, courses)
        ...     all_role_results.append(final_json)
        >>> 
        >>> # In recommender.py:
        >>> role_data = parse_stage2_multi_role_json(all_role_results)
        >>> for role, (gaps, courses) in role_data.items():
        ...     print(f"{role}: {len(gaps)} gaps, {len(courses)} courses")
    """
    if not isinstance(all_role_results, list):
        raise ValueError("all_role_results must be a list of role analysis results")
    
    if not all_role_results:
        raise ValueError("all_role_results is empty - no roles to parse")
    
    role_data_map = {}
    successful_parses = 0
    failed_parses = 0
    
    logger.info(f"Parsing {len(all_role_results)} role results from skillgap.py")
    
    for i, role_result in enumerate(all_role_results):
        try:
            # Parse this role's data using the single-role parser
            target_role, skill_gaps, candidate_course_ids = parse_stage2_json(role_result)
            
            # Store in map
            role_data_map[target_role] = (skill_gaps, candidate_course_ids)
            successful_parses += 1
            
        except (KeyError, ValueError, TypeError) as e:
            failed_parses += 1
            logger.warning(f"Failed to parse role result {i}: {e}")
            continue
    
    logger.info(f"Successfully parsed {successful_parses} role(s), failed {failed_parses}")
    
    if not role_data_map:
        raise ValueError("No valid role results could be parsed from all_role_results")
    
    return role_data_map


def _priority_to_float(priority_str: str) -> float:
    """
    Convert priority string to normalized float value.
    
    Args:
        priority_str: Priority level ("critical"|"high"|"medium"|"low")
        
    Returns:
        Float value in [0.0, 1.0]
    """
    priority_map = {
        "critical": 0.95,
        "high": 0.75,
        "medium": 0.50,
        "low": 0.25
    }
    normalized = priority_str.lower().strip()
    return priority_map.get(normalized, 0.50)


def load_stage2_from_json_file(filepath: str) -> Tuple[str, List[SkillGap], List[str]]:
    """
    Load Stage 2 JSON from file (single role).
    
    Args:
        filepath: Path to JSON file containing skillgap.py output
        
    Returns:
        (target_role, skill_gaps, candidate_course_ids)
        
    Raises:
        FileNotFoundError: If file doesn't exist
        json.JSONDecodeError: If file contains invalid JSON
    """
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
        return parse_stage2_json(data)
    except FileNotFoundError:
        raise FileNotFoundError(f"Stage 2 JSON file not found: {filepath}")
    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(f"Invalid JSON in file {filepath}: {e}", e.doc, e.pos)


def load_stage2_multi_role_from_json_file(
    filepath: str
) -> Dict[str, Tuple[List[SkillGap], List[str]]]:
    """
    Load Stage 2 multi-role JSON from file (all_role_results).
    
    Args:
        filepath: Path to JSON file containing skillgap.py all_role_results
        
    Returns:
        Dictionary mapping target_role -> (skill_gaps, candidate_course_ids)
        
    Raises:
        FileNotFoundError: If file doesn't exist
        json.JSONDecodeError: If file contains invalid JSON
        
    Example:
        >>> # Load multi-role results from file
        >>> role_data = load_stage2_multi_role_from_json_file('all_roles.json')
        >>> for role, (gaps, courses) in role_data.items():
        ...     print(f"{role}: {len(gaps)} gaps")
    """
    try:
        with open(filepath, 'r') as f:
            all_role_results = json.load(f)
        return parse_stage2_multi_role_json(all_role_results)
    except FileNotFoundError:
        raise FileNotFoundError(f"Stage 2 JSON file not found: {filepath}")
    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(f"Invalid JSON in file {filepath}: {e}", e.doc, e.pos)


def load_stage2_from_delta(table_name: str, user_id: str, target_role: str):
    """
    Load Stage 2 JSON from Delta table (single role).
    
    Requires PySpark in Databricks environment.
    
    Args:
        table_name: Fully qualified Delta table name (e.g., "skillsup.gap_analysis.user_analysis_log")
        user_id: User ID to filter by
        target_role: Target role to filter by
        
    Returns:
        (target_role, skill_gaps, candidate_course_ids)
    """
    try:
        query = f"SELECT gap_analysis_json FROM {table_name} WHERE user_id = '{user_id}' AND target_role = '{target_role}' ORDER BY computed_at DESC LIMIT 1"
        df_pandas = execute_sql_query(query)
        
        if len(df_pandas) == 0:
            raise ValueError(f"No records found for user_id={user_id}, target_role={target_role}")
        
        json_str = df_pandas.iloc[0]['gap_analysis_json']
        data = json.loads(json_str)
        return parse_stage2_json(data)
    
    except Exception as e:
        if isinstance(e, ValueError):
            raise e
        raise RuntimeError(f"Data access failed: {e}")


def load_stage2_multi_role_from_delta(
    table_name: str, 
    user_id: str
) -> Dict[str, Tuple[List[SkillGap], List[str]]]:
    """
    Load Stage 2 multi-role JSON from Delta table (all roles for a user).
    
    Requires PySpark in Databricks environment.
    
    Args:
        table_name: Fully qualified Delta table name (e.g., "skillsup.gap_analysis.user_analysis_log")
        user_id: User ID to filter by
        
    Returns:
        Dictionary mapping target_role -> (skill_gaps, candidate_course_ids)
        
    Example:
        >>> # Load all roles for a user from Delta
        >>> role_data = load_stage2_multi_role_from_delta('skillsup.gap_analysis.user_analysis_log', 'user123')
        >>> for role, (gaps, courses) in role_data.items():
        ...     print(f"{role}: {len(gaps)} gaps")
    """
    try:
        query = f"SELECT gap_analysis_json FROM {table_name} WHERE user_id = '{user_id}' ORDER BY computed_at DESC"
        df_pandas = execute_sql_query(query)
        
        if len(df_pandas) == 0:
            raise ValueError(f"No records found for user_id={user_id}")
        
        all_role_results = []
        for _, row in df_pandas.iterrows():
            json_str = row['gap_analysis_json']
            data = json.loads(json_str)
            all_role_results.append(data)
        
        return parse_stage2_multi_role_json(all_role_results)
    
    except Exception as e:
        if isinstance(e, ValueError):
            raise e
        raise RuntimeError(f"Data access failed: {e}")


def load_stage2_from_skillgap_direct(
    user_id: str,
    target_role: str,
    user_skills: List[str],
    skillgap_module_path: Optional[str] = None
) -> Tuple[str, List[SkillGap], List[str]]:
    """
    DIRECT INTEGRATION: Import and call skillgap.py directly to generate Stage 2 output.
    
    NOTE: This is currently a PLACEHOLDER implementation. For production use:
    - Use load_stage2_from_json_file() to load from saved JSON
    - Use load_stage2_from_delta() to load from Delta table
    - Or manually call skillgap functions and pass result to parse_stage2_json()
    
    Args:
        user_id: User identifier
        target_role: Target job role for skill gap analysis
        user_skills: List of user's current skills
        skillgap_module_path: Optional path to skillgap.py directory. 
                             If None, assumes it's in ../skillgap/ relative to this file.
    
    Returns:
        (target_role, skill_gaps, candidate_course_ids)
    
    Raises:
        ImportError: If skillgap module cannot be imported
        RuntimeError: If skillgap functions fail
    
    Example:
        >>> # Placeholder - use load_stage2_from_json_file() instead
        >>> target_role, gaps, course_ids = load_stage2_from_json_file('stage2_output.json')
    """
    try:
        # Try to determine the module directory
        skillgap_dir = None
        
        if skillgap_module_path:
            skillgap_dir = skillgap_module_path
        else:
            # Try multiple methods to find the skillgap directory
            try:
                # Method 1: Use __file__ if available
                current_file = globals().get('__file__')
                if current_file:
                    current_dir = Path(current_file).parent
                    skillgap_dir = str(current_dir.parent / "skillgap")
            except:
                pass
            
            if not skillgap_dir or not Path(skillgap_dir).exists():
                # Method 2: Use current working directory
                cwd = Path(os.getcwd())
                potential_paths = [
                    cwd / "skillgap",
                    cwd / ".." / "skillgap",
                    cwd / "skillup" / "skillgap"
                ]
                for p in potential_paths:
                    if p.exists():
                        skillgap_dir = str(p.resolve())
                        break
        
        if skillgap_dir and Path(skillgap_dir).exists():
            sys.path.insert(0, str(skillgap_dir))
            logger.info(f"Looking for skillgap module in: {skillgap_dir}")
        
        # Try to import skillgap module
        try:
            import skillgap
            logger.info("Successfully imported skillgap module")
            
            # Check if it has the required function
            if hasattr(skillgap, 'build_json_output'):
                logger.info("Found build_json_output function")
                logger.warning("Direct integration requires implementing the full skillgap pipeline.")
            else:
                logger.warning("skillgap module exists but doesn't have 'build_json_output' function")
        
        except ImportError as e:
            logger.warning(f"Cannot import skillgap module: {e}")
        
        # Return placeholder
        logger.info("PLACEHOLDER IMPLEMENTATION - Use load_stage2_from_json_file() or load_stage2_from_delta() instead")
        
        # Return empty placeholder that parse_stage2_json can handle
        stage2_output = {
            "skill_gaps": {
                "target_role": target_role,
                "total_gaps": 0,
                "gaps": [],
                "candidate_courses": []
            }
        }
        
        raise NotImplementedError(
            "load_stage2_from_skillgap_direct() is a placeholder. "
            "Use load_stage2_from_json_file() or load_stage2_from_delta() instead. "
            "See function docstring for details."
        )
        
    except NotImplementedError:
        raise
    except Exception as e:
        raise RuntimeError(f"Failed to load Stage 2 from skillgap.py: {e}")


# ============================================================================
