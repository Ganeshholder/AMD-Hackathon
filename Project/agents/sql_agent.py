"""
SQL agent — converts a natural language question into a SQLite SQL query.
Uses defog/sqlcoder-7b-2 via text_generation on Featherless AI provider.
"""

import re
from config.settings import TABLE_METADATA, SQL_MAX_NEW_TOKENS
from agents.llm_client import get_sql_client, generate


def _build_schema_ddl(tables: list[str]) -> str:
    """
    Build a DDL-style schema string with column descriptions AND sample values.
    Sample values in comments help the model map user-provided values to the correct column.
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


def _strip_invalid_joins(sql: str, allowed_tables: list[str]) -> str:
    """
    Remove any JOIN clauses that reference tables not in the allowed list.
    Also fix dangling alias prefixes left behind after JOIN removal.
    """
    alias_map: dict[str, str] = {}
    for m in re.finditer(
        r"\b(?:LEFT\s+|RIGHT\s+|INNER\s+|OUTER\s+|FULL\s+|CROSS\s+)?JOIN\s+(\w+)\s+(\w+)\b",
        sql,
        flags=re.IGNORECASE,
    ):
        table_name, alias = m.group(1), m.group(2)
        if alias.upper() not in ("ON", "WHERE", "SET"):
            alias_map[alias] = table_name

    if len(allowed_tables) == 1:
        sql = re.sub(
            r"\b(?:LEFT\s+|RIGHT\s+|INNER\s+|OUTER\s+|FULL\s+|CROSS\s+)?JOIN\s+\w+(?:\s+\w+)?\s+ON\s+[^\n]+",
            "",
            sql,
            flags=re.IGNORECASE,
        )
        sql = re.sub(
            r"\b(?:LEFT\s+|RIGHT\s+|INNER\s+|OUTER\s+|FULL\s+|CROSS\s+)?JOIN\s+\w+(?:\s+\w+)?",
            "",
            sql,
            flags=re.IGNORECASE,
        )
    else:
        known = set(t.lower() for t in allowed_tables)

        def _remove_if_unknown(m: re.Match) -> str:
            join_table = m.group(1).lower()
            if join_table not in known:
                alias_map[m.group(2)] = join_table
                return ""
            return m.group(0)

        sql = re.sub(
            r"\b(?:LEFT\s+|RIGHT\s+|INNER\s+|OUTER\s+|FULL\s+|CROSS\s+)?JOIN\s+(\w+)\s+(\w+)\s+ON\s+[^\n]+",
            _remove_if_unknown,
            sql,
            flags=re.IGNORECASE,
        )

    known_set = set(t.lower() for t in allowed_tables)
    for alias, table in alias_map.items():
        if table.lower() not in known_set:
            sql = re.sub(
                rf"\b{re.escape(alias)}\.([\w]+)",
                r"\1",
                sql,
            )

    sql = re.sub(r"[ \t]{2,}", " ", sql).strip()
    return sql


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
                remove.add(i)
            else:
                depth -= 1

    sql = "".join(ch for i, ch in enumerate(chars) if i not in remove)

    opens, closes = _count_unquoted_parens(sql)
    if opens > closes:
        sql += ")" * (opens - closes)

    return sql


def _fix_sqlite_compat(sql: str) -> str:
    """
    Post-process the generated SQL to fix common model mistakes.
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

    # Fix 3: Unicode comparison operators → ASCII
    sql = sql.replace("≥", ">=").replace("≤", "<=").replace("≠", "!=").replace("→", "->")

    # Fix 4: PostgreSQL interval → SQLite date()
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

    # Fix 4b: strftime('...', column) where 'column' is literally the word 'column'
    def _fix_strftime_placeholder(sql: str) -> str:
        from_match = re.search(r"\bFROM\s+([\w]+)", sql, re.IGNORECASE)
        if not from_match:
            return sql
        table = from_match.group(1).lower()
        date_col_map = {
            "palo_alto_logs":    "log_date",
            "transactions":      "created_at",
            "log_table":         "log_time",
            "ping_identity_logs":"event_date",
            "zscaler_logs":      "event_date",
            "linux_logs":        "event_date",
            "bluecoat_proxy_logs":"event_date",
        }
        date_col = date_col_map.get(table, "event_date")
        sql = re.sub(
            r"(strftime\s*\(\s*'[^']+'\s*,\s*)\bcolumn\b",
            lambda m: f"{m.group(1)}{date_col}",
            sql,
            flags=re.IGNORECASE,
        )
        sql = re.sub(
            r"\bdate\s*\(\s*column\s*\)",
            f"date({date_col})",
            sql,
            flags=re.IGNORECASE,
        )
        return sql

    sql = _fix_strftime_placeholder(sql)

    # Fix 5: EXTRACT(part FROM col) → strftime()
    _EXTRACT_MAP = {
        "year": "%Y", "month": "%m", "day": "%d",
        "hour": "%H", "minute": "%M", "second": "%S",
    }
    def _extract_to_strftime(m: re.Match) -> str:
        part = m.group(1).lower()
        col  = m.group(2)
        fmt  = _EXTRACT_MAP.get(part, f"%{part[0]}")
        if part in ("year", "month", "day", "hour", "minute", "second"):
            return f"CAST(strftime('{fmt}', {col}) AS INTEGER)"
        return f"strftime('{fmt}', {col})"

    sql = re.sub(
        r"EXTRACT\s*\(\s*(\w+)\s+FROM\s+([\w\.]+)\s*\)",
        _extract_to_strftime,
        sql,
        flags=re.IGNORECASE,
    )

    # Fix 6: date_trunc()
    _TRUNC_MAP = {
        "year":  ("%Y",    False),
        "month": ("%Y-%m", False),
        "day":   (None,    True),
        "hour":  ("%Y-%m-%d %H", False),
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

    # Fix 7: DATE_FORMAT / TO_CHAR
    sql = re.sub(
        r"DATE_FORMAT\s*\(\s*([\w\.]+)\s*,\s*('[^']*')\s*\)",
        lambda m: f"strftime({m.group(2)}, {m.group(1)})",
        sql, flags=re.IGNORECASE,
    )
    sql = re.sub(
        r"TO_CHAR\s*\(\s*([\w\.]+)\s*,\s*('[^']*')\s*\)",
        lambda m: f"strftime({m.group(2)}, {m.group(1)})",
        sql, flags=re.IGNORECASE,
    )

    # Fix 8: NULLS LAST / FIRST
    sql = re.sub(r"\s+NULLS\s+(?:LAST|FIRST)", "", sql, flags=re.IGNORECASE)

    # Fix 9: Balance parentheses
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
    """
    schema_ddl  = _build_schema_ddl(tables)
    table_name  = tables[0] if len(tables) == 1 else ", ".join(tables)
    alias_hint  = f"Use alias 't' for table '{tables[0]}'." if len(tables) == 1 else ""

    prompt = f"""### Task
Generate a SQLite3 SQL query to answer the following question.
You MUST generate valid SQLite3 syntax ONLY — not PostgreSQL, MySQL, or any other dialect.

STRICT RULES:
1. Query ONLY this table: {table_name}. {alias_hint}
2. NEVER use JOIN — this table contains all required columns. There are no related tables.
3. NEVER invent or reference any table that is not in the schema below.
4. NEVER use a table alias that does not match a table in the schema.
5. SELECT all columns that are relevant to the question — do not limit to just one column unless asked.
6. VALUE-TO-COLUMN MATCHING: Each column description lists its valid values after the colon.
   Before writing a WHERE condition, read the column descriptions carefully and use the column
   whose description mentions the value the user is asking about.
   Example: if user says "blocked", find which column description contains "Blocked" — use THAT column.
   NEVER guess — always match the value to the correct column from the schema description.
7. Do NOT use ILIKE — use LOWER(col) LIKE LOWER('%val%') instead.
8. ALL text WHERE comparisons MUST use: LOWER(column) LIKE LOWER('%value%')
   NEVER use = or == for text columns in WHERE.
9. Use only ASCII operators: >= <= != > < =   NEVER use: ≥ ≤ ≠
10. Do NOT use NULLS LAST or NULLS FIRST.

SQLite3 DATE FUNCTIONS (use ONLY these):
  - Last N days:       date('now', '-N days')
  - Last N months:     date('now', '-N months')
  - Last N years:      date('now', '-N years')
  - Extract year:      strftime('%Y', col)   e.g. strftime('%Y', event_date)
  - Extract month:     strftime('%m', col)   e.g. strftime('%m', event_date)
  - Truncate to month: strftime('%Y-%m', col)
  Replace col with the ACTUAL column name — never write the word "column".

FORBIDDEN (will cause errors):
  JOIN, EXTRACT(), date_trunc(), DATE_FORMAT(), TO_CHAR(), NOW(), interval,
  DATEADD(), YEAR(), MONTH(), DAY(), NULLS LAST, NULLS FIRST, ≥, ≤, ≠

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
    sql = _strip_invalid_joins(sql, tables)
    sql = _fix_sqlite_compat(sql)
    return sql
