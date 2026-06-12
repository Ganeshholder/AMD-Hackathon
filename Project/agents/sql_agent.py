"""
SQL agent — converts a natural language question into a SQLite SQL query.
Uses defog/sqlcoder-7b-2 via text_generation on Featherless AI provider.
"""

import re
from config.settings import TABLE_METADATA, SQL_MAX_NEW_TOKENS
from agents.llm_client import get_sql_client, generate


def _build_schema_ddl(tables: list[str]) -> str:
    """
    Build a DDL-style schema string — the format sqlcoder-7b-2 was trained on.
    Column comments make the model less likely to hallucinate JOINs.
    """
    lines = []
    for table in tables:
        if table not in TABLE_METADATA:
            continue
        info = TABLE_METADATA[table]
        col_defs = ",\n".join(
            f"    {col}  -- {desc}"
            for col, desc in info["columns"].items()
        )
        lines.append(
            f"-- {info['description']}\n"
            f"CREATE TABLE {table} (\n{col_defs}\n);"
        )
    return "\n\n".join(lines)


def _count_unquoted_parens(sql: str) -> tuple[int, int]:
    """Count ( and ) that are outside string literals."""
    opens = closes = 0
    in_str = False
    quote_char = None
    for ch in sql:
        if in_str:
            if ch == quote_char:
                in_str = False
        else:
            if ch in ("'", '"'):
                in_str = True
                quote_char = ch
            elif ch == "(":
                opens += 1
            elif ch == ")":
                closes += 1
    return opens, closes


def _balance_parens(sql: str) -> str:
    """
    Remove extra unmatched closing parens from the SQL string.
    Works by scanning left-to-right with a depth counter,
    marking any ')' that would go negative as removable.
    """
    chars = list(sql)
    depth = 0
    remove = set()
    in_str = False
    quote_char = None

    for i, ch in enumerate(chars):
        if in_str:
            if ch == quote_char:
                in_str = False
            continue
        if ch in ("'", '"'):
            in_str = True
            quote_char = ch
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            if depth == 0:
                remove.add(i)   # unmatched — mark for removal
            else:
                depth -= 1

    # Remove marked positions
    sql = "".join(ch for i, ch in enumerate(chars) if i not in remove)

    # If still unbalanced the other way (more opens), append closing parens
    opens, closes = _count_unquoted_parens(sql)
    if opens > closes:
        sql += ")" * (opens - closes)

    return sql


def _fix_sqlite_compat(sql: str) -> str:
    """
    Post-process the generated SQL to fix common model mistakes.

    Fixes applied in order:
    1. ILIKE  → LOWER(col) LIKE LOWER('val')
    2. col = 'string' or col == 'string' → LOWER(col) LIKE LOWER('%string%')
    3. Unicode comparison operators → ASCII (≥ → >=, ≤ → <=, ≠ → !=)
    4. PostgreSQL interval syntax → SQLite date() function
    5. Unbalanced parentheses
    """

    # Fix 1: ILIKE → LOWER LIKE LOWER
    sql = re.sub(
        r"([\w\.]+)\s+ILIKE\s+('[^']*')",
        lambda m: f"LOWER({m.group(1)}) LIKE LOWER({m.group(2)})",
        sql,
        flags=re.IGNORECASE,
    )

    # Fix 2: col = 'string' or col == 'string' → LOWER(col) LIKE LOWER('%string%')
    def _eq_to_like(m: re.Match) -> str:
        col   = m.group(1)
        val   = m.group(2)
        inner = val.strip("'\"")
        return f"LOWER({col}) LIKE LOWER('%{inner}%')"

    sql = re.sub(
        r"(?<!\w)([\w\.]+)\s*==?\s*('[^']*')",
        _eq_to_like,
        sql,
        flags=re.IGNORECASE,
    )

    # Fix 3: Unicode comparison operators → ASCII equivalents
    sql = sql.replace("≥", ">=").replace("≤", "<=").replace("≠", "!=").replace("→", "->")

    # Fix 4: PostgreSQL/MySQL interval syntax → SQLite date() function
    sql = re.sub(
        r"(?:CURRENT_DATE|CURRENT_TIMESTAMP|NOW\(\))\s*-\s*interval\s*'(\d+)\s*(year|years|month|months|day|days|hour|hours|week|weeks)'",
        lambda m: f"date('now', '-{m.group(1)} {m.group(2)}')",
        sql,
        flags=re.IGNORECASE,
    )
    sql = re.sub(
        r"DATEADD\s*\(\s*(\w+)\s*,\s*-(\d+)\s*,\s*(?:CURRENT_DATE|GETDATE\(\)|NOW\(\))\s*\)",
        lambda m: f"date('now', '-{m.group(2)} {m.group(1)}')",
        sql,
        flags=re.IGNORECASE,
    )

    # Fix 4b: strftime('%Y', column) where 'column' is a literal placeholder word
    # Detect the actual date column from the FROM clause and substitute it
    def _fix_strftime_placeholder(sql: str) -> str:
        # Find the first table referenced in FROM
        from_match = re.search(r"\bFROM\s+([\w]+)", sql, re.IGNORECASE)
        if not from_match:
            return sql
        # Guess the date column based on known table patterns
        table = from_match.group(1).lower()
        date_col_map = {
            "palo_alto_logs": "log_date",
            "transactions":   "created_at",
            "log_table":      "log_time",
        }
        date_col = date_col_map.get(table, "created_at")
        # Replace strftime('...', column) where column is literally the word 'column'
        sql = re.sub(
            r"(strftime\s*\(\s*'[^']+'\s*,\s*)\bcolumn\b",
            lambda m: f"{m.group(1)}{date_col}",
            sql,
            flags=re.IGNORECASE,
        )
        # Also fix date(column) literal
        sql = re.sub(
            r"\bdate\s*\(\s*column\s*\)",
            f"date({date_col})",
            sql,
            flags=re.IGNORECASE,
        )
        return sql

    sql = _fix_strftime_placeholder(sql)

    # Fix 5: EXTRACT(part FROM col) → strftime() for SQLite
    _EXTRACT_MAP = {
        "year": "%Y", "month": "%m", "day": "%d",
        "hour": "%H", "minute": "%M", "second": "%S",
    }
    def _extract_to_strftime(m: re.Match) -> str:
        part = m.group(1).lower()
        col  = m.group(2)
        fmt  = _EXTRACT_MAP.get(part, f"%{part[0]}")
        result = f"strftime('{fmt}', {col})"
        if part in ("year", "month", "day", "hour", "minute", "second"):
            result = f"CAST(strftime('{fmt}', {col}) AS INTEGER)"
        return result

    sql = re.sub(
        r"EXTRACT\s*\(\s*(\w+)\s+FROM\s+([\w\.]+)\s*\)",
        _extract_to_strftime,
        sql,
        flags=re.IGNORECASE,
    )

    # Fix 6: date_trunc('year', col)  → strftime('%Y', col)
    #         date_trunc('month', col) → strftime('%Y-%m', col)
    #         date_trunc('day', col)   → date(col)
    _TRUNC_MAP = {
        "year":    ("%Y",    False),
        "quarter": ("%Y",    False),   # approximate with year
        "month":   ("%Y-%m", False),
        "week":    ("%Y-%W", False),
        "day":     (None,    True),    # use date() directly
        "hour":    ("%Y-%m-%d %H", False),
    }
    def _date_trunc(m: re.Match) -> str:
        part = m.group(1).strip("'\"").lower()
        col  = m.group(2).strip()
        info = _TRUNC_MAP.get(part, ("%Y-%m-%d", False))
        fmt, use_date = info
        if use_date:
            return f"date({col})"
        return f"strftime('{fmt}', {col})"

    sql = re.sub(
        r"date_trunc\s*\(\s*('[^']*'|\"[^\"]*\")\s*,\s*([\w\.]+)\s*\)",
        _date_trunc,
        sql,
        flags=re.IGNORECASE,
    )

    # Fix 7: DATE_FORMAT(col, fmt) → strftime(fmt, col)
    sql = re.sub(
        r"DATE_FORMAT\s*\(\s*([\w\.]+)\s*,\s*('[^']*')\s*\)",
        lambda m: f"strftime({m.group(2)}, {m.group(1)})",
        sql,
        flags=re.IGNORECASE,
    )

    # Fix 8: TO_CHAR(col, fmt) → strftime(fmt, col)
    sql = re.sub(
        r"TO_CHAR\s*\(\s*([\w\.]+)\s*,\s*('[^']*')\s*\)",
        lambda m: f"strftime({m.group(2)}, {m.group(1)})",
        sql,
        flags=re.IGNORECASE,
    )

    # Fix 9: NULLS LAST / NULLS FIRST — not supported in SQLite, just remove
    sql = re.sub(r"\s+NULLS\s+(?:LAST|FIRST)", "", sql, flags=re.IGNORECASE)

    # Fix 10: Balance parentheses
    sql = _balance_parens(sql)

    return sql


def _extract_sql(raw: str) -> str:
    """Strip markdown fences and extract the SELECT statement."""
    raw = re.sub(r"```(?:sql)?", "", raw, flags=re.IGNORECASE).strip("`").strip()
    match = re.search(r"(SELECT\b.*?)(?:;|$)", raw, re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).strip()
    return raw.strip()


def generate_sql(question: str, tables: list[str]) -> str:
    """
    Generate a SQLite SQL query for the question using only the given tables.

    Uses sqlcoder's recommended prompt format:
    ### Task / ### Database Schema / ### Answer

    Args:
        question: Natural language question.
        tables: Table names to include in the schema context.

    Returns:
        A SQLite-compatible SQL query string.
    """
    schema_ddl = _build_schema_ddl(tables)

    prompt = f"""### Task
Generate a SQLite3 SQL query to answer the following question.
You MUST generate valid SQLite3 syntax ONLY — not PostgreSQL, MySQL, or any other dialect.

STRICT RULES:
1. Use ONLY the tables and columns defined in the schema below.
2. Do NOT use ILIKE — use LOWER(col) LIKE LOWER('%val%') instead.
3. ALL text WHERE comparisons MUST use: LOWER(column) LIKE LOWER('%value%')
   NEVER use = or == for text columns in WHERE.
4. If a column comment says "NOT a foreign key", treat it as plain text — do NOT JOIN on it.
5. Use only ASCII operators: >= <= != > < =   NEVER use: ≥ ≤ ≠
6. Do NOT use NULLS LAST or NULLS FIRST — not supported in SQLite3.

SQLite3 DATE FUNCTIONS (use ONLY these):
  - Current date:      date('now')
  - Current datetime:  datetime('now')
  - Last N days:       date('now', '-N days')      e.g. date('now', '-30 days')
  - Last N months:     date('now', '-N months')    e.g. date('now', '-6 months')
  - Last N years:      date('now', '-N years')     e.g. date('now', '-1 years')
  - Extract year:      strftime('%Y', <col_name>)  e.g. strftime('%Y', log_date)
  - Extract month:     strftime('%m', <col_name>)  e.g. strftime('%m', log_date)
  - Extract day:       strftime('%d', <col_name>)  e.g. strftime('%d', log_date)
  - Truncate to year:  strftime('%Y', <col_name>)
  - Truncate to month: strftime('%Y-%m', <col_name>)
  - Truncate to day:   date(<col_name>)
  IMPORTANT: Replace <col_name> with the ACTUAL column name from the schema — never write the word "column".

FORBIDDEN functions (do NOT use these — they are NOT in SQLite3):
  EXTRACT(), date_trunc(), DATE_FORMAT(), TO_CHAR(), NOW(), GETDATE(),
  DATE_ADD(), DATE_SUB(), DATEADD(), DATEDIFF(), interval keyword,
  YEAR(), MONTH(), DAY(), HOUR(), TO_DATE(), CONVERT(), COALESCE is OK.

### Database Schema
{schema_ddl}

### Answer
Given the database schema, here is the SQLite3 SQL query that answers [QUESTION]{question}[/QUESTION]
[SQL]"""

    raw = generate(
        client=get_sql_client(),
        prompt=prompt,
        max_new_tokens=SQL_MAX_NEW_TOKENS,
        temperature=0.0,
    )
    sql = _extract_sql(raw)
    sql = _fix_sqlite_compat(sql)
    return sql
