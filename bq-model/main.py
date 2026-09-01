import os
import json
import logging

from flask import Flask, request, jsonify, Response, stream_with_context
from google.cloud import bigquery
from openai import OpenAI

from schema_glossary import format_column_notes, format_few_shot_examples

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

# Models the front end is allowed to request via the "model" field.
# Access control for this endpoint is Origin-based (see query() below), not
# a shared secret, so this allowlist is what stops an arbitrary/expensive
# model string from being passed straight through to the OpenAI API.
ALLOWED_OPENAI_MODELS = {"gpt-4o", "gpt-4o-mini"}

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

def format_history_block(history: list[dict] | None, max_messages: int = 12, max_chars_per_message: int = 800) -> str:
    """Renders prior conversation turns as a text block for prompt context.
    Applies its own caps regardless of what the caller already trimmed to,
    since a verbose front-end message (e.g. one containing a prior SQL
    block) could otherwise dominate the prompt's token budget."""
    if not history:
        return ""
    lines = []
    for turn in history[-max_messages:]:
        if not isinstance(turn, dict):
            continue
        content = str(turn.get("content") or "").strip()
        if not content:
            continue
        if len(content) > max_chars_per_message:
            content = content[:max_chars_per_message] + "... [truncated]"
        role = "User" if turn.get("role") == "user" else "Assistant"
        lines.append(f"{role}: {content}")
    if not lines:
        return ""
    return "Conversation so far (most recent last):\n" + "\n".join(lines) + "\n\n"


def build_sql_prompt(question: str, schema: str, full_table: str = FULL_TABLE, max_rows: int = MAX_ROWS_RETURNED, broaden: bool = False, history: list[dict] | None = None) -> str:
    broaden_instruction = ""
    if broaden:
        broaden_instruction = """
IMPORTANT: A previous, more specific version of this query returned zero rows.
Write a broader query this time:
- Use LIKE '%keyword%' instead of exact equality for any name, title, or category match.
- Match on partial keywords rather than the full phrase (e.g. for "data scientist", also consider matching just "data" or "scientist" separately with OR).
- Drop the least essential filter condition if the question has more than one (keep the one most central to the question).
"""

    history_block = format_history_block(history)
    column_notes = format_column_notes()
    few_shot_examples = format_few_shot_examples(full_table)

    # Static content (schema, column notes, examples, rules) comes first and
    # is identical across requests; dynamic content (broaden retry flag,
    # conversation history, the question itself) comes last. This ordering
    # lets providers that support prompt caching reuse the static prefix
    # across requests instead of reprocessing it every time.
    return f"""You write BigQuery Standard SQL queries.

Table: {full_table}

Schema:
{schema}

{column_notes}

{few_shot_examples}

Rules:
- Return ONLY the SQL query, no explanation, no markdown code fences.
- Use only SELECT statements. Never write INSERT, UPDATE, DELETE, DROP, MERGE, or DDL of any kind.
- Select only the specific columns needed to answer the question. Never use SELECT *.
- Always include a LIMIT clause, maximum {max_rows} rows, unless the question asks for a count or aggregate.
- Reference the table using its fully qualified name exactly as given above.
- For company names, job titles, and any other free-text fields, always use LOWER(column) LIKE LOWER('%value%'). Never use exact equality (=) for text fields, since real-world data has inconsistent naming, abbreviations, and suffixes (e.g. "TikTok" may be stored as "TikTok Pte. Ltd." or "ByteDance").
- If the question is vague or does not specify what to look for, select a small number of representative rows (5-10) with only the most relevant columns, rather than the full table.
- If the question refers back to the conversation history provided (e.g. "those jobs", "that company", "the same roles"), resolve the reference using it and carry over any filters it implies (e.g. a job title or role type mentioned earlier), unless the new question clearly changes topic.
{broaden_instruction}
{history_block}Question: {question}

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


def generate_sql(question: str, schema: str, model: str = OPENAI_MODEL, broaden: bool = False, history: list[dict] | None = None) -> str:
    response = get_openai_client().chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are a precise SQL generator. Output only valid BigQuery Standard SQL, nothing else."},
            {"role": "user", "content": build_sql_prompt(question, schema, broaden=broaden, history=history)},
        ],
        temperature=0,
    )
    return clean_sql_response(response.choices[0].message.content)


def run_query(sql: str) -> list[dict]:
    query_job = get_bq_client().query(sql)
    results = query_job.result()
    return [dict(row) for row in results]


def truncate_row_values(row: dict, max_chars: int = 300) -> dict:
    """Caps any single field's string length before sending rows to the LLM.
    Prevents one verbose text column (e.g. a long pipe-separated skills list)
    from consuming a disproportionate share of the token budget."""
    truncated = {}
    for key, value in row.items():
        if isinstance(value, str) and len(value) > max_chars:
            truncated[key] = value[:max_chars] + "... [truncated]"
        else:
            truncated[key] = value
    return truncated


def summarize_results(question: str, sql: str, rows: list[dict], model: str = OPENAI_MODEL, history: list[dict] | None = None) -> str:
    # Cap both row count and per-field length, since a single row with several
    # verbose text columns can be as large as tens of ordinary rows.
    sample = [truncate_row_values(row) for row in rows[:10]]
    history_block = format_history_block(history)
    response = get_openai_client().chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You answer questions using the query results provided, using the prior conversation only to understand what is being asked (e.g. what \"those\" or \"that\" refers to). Be concise and factual. If the results are empty, say so plainly."},
            {"role": "user", "content": f"{history_block}Question: {question}\n\nSQL used: {sql}\n\nResults ({len(rows)} row(s) total, showing up to 10, long text fields truncated):\n{json.dumps(sample, default=str, indent=2)}\n\nAnswer the question in plain language."},
        ],
        temperature=0,
    )
    return response.choices[0].message.content.strip()


# --- ROUTES ---

@app.route("/query", methods=["POST"])
def query():
    # Access control is Origin-based rather than a shared secret: only
    # requests carrying one of the allowed front-end origins are served.
    # Note this is enforced the same way the CORS headers above are — it
    # stops browsers from completing cross-origin calls, but an Origin
    # header can be forged by a non-browser client. It is not a substitute
    # for real auth if this endpoint ever needs to resist a targeted caller.
    origin = request.headers.get("Origin", "")
    if origin not in ALLOWED_ORIGINS:
        logger.warning(f"Rejected request from disallowed origin: {origin!r}")
        return jsonify({"error": "Forbidden"}), 403

    body = request.get_json(silent=True) or {}
    # app.js sends both "question" and "prompt" with the same value; accept either.
    question = (body.get("question") or body.get("prompt") or "").strip()
    requested_model = body.get("model") or OPENAI_MODEL

    # app.js sends the same conversation as "history", "messages", and "context"
    # in different shapes; "history" (a list of {"role", "content"} turns, not
    # including the current question) is the one we actually use. Sanitized here
    # rather than trusted as-is, since it comes straight from the client.
    history = []
    for turn in (body.get("history") or []):
        if isinstance(turn, dict) and isinstance(turn.get("content"), str):
            role = turn.get("role") if turn.get("role") in ("user", "assistant") else "assistant"
            history.append({"role": role, "content": turn["content"]})

    if not question:
        return jsonify({"error": "Request body must include a 'question' field"}), 400
    if requested_model not in ALLOWED_OPENAI_MODELS:
        return jsonify({"error": f"Unsupported model: {requested_model}"}), 400

    def generate_events():
        # Streamed as newline-delimited JSON so the front end can render
        # each stage (generating SQL, running it, summarizing) as it
        # happens instead of waiting on one final response. Because the
        # HTTP status is already committed to 200 once streaming starts,
        # failures are reported as a {"stage": "error"} event rather than
        # an HTTP error status — the front end must check for that stage.
        try:
            yield json.dumps({"stage": "generating_sql"}) + "\n"
            schema = get_table_schema()
            sql = generate_sql(question, schema, model=requested_model, history=history)
            validate_sql_is_read_only(sql)
            yield json.dumps({"stage": "sql_generated", "sql": sql}) + "\n"

            yield json.dumps({"stage": "running_query"}) + "\n"
            rows = run_query(sql)

            # If the specific query found nothing, automatically retry once with a
            # broader query rather than reporting "no data" on what may just be a
            # too-narrow match (e.g. exact company name mismatch).
            broadened = False
            if not rows:
                logger.info("Initial query returned 0 rows, retrying with a broadened query")
                yield json.dumps({"stage": "broadening"}) + "\n"
                sql_broad = generate_sql(question, schema, model=requested_model, broaden=True, history=history)
                validate_sql_is_read_only(sql_broad)
                rows_broad = run_query(sql_broad)
                if rows_broad:
                    sql = sql_broad
                    rows = rows_broad
                    broadened = True
                    yield json.dumps({"stage": "sql_generated", "sql": sql}) + "\n"

            yield json.dumps({"stage": "summarizing"}) + "\n"
            answer = summarize_results(question, sql, rows, model=requested_model, history=history)
            if broadened:
                answer += "\n\n*Note: no exact match was found, so this used a broader search.*"

            yield json.dumps({
                "stage": "done",
                "question": question,
                "sql": sql,
                "row_count": len(rows),
                "rows": rows[:MAX_ROWS_RETURNED],
                "answer": answer,
                "broadened": broadened,
            }) + "\n"

        except ValueError as e:
            logger.warning(f"Rejected query: {e}")
            yield json.dumps({"stage": "error", "error": str(e)}) + "\n"
        except Exception as e:
            logger.exception("Query failed")
            yield json.dumps({"stage": "error", "error": "Internal error processing query", "detail": str(e)}) + "\n"

    response = Response(stream_with_context(generate_events()), mimetype="application/x-ndjson")
    response.headers["X-Accel-Buffering"] = "no"
    return response


@app.route("/status", methods=["GET"])
def status():
    # Not named /healthz on purpose: Cloud Run's own infrastructure
    # intercepts requests to that exact path for its internal probing and
    # never forwards them to this container, so a public health check
    # against /healthz can never succeed regardless of what this app does.
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
