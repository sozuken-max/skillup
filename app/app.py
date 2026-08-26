import streamlit as st
import openai
from openai import OpenAI
import json
import os
import random
import time
import datetime
import re
import math
import sys


# --- TEXT CLEANING UTILITY ---
def clean_text(raw_html):
    """Clean text by fixing encoding issues and removing HTML tags."""
    if not raw_html:
        return ""
    
    # 1. Fix common encoding issues manually
    text = str(raw_html)
    text = text.replace('â€¢', '•')
    text = text.replace('â€™', "'")
    text = text.replace('â€œ', '"')
    text = text.replace('â€', '"')
    text = text.replace('â€"', '–')
    text = text.replace('â€"', '—')
    text = text.replace('Â', '')
    
    # 2. Remove HTML tags
    text = re.sub(r'<[^>]+>', ' ', text)
    
    # 3. Collapse all whitespace and newlines into single spaces
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text

# --- CV PARSING UTILITIES ---
def parse_docx_cv(uploaded_file):
    """Extract text from uploaded DOCX CV file."""
    try:
        import docx
        doc = docx.Document(uploaded_file)
        text = "\n".join([para.text for para in doc.paragraphs])
        return text
    except ImportError:
        st.warning("⚠️ python-docx not installed. Cannot parse DOCX.")
        return None
    except Exception as e:
        st.warning(f"⚠️ Error parsing DOCX: {e}")
        return None

def parse_pdf_cv(uploaded_file):
    """Extract text from uploaded PDF CV file."""
    try:
        import fitz  # PyMuPDF
        
        # Read the uploaded file bytes
        pdf_bytes = uploaded_file.read()
        
        # Open PDF from bytes
        pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
        
        # Extract text from all pages
        text = ""
        for page_num in range(pdf_document.page_count):
            page = pdf_document[page_num]
            text += page.get_text()
        
        pdf_document.close()
        return text
    except ImportError:
        st.warning("⚠️ PyMuPDF (fitz) not installed. Cannot parse PDF.")
        return None
    except Exception as e:
        st.warning(f"⚠️ Error parsing PDF: {e}")
        return None

def extract_role_and_skills_from_cv(cv_text):
    """
    Use LLM to extract current role and top 10 skills from CV text.
    Returns: (current_role: str, skills_list: list[str])
    """
    if not cv_text or not cv_text.strip():
        return None, []
    
    try:
        client = get_openai_client()
        
        system_prompt = """You are an expert CV/resume parser for career analysis.
Extract the following information from the CV:
1. The most recent job title/role (just the title, no company name)
2. Top 10 most relevant technical and professional skills from the 2 most recent roles

Return your response as a JSON object with this exact structure:
{
  "current_role": "Job Title Here",
  "skills": ["Skill 1", "Skill 2", ..., "Skill 10"]
}

Focus on:
- Technical skills (programming languages, tools, frameworks)
- Domain skills (data analysis, project management, etc.)
- Certifications and specialized knowledge
- Avoid soft skills like "communication" or "teamwork" unless specifically technical

If the CV is unclear or missing information, make your best inference."""

        response = client.chat.completions.create(
            model=CONFIG_LLM_MODEL,
            max_tokens=500,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Extract current role and top 10 skills from this CV:\n\n{cv_text[:4000]}"}  # Limit to first 4000 chars
            ]
        )
        
        result = response.choices[0].message.content.strip()
        
        # Parse JSON response
        # Remove markdown code blocks if present
        if result.startswith("```"):
            result = result.split("```")[1]
            if result.startswith("json"):
                result = result[4:]
            result = result.strip()
        
        data = json.loads(result)
        current_role = data.get("current_role", "")
        skills = data.get("skills", [])[:10]  # Ensure max 10 skills
        
        return current_role, skills
        
    except Exception as e:
        st.warning(f"⚠️ Error extracting info from CV: {e}")
        return None, []

def fetch_career_recommendation(courses, skill_levels, gap_matrix, current_role, aspired_role):
    """
    Sends course list, skill levels, and skill gaps to LLM.
    Returns a career advisor recommendation string.
    """
    if not courses:
        return None
    try:
        client = get_openai_client()

        course_payload = [
            {
                "course_id": c.get("course_id", "N/A"),
                "title": c["title"],
                "what_you_learn": c.get("description", "N/A")
            }
            for c in courses[:10]
        ]

        gap_payload = [
            {"skill": g["skill"], "gap_percentage": g["gap_percentage"]}
            for g in gap_matrix
        ]

        user_message = f"""
Current Role: {current_role}
Target Role: {aspired_role}

Current Skills (self-declared):
{json.dumps(skill_levels, indent=2)}

Top Skill Gaps (%):
{json.dumps(gap_payload, indent=2)}

Recommended Courses Available:
{json.dumps(course_payload, indent=2)}
"""

        response = client.chat.completions.create(
            model=CONFIG_LLM_MODEL,
            max_tokens=400,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a concise career advisor. Given a user's current role, target role, "
                        "existing skills, skill gaps, and a list of available courses, provide: "
                        "1) A brief overall assessment (2-3 sentences). "
                        "2) The single most important next step. "
                        "3) The one course you recommend they take first with quoted course ID, and why. "
                        "Be direct and specific using information provided by the user. Do not list all courses. Do not use bullet points for the course recommendation — write it as a short paragraph."
                    )
                },
                {"role": "user", "content": user_message}
            ]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return None

# --- CONFIGURATION ---
REQUIRED = ["cv_role", "target_role", "budget", "time_commit"]
CONFIG_LLM_MODEL = "gpt-4o-mini"
CONFIG_MAX_SKILLS_TO_CALIBRATE = 3
CONFIG_MAX_COURSES = 10
CONFIG_MAX_GAP = 5
CONFIG_SHOW_SETTINGS = False
MAX_HISTORY_TURNS = 10
CONFIG_TEXT = {
    # App titles and main headings
    "app_title": "AI Career Coach",
    "main_title": "Career Intelligence",
    "main_subtitle": "Configure your SkillsFuture profile via direct input or our AI Coach.",
    "pathway_title": "Optimized Pathway",
    
    # Sidebar
    "sidebar_title": "Settings",
    "sidebar_api_key_label": "OpenAI API Key",
    "sidebar_api_key_help": "Enter your OpenAI API key to enable AI chat.",
    "sidebar_backend_label": "Databricks Backend:",
    "sidebar_backend_disconnected": "Disconnected",
    "sidebar_backend_detail": "Using intelligence placeholder nodes",
    "reset_button": "Reset Profile Parameters",
    
    # CV Upload Section
    "cv_upload_title": "Upload Your CV (Optional)",
    "cv_upload_desc": "Upload your CV to automatically extract your current role and relevant skills.",
    "cv_upload_label": "Drop your CV here or browse",
    "cv_upload_help": "Upload a PDF CV to auto-fill your current role and extract skills",
    "cv_parsing_spinner": "📄 Parsing your CV and extracting information...",
    "cv_extracted_role": "✅ Extracted current role: **{current_role}**",
    "cv_extracted_skills": "✅ Extracted {count} skills: {preview}",
    "cv_processed_info": "✅ CV processed. Skills will be used for the first skill gap analysis.",
    
    # Profile Parameters
    "profile_params_title": "Profile Parameters (Auto-syncs with AI Coach)",
    "current_role_label": "Current Role",
    "current_role_placeholder": "e.g. Junior Data Analyst",
    "aspired_role_label": "Aspired Role (Target)",
    "aspired_role_placeholder": "e.g. Senior Data Scientist",
    "citizenship_label": "Citizenship Status",
    "citizenship_singapore": "Singapore Citizen",
    "citizenship_pr": "Permanent Resident",
    "citizenship_other": "Other",
    "budget_label": "Target Budget",
    "budget_placeholder": "e.g. $500",
    "time_label": "Time Commitment",
    "time_placeholder": "e.g. 5 hours/week",
    
    # Chat Interface
    "chat_title": "AI Career Coach",
    "chat_desc": "Talk to the AI to update your profile automatically.",
    "chat_init_message": "System Initialized. I am your AI Career Coach. Tell me about your current role and aspirations, or ask me to test your knowledge to calibrate your skills!",
    
    # Skills Calibration
    "calibrate_skills_title": "Calibrate Your Skills",
    "calibrate_skills_desc": "Please calibrate your current competency of top skills required for the role: {target_role}",    "skill_level_label": "Level",
    
    # Regeneration
    "regen_button": "✨ Regenerate Recommendations",
    "regen_spinner_gap": "Analyzing skills against Singapore job listings and peer CVs...",
    "regen_spinner_courses": "Optimizing course pathways...",
    "regen_timestamp": "Last regenerated: {formatted_time}<br>({relative_time})",
    
    # Skills Gap
    "skills_gap_title": "Skills Gap:",
    "gap_percentage_label": "% Gap",
    
    # Courses
    "recommended_modules_title": "Recommended SkillsFuture Modules",
    "courses_filters_applied": "Filters applied — Budget: <b>{budget}</b> | Time: <b>{time}</b>",
    "courses_empty_title": "No Courses Available",
    "courses_empty_desc": "We couldn't find suitable courses matching your criteria. Try adjusting your budget, time commitment, or target role.",
    "course_badge_skillsfuture": "SkillsFuture Credit Eligible",
    "course_badge_subsidies": "Subsidies Available",
    "course_level_label": "Level:",
    "course_format_label": "Format:",
    "course_cost_label": "Est. Cost:",
    "course_cost_subsidy": "(after subsidy)",
    "course_duration_label": "Duration:",
    
    # System States
    "system_locked_title": "System Locked",
    "system_locked_desc": "Awaiting input parameters to compute optimal learning trajectories:<br><b>Current Role</b>, <b>Aspired Role</b>, <b>Budget</b>, & <b>Time Commitment</b>",
    "synthesis_complete": "Profile synthesis complete for {role}.",
    "synthesis_ai_adjusted": "Profile synthesis complete with adjustment. AI Coach suggested: {changes}.",
    
    # Debug Panel
    "debug_title": "🔍 Debug Data Flow",
    "debug_skillgap_input": "**1️⃣ SkillGap Module - INPUT**",
    "debug_skillgap_output": "**2️⃣ SkillGap Module - OUTPUT**",
    "debug_recommender_input": "**3️⃣ Recommender Module - INPUT**",
    "debug_recommender_output": "**4️⃣ Recommender Module - OUTPUT**",
    "debug_no_data": "No {module} data yet",
}

SVG_BAR_CHART = """<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle; margin-right: 8px; margin-bottom: 3px;"><line x1="18" y1="20" x2="18" y2="10"></line><line x1="12" y1="20" x2="12" y2="4"></line><line x1="6" y1="20" x2="6" y2="14"></line></svg>"""
SVG_ARROW = """<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle; margin: 0 8px; margin-bottom: 3px;"><line x1="5" y1="12" x2="19" y2="12"></line><polyline points="12 5 19 12 12 19"></polyline></svg>"""
SVG_CAP = """<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle; margin-right: 8px; margin-bottom: 3px;"><path d="M22 10v6M2 10l10-5 10 5-10 5z"></path><path d="M6 12v5c3 3 9 3 12 0v-5"></path></svg>"""


st.set_page_config(page_title=CONFIG_TEXT["app_title"], layout="wide", initial_sidebar_state="collapsed" if not CONFIG_SHOW_SETTINGS else "collapsed")

# --- LOAD CSS ---
css_path = os.path.join(os.path.dirname(__file__), "style.css")
with open(css_path, "r") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# ==========================================
# EXTERNAL MODULE INTEGRATION POINTS
# ==========================================
def get_openai_client():
    api_key = os.getenv("OPENAI_API_KEY", "")

    if not api_key:
        try:
            import base64
            from databricks.sdk import WorkspaceClient
            w = WorkspaceClient(
                host=os.environ["DATABRICKS_HOST"],
                client_id=os.environ["DATABRICKS_CLIENT_ID"],
                client_secret=os.environ["DATABRICKS_CLIENT_SECRET"],
            )
            api_key = w.secrets.get_secret(scope="my-secrets", key="openai-api-key01").value
            try:
                api_key = base64.b64decode(api_key).decode("utf-8")
            except Exception:
                pass
        except Exception as e:
            pass

    if not api_key:
        st.warning("⚠️ OpenAI API key not found.")
        st.stop()

    return OpenAI(api_key=api_key)

def normalize_profile_with_ai(field, value):
    """Quickly normalizes a profile field value using AI."""
    if not value or not value.strip():
        return value
    try:
        client = get_openai_client()
        response = client.chat.completions.create(
            model=CONFIG_LLM_MODEL,
            max_tokens=50,
            messages=[
                {"role": "system", "content": "You are a career profile normalizer who understands job roles and job titles very well. Fix user inputed aspiring job typos, capitalization and expand abbreviations in job titles and skills to their proper full names. Return ONLY the corrected text, nothing else. Keep it concise. Examples: 'Web application englleer' -> 'Web Application Engineer', 'ML eng' -> 'Machine Learning Engineer', 'js dev' -> 'JavaScript Developer'"},
                {"role": "user", "content": value}
            ]
        )
        return response.choices[0].message.content.strip()
    except:
        return value

def parse_budget(budget_str):
    """
    Parse budget string to float.
    Examples: '$500', 'SGD 1000', '2000' -> floats
    Returns: float value or 10000.0 as default
    """
    if not budget_str or not budget_str.strip():
        return 10000.0  # Default max budget
    
    try:
        # Remove common prefixes and whitespace
        cleaned = budget_str.strip().replace('$', '').replace('SGD', '').replace(',', '').strip()
        value = float(cleaned)
        return max(value, 0.0)  # Ensure non-negative
    except (ValueError, AttributeError):
        return 10000.0  # Default on parse error

def parse_time_commitment(time_str):
    """
    Parse time commitment string to hours per week.
    Examples: '5 hours/week', '10 hours per week', '20h' -> floats
    Returns: float value or 40.0 as default
    """
    if not time_str or not time_str.strip():
        return 40.0  # Default max hours

    try:
        # Extract numbers from the string
        numbers = re.findall(r'\d+\.?\d*', time_str.lower())
        if numbers:
            value = float(numbers[0])
            return max(value, 0.0)  # Ensure non-negative
        return 40.0  # Default if no numbers found
    except (ValueError, AttributeError, IndexError):
        return 40.0  # Default on parse error

def parse_json(raw: str) -> dict:
    """
    Parse JSON response from LLM, handling various formats.
    Returns: dict or fallback dict with error message
    """
    if not raw or not raw.strip():
        return {"message": "Empty response from LLM"}

    try:
        # Remove markdown code blocks if present
        if raw.startswith("```"):
            # Split by code blocks and find the last JSON block
            blocks = raw.split("```")
            for block in reversed(blocks):
                block = block.strip()
                if block.startswith("json"):
                    raw = block[4:].strip()
                    break
                elif block and not block.startswith("json") and block != "json":
                    # Try parsing this block as JSON
                    try:
                        return json.loads(block)
                    except:
                        continue
            else:
                # If no valid JSON block found, try the whole string
                raw = raw
        else:
            raw = raw.strip()

        # Parse JSON
        return json.loads(raw)
    except (json.JSONDecodeError, IndexError) as e:
        # Return fallback dict for malformed JSON
        return {"message": f"Failed to parse JSON response: {str(e)}", "raw_response": raw[:500]}

def test_sql_connection():
    """
    Test SQL connection by running a simple query.
    Returns: (success: bool, message: str, error_details: str or None)
    """
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
        import skillgap.skillgap as skillgap
        
        # Configure SQL connector mode
        skillgap.IN_DATABRICKS = True
        skillgap.USE_SQL_CONNECTOR = True
        skillgap.WAREHOUSE_HTTP_PATH = "/sql/1.0/warehouses/10d7685b7261f4d2"
        
        # Try a simple query to test connection
        test_query = """
            SELECT COUNT(*) as row_count 
            FROM workspace.default.job_description 
            LIMIT 1
        """
        
        result_df = skillgap.execute_sql_query(test_query)
        
        if len(result_df) > 0:
            row_count = result_df.iloc[0]['row_count']
            return True, f"✅ SQL Connection Active ({row_count:,} job listings available)", None
        else:
            return False, "⚠️ SQL query returned no data", "Empty result set"
            
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        return False, f"❌ SQL Connection Failed", str(e) + "\n\n" + error_trace

def fetch_skills_gap_matrix(target_role, current_skills_dict):
    """
    Calls new skillgap.process_single_user() API.
    Returns: (result_gaps, final_json, top_5_skills)
    - result_gaps: list of gap dicts for display (ALL gaps, not just top 5)
    - final_json: full result JSON for recommender
    - top_5_skills: list of top 5 skill names for calibration UI
    """
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

    try:   
        import skillgap.skillgap as skillgap
        
        skillgap.IN_DATABRICKS = True
        skillgap.USE_SQL_CONNECTOR = True
        skillgap.WAREHOUSE_HTTP_PATH = "/sql/1.0/warehouses/10d7685b7261f4d2"

        # Build user_skills dict in the format expected by process_single_user
        # Always pass current skill levels back to skillgap
        user_skills = {
            skill: level
            for skill, level in sorted(current_skills_dict.items())
            if level and level != "None"
        }
        
        # If no skills yet, pass empty dict (first time or CV not uploaded)
        if not user_skills:
            user_skills = {}

        # DEBUG: Store all input parameters as raw JSON
        st.session_state.debug_skillgap_input = {
            "target_role": target_role,
            "user_skills": user_skills,
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        # Call new API
        result = skillgap.process_single_user(
            user_id=st.session_state.session_user_id,
            user_skills=user_skills,
            target_roles=target_role
        )
        
        # Extract top_5_skills from first role result
        top_5_skills = []
        if result and 'all_role_results' in result and len(result['all_role_results']) > 0:
            skill_gaps_data = result['all_role_results'][0].get('skill_gaps', {})
            top_5_skills = skill_gaps_data.get('top_5_skills', [])
        
        # Extract prioritised_gaps for display (all gaps, not just top 5)
        prioritised_gaps = []
        if result and 'all_role_results' in result and len(result['all_role_results']) > 0:
            prioritised_gaps = result['all_role_results'][0].get('skill_gaps', {}).get('gaps', [])
        
        # Normalize output to match app's expected format for display
        gaps = []
        for gap in sorted(prioritised_gaps, key=lambda x: x.get("unified_score", 0), reverse=True)[:CONFIG_MAX_GAP+5]:
            skill_name = gap.get("skill", "Unknown Skill")
            gap_pct = int(round(gap.get("unified_score", 0) * 100))
            demand = int(round(gap.get("demand_score", 0) * 100))
            peer = int(round(gap.get("peer_score", 0) * 100))
            justification = f"<b>{demand}%</b> of target jobs require this skill; <b>{peer}%</b> of peers in this role have this skill"
            gaps.append({
                "skill": skill_name,
                "gap_percentage": gap_pct,
                "justification": justification
            })
        
        result_gaps = gaps[:CONFIG_MAX_GAP]
        
        # DEBUG: Store raw output
        st.session_state.debug_skillgap_output = {
            "result_gaps": result_gaps,
            "top_5_skills": top_5_skills,
            "full_result": result,
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # Return full result as final_json for recommender
        return result_gaps, result, top_5_skills

    except ImportError as e:
        error_msg = f"⚠️ Skillgap module not available: {e}"
        st.warning(error_msg)
        st.session_state.debug_skillgap_output = {"error": error_msg}
        return [], None, []

    except Exception as e:
        import traceback
        error_msg = f"⚠️ Skillgap module error: {e}"
        st.warning(error_msg)
        st.session_state.debug_skillgap_output = {"error": error_msg, "traceback": traceback.format_exc()}
        return [], None, []

def fetch_recommended_courses(skills_needed, user_budget, user_time, citizenship):
    """
    Calls real recommender module if available, falls back to empty list.
    
    NOTE: skills_needed parameter is DEPRECATED - kept for backwards compatibility.
    The function now extracts skill gaps directly from skillgap_json in session state.
    """
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

    skillgap_json = st.session_state.get("skillgap_json")
    
    # DEBUG: Store INPUT parameters FIRST, before any validation or early returns
    st.session_state.debug_recommender_input = {
        "user_budget": user_budget,
        "user_time": user_time,
        "citizenship": citizenship,
        "skillgap_json": skillgap_json,
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    if not skillgap_json:
        st.session_state.debug_recommender_output = {"error": "No skillgap_json available"}
        return []

    try:
        from recommender.recommender import CourseRecommender
        from recommender.models import UserProfile, Modality, Schedule
        from recommender.config import RecommenderConfig
        from recommender.serialization import serialize_learning_path_to_json

        import skillgap.skillgap
        from skillgap.skillgap import execute_sql_query
        from recommender.models import SkillGap

        skillgap.skillgap.IN_DATABRICKS = True
        skillgap.skillgap.USE_SQL_CONNECTOR = True
        skillgap.skillgap.WAREHOUSE_HTTP_PATH = "/sql/1.0/warehouses/10d7685b7261f4d2"

        # Extract data directly from new process_single_user() format
        # New format: result['all_role_results'][0]['skill_gaps']['gaps']
        target_role = st.session_state.aspired_role
        skill_gaps = []
        candidate_course_ids = []
        
        if skillgap_json and 'all_role_results' in skillgap_json and len(skillgap_json['all_role_results']) > 0:
            first_role_result = skillgap_json['all_role_results'][0]
            
            # Extract target role if available
            if 'role' in first_role_result:
                target_role = first_role_result['role']
            
            # Extract skill gaps from prioritised_gaps
            skill_gaps_data = first_role_result.get('skill_gaps', {})
            prioritised_gaps = skill_gaps_data.get('gaps', [])
            
            # Transform to format expected by recommender
            for gap in prioritised_gaps:
                skill_gaps.append(SkillGap(
                    skill=gap.get("skill", ""),
                    priority=gap.get("demand_score", 0),        # 0.0–1.0 float
                    current_level=gap.get("user_skill_proficiency", 0),  # 0.0–1.0 float
                    target_level=1.0,                             # always target full proficiency
                    gap_size=1.0 - gap.get("user_skill_proficiency", 0)  # target - current
                ))
            
            # Extract candidate course IDs if available
            candidate_course_ids = skill_gaps_data.get('candidate_courses', [])

        # CRITICAL VALIDATION: Check if we have valid skill gaps before proceeding
        if not skill_gaps:
            error_msg = "No valid skill gaps extracted from skillgap_json"
            st.session_state.debug_recommender_output = {
                "error": error_msg,
                "skillgap_json_keys": list(skillgap_json.keys()) if skillgap_json else [],
                "structure_check": {
                    "has_all_role_results": 'all_role_results' in skillgap_json if skillgap_json else False,
                    "all_role_results_length": len(skillgap_json.get('all_role_results', [])) if skillgap_json else 0,
                    "has_skill_gaps_key": 'skill_gaps' in skillgap_json.get('all_role_results', [{}])[0] if skillgap_json and skillgap_json.get('all_role_results') else False,
                    "gaps_length": len(skillgap_json.get('all_role_results', [{}])[0].get('skill_gaps', {}).get('gaps', [])) if skillgap_json and skillgap_json.get('all_role_results') else 0
                },
                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            st.warning(f"⚠️ {error_msg}. Check Debug Data Flow panel for details.")
            return []

        # Load courses from Databricks
        COURSE_TABLE = "workspace.default.my_skills_future_course_directory"

        # Embedding-based candidate lookup
        from skillgap.skillgap import get_candidate_course_ids_for_skills
        candidate_course_ids = get_candidate_course_ids_for_skills(skill_gaps, top_k_per_skill=5, min_similarity=0.40)

        if candidate_course_ids:
            id_list = ",".join([f"'{c}'" for c in candidate_course_ids])
            query = f"""
                SELECT coursereferencenumber, coursetitle, trainingprovideralias,
                       trainingprovideruen, courseratings_stars, courseratings_value,
                       courseratings_noofrespondents, jobcareer_impact_stars,
                       jobcareer_impact_value, jobcareer_impact_noofrespondents,
                       attendancecount, full_course_fee, course_fee_after_subsidies,
                       number_of_hours, training_commitment, conducted_in,
                       about_this_course, what_you_learn, minimum_entry_requirement
                FROM {COURSE_TABLE}
                WHERE coursereferencenumber IN ({id_list})
            """
        else:
            query = f"""
                SELECT coursereferencenumber, coursetitle, trainingprovideralias,
                       trainingprovideruen, courseratings_stars, courseratings_value,
                       courseratings_noofrespondents, jobcareer_impact_stars,
                       jobcareer_impact_value, jobcareer_impact_noofrespondents,
                       attendancecount, full_course_fee, course_fee_after_subsidies,
                       number_of_hours, training_commitment, conducted_in,
                       about_this_course, what_you_learn, minimum_entry_requirement
                FROM {COURSE_TABLE}
                LIMIT 50
            """
        courses_df = execute_sql_query(query)

        # Map pandas rows to Course objects
        from recommender.models import Course
        courses = []
        for _, row in courses_df.iterrows():
            try:
                cost = float(row['full_course_fee']) if row['full_course_fee'] is not None else 0.0
                cost_after = float(row['course_fee_after_subsidies']) if row['course_fee_after_subsidies'] is not None else cost
                conducted = str(row.get('conducted_in', '') or '').lower()
                commitment = str(row.get('training_commitment', '') or '').lower()
                modality = 'online' if 'online' in conducted else 'onsite' if 'classroom' in conducted else 'blended' if 'blended' in conducted else None
                schedule = 'weekday' if 'weekday' in commitment else 'weekend' if 'weekend' in commitment else 'evening' if 'evening' in commitment else None
                courses.append(Course(
                    course_id=row['coursereferencenumber'],
                    title=row['coursetitle'],
                    provider=row['trainingprovideralias'],
                    provider_uen=row.get('trainingprovideruen'),
                    rating=float(row['courseratings_stars']) if row['courseratings_stars'] is not None else 0.0,
                    rating_value=float(row['courseratings_value']) if row.get('courseratings_value') is not None else None,
                    rating_respondents=int(row['courseratings_noofrespondents']) if row['courseratings_noofrespondents'] is not None else 0,
                    career_impact_stars=float(row['jobcareer_impact_stars']) if row.get('jobcareer_impact_stars') is not None else None,
                    career_impact_value=float(row['jobcareer_impact_value']) if row.get('jobcareer_impact_value') is not None else None,
                    career_impact_respondents=int(row['jobcareer_impact_noofrespondents']) if row.get('jobcareer_impact_noofrespondents') is not None else None,
                    enrollment_count=int(row['attendancecount']) if row['attendancecount'] is not None else 0,
                    cost=cost,
                    cost_after_subsidy=cost_after,
                    total_hours=float(row['number_of_hours']) if row['number_of_hours'] is not None else 0.0,
                    training_commitment=row.get('training_commitment'),
                    conducted_in=row.get('conducted_in'),
                    description=row.get('about_this_course'),
                    skills_covered=row.get('what_you_learn'),
                    prerequisites=row.get('minimum_entry_requirement'),
                    modality=modality,
                    schedule=schedule,
                    skillsfuture_eligible=(cost > cost_after) if cost > 0 else True
                ))
            except Exception:
                continue

        # Deduplicate courses by course_id (embedding lookup may return same ID for multiple skills)
        seen_ids = set()
        deduped_courses = []
        for c in courses:
            if c.course_id not in seen_ids:
                seen_ids.add(c.course_id)
                deduped_courses.append(c)
        courses = deduped_courses

        # Build UserProfile with user's actual budget and time commitment
        skillsfuture_eligible = citizenship in [CONFIG_TEXT["citizenship_singapore"], CONFIG_TEXT["citizenship_pr"]]

        parsed_budget = parse_budget(user_budget)
        parsed_hours = parse_time_commitment(user_time)
        
        user_profile = UserProfile(
            user_id=st.session_state.session_user_id,
            current_role=st.session_state.current_role or "Professional",
            target_role=target_role,
            current_skills=list(st.session_state.skill_levels.keys()),
            budget=parsed_budget,
            available_hours_per_week=parsed_hours,
            preferred_modality=Modality.ONLINE,
            preferred_schedule=Schedule.FLEXIBLE,
            skillsfuture_eligible=skillsfuture_eligible,
            preferred_providers=[],
            preferred_duration_weeks=52
        )

        # Run recommender
        config = RecommenderConfig()
        config.enable_mlflow = False
        config.min_relevance_threshold = 0.01  # disable relevance hard filter, let scoring handle it
        recommender = CourseRecommender(config)

        # Perform basic semantic search from vector embeddings (skill---> top 20 courses)
        # already performed above.
        
        # Filter courses from filtered_catalog
        learning_path = recommender.recommend(user_profile, skill_gaps, candidate_courses=courses)

        # Convert LearningPath to app's expected format - clean all text fields
        result = []
        for rec in learning_path.courses[:CONFIG_MAX_COURSES]:
            result.append({
                "course_id": rec.course.course_id,
                "title": clean_text(rec.course.title),
                "provider": clean_text(rec.course.provider),
                "description": clean_text(rec.course.description),
                "cost": rec.course.cost,
                "cost_after_subsidy": rec.course.cost_after_subsidy,
                "duration": f"{rec.course.duration_weeks:.0f} Weeks" if hasattr(rec.course, 'duration_weeks') else "N/A",
                "format": clean_text(rec.course.conducted_in or rec.course.modality or "N/A"),
                "level": "N/A",
                "rating": rec.course.rating or 0.0,
                "reviews": rec.course.rating_respondents or 0,
                "is_skillsfuture_eligible": rec.course.skillsfuture_eligible
            })

        # Update INPUT with parsed data after successful extraction
        st.session_state.debug_recommender_input.update({
            "parsed_target_role": target_role,
            "parsed_skill_gaps": skill_gaps,
            "parsed_candidate_course_ids": candidate_course_ids,
            "courses": courses
        })
                
        # DEBUG: Store raw output
        try:
            raw = learning_path.model_dump()
        except AttributeError:
            import dataclasses
            raw = dataclasses.asdict(learning_path)
        st.session_state.debug_recommender_output = {
            "raw_learning_path": raw,
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        return result

    except Exception as e:
        import traceback
        error_msg = f"⚠️ Recommender module error: {e}"
        print(f"RECOMMENDER ERROR: {e}")
        traceback.print_exc()
        st.warning(error_msg)
        st.session_state.debug_recommender_output = {"error": error_msg, "traceback": traceback.format_exc()}
        return []

# --- HELPER FUNCTIONS ---
def get_mock_skills(role):
    skills = []
    return skills[:CONFIG_MAX_GAP]

SKILL_DESCRIPTIONS = {
    "Python": "General-purpose language for data and logic.",
    "SQL": "Database querying and data manipulation.",
    "Data Visualization": "Designing charts to communicate insights.",
    "Statistics": "Mathematical analysis of data.",
    "Machine Learning": "Algorithms that learn from data.",
    "SEO": "Optimizing web content for search engines.",
    "Content Strategy": "Planning and managing media content.",
    "Google Analytics": "Tracking website traffic and performance.",
    "Copywriting": "Writing persuasive marketing text.",
    "Campaign Management": "Overseeing advertising campaigns.",
    "JavaScript": "Web scripting language for interactivity.",
    "React": "Library for building user interfaces.",
    "Node.js": "Backend JavaScript runtime environment.",
    "Git": "Version control system for tracking changes.",
    "System Design": "Architecting large-scale software systems.",
    "Figma": "Collaborative interface design tool.",
    "User Research": "Studying target audiences and needs.",
    "Prototyping": "Creating mockups of products.",
    "Adobe CC": "Suite of creative design software.",
    "Wireframing": "Creating skeletal frameworks for apps.",
    "Agile Methodology": "Iterative project management approach.",
    "Roadmapping": "Strategic planning for product releases.",
    "Stakeholder Management": "Communicating with project investors/leaders.",
    "Jira": "Issue tracking and project management tool.",
    "Project Management": "Organizing and executing projects.",
    "Communication": "Effectively sharing information.",
    "Problem Solving": "Identifying and resolving issues.",
    "Leadership": "Guiding and inspiring a team.",
    "Data Analysis": "Extracting insights from raw data."
}

def get_skill_desc(skill):
    return SKILL_DESCRIPTIONS.get(skill, "Core competency evaluation.")

def trigger_star_animation():
    stars_html = ""
    for i in range(30):
        left = random.randint(0, 100)
        delay = random.uniform(0, 1.5)
        duration = random.uniform(2, 3)
        size = random.randint(16, 32)
        stars_html += f'<div class="magic-star" style="left: {left}vw; animation-delay: {delay}s; animation-duration: {duration}s; font-size: {size}px;">✨</div>'
    st.markdown(f'<div id="star-container">{stars_html}</div>', unsafe_allow_html=True)

# --- SESSION STATE INITIALIZATION ---
def initialize_session_state():
    if "current_role" not in st.session_state: st.session_state.current_role = ""
    if "aspired_role" not in st.session_state: st.session_state.aspired_role = ""
    if "budget" not in st.session_state: st.session_state.budget = ""
    if "time_commitment" not in st.session_state: st.session_state.time_commitment = ""
    if "citizenship" not in st.session_state: st.session_state.citizenship = CONFIG_TEXT["citizenship_singapore"]
    if "messages" not in st.session_state: st.session_state.messages = []
    if "celebrated" not in st.session_state: st.session_state.celebrated = False
    if "regen_count" not in st.session_state: st.session_state.regen_count = 0
    if "skill_levels" not in st.session_state: st.session_state.skill_levels = {}
    if "last_regen_time" not in st.session_state: st.session_state.last_regen_time = time.time()
    if "profile_normalized" not in st.session_state: st.session_state.profile_normalized = False
    if "normalization_changes" not in st.session_state: st.session_state.normalization_changes = ""
    if "pending_skill_updates" not in st.session_state: st.session_state.pending_skill_updates = {}
    if "skillgap_json" not in st.session_state: st.session_state.skillgap_json = None
    if "cv_extracted_skills" not in st.session_state: st.session_state.cv_extracted_skills = []
    if "use_cv_skills_for_gap" not in st.session_state: st.session_state.use_cv_skills_for_gap = False
    if "cv_processed" not in st.session_state: st.session_state.cv_processed = False
    if "top_5_skills" not in st.session_state: st.session_state.top_5_skills = []
    if "sql_test_result" not in st.session_state: st.session_state.sql_test_result = None
    if "session_user_id" not in st.session_state:
        st.session_state.session_user_id = f"streamlit_user_{random.randint(100000, 999999)}"

# --- DEBUG: Initialize debug session state variables ---
def init_debug_state():
    if "debug_skillgap_input" not in st.session_state: st.session_state.debug_skillgap_input = None
    if "debug_skillgap_output" not in st.session_state: st.session_state.debug_skillgap_output = None
    if "debug_recommender_input" not in st.session_state: st.session_state.debug_recommender_input = None
    if "debug_recommender_output" not in st.session_state: st.session_state.debug_recommender_output = None

try:
    init_debug_state()
except:
    pass


initialize_session_state()

def is_profile_complete():
    try:
        return all([
            st.session_state.current_role.strip(),
            st.session_state.aspired_role.strip(),
            st.session_state.budget.strip(),
            st.session_state.time_commitment.strip()
        ])
    except (AttributeError, KeyError):
        return False

if "current_role" in st.session_state and st.session_state.current_role:
    mock_skills = get_mock_skills(st.session_state.current_role)
    for skill in mock_skills:
        if skill not in st.session_state.skill_levels:
            st.session_state.skill_levels[skill] = "Beginner"

# --- SIDEBAR CONFIG ---
with st.sidebar:
    if CONFIG_SHOW_SETTINGS:
        st.markdown(f"""
        <div style="display: flex; align-items: center; margin-bottom: 20px;">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#1c1d1f" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right: 10px;">
                <circle cx="12" cy="12" r="3"></circle>
                <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
            </svg>
            <h2 style="margin: 0; font-size: 20px; color: #1c1d1f;">{CONFIG_TEXT["sidebar_title"]}</h2>
        </div>
        """, unsafe_allow_html=True)
        
        api_key = st.text_input(CONFIG_TEXT["sidebar_api_key_label"], type="password", help=CONFIG_TEXT["sidebar_api_key_help"])
        if api_key:
            os.environ["OPENAI_API_KEY"] = api_key
        st.markdown("---")
        st.markdown(f"""
        <div style="background: rgba(255, 75, 75, 0.05); padding: 12px; border-radius: 8px; border: 1px solid rgba(255, 75, 75, 0.2); margin-bottom: 20px;">
            <p style="margin: 0; font-size: 13px; color: #1c1d1f;"><strong>{CONFIG_TEXT["sidebar_backend_label"]}</strong> <span style="color: #ff4b4b;">{CONFIG_TEXT["sidebar_backend_disconnected"]}</span></p>
            <p style="margin: 4px 0 0 0; font-size: 11px; color: #6a6f73;">{CONFIG_TEXT["sidebar_backend_detail"]}</p>
        </div>
        """, unsafe_allow_html=True)
    
    if st.button(CONFIG_TEXT["reset_button"], key="reset_btn"):
        # Reset all profile input fields
        st.session_state.current_role = ""
        st.session_state.aspired_role = ""
        st.session_state.budget = ""
        st.session_state.time_commitment = ""
        st.session_state.citizenship = CONFIG_TEXT["citizenship_singapore"]
        
        # Reset chat and UI state
        st.session_state.messages = []
        st.session_state.celebrated = False
        
        # Reset skill-related state
        st.session_state.skill_levels = {}
        st.session_state.pending_skill_updates = {}
        st.session_state.top_5_skills = []
        
        # Reset CV processing state
        st.session_state.cv_extracted_skills = []
        st.session_state.use_cv_skills_for_gap = False
        st.session_state.cv_processed = False
        
        # Reset recommendation state (CRITICAL FIX: These were missing)
        st.session_state.matrix_data = []
        st.session_state.courses_data = []
        st.session_state.skillgap_json = None
        
        # Reset regeneration counters (CRITICAL FIX: These were missing)
        st.session_state.regen_count = 0
        st.session_state.last_regen_time = time.time()
        st.session_state.last_fetched_regen = -1
        
        # Reset normalization state (CRITICAL FIX: These were missing)
        st.session_state.profile_normalized = False
        st.session_state.normalization_changes = ""
        
        # Reset debug state
        st.session_state.debug_skillgap_input = None
        st.session_state.debug_skillgap_output = None
        st.session_state.debug_recommender_input = None
        st.session_state.debug_recommender_output = None
        
        # Other state
        st.session_state.sql_test_result = None
        st.session_state.session_user_id = f"streamlit_user_{random.randint(100000, 999999)}"
        
        st.rerun()
    
    # DEBUG PANEL - Smaller font (reduced by 2pts)
    with st.expander(CONFIG_TEXT["debug_title"], expanded=False):
        st.markdown('<div class="debug-panel">', unsafe_allow_html=True)
        
        st.markdown(CONFIG_TEXT["debug_skillgap_input"])
        if st.session_state.debug_skillgap_input:
            st.json(st.session_state.debug_skillgap_input)
        else:
            st.info(CONFIG_TEXT["debug_no_data"].format(module="skillgap input"))
        
        st.markdown(CONFIG_TEXT["debug_skillgap_output"])
        if st.session_state.debug_skillgap_output:
            st.json(st.session_state.debug_skillgap_output)
        else:
            st.info(CONFIG_TEXT["debug_no_data"].format(module="skillgap output"))
        
        st.markdown("---")
        
        st.markdown(CONFIG_TEXT["debug_recommender_input"])
        if st.session_state.debug_recommender_input:
            st.json(st.session_state.debug_recommender_input)
        else:
            st.info(CONFIG_TEXT["debug_no_data"].format(module="recommender input"))
        
        st.markdown(CONFIG_TEXT["debug_recommender_output"])
        if st.session_state.debug_recommender_output:
            st.json(st.session_state.debug_recommender_output)
        else:
            st.info(CONFIG_TEXT["debug_no_data"].format(module="recommender output"))
        
        st.markdown('</div>', unsafe_allow_html=True)

# --- MAIN LAYOUT ---
col1, col2 = st.columns([1.2, 1.0])

# --- LEFT COLUMN: INPUTS & CHAT ---
with col1:
    logo_path = os.path.join(os.path.dirname(__file__), "skillup_logo_cropped.png")
    st.image(logo_path, width=400)
    st.markdown(f"<p style='color: #6a6f73; font-size: 16px; margin-bottom: 24px;'>{CONFIG_TEXT['main_subtitle']}</p>", unsafe_allow_html=True)
    
    # --- CV UPLOAD SECTION ---
    st.markdown(f"""
    <div style="display: flex; align-items: center; margin-bottom: 12px;">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#8752cc" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right: 8px;">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
            <polyline points="14 2 14 8 20 8"></polyline>
            <line x1="12" y1="18" x2="12" y2="12"></line>
            <line x1="9" y1="15" x2="15" y2="15"></line>
        </svg>
        <h3 style="margin: 0; font-weight: 600; font-size: 18px; color: #1c1d1f;">{CONFIG_TEXT["cv_upload_title"]}</h3>
    </div>
    <p style="color: #6a6f73; font-size: 14px; margin-bottom: 12px;">{CONFIG_TEXT["cv_upload_desc"]}</p>
    """, unsafe_allow_html=True)
    
    uploaded_cv = st.file_uploader(
        CONFIG_TEXT["cv_upload_label"],
        type=['pdf'],
        key="cv_uploader",
        help=CONFIG_TEXT["cv_upload_help"],
        label_visibility="collapsed"
    )
    
    # Process CV if uploaded and not yet processed
    if uploaded_cv is not None and not st.session_state.cv_processed:
        with st.spinner(CONFIG_TEXT["cv_parsing_spinner"]):
            cv_text = parse_pdf_cv(uploaded_cv)
            
            if cv_text:
                current_role, skills = extract_role_and_skills_from_cv(cv_text)
                
                if current_role:
                    st.session_state.current_role = current_role
                    st.success(CONFIG_TEXT["cv_extracted_role"].format(current_role=current_role))
                
                if skills:
                    st.session_state.cv_extracted_skills = skills
                    st.session_state.use_cv_skills_for_gap = True
                    
                    # Populate skill_levels with CV skills at Beginner level
                    for skill in skills:
                        if skill not in st.session_state.skill_levels:
                            st.session_state.skill_levels[skill] = "Beginner"
                    
                    skills_preview = ', '.join(skills[:5]) + ('...' if len(skills) > 5 else '')
                    st.success(CONFIG_TEXT["cv_extracted_skills"].format(count=len(skills), preview=skills_preview))
                
                st.session_state.cv_processed = True
                st.rerun()
    
    if st.session_state.cv_processed:
        st.info(CONFIG_TEXT["cv_processed_info"])
    
    st.markdown("<div style='margin-bottom: 24px;'></div>", unsafe_allow_html=True)
    
    with st.expander(CONFIG_TEXT["profile_params_title"], expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            st.text_input(CONFIG_TEXT["current_role_label"], key="_w_current_role", placeholder=CONFIG_TEXT["current_role_placeholder"], value=st.session_state.current_role)
            st.text_input(CONFIG_TEXT["aspired_role_label"], key="_w_aspired_role", placeholder=CONFIG_TEXT["aspired_role_placeholder"], value=st.session_state.aspired_role)
            st.selectbox(CONFIG_TEXT["citizenship_label"], [CONFIG_TEXT["citizenship_singapore"], CONFIG_TEXT["citizenship_pr"], CONFIG_TEXT["citizenship_other"]], key="citizenship")
        with c2:
            st.text_input(CONFIG_TEXT["budget_label"], key="_w_budget", placeholder=CONFIG_TEXT["budget_placeholder"], value=st.session_state.budget)
            st.text_input(CONFIG_TEXT["time_label"], key="_w_time_commitment", placeholder=CONFIG_TEXT["time_placeholder"], value=st.session_state.time_commitment)
        st.session_state.current_role = st.session_state._w_current_role
        st.session_state.aspired_role = st.session_state._w_aspired_role
        st.session_state.budget = st.session_state._w_budget
        st.session_state.time_commitment = st.session_state._w_time_commitment
    st.markdown(f"""
    <div style="display: flex; align-items: center; margin-top: 24px; margin-bottom: 16px;">
        <div class="icon-circle icon-blue" style="width: 36px; height: 36px; margin-right: 12px;">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
            </svg>
        </div>
        <h3 style="margin: 0; font-weight: 600; font-size: 20px; color: #1c1d1f;">{CONFIG_TEXT["chat_title"]}</h3>
    </div>
    """, unsafe_allow_html=True)
    
    chat_container = st.container(height=450)
    with chat_container:
        if not st.session_state.messages:
            st.info(CONFIG_TEXT["chat_init_message"])
        for msg in st.session_state.messages:
            if msg["role"] != "system" and msg.get("content"):
                st.chat_message(msg["role"]).write(msg["content"])
                
    if prompt := st.chat_input("E.g. I am a marketing exec looking to learn python. Test my knowledge!"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with chat_container:
            st.chat_message("user").write(prompt)
        
        client = get_openai_client()
        
        skills_context = ", ".join([f"{k}: {v}" for k, v in st.session_state.skill_levels.items()])
        
        system_prompt = f"""
        You are a helpful, enthusiastic AI Career Coach for Singapore SkillsFuture.
        Your goal is to collect information to build their learning profile:
        1. Current Role: {st.session_state.current_role or 'Missing'}
        2. Aspired Role: {st.session_state.aspired_role or 'Missing'}
        3. Budget: {st.session_state.budget or 'Missing'}
        4. Time: {st.session_state.time_commitment or 'Missing'}
        5. Citizenship: {st.session_state.citizenship}
        
        Current known skills and levels: {skills_context if skills_context else 'None yet'}
        
        If any basic information is missing, ask conversational questions to gather it.
        If the user asks to be tested or evaluated, ask them a question about one of their skills to gauge their level.
        If the user mentions or implies their skill level for ANY skill (e.g. "I'm a noob at Python", "I know SQL well", "I'm advanced in Java"), ALWAYS immediately call the 'update_profile' tool to update that skill level. Do not just acknowledge it conversationally.
        Based on their response, use the 'update_profile' tool to update their skill levels (None, Beginner, Intermediate, Advanced) and other profile fields. Do not make any further recommendations on how to change or improve their skills. Just acknowledge.
        Always maintain an encouraging and professional tone.
        """
        
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "update_profile",
                    "description": "Update the user's profile and self-declared skill levels from the chat.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "current_role": {"type": "string"},
                            "aspired_role": {"type": "string"},
                            "budget": {"type": "string"},
                            "time_commitment": {"type": "string"},
                            "skills": {
                                "type": "object",
                                "description": "Dictionary of skill names and their proficiency level evaluated.",
                                "additionalProperties": {"type": "string", "enum": ["None", "Beginner", "Intermediate", "Advanced"]}
                            }
                        }
                    }
                }
            }
        ]
        
        messages_for_api = [{"role": "system", "content": system_prompt}] + [
            m for m in st.session_state.messages if m.get("content") or m.get("tool_calls")
        ]
        
        with chat_container:
            with st.spinner("Processing..."):
                try:
                    response = client.chat.completions.create(
                        model=CONFIG_LLM_MODEL,
                        messages=messages_for_api,
                        tools=tools,
                        tool_choice="auto"
                    )
                    
                    response_message = response.choices[0].message
                    
                    if response_message.tool_calls:
                        st.session_state.messages.append(response_message.model_dump())
                        
                        for tool_call in response_message.tool_calls:
                            if tool_call.function.name == "update_profile":
                                args = json.loads(tool_call.function.arguments)
                                if args.get("current_role"): st.session_state.current_role = args["current_role"]
                                if args.get("aspired_role"): st.session_state.aspired_role = args["aspired_role"]
                                if args.get("budget"): st.session_state.budget = args["budget"]
                                if args.get("time_commitment"): st.session_state.time_commitment = args["time_commitment"]
                                
                                updated_skills = args.get("skills", {})
                                # Track which skills were updated but not visible in calibration UI
                                invisible_updates = []
                                
                                for sk, lvl in updated_skills.items():
                                    st.session_state.skill_levels[sk] = lvl
                                    st.session_state.pending_skill_updates[sk] = lvl
                                    # FIX 1: Directly set slider widget state to ensure update (instead of deleting)
                                    st.session_state[f"slider_{sk}"] = lvl
                                    
                                    # FIX 3: Check if skill is in visible calibration UI
                                    if sk not in st.session_state.get("top_5_skills", []):
                                        invisible_updates.append(f"{sk} → {lvl}")
                                
                                # Build feedback message with visibility status
                                feedback_msg = "Profile parameters and skills updated."
                                if invisible_updates:
                                    feedback_msg += f" Note: {len(invisible_updates)} skill(s) noted but they are not in the top skills required: {', '.join(invisible_updates)}. They'll appear if your target role requires them."
                                
                                st.session_state.messages.append({
                                    "role": "tool",
                                    "tool_call_id": tool_call.id,
                                    "name": tool_call.function.name,
                                    "content": feedback_msg
                                })
                                
                        messages_for_api = [{"role": "system", "content": system_prompt}] + st.session_state.messages
                        second_response = client.chat.completions.create(
                            model=CONFIG_LLM_MODEL,
                            messages=messages_for_api
                        )
                        final_text = second_response.choices[0].message.content
                        st.session_state.messages.append({"role": "assistant", "content": final_text})
                        st.chat_message("assistant").write(final_text)
                        st.rerun()
                    else:
                        st.session_state.messages.append({"role": "assistant", "content": response_message.content})
                        st.chat_message("assistant").write(response_message.content)
                        
                except Exception as e:
                    st.error(f"Network interface error: {e}")

# --- RIGHT COLUMN: DYNAMIC OUTPUT ---
with col2:
    st.markdown(f"""
    <div style="display: flex; align-items: center; margin-bottom: 24px;">
        <div class="icon-circle icon-green">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="8" r="7"></circle>
                <polyline points="8.21 13.89 7 23 12 20 17 23 15.79 13.88"></polyline>
            </svg>
        </div>
        <h1 style="margin: 0; font-size: 32px; font-weight: 700; color: #1c1d1f; letter-spacing: -0.5px;">{CONFIG_TEXT["pathway_title"]}</h1>
    </div>
    """, unsafe_allow_html=True)
    
    if is_profile_complete():
        if not st.session_state.celebrated:
            trigger_star_animation()
            st.session_state.celebrated = True
            
        st.markdown(f"""
        <div style="display: flex; align-items: center; margin-top: 8px; margin-bottom: 8px;">
            <div class="icon-circle icon-yellow" style="width: 32px; height: 32px; margin-right: 10px;">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon>
                </svg>
            </div>
            <h3 style="font-size: 18px; font-weight: 600; margin: 0; color: #1c1d1f;">{CONFIG_TEXT["calibrate_skills_title"]}</h3>
        </div>
        """, unsafe_allow_html=True)
        
        #st.markdown(f"<p style='color: #6a6f73; font-size: 14px; margin-bottom: 16px;'>{CONFIG_TEXT['calibrate_skills_desc']}</p>", unsafe_allow_html=True)
        st.markdown(f"<p style='color: #6a6f73; font-size: 14px; margin-bottom: 16px;'>{CONFIG_TEXT['calibrate_skills_desc'].format(target_role=st.session_state.aspired_role.title() or 'Target Role')}</p>", unsafe_allow_html=True)
        
        current_role = st.session_state.current_role
        
        # Use top_5_skills for calibration UI (from skillgap module)
        # Fall back to empty list if not available yet
        skills = st.session_state.get("top_5_skills", [])[:CONFIG_MAX_SKILLS_TO_CALIBRATE]
        if not skills:
            skills = []
        
        options = ["None", "Beginner", "Intermediate", "Advanced"]
        
        for skill in skills:
            col_a, col_b = st.columns([1, 1])
            with col_a:
                st.markdown(f"<div style='padding-top: 8px; font-weight: 600; font-size: 15px; color: #1c1d1f;'>{skill}</div>", unsafe_allow_html=True)
                st.markdown(f"<div style='font-size: 12px; color: #6a6f73; line-height: 1.3; padding-right: 10px;'>{get_skill_desc(skill)}</div>", unsafe_allow_html=True)
            with col_b:
                val = st.select_slider(
                    CONFIG_TEXT["skill_level_label"],
                    options=options,
                    value=st.session_state.pending_skill_updates.pop(skill, st.session_state.skill_levels.get(skill, "Beginner")),
                    key=f"slider_{skill}",
                    label_visibility="collapsed"
                )
        
        st.markdown("<hr style='margin: 24px 0; border: none; border-top: 1px solid #e1e4e8;'>", unsafe_allow_html=True)
        
        # Regenerate Button & Time Logic
        col_btn, col_time = st.columns([1, 1])
        with col_btn:
            if st.button(CONFIG_TEXT["regen_button"], use_container_width=True, key="regen_btn"):
                st.session_state.normalization_changes = ""
                
                # Store previous top_5_skills to compare
                previous_top5 = set(st.session_state.get("top_5_skills", []))
                
                # Capture current slider values for skills
                for skill in skills:
                    if f"slider_{skill}" in st.session_state:
                        st.session_state.skill_levels[skill] = st.session_state[f"slider_{skill}"]
                
                original_role = st.session_state.current_role
                original_aspired = st.session_state.aspired_role
                st.session_state.current_role = normalize_profile_with_ai("current_role", st.session_state.current_role)
                st.session_state.aspired_role = normalize_profile_with_ai("aspired_role", st.session_state.aspired_role)
                changes = []
                if original_role != st.session_state.current_role:
                    changes.append(f"Current Role: '{original_role}' → '{st.session_state.current_role}'")
                if original_aspired != st.session_state.aspired_role:
                    changes.append(f"Aspired Role: '{original_aspired}' → '{st.session_state.aspired_role}'")
                st.session_state.normalization_changes = " | ".join(changes)
                st.session_state.matrix_data = []
                st.session_state.courses_data = []
                st.session_state.skillgap_json = None
                st.session_state.regen_count += 1
                st.session_state.last_regen_time = time.time()
                
        @st.fragment(run_every=15)
        def render_live_timestamp():
            now = time.time()
            delta_sec = math.floor(now - st.session_state.last_regen_time)
            if delta_sec < 60:
                time_str = f"{delta_sec} sec ago"
            else:
                mins = delta_sec // 60
                time_str = f"{mins} min{'s' if mins > 1 else ''} ago"
            
            formatted_time = datetime.datetime.fromtimestamp(st.session_state.last_regen_time, tz=datetime.timezone(datetime.timedelta(hours=8))).strftime('%I:%M %p')
            st.markdown(CONFIG_TEXT["regen_timestamp"].format(formatted_time=formatted_time, relative_time=time_str), unsafe_allow_html=True)

        with col_time:
            render_live_timestamp()
        
        aspired = st.session_state.aspired_role.title() or "Target Role"
        current = st.session_state.current_role.title() or "Current Role"
 
        # 1-Liner synthesis complete
        st.markdown(f"""
        <div style="margin-top: 16px; margin-bottom: 24px; display: flex; align-items: center; color: #8752cc; font-size: 14px; font-weight: 500;">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right: 8px;">
                <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
                <polyline points="22 4 12 14.01 9 11.01"></polyline>
            </svg>
            {CONFIG_TEXT["synthesis_ai_adjusted"].format(changes=st.session_state.normalization_changes, role=aspired) if st.session_state.normalization_changes else CONFIG_TEXT["synthesis_complete"].format(role=aspired)}
        </div>
        """, unsafe_allow_html=True)
       
        if "matrix_data" not in st.session_state:
            st.session_state.matrix_data = []
            st.session_state.courses_data = []
            st.session_state.last_fetched_regen = -1

        needs_fetch = st.session_state.last_fetched_regen != st.session_state.regen_count
        if needs_fetch and not st.session_state.profile_normalized:
            st.session_state.current_role = normalize_profile_with_ai("current_role", st.session_state.current_role)
            st.session_state.aspired_role = normalize_profile_with_ai("aspired_role", st.session_state.aspired_role)
            st.session_state.profile_normalized = True
            st.rerun()

        if needs_fetch:
            # FIX A: Clean stale skills before fetch (keep only current top_5_skills from previous run)
            if st.session_state.top_5_skills:
                # Remove skills that aren't in the current top 5 to prevent stale values
                stale_skills = [s for s in st.session_state.skill_levels.keys() if s not in st.session_state.top_5_skills]
                for skill in stale_skills:
                    del st.session_state.skill_levels[skill]
            
            # FIX D: On first run (regen_count=0), pass empty dict to avoid uninitialized data
            skills_input = {} if st.session_state.regen_count == 1 else st.session_state.skill_levels
            
            # External Module 1: Fetch Gap Matrix and top_5_skills
            try:
                with st.spinner(CONFIG_TEXT["regen_spinner_gap"]):
                    time.sleep(1.0)
                    result_gaps, skillgap_json, new_top5 = fetch_skills_gap_matrix(st.session_state.aspired_role, skills_input)
                    
                    # Store previous top5 for comparison
                    previous_top5 = set(st.session_state.get("top_5_skills", []))
                    new_top5_set = set(new_top5)
                    
                    # Update session state
                    st.session_state.matrix_data = result_gaps
                    st.session_state.skillgap_json = skillgap_json
                    st.session_state.top_5_skills = new_top5
                    
                    # Handle skill level preservation/initialization
                    # For new skills not in previous top5, set to Beginner
                    # For existing skills, preserve user's selection
                    new_skills = new_top5_set - previous_top5
                    for skill in new_skills:
                        if skill not in st.session_state.skill_levels:
                            st.session_state.skill_levels[skill] = "Beginner"
                    
            except Exception as e:
                st.warning("⚠️ Neural Skill Matrix currently unavailable. Please try again later.")
            
            # External Module 2: Fetch Courses (uses ALL gaps, not top_5_skills)
            try:
                with st.spinner(CONFIG_TEXT["regen_spinner_courses"]):
                    time.sleep(1.5)
                    # Pass ALL gap skills to recommender, not just top 5
                    skills_needed = [s["skill"] for s in st.session_state.matrix_data] if st.session_state.matrix_data else []
                    st.session_state.courses_data = fetch_recommended_courses(skills_needed, st.session_state.budget, st.session_state.time_commitment, st.session_state.citizenship)
            except Exception as e:
                st.warning("⚠️ Recommended modules currently unavailable. Please try again later.")
            
            # Add career recommendation to chat
            if st.session_state.courses_data and st.session_state.matrix_data:
                recommendation = fetch_career_recommendation(
                    st.session_state.courses_data,
                    st.session_state.skill_levels,
                    st.session_state.matrix_data,
                    st.session_state.current_role,
                    st.session_state.aspired_role
                )
                if recommendation:
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": recommendation
                    })

            st.session_state.last_fetched_regen = st.session_state.regen_count
            if st.session_state.regen_count == 0:
                st.rerun()

        gap_matrix = st.session_state.matrix_data
        courses = st.session_state.courses_data

        # SECTION 1: Skills Gap (Always render independently if data exists)
        if gap_matrix:
            try:
                gap_html = f"""<div style="background: linear-gradient(to bottom right, #ffffff, #fdfbf7); border-radius: 16px; padding: 32px; box-shadow: 0 10px 40px rgba(135,82,204,0.08); border: 1px solid rgba(135,82,204,0.15); margin-top: 10px;">
<h3 style='display: flex; align-items: center; font-size: 20px; font-weight: 700; color: #1c1d1f; margin-top: 0; margin-bottom: 24px;'>{SVG_BAR_CHART} {CONFIG_TEXT['skills_gap_title']} <span style='color: #8752cc; margin-left: 6px;'>{current}</span> {SVG_ARROW} <span style='color: #8752cc;'>{aspired}</span></h3>
<div class="metric-card" style="box-shadow: none; border: 1px solid #f0f0f0;">
"""
                displayed = 0
                for item in gap_matrix:
                    if st.session_state.skill_levels.get(item.get("skill")) == "Advanced":
                        continue
                    if displayed >= CONFIG_MAX_GAP:
                        break
                    displayed += 1
                    gap_html += f"""<div style="margin-bottom: 16px;">
<div style="display: flex; justify-content: space-between; font-size: 14px; color: #6a6f73; margin-bottom: 4px;">
<span style="font-weight: 500;">{item.get('skill', '')} <span style="font-weight: 400; color: #9b9b9b; font-size: 13px;">({item.get('justification', '')})</span></span>
<span>{item.get('gap_percentage', 0)}{CONFIG_TEXT["gap_percentage_label"]}</span>
</div>
<div class="ai-progress-bg">
<div class="ai-progress-fill" style="width: {item.get('gap_percentage', 0)}%;"></div>
</div>
</div>"""
                gap_html += "</div></div>"  # Close metric-card and main div
                st.markdown(gap_html, unsafe_allow_html=True)
            except Exception as e:
                st.error(f"⚠️ Error rendering skills gap: {e}")

        # SECTION 2: Courses (Always render header if fetched, show message if empty)
        if courses is not None:  # Check if courses data has been fetched (not None)
            try:
                courses_html = f"""<div style="background: linear-gradient(to bottom right, #ffffff, #fdfbf7); border-radius: 16px; padding: 32px; box-shadow: 0 10px 40px rgba(135,82,204,0.08); border: 1px solid rgba(135,82,204,0.15); margin-top: 16px;">
<h3 style='display: flex; align-items: center; font-size: 20px; font-weight: 700; color: #1c1d1f; margin-top: 0; margin-bottom: 8px;'>{SVG_CAP} {CONFIG_TEXT['recommended_modules_title']}</h3>
<p style='color: #6a6f73; font-size: 14px; margin-bottom: 24px;'>{CONFIG_TEXT['courses_filters_applied'].format(budget=st.session_state.budget, time=st.session_state.time_commitment)}</p>
"""
                
                if not courses or len(courses) == 0:
                    # Show empty state message when no courses available
                    courses_html += f"""<div style="text-align: center; padding: 40px 20px; background: #f9fafb; border-radius: 12px; border: 1px solid #e5e7eb;">
    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#9ca3af" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="margin-bottom: 16px;">
        <circle cx="12" cy="12" r="10"></circle>
        <line x1="12" y1="8" x2="12" y2="12"></line>
        <line x1="12" y1="16" x2="12.01" y2="16"></line>
    </svg>
    <h4 style="margin: 0 0 8px 0; color: #6b7280; font-size: 16px; font-weight: 600;">{CONFIG_TEXT["courses_empty_title"]}</h4>
    <p style="margin: 0; color: #9ca3af; font-size: 14px;">{CONFIG_TEXT["courses_empty_desc"]}</p>
</div>"""
                else:
                    # Render courses normally
                    import urllib.parse
                    for course in courses[:CONFIG_MAX_COURSES]:
                        badge_text = CONFIG_TEXT["course_badge_skillsfuture"] if st.session_state.citizenship == CONFIG_TEXT["citizenship_singapore"] else CONFIG_TEXT["course_badge_subsidies"]
                        stars_html = "".join(["★" for _ in range(int(course['rating']))])
                        if course['rating'] % 1 > 0: stars_html += "½"

                        sf_url = f"https://www.myskillsfuture.gov.sg/content/portal/en/portal-search/portal-search.html?fq=Course_Supp_Period_To_1%3A%5B2026-05-03T00%3A00%3A00Z%20TO%20*%5D&fq=IsValid%3Atrue&q={urllib.parse.quote(course['title'])}"
                        
                        courses_html += f"""<div class="course-card" style="box-shadow: none; border: 1px solid #f0f0f0;">
        <div style="display: flex; justify-content: space-between; align-items: flex-start;">
            <h4 style="margin: 0 0 4px 0; color: #1c1d1f; font-size: 18px;">{course['title']}</h4>
            <span class="subsidy-badge">{badge_text}</span>
        </div>
        <p style="color: #8752cc; font-size: 13px; font-weight: 500; margin: 0 0 10px 0;">{course.get('provider', '')}</p>
        <div style="margin-bottom: 12px; display: flex; align-items: center;">
            <span class="star-rating">{stars_html}</span>
            <span class="review-count"><b>{course['rating']}</b> ({course['reviews']} reviews)</span>
        </div>
        <p style="color: #6a6f73; font-size: 14px; margin-bottom: 16px; line-height: 1.5;">{course['description']}</p>
        <div style="margin-bottom: 16px;">
            <span class="course-tag">{CONFIG_TEXT["course_level_label"]} {course['level']}</span>
            <span class="course-tag">{CONFIG_TEXT["course_format_label"]} {course['format']}</span>
        </div>
        <div style="display: flex; justify-content: space-between; align-items: center; font-size: 14px; color: #1c1d1f; border-top: 1px solid #edf2f7; padding-top: 12px;">
            <span><strong>{CONFIG_TEXT["course_cost_label"]}</strong> SGD {course.get('cost_after_subsidy', course['cost']):.0f} <span style="color: #6a6f73; font-size: 12px;">{CONFIG_TEXT["course_cost_subsidy"]}</span></span>
            <span><strong>{CONFIG_TEXT["course_duration_label"]}</strong> {course['duration']}</span>
            <a href="{sf_url}" target="_blank" rel="noopener noreferrer" style="display: inline-flex; align-items: center; gap: 6px; background: #8752cc; color: #ffffff; font-size: 13px; font-weight: 600; padding: 7px 14px; border-radius: 8px; text-decoration: none; white-space: nowrap;">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path><polyline points="15 3 21 3 21 9"></polyline><line x1="10" y1="14" x2="21" y2="3"></line></svg>
                View on SkillsFuture
            </a>
        </div>
    </div>"""
                
                courses_html += "</div>"  # Close main div
                st.markdown(courses_html, unsafe_allow_html=True)

            except Exception as e:
                st.error(f"⚠️ Error rendering courses: {e}")
        
    else:
        st.markdown(f"""<div class="locked-state">
    <div style="margin-bottom: 20px; display: flex; justify-content: center;">
        <div class="icon-circle icon-blue" style="width: 64px; height: 64px;">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
                <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
            </svg>
        </div>
    </div>
    <h3 style="margin: 0 0 12px 0; font-weight: 600; color: #1c1d1f;">{CONFIG_TEXT['system_locked_title']}</h3>
    <p style="font-size: 15px; margin: 0; line-height: 1.6; color: #6a6f73;">
        {CONFIG_TEXT['system_locked_desc']}
    </p>
</div>""", unsafe_allow_html=True)
