#!/bin/zsh
# Send SQL (from stdin) to the persistent Snowflake session and print results.
DIR="${0:A:h}"
RUNDIR="$DIR/.sfrun"
STUB="$(mktemp "$RUNDIR/q.XXXXXX")"
REQ="$STUB.sql"
cat > "$REQ"
echo "$REQ" > "$RUNDIR/cmd.fifo"
OUT="$(head -1 "$RUNDIR/resp.fifo")"
cat "$OUT"
rm -f "$STUB" "$REQ" "$OUT"
