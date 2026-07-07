"""Long-lived Snowflake session. Authenticates ONCE, then serves queries via FIFOs.

Protocol: client writes the path of a .sql file to CMD_FIFO. Server runs it,
writes results to <sqlfile>.out, then writes that path to RESP_FIFO.
"""
import os
import traceback
import snowflake.connector

DIR = os.path.dirname(os.path.abspath(__file__))
RUNDIR = os.path.join(DIR, '.sfrun')
os.makedirs(RUNDIR, exist_ok=True)
CMD_FIFO = os.path.join(RUNDIR, 'cmd.fifo')
RESP_FIFO = os.path.join(RUNDIR, 'resp.fifo')

for f in (CMD_FIFO, RESP_FIFO):
    if os.path.exists(f):
        os.remove(f)
    os.mkfifo(f)

conn = snowflake.connector.connect(
    account='pda47359.us-east-1',
    user='JKARNIK',
    authenticator='externalbrowser',
    role='FR_PRODUCT_ANALYST',
    warehouse='TEAM_PRODUCT_ANALYST_XSMALL',
    client_store_temporary_credential=True,
)
print('SESSION READY', flush=True)


def run(sql, out):
    with open(out, 'w') as o:
        cur = conn.cursor()
        try:
            for stmt in [s.strip() for s in sql.split(';') if s.strip()]:
                cur.execute(stmt)
                cols = [c[0] for c in cur.description] if cur.description else []
                rows = cur.fetchall()
                o.write('\t'.join(cols) + '\n')
                for r in rows:
                    o.write('\t'.join('' if v is None else str(v) for v in r) + '\n')
                o.write(f'-- {len(rows)} rows --\n')
        except Exception:
            o.write('ERROR:\n' + traceback.format_exc())
        finally:
            cur.close()


while True:
    with open(CMD_FIFO) as c:
        req = c.read().strip()
    if not req or req == 'QUIT':
        break
    out = req + '.out'
    try:
        with open(req) as f:
            run(f.read(), out)
    except Exception:
        with open(out, 'w') as o:
            o.write('ERROR:\n' + traceback.format_exc())
    with open(RESP_FIFO, 'w') as r:
        r.write(out + '\n')

conn.close()
