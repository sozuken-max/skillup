import os
import json
import logging

from flask import Flask, request, jsonify
from google.cloud import bigquery
from openai import OpenAI

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# --- CORS ---
# app.js calls this service directly from the browser (skillup-3fc42.web.app),
# so the browser requires these headers on every response, including the
# preflight OPTIONS request, or it blocks the response before JS ever sees it.
ALLOWED_ORIGINS = {
    "https://skillup-3fc42.web.app",
    "https://skillup-3fc42.firebaseapp.com",
}


@app.after_request
def add_cors_headers(response):
    origin = request.headers.get("Origin", "")
    if origin in ALLOWED_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Api-Key, Authorization"
    return response


@app.route("/query", methods=["OPTIONS"])
def query_preflight():
    # Browsers send an OPTIONS request before the real POST, to ask permission.
    # This must return 200 with the CORS headers above (added by after_request),
    # and no body, or the browser cancels the actual POST that follows.
    return "", 200

# --- CONFIGURATION ---
PROJECT_ID = os.environ.get("BQ_PROJECT_ID", "")
DATASET_ID = os.environ.get("BQ_DATASET_ID", "")
TABLE_ID = os.environ.get("BQ_TABLE_ID", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o")
MAX_ROWS_RETURNED = int(os.environ.get("MAX_ROWS_RETURNED", "200"))
API_SHARED_SECRET = os.environ.get("API_SHARED_SECRET", "")

FULL_TABLE = f"`{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}`"

# Clients are created lazily, not at import time. This means importing
# main.py in a test file no longer requires real credentials or env vars.
_bq_client = None
_openai_client = None


def get_bq_client():
    global _bq_client
    if _bq_client is None:
        _bq_client = bigquery.Client(project=PROJECT_ID)
    return _bq_client


def get_openai_client():
    global _openai_client
    if _openai_client is None:
        _openai_client = OpenAI(api_key=OPENAI_API_KEY)
    return _openai_client


# --- PURE / TESTABLE FUNCTIONS ---
# These take plain inputs and return plain outputs, with no client creation
# and no network calls. This is what unit tests target directly.

def build_sql_prompt(question: str, schema: str, full_table: str = FULL_TABLE, max_rows: int = MAX_ROWS_RETURNED) -> str:
    return f"""You write BigQuery Standard SQL queries.

Table: {full_table}

Schema:
{schema}

Rules:
- Return ONLY the SQL query, no explanation, no markdown code fences.
- Use only SELECT statements. Never write INSERT, UPDATE, DELETE, DROP, MERGE, or DDL of any kind.
- Always include a LIMIT clause, maximum {max_rows} rows, unless the question asks for a count or aggregate.
- Reference the table using its fully qualified name exactly as given above.
- If the question mentions a company name, match it case-insensitively, e.g. using LOWER(column) = LOWER('value') or LOWER(column) LIKE LOWER('%value%').

Question: {question}

SQL query:"""


def clean_sql_response(raw_sql: str) -> str:
    """Strip markdown fences if the model adds them despite instructions."""
    sql = raw_sql.strip()
    if sql.startswith("```"):
        sql = sql.strip("`")
        sql = sql.replace("sql\n", "", 1) if sql.lower().startswith("sql\n") else sql
    return sql.strip()


def validate_sql_is_read_only(sql: str) -> None:
    """Raises ValueError if the SQL contains a write/DDL keyword or doesn't start with SELECT.
    This is defense in depth, not a substitute for BigQuery IAM permissions, which should
    be read-only for the service account regardless."""
    forbidden = ["insert", "update", "delete", "drop", "merge", "alter", "create", "truncate", "grant", "revoke"]
    lowered = sql.lower()
    for word in forbidden:
        if word in lowered.split() or f" {word} " in f" {lowered} ":
            raise ValueError(f"Generated SQL contains a disallowed keyword: {word}")
    if not lowered.strip().startswith("select"):
        raise ValueError("Generated SQL must start with SELECT")


def format_schema_from_fields(fields) -> str:
    """Takes an iterable of objects with .name and .field_type (matches BigQuery
    SchemaField, but any object with those two attributes works, real or fake)."""
    return "\n".join(f"- {field.name} ({field.field_type})" for field in fields)


# --- FUNCTIONS THAT TALK TO EXTERNAL SERVICES ---
# These are thin wrappers around the pure functions above, plus one client call each.
# Test these with a mocked client rather than pure unit tests.

def get_table_schema() -> str:
    table_ref = get_bq_client().dataset(DATASET_ID).table(TABLE_ID)
    table = get_bq_client().get_table(table_ref)
    return format_schema_from_fields(table.schema)


def generate_sql(question: str, schema: str) -> str:
    response = get_openai_client().chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": "You are a precise SQL generator. Output only valid BigQuery Standard SQL, nothing else."},
            {"role": "user", "content": build_sql_prompt(question, schema)},
        ],
        temperature=0,
    )
    return clean_sql_response(response.choices[0].message.content)


def run_query(sql: str) -> list[dict]:
    query_job = get_bq_client().query(sql)
    results = query_job.result()
    return [dict(row) for row in results]


def summarize_results(question: str, sql: str, rows: list[dict]) -> str:
    sample = rows[:50]
    response = get_openai_client().chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": "You answer questions using only the query results provided. Be concise and factual. If the results are empty, say so plainly."},
            {"role": "user", "content": f"Question: {question}\n\nSQL used: {sql}\n\nResults ({len(rows)} row(s), showing up to 50):\n{json.dumps(sample, default=str, indent=2)}\n\nAnswer the question in plain language."},
        ],
        temperature=0,
    )
    return response.choices[0].message.content.strip()


# --- ROUTES ---

@app.route("/query", methods=["POST"])
def query():
    provided_key = request.headers.get("X-Api-Key", "")
    if not API_SHARED_SECRET or provided_key != API_SHARED_SECRET:
        logger.warning("Rejected request with invalid or missing API key")
        return jsonify({"error": "Unauthorized"}), 401

    body = request.get_json(silent=True) or {}
    # app.js sends both "question" and "prompt" with the same value; accept either.
    question = (body.get("question") or body.get("prompt") or "").strip()

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
