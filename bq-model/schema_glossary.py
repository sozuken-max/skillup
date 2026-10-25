"""
Column-level documentation and worked examples for the mcf_jobs table.

This exists because the raw BigQuery schema (column name + type) doesn't tell
an LLM what values actually look like, which columns are noise, or the SQL
patterns this dataset's specific quirks require (duplicate scrape rows,
pipe-delimited multi-value fields, agency vs. real employer, salary units).
When a bad query reveals a new gotcha, add it here rather than hand-editing
prose into main.py's prompt f-string.
"""

# Notes for columns worth an LLM knowing about before it writes SQL against
# this table. Columns not listed here are either self-explanatory (raw
# schema name + type is enough) or covered by CODE_COLUMNS_NOTE /
# NOISE_COLUMNS_NOTE below — intentionally not documented individually, to
# keep the prompt lean.
COLUMN_NOTES = {
    "uuid": (
        "Unique listing identifier. This table contains duplicate rows — "
        "roughly 1,773 listings were scraped more than once. Always use "
        "COUNT(DISTINCT uuid) instead of COUNT(*) when counting listings."
    ),
    "job_post_id": "Alternate unique listing ID; same duplicate-row caveat as uuid.",
    "title": "Free-text job title. Match with LOWER(title) LIKE LOWER('%keyword%').",
    "salary_min": (
        "Monthly SGD salary lower bound (salary_type is uniformly 'Monthly' in "
        "this table — treat all salary figures as monthly, never annual). For a "
        "single representative salary figure, use (salary_min + salary_max) / 2 "
        "unless the question specifically asks for the minimum or the maximum. "
        "Rare outliers exist up to ~SGD 250k-350k/month — a raw MAX() answer may "
        "reflect one outlier listing rather than a typical market rate; say so if "
        "reporting a MAX()."
    ),
    "salary_max": "Monthly SGD salary upper bound. See salary_min for conventions.",
    "employer_name": (
        "The company that POSTED the listing — this is frequently a recruitment "
        "or staffing agency, not the actual hiring company. See hiring_company_name."
    ),
    "hiring_company_name": (
        "The real end employer, populated only when is_posted_on_behalf is true "
        "(an agency posted on the employer's behalf); blank otherwise. For "
        "'which company is hiring' questions, use "
        "COALESCE(NULLIF(hiring_company_name, ''), employer_name) to report the "
        "real employer where known, falling back to the posting agency otherwise."
    ),
    "is_posted_on_behalf": "True when employer_name is an agency posting for a client — see hiring_company_name.",
    "region": (
        "Singapore's 5 planning regions (Central/East/North/North-East/West) "
        "PLUS 'Overseas' as one of its 7 distinct values — this table includes "
        "some non-Singapore-based listings even though the source (MyCareersFuture) "
        "is Singapore's national job portal. Never filter with "
        "LOWER(region) LIKE LOWER('%singapore%') — no column literally contains "
        "the word 'Singapore'. To exclude overseas postings specifically, filter "
        "is_overseas = false or region != 'Overseas', and only do this when the "
        "question distinguishes local vs. overseas, not just because it mentions "
        "'Singapore' generically."
    ),
    "is_overseas": "True if the role is based outside Singapore. See region.",
    "district": "Finer-grained location than region (29 Singapore districts + 'Overseas').",
    "lat": "Latitude; a value of 0 means unknown/missing, not a literal location — filter lat != 0 before geo math.",
    "lng": "Longitude; a value of 0 means unknown/missing, not a literal location — filter lng != 0 before geo math.",
    "number_of_vacancies": (
        "Each row is one job LISTING, which can represent more than one open "
        "position (values up to ~999). COUNT(*)/COUNT(DISTINCT uuid) counts "
        "listings; SUM(number_of_vacancies) counts actual open headcount. Default "
        "to counting listings unless the question specifically asks about "
        "headcount, vacancies, or openings."
    ),
    "skills_pipe": (
        "Pipe-delimited list of ALL extracted skills per listing (e.g. "
        "'Python|SQL|Java'). A single-skill search can use "
        "LOWER(skills_pipe) LIKE LOWER('%python%'), but to count or rank skills "
        "by frequency, split it first: "
        "..., UNNEST(SPLIT(skills_pipe, '|')) AS skill GROUP BY skill — a plain "
        "LIKE-based GROUP BY will not correctly rank individual skills."
    ),
    "key_skills_pipe": (
        "A smaller, curated subset of headline skills per listing (pipe-delimited), "
        "distinct from the fuller skills_pipe. Use when the question asks for the "
        "'key' or 'top' skills for a listing rather than the exhaustive list."
    ),
    "categories": "Pipe-delimited multi-value industry/category tags (e.g. 'Accounting|Auditing'). Use the same UNNEST(SPLIT(categories, '|')) pattern as skills_pipe when counting.",
    "employment_types": "Pipe-delimited multi-value field (e.g. 'Permanent|Contract'). Same UNNEST(SPLIT(...)) pattern applies when counting.",
    "position_levels": "Single-valued seniority level (Executive .. Senior Management) — safe to GROUP BY directly.",
    "min_years_experience": "Minimum years of experience required, as a plain integer.",
    "original_posting_date": (
        "Use this — not new_posting_date, which reflects batch scrape/refresh "
        "cycles rather than a listing's own history — for a listing's actual "
        "first-posted date."
    ),
    "status": "'Open' or 'Re-open' — this table only contains currently active listings; there is no 'Closed' status present.",
    "expiry_date": "Date the listing closes.",
    "description_text": "Plain-text job description. Prefer this over description_html, which carries the same content plus markup noise.",
    "total_views": "Page views for a single listing — an engagement metric, not a count of anything job-market-wide.",
    "total_applications": "Applications received on the portal for a single listing.",
    "employer_employee_count": "Employer's company size (number of employees); 0 means unknown.",
    "scraped_at": (
        "Ingestion timestamp. This table is a snapshot of currently active "
        "listings (all rows scraped within about a day of each other), not a "
        "historical archive spanning the posting-date range."
    ),
}

# Internal Singapore government classification codes present in the schema
# (occupation/education/industry). They exist in the table but are not
# human-readable and should not be used for filtering unless the question
# explicitly supplies a code.
CODE_COLUMNS_NOTE = (
    "ssoc_code, ssoc_version, occupation_id, ssec_eqa, ssec_fos, and employer_ssic "
    "are internal Singapore government classification codes (occupation / "
    "education / industry), not human-readable. Don't filter on these unless "
    "the question explicitly supplies a code — prefer title, categories, "
    "skills_pipe, position_levels, or min_years_experience instead."
)

# working_hours, other_requirements, and shift_pattern are always blank in
# this table; is_hide_salary and salary_type are effectively constant
# (always false / always "Monthly"). Not worth documenting individually, but
# worth telling the model not to bother with them.
NOISE_COLUMNS_NOTE = (
    "working_hours, other_requirements, and shift_pattern are always blank in "
    "this table — don't select or filter on them. is_hide_salary and "
    "salary_type are effectively constant (always false / always 'Monthly')."
)


def format_column_notes() -> str:
    lines = [f"- {col}: {note}" for col, note in COLUMN_NOTES.items()]
    lines.append(f"- {CODE_COLUMNS_NOTE}")
    lines.append(f"- {NOISE_COLUMNS_NOTE}")
    return "Column notes (things the raw schema above doesn't tell you):\n" + "\n".join(lines)


# (question, SQL template) pairs demonstrating the conventions above. Kept
# short and few in number on purpose — a handful of worked examples anchors
# an LLM's SQL conventions far more reliably than more prose rules do.
_FEW_SHOT_TEMPLATES = [
    (
        "What is the median monthly salary for Data Scientists in Singapore?",
        """SELECT APPROX_QUANTILES((salary_min + salary_max) / 2, 2)[OFFSET(1)] AS median_salary
FROM {full_table}
WHERE LOWER(title) LIKE LOWER('%data scientist%')""",
    ),
    (
        "What are the top 5 companies hiring for Software Engineers?",
        """SELECT
  COALESCE(NULLIF(hiring_company_name, ''), employer_name) AS company,
  COUNT(DISTINCT uuid) AS job_count
FROM {full_table}
WHERE LOWER(title) LIKE LOWER('%software engineer%')
GROUP BY company
ORDER BY job_count DESC
LIMIT 5""",
    ),
    (
        "What are the most in-demand skills for Data Analyst roles?",
        """SELECT skill, COUNT(DISTINCT uuid) AS listing_count
FROM {full_table}, UNNEST(SPLIT(skills_pipe, '|')) AS skill
WHERE LOWER(title) LIKE LOWER('%data analyst%')
GROUP BY skill
ORDER BY listing_count DESC
LIMIT 10""",
    ),
    (
        "How many Data Scientist jobs are based in Singapore, not overseas?",
        """SELECT COUNT(DISTINCT uuid) AS job_count
FROM {full_table}
WHERE LOWER(title) LIKE LOWER('%data scientist%')
  AND is_overseas = false""",
    ),
]


def format_few_shot_examples(full_table: str) -> str:
    blocks = []
    for question, sql_template in _FEW_SHOT_TEMPLATES:
        sql = sql_template.format(full_table=full_table)
        blocks.append(f"Q: {question}\nSQL:\n{sql}")
    return "Worked examples:\n" + "\n\n".join(blocks)
