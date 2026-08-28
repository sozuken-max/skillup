# Test file for main API run for mcf_jobs queries.
import os
import json
import logging

from flask import Flask, request, jsonify
from google.cloud import bigquery
from openai import OpenAI

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# --- CONFIGURATION (set these as environment variables on Cloud Run) ---
PROJECT_ID = os.environ["BQ_PROJECT_ID"]          # e.g. "skillup-506706"
DATASET_ID = os.environ["BQ_DATASET_ID"]          # e.g. "databricks_mcf_jobs"
TABLE_ID = os.environ["BQ_TABLE_ID"]              # e.g. "mcf_jobs"
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o")
MAX_ROWS_RETURNED = int(os.environ.get("MAX_ROWS_RETURNED", "200"))

bq_client = bigquery.Client(project=PROJECT_ID)
openai_client = OpenAI(api_key=OPENAI_API_KEY)

FULL_TABLE = f"`{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}`"


def get_table_schema() -> str:
    """Fetch column names and types from BigQuery so the LLM knows what it can query."""
    table_ref = bq_client.dataset(DATASET_ID).table(TABLE_ID)
    table = bq_client.get_table(table_ref)
    lines = [f"- {field.name} ({field.field_type})" for field in table.schema]
    return "\n".join(lines)


def build_sql_prompt(question: str, schema: str) -> str:
    return f"""You write BigQuery Standard SQL queries.

Table: {FULL_TABLE}

Schema:
{schema}

Rules:
- Return ONLY the SQL query, no explanation, no markdown code fences.
- Use only SELECT statements. Never write INSERT, UPDATE, DELETE, DROP, MERGE, or DDL of any kind.
- Always include a LIMIT clause, maximum {MAX_ROWS_RETURNED} rows, unless the question asks for a count or aggregate.
- Reference the table using its fully qualified name exactly as given above.
- If the question mentions a company name, match it case-insensitively, e.g. using LOWER(column) = LOWER('value') or LOWER(column) LIKE LOWER('%value%').

Question: {question}

SQL query:"""


def generate_sql(question: str, schema: str) -> str:
    response = openai_client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": "You are a precise SQL generator. Output only valid BigQuery Standard SQL, nothing else."},
            {"role": "user", "content": build_sql_prompt(question, schema)},
        ],
        temperature=0,
    )
    sql = response.choices[0].message.content.strip()
    if sql.startswith("```"):
        sql = sql.strip("`")
        sql = sql.replace("sql\n", "", 1) if sql.lower().startswith("sql\n") else sql
    return sql.strip()


def validate_sql_is_read_only(sql: str) -> None:
    """Basic guardrail. This is defense in depth, not a substitute for BigQuery
    IAM permissions, which should be read-only for the service account regardless."""
    forbidden = ["insert", "update", "delete", "drop", "merge", "alter", "create", "truncate", "grant", "revoke"]
    lowered = sql.lower()
    for word in forbidden:
        if word in lowered.split() or f" {word} " in f" {lowered} ":
            raise ValueError(f"Generated SQL contains a disallowed keyword: {word}")
    if not lowered.strip().startswith("select"):
        raise ValueError("Generated SQL must start with SELECT")


def run_query(sql: str) -> list[dict]:
    query_job = bq_client.query(sql)
    results = query_job.result()
    rows = [dict(row) for row in results]
    return rows


def summarize_results(question: str, sql: str, rows: list[dict]) -> str:
    """Ask the LLM to turn the raw rows into a short natural language answer."""
    sample = rows[:50]
    response = openai_client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": "You answer questions using only the query results provided. Be concise and factual. If the results are empty, say so plainly."},
            {"role": "user", "content": f"Question: {question}\n\nSQL used: {sql}\n\nResults ({len(rows)} row(s), showing up to 50):\n{json.dumps(sample, default=str, indent=2)}\n\nAnswer the question in plain language."},
        ],
        temperature=0,
    )
    return response.choices[0].message.content.strip()


@app.route("/query", methods=["POST"])
def query():
    body = request.get_json(silent=True) or {}
    question = body.get("question", "").strip()

    if not question:
        return jsonify({"error": "Request body must include a 'question' field"}), 400

    try:
        schema = get_table_schema()
        sql = generate_sql(question, schema)
        validate_sql_is_read_only(sql)
        rows = run_query(sql)
        answer = summarize_results(question, sql, rows)

        return jsonify({
            "question": question,
            "sql": sql,
            "row_count": len(rows),
            "rows": rows[:MAX_ROWS_RETURNED],
            "answer": answer,
        })

    except ValueError as e:
        logger.warning(f"Rejected query: {e}")
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.exception("Query failed")
        return jsonify({"error": "Internal error processing query", "detail": str(e)}), 500


@app.route("/healthz", methods=["GET"])
def healthz():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
