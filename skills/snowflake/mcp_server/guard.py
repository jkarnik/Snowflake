"""Read-only guard: only single SELECT, SHOW and DESCRIBE statements may reach Snowflake."""
import logging

import sqlglot
from sqlglot import exp, tokens

# sqlglot warns on stderr whenever it falls back to a generic Command; the guard handles those.
logging.getLogger("sqlglot").setLevel(logging.ERROR)

ALLOWED_HINT = "Only single SELECT, SHOW and DESCRIBE statements are allowed."


class Blocked(Exception):
    """The statement must not reach Snowflake. str(exc) says why."""


def check_sql(sql: str) -> str:
    """Return "SELECT", "SHOW" or "DESCRIBE" for an allowed statement; raise Blocked otherwise."""
    try:
        # Snowflake's ->> flow operator chains statements without a semicolon; block it.
        tokenized = sqlglot.tokenize(sql, dialect="snowflake")
        if any(t.token_type == tokens.TokenType.DARROW for t in tokenized):
            raise Blocked(f"the ->> flow operator chains statements; send exactly one. {ALLOWED_HINT}")
        parsed = sqlglot.parse(sql, dialect="snowflake")
    except sqlglot.errors.SqlglotError as exc:
        first_line = str(exc).splitlines()[0]
        raise Blocked(f"could not parse the statement ({first_line}). {ALLOWED_HINT}") from None
    statements = [s for s in parsed if s is not None and not isinstance(s, exp.Semicolon)]
    if not statements:
        raise Blocked(f"no statement found. {ALLOWED_HINT}")
    if len(statements) > 1:
        raise Blocked(f"{len(statements)} statements found; send exactly one. {ALLOWED_HINT}")
    stmt = statements[0]
    if isinstance(stmt, exp.Select) and stmt.args.get("into"):
        raise Blocked(f"SELECT ... INTO writes a table. {ALLOWED_HINT}")
    if isinstance(stmt, (exp.Select, exp.SetOperation)):
        return "SELECT"
    if isinstance(stmt, exp.Show):
        return "SHOW"
    if isinstance(stmt, exp.Describe):
        return "DESCRIBE"
    kind = str(stmt.this).upper() if isinstance(stmt, exp.Command) else type(stmt).__name__
    if kind == "SHOW":
        return "SHOW"
    raise Blocked(f"{kind} statements are not allowed. {ALLOWED_HINT}")
