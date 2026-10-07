"""
SQL Safety and AST Validator for student-api service.
Ensures generated SQL is strictly a read-only SELECT statement with no mutations or chaining.
"""
import re

FORBIDDEN_KEYWORDS = [
    r"\bINSERT\b",
    r"\bUPDATE\b",
    r"\bDELETE\b",
    r"\bDROP\b",
    r"\bALTER\b",
    r"\bTRUNCATE\b",
    r"\bGRANT\b",
    r"\bREVOKE\b",
    r"\bEXEC\b",
    r"\bEXECUTE\b",
    r"\bCREATE\b",
    r"\bREPLACE\b",
    r"\bATTACH\b",
    r"\bDETACH\b",
]

def sanitize_and_validate_sql(raw_sql: str) -> str:
    """
    Cleans markdown backticks and validates that the SQL query is strictly safe and read-only.
    Raises ValueError if unsafe tokens or statement chaining are detected.
    """
    clean_sql = raw_sql.strip()
    
    # Strip markdown code blocks ```sql ... ``` or ``` ... ```
    if clean_sql.startswith("```"):
        lines = clean_sql.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        clean_sql = "\n".join(lines).strip()

    # Disallow empty query
    if not clean_sql:
        raise ValueError("Generated SQL query is empty.")

    # Must start with SELECT (or WITH ... SELECT)
    upper_sql = clean_sql.upper().strip()
    if not (upper_sql.startswith("SELECT") or upper_sql.startswith("WITH")):
        raise ValueError("Security violation: Only SELECT queries are permitted.")

    # Check forbidden mutation keywords
    for pattern in FORBIDDEN_KEYWORDS:
        if re.search(pattern, clean_sql, re.IGNORECASE):
            raise ValueError(f"Security violation: Query contains disallowed keyword matching '{pattern}'.")

    # Check for multiple chained statements (semicolon inside query)
    statements = [s.strip() for s in clean_sql.split(";") if s.strip()]
    if len(statements) > 1:
        raise ValueError("Security violation: Multiple SQL statements detected via semicolon chaining.")

    # Return valid single query (without trailing semicolon to be safe with subqueries)
    return statements[0]

