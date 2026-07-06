import sys
import snowflake.connector

conn = snowflake.connector.connect(
    account='pda47359.us-east-1',
    user='JKARNIK',
    authenticator='externalbrowser',
    role='FR_PRODUCT_ANALYST',
    warehouse='TEAM_PRODUCT_ANALYST_XSMALL',
    client_store_temporary_credential=True,
)

sql = sys.stdin.read()
cur = conn.cursor()
try:
    for stmt in [s.strip() for s in sql.split(';') if s.strip()]:
        cur.execute(stmt)
        cols = [c[0] for c in cur.description] if cur.description else []
        rows = cur.fetchall()
        print('\t'.join(cols))
        for r in rows:
            print('\t'.join('' if v is None else str(v) for v in r))
        print(f'-- {len(rows)} rows --')
finally:
    cur.close()
    conn.close()
