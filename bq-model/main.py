import os
import json
import logging

import numpy as np
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

# Prefix the SQL-generation model uses to signal "no query needed, this is
# the direct reply" instead of SQL. Keeps chit-chat turns (greetings,
# thanks, reactions to a previous answer) to a single LLM call with no
# BigQuery round trip, instead of always running the full generate-SQL ->
# execute -> summarize pipeline regardless of whether the message needs it.
REPLY_PREFIX = "REPLY:"

FULL_TABLE = f"`{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}`"

# --- SEMANTIC ROLE-TITLE SEARCH ---
# `title` in the jobs table is free-text scraped from job posts, so a user
# asking for e.g. "data science engineer" can get zero rows via LIKE even
# though the dataset only ever uses a different exact phrase for that role.
# This table holds one pre-computed embedding per canonical role title
# (all-MiniLM-L6-v2, 384-dim, L2-normalized); we embed the user's phrase the
# same way and rank by cosine similarity (a dot product, since both sides are
# normalized) instead of relying on the SQL-generation model to guess the
# dataset's exact wording.
#
# Embedding runs through fastembed's ONNX export of this model rather than
# the original sentence-transformers/PyTorch one. Same weights and tokenizer,
# so the vectors it produces are compatible with the ones already stored in
# the table (nearest-neighbour ranking is unaffected by the runtime swap),
# but without pulling in torch — cuts several hundred MB and a slower import
# off the image for a single small ONNX model.
ROLE_EMBEDDINGS_TABLE = os.environ.get(
    "ROLE_EMBEDDINGS_TABLE", "skillup-506706.databricks_mcf_jobs.mcf_role_embeddings"
)
EMBEDDING_MODEL_NAME = os.environ.get("EMBEDDING_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2")
# Must match the cache_dir the Dockerfile pre-downloads the model weights into
# at build time (see get_embedding_model() below) — otherwise the first
# semantic-search request on a fresh container fetches ~80MB from Hugging
# Face over the network inside the request itself, which is slow enough to
# blow through the request timeout on its own.
EMBEDDING_CACHE_DIR = os.environ.get("EMBEDDING_CACHE_DIR", "/app/model_cache")
EMBEDDING_DIMS = 384
SEMANTIC_TOP_K = 5

# Clients are created lazily, not at import time. This means importing
# main.py in a test file no longer requires real credentials or env vars.
_bq_client = None
_openai_client = None
_embedding_model = None
_role_embeddings_cache = None  # (meta: list[dict], matrix: np.ndarray), see get_role_embeddings()


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


def get_embedding_model():
    """Loads the ONNX-runtime embedding model from the local cache the
    Dockerfile pre-populated at build time (see EMBEDDING_CACHE_DIR) — no
    network call at request time. Import is inside the function rather than
    at module level purely so a process that never needs semantic search
    doesn't pay for importing fastembed."""
    global _embedding_model
    if _embedding_model is None:
        from fastembed import TextEmbedding
        _embedding_model = TextEmbedding(model_name=EMBEDDING_MODEL_NAME, cache_dir=EMBEDDING_CACHE_DIR)
    return _embedding_model


def get_role_embeddings():
    """Fetches and caches the full role-embeddings table in memory (a few
    thousand rows x 384 floats - a few MB), so each semantic search after the
    first is a local numpy operation rather than a fresh BigQuery round trip."""
    global _role_embeddings_cache
    if _role_embeddings_cache is None:
        dim_cols = ", ".join(f"dim_{i}" for i in range(EMBEDDING_DIMS))
        query = f"SELECT title, primary_category, job_count, context_text, {dim_cols} FROM `{ROLE_EMBEDDINGS_TABLE}`"
        rows = list(get_bq_client().query(query).result())
        meta = [
            {
                "title": row["title"],
                "primary_category": row["primary_category"],
                "job_count": row["job_count"],
                "context_text": row["context_text"],
            }
            for row in rows
        ]
        matrix = np.array(
            [[row[f"dim_{i}"] for i in range(EMBEDDING_DIMS)] for row in rows],
            dtype=np.float32,
        )
        _role_embeddings_cache = (meta, matrix)
    return _role_embeddings_cache


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


def top_k_similar(query_vector: np.ndarray, matrix: np.ndarray, meta: list[dict], k: int = SEMANTIC_TOP_K) -> list[dict]:
    """Returns the k entries of `meta` whose embedding row is most similar to
    query_vector, each annotated with a "score" (cosine similarity). Both
    query_vector and the rows of matrix are assumed L2-normalized already, so
    similarity is a plain dot product rather than needing norms divided out."""
    scores = matrix @ query_vector
    top_indices = np.argsort(scores)[::-1][:k]
    return [{**meta[i], "score": float(scores[i])} for i in top_indices]


def build_sql_prompt(question: str, schema: str, full_table: str = FULL_TABLE, max_rows: int = MAX_ROWS_RETURNED, broaden: bool = False, history: list[dict] | None = None, resolved_titles: list[str] | None = None) -> str:
    broaden_instruction = ""
    if broaden:
        broaden_instruction = """
IMPORTANT: A previous, more specific version of this query returned zero rows.
Write a broader query this time:
- Use LIKE '%keyword%' instead of exact equality for any name, title, or category match.
- Match on partial keywords rather than the full phrase (e.g. for "data scientist", also consider matching just "data" or "scientist" separately with OR).
- Drop the least essential filter condition if the question has more than one (keep the one most central to the question).
"""

    resolved_titles_instruction = ""
    if resolved_titles:
        titles_list = "\n".join(f'  - "{t}"' for t in resolved_titles)
        resolved_titles_instruction = f"""
IMPORTANT: A semantic search has already resolved the role the user is asking about to these exact title(s) as they appear in the data:
{titles_list}
Build the title filter using ONLY these exact title(s) — LOWER(title) LIKE LOWER('%<title>%') for each, combined with OR if there is more than one — instead of the user's own phrasing.
"""

    history_block = format_history_block(history)
    column_notes = format_column_notes()
    few_shot_examples = format_few_shot_examples(full_table)

    # Static content (schema, column notes, examples, rules) comes first and
    # is identical across requests; dynamic content (broaden retry flag,
    # conversation history, the question itself) comes last. This ordering
    # lets providers that support prompt caching reuse the static prefix
    # across requests instead of reprocessing it every time.
    return f"""You are Mya, a Singapore job-market assistant backed by a BigQuery jobs table. For each message, first decide whether answering it requires querying that table for factual data (specific numbers, listings, companies, skills, salaries, counts, comparisons). If the message is a greeting, thanks, small talk, a reaction or opinion about something already discussed (e.g. "wow that's high", "nice", "thank you"), a meta question about you as an assistant, or otherwise doesn't need fresh data from the table, do NOT write SQL — respond directly instead by outputting a line starting with `{REPLY_PREFIX}` followed by a short, warm, natural-language reply in your own voice as Mya. When it fits naturally, suggest one or two follow-up questions the user could ask about Singapore's job market (salaries, skills, hiring trends) to keep the conversation useful — but don't force this onto simple greetings or thanks where it would feel out of place.

If a query genuinely IS needed, output ONLY the SQL query as specified in the rules below — no `{REPLY_PREFIX}` prefix, no explanation, no markdown code fences.

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
{broaden_instruction}{resolved_titles_instruction}
{history_block}Question: {question}

SQL query or {REPLY_PREFIX}:"""


def clean_sql_response(raw_sql: str) -> str:
    """Strip markdown fences and any leading comment/blank lines the model
    adds despite being told not to explain itself. Without this, a stray
    leading "-- comment" line makes validate_sql_is_read_only's startswith
    check fail deterministically (same input, same output at temperature=0),
    so a client-side retry alone would never recover from it."""
    sql = raw_sql.strip()
    if sql.startswith("```"):
        sql = sql.strip("`")
        sql = sql.replace("sql\n", "", 1) if sql.lower().startswith("sql\n") else sql
    sql = sql.strip()

    lines = sql.split("\n")
    while lines and (not lines[0].strip() or lines[0].strip().startswith("--")):
        lines.pop(0)
    return "\n".join(lines).strip()


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


def generate_sql_or_reply(question: str, schema: str, model: str = OPENAI_MODEL, broaden: bool = False, history: list[dict] | None = None, resolved_titles: list[str] | None = None) -> tuple[str | None, str | None]:
    """Returns (sql, direct_reply) with exactly one of the two set.

    A single model call decides whether the question needs a BigQuery query
    at all before generating anything — this is what lets a message like
    "Hi there" skip SQL generation, execution, and summarization entirely
    instead of always running the full three-call pipeline.
    """
    response = get_openai_client().chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": f"You are a precise SQL generator that also knows when SQL isn't needed. Output only valid BigQuery Standard SQL, or a single line starting with '{REPLY_PREFIX}' — nothing else."},
            {"role": "user", "content": build_sql_prompt(question, schema, broaden=broaden, history=history, resolved_titles=resolved_titles)},
        ],
        temperature=0,
    )
    raw = response.choices[0].message.content.strip()
    if raw[:len(REPLY_PREFIX)].upper() == REPLY_PREFIX.upper():
        return None, raw[len(REPLY_PREFIX):].strip()
    return clean_sql_response(raw), None


def extract_job_title_query(question: str, model: str = OPENAI_MODEL, history: list[dict] | None = None) -> str | None:
    """Asks the LLM whether answering this question requires filtering the
    jobs table on a specific job title/role, and if so, what that role is.
    Returns None for questions that don't hinge on a specific title (greetings,
    aggregate questions about the whole market, questions already resolved by
    conversation history into something other than a title, etc.) — those skip
    semantic search entirely and go straight to normal SQL generation."""
    history_block = format_history_block(history)
    prompt = f"""{history_block}Question: {question}

Does answering this question require finding jobs with a specific job title or role (e.g. "data science engineer", "product manager")? Only answer yes if the question is about a particular role, not jobs/the market in general. If yes, reply with ONLY that role/title phrase, in plain English, as close to the user's own wording as possible (resolve "those jobs"/"that role" etc. using the conversation above if needed). If no, reply with exactly: NONE"""
    response = get_openai_client().chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You extract the job title/role a question is asking about, or say NONE. Reply with only the title phrase or the word NONE — nothing else."},
            {"role": "user", "content": prompt},
        ],
        temperature=0,
    )
    raw = response.choices[0].message.content.strip().strip('"')
    if not raw or raw.upper() == "NONE":
        return None
    return raw


def semantic_search_titles(phrase: str, k: int = SEMANTIC_TOP_K) -> list[dict]:
    """Embeds `phrase` with the same model weights used to build the
    reference table (fastembed returns L2-normalized vectors already), then
    returns the k most similar canonical role rows."""
    meta, matrix = get_role_embeddings()
    query_vector = next(iter(get_embedding_model().embed([phrase])))
    return top_k_similar(np.asarray(query_vector, dtype=np.float32), matrix, meta, k=k)


def rationalize_semantic_matches(question: str, extracted_title: str, candidates: list[dict], model: str = OPENAI_MODEL) -> list[str]:
    """Given the top-K semantically similar canonical titles, asks the LLM
    which of them (if any) actually mean the same role the user is asking
    about — nearest-neighbour by embedding distance is not always a correct
    match (e.g. "data engineer" and "data science engineer" can rank close
    together without being interchangeable). Returns the confirmed titles,
    exactly as given, in the model's stated order of relevance; empty if none
    of the candidates are a genuine match."""
    listing = "\n".join(
        f'{i + 1}. "{c["title"]}" (category: {c["primary_category"]}, {c["job_count"]} jobs) — {c["context_text"]}'
        for i, c in enumerate(candidates)
    )
    prompt = f"""A user asked about the role "{extracted_title}" (from the question: "{question}").

Here are the {len(candidates)} closest canonical role titles found by embedding similarity search:
{listing}

Which of these titles genuinely refer to the same role the user means? A high similarity score alone isn't proof — only include a title if it is a real match, not just a related-but-different role. Reply with a comma-separated list of the matching titles, copied EXACTLY as given above (same wording and capitalization), in order of relevance. If none of them are a real match, reply with exactly: NONE"""
    response = get_openai_client().chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You judge whether candidate job titles match a user's intent. Reply with only a comma-separated list of exact matching titles from the list given, or NONE."},
            {"role": "user", "content": prompt},
        ],
        temperature=0,
    )
    raw = response.choices[0].message.content.strip()
    if not raw or raw.upper() == "NONE":
        return []
    candidate_titles = {c["title"] for c in candidates}
    confirmed = []
    for part in raw.split(","):
        title = part.strip().strip('"')
        if title in candidate_titles and title not in confirmed:
            confirmed.append(title)
    return confirmed


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

            # Before writing SQL, check whether this question hinges on a
            # specific job title/role. If so, resolve the user's own phrasing
            # to the exact title(s) present in the data via embedding
            # similarity, rather than letting the SQL-generation model guess
            # the dataset's wording with a LIKE match that may return nothing.
            resolved_titles = None
            try:
                extracted_title = extract_job_title_query(question, model=requested_model, history=history)
            except Exception:
                logger.exception("Role-title extraction failed; continuing without semantic search")
                extracted_title = None

            if extracted_title:
                yield json.dumps({"stage": "semantic_search", "query_title": extracted_title}) + "\n"
                try:
                    candidates = semantic_search_titles(extracted_title)
                    yield json.dumps({
                        "stage": "semantic_search_results",
                        "query_title": extracted_title,
                        "candidates": [{"title": c["title"], "score": round(c["score"], 4)} for c in candidates],
                    }) + "\n"

                    confirmed_titles = rationalize_semantic_matches(question, extracted_title, candidates, model=requested_model)
                    yield json.dumps({"stage": "semantic_search_confirmed", "titles": confirmed_titles}) + "\n"
                    if confirmed_titles:
                        resolved_titles = confirmed_titles
                except Exception as e:
                    logger.exception("Semantic title search failed; falling back to plain LIKE matching")
                    yield json.dumps({"stage": "semantic_search_error", "error": str(e)}) + "\n"

            sql, direct_reply = generate_sql_or_reply(question, schema, model=requested_model, history=history, resolved_titles=resolved_titles)

            if direct_reply is not None:
                # No query needed (greeting, thanks, a reaction to a prior
                # answer, etc.) — skip BigQuery and summarization entirely.
                yield json.dumps({
                    "stage": "done",
                    "question": question,
                    "sql": None,
                    "row_count": 0,
                    "rows": [],
                    "answer": direct_reply,
                    "broadened": False,
                }) + "\n"
                return

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
                sql_broad, _ = generate_sql_or_reply(question, schema, model=requested_model, broaden=True, history=history)
                if sql_broad:
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


# Warm the embedding model and role-embeddings cache once, at process start,
# rather than lazily on the first live request. Without this, the first user
# to trigger semantic search on a freshly started container pays for loading
# the ONNX model AND fetching the embeddings table from BigQuery inside their
# own request — on top of the two LLM calls the semantic-search stage already
# makes, that's often enough to blow through the request timeout. Wrapped in
# try/except (rather than left to crash worker boot) so a transient BigQuery
# hiccup at startup doesn't take the whole container down; get_embedding_model()
# / get_role_embeddings() still work lazily on first use if this fails or is
# skipped (e.g. when main.py is imported without real credentials, such as in
# a test).
try:
    get_embedding_model()
    get_role_embeddings()
except Exception:
    logger.exception("Startup warm-up of semantic search failed; will load lazily on first request instead")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
