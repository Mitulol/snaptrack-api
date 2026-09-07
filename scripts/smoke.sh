#!/usr/bin/env bash
# End-to-end smoke test against a running stack (default: docker-compose on :8000).
# Exercises: register -> login -> upload -> async thumbnail -> cached read -> delete.
set -euo pipefail

BASE="${BASE_URL:-http://localhost:8000}"
EMAIL="smoke-$(date +%s)@example.com"
PASS="password123"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

say() { printf '\n\033[1;34m== %s\033[0m\n' "$1"; }

say "health"
curl -fsS "$BASE/healthz"; echo
curl -fsS "$BASE/readyz"; echo

say "register + login"
curl -fsS -X POST "$BASE/auth/register" -H 'content-type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASS\"}" >/dev/null
TOKEN="$(curl -fsS -X POST "$BASE/auth/login" -H 'content-type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASS\"}" | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')"
AUTH=(-H "authorization: Bearer $TOKEN")

say "make a test PNG (320x240, pure-stdlib generator)"
python3 - "$TMP/pic.png" <<'PY'
import sys, zlib, struct

w, h = 320, 240


def chunk(typ, data):
    return (struct.pack(">I", len(data)) + typ + data
            + struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF))


raw = b"".join(b"\x00" + b"\x46\x82\xb4" * w for _ in range(h))  # filter 0 + steel-blue
png = (b"\x89PNG\r\n\x1a\n"
       + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
       + chunk(b"IDAT", zlib.compress(raw, 9))
       + chunk(b"IEND", b""))
open(sys.argv[1], "wb").write(png)
PY

say "upload"
PID="$(curl -fsS -X POST "$BASE/photos" "${AUTH[@]}" -F "file=@$TMP/pic.png" -F "caption=smoke test" \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["id"])')"
echo "photo id = $PID"

say "poll thumbnail (worker is async)"
for i in $(seq 1 30); do
  STATUS="$(curl -fsS "$BASE/photos/$PID/thumbnail" "${AUTH[@]}" \
    | python3 -c 'import sys,json;print(json.load(sys.stdin)["status"])')"
  echo "  attempt $i: $STATUS"
  [ "$STATUS" = "ready" ] && break
  [ "$STATUS" = "failed" ] && { echo "thumbnail FAILED"; exit 1; }
  sleep 1
done
[ "$STATUS" = "ready" ] || { echo "thumbnail never became ready"; exit 1; }

say "fetch thumbnail bytes"
curl -fsS "$BASE/photos/$PID/thumbnail/file" "${AUTH[@]}" -o "$TMP/thumb.jpg"
# JPEG magic bytes: FF D8 FF
head -c 3 "$TMP/thumb.jpg" | od -An -tx1 | grep -q 'ff d8 ff' \
  && echo "  thumbnail is a JPEG ($(wc -c < "$TMP/thumb.jpg") bytes)" \
  || { echo "thumbnail is not a JPEG"; exit 1; }

say "cached read + 404 for a stranger"
curl -fsS "$BASE/photos/$PID" "${AUTH[@]}" >/dev/null
curl -fsS "$BASE/photos/$PID" "${AUTH[@]}" >/dev/null   # 2nd read served from Redis
code="$(curl -s -o /dev/null -w '%{http_code}' "$BASE/photos/$PID")"
[ "$code" = "403" ] || [ "$code" = "401" ] || { echo "expected auth failure, got $code"; exit 1; }

say "delete"
curl -fsS -X DELETE "$BASE/photos/$PID" "${AUTH[@]}" -o /dev/null -w '  delete -> %{http_code}\n'
code="$(curl -s -o /dev/null -w '%{http_code}' "$BASE/photos/$PID" "${AUTH[@]}")"
[ "$code" = "404" ] || { echo "expected 404 after delete, got $code"; exit 1; }

printf '\n\033[1;32mSMOKE PASSED\033[0m\n'
