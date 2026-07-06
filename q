#!/bin/zsh
# Send SQL (from stdin) to the persistent Snowflake session and print results.
DIR="${0:A:h}"
REQ="$(mktemp "$DIR/.sfq.XXXXXX").sql"
cat > "$REQ"
echo "$REQ" > "$DIR/.sf_cmd.fifo"
OUT="$(head -1 "$DIR/.sf_resp.fifo")"
cat "$OUT"
rm -f "$REQ" "$OUT"
