#!/usr/bin/env bash
# shellcheck disable=SC2034  # variables below are read inside check()'s eval
# Offline tests for scripts/as-agent: JWT signing, bot identity, owner co-author trailer, and the
# push credential setup. Doesn't contact GitHub (DEV_TOOLING_AGENT_TOKEN stands in for the token).
set -euo pipefail
KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AS="$KIT/scripts/as-agent"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
fail=0
check() { if eval "$2"; then echo "  ok   $1"; else echo "  FAIL $1"; fail=1; fi; }

PY="$(command -v python3 || command -v python)"
export DEV_TOOLING_AGENTS_DIR="$TMP/agents" XDG_CACHE_HOME="$TMP/cache"
mkdir -p "$DEV_TOOLING_AGENTS_DIR"
openssl genrsa -out "$DEV_TOOLING_AGENTS_DIR/builder.pem" 2048 2>/dev/null
openssl rsa -in "$DEV_TOOLING_AGENTS_DIR/builder.pem" -pubout -out "$TMP/builder.pub" 2>/dev/null
printf 'CLIENT_ID=Iv23.testclient\nBOT_LOGIN="kw-builder[bot]"\nBOT_ID=4242\n' > "$DEV_TOOLING_AGENTS_DIR/builder.env"
printf 'OWNER_NAME="Knowing Wings"\nOWNER_EMAIL="1+knowingwings@users.noreply.github.com"\n' > "$DEV_TOOLING_AGENTS_DIR/owner.env"

echo "== JWT"
jwt="$("$AS" jwt builder)"
IFS=. read -r h p s <<< "$jwt"
pad() { local x="$1"; while (( ${#x} % 4 )); do x+="="; done; printf '%s' "$x" | tr -- '-_' '+/'; }
payload="$(pad "$p" | openssl base64 -d -A)"
check "header is RS256"                    '[[ "$(pad "$h" | openssl base64 -d -A)" == "{\"alg\":\"RS256\",\"typ\":\"JWT\"}" ]]'
check "issuer is the client id"            'grep -q "\"iss\":\"Iv23.testclient\"" <<< "$payload"'
check "expires within 10 minutes"          '"$PY" -c "import json,sys,time; d=json.loads(sys.argv[1]); assert 0 < d[\"exp\"]-time.time() <= 600" "$payload"'
pad "$s" | openssl base64 -d -A > "$TMP/sig.bin"
check "signature verifies with public key" 'printf "%s.%s" "$h" "$p" | openssl dgst -sha256 -verify "$TMP/builder.pub" -signature "$TMP/sig.bin" >/dev/null'

echo "== key in 1Password"
FAKE_OP="$TMP/fakebin"; mkdir -p "$FAKE_OP"
cat > "$FAKE_OP/op" <<OP
#!/usr/bin/env bash
case "\$*" in
  "read --no-newline op://Dev/kw-reviewer/private_key") cat "$DEV_TOOLING_AGENTS_DIR/builder.pem" ;;
  "read --no-newline op://Dev/kw-reviewer/client_id") printf 'Iv23.fromvault' ;;
  *) echo "[ERROR] not found: \$*" >&2; exit 1 ;;
esac
OP
chmod +x "$FAKE_OP/op"
printf 'CLIENT_ID=op://Dev/kw-reviewer/client_id\nKEY=op://Dev/kw-reviewer/private_key\nBOT_LOGIN="kw-reviewer[bot]"\nBOT_ID=99\n' > "$DEV_TOOLING_AGENTS_DIR/reviewer.env"
before="$(find "${TMPDIR:-/tmp}" -maxdepth 1 -name 'tmp.*' 2>/dev/null | wc -l)"
vjwt="$(PATH="$FAKE_OP:$PATH" "$AS" jwt reviewer)"
after="$(find "${TMPDIR:-/tmp}" -maxdepth 1 -name 'tmp.*' 2>/dev/null | wc -l)"
IFS=. read -r vh vp vs <<< "$vjwt"
pad "$vs" | openssl base64 -d -A > "$TMP/vsig.bin"
check "signs with the key from 1Password"  'printf "%s.%s" "$vh" "$vp" | openssl dgst -sha256 -verify "$TMP/builder.pub" -signature "$TMP/vsig.bin" >/dev/null'
check "client id read from 1Password"      'pad "$vp" | openssl base64 -d -A | grep -q "\"iss\":\"Iv23.fromvault\""'
check "temporary key file removed"         '[[ "$before" == "$after" ]]'
printf 'CLIENT_ID=Iv23.x\nKEY=op://Dev/missing/key\n' > "$DEV_TOOLING_AGENTS_DIR/ghost.env"
op_err="$(PATH="$FAKE_OP:$PATH" "$AS" jwt ghost 2>&1 || true)"
check "1Password errors are explained"     'grep -q "1Password couldn.t read op://Dev/missing/key" <<< "$op_err"'
NOOP="$TMP/no-op-bin"; mkdir -p "$NOOP"   # the system tools without op, which may be in /usr/bin
for f in /usr/bin/* /bin/*; do n="${f##*/}"; [[ "$n" == op || -e "$NOOP/$n" || -L "$NOOP/$n" ]] || ln -s "$f" "$NOOP/$n"; done
noop_err="$(PATH="$NOOP" "$AS" jwt ghost 2>&1 || true)"
check "missing op CLI is explained"        'grep -q "op CLI isn.t installed" <<< "$noop_err"'

echo "== acting as the builder"
export DEV_TOOLING_AGENT_TOKEN="fake-token-123"
R="$TMP/repo"; mkdir -p "$R"; cd "$R"; git init -q -b main
git remote add origin git@github.com:knowingwings/demo.git
"$AS" builder git commit -q --allow-empty -m "feat: try the builder identity"
check "author is the bot"                  '[[ "$(git log -1 --format="%an <%ae>")" == "kw-builder[bot] <4242+kw-builder[bot]@users.noreply.github.com>" ]]'
check "committer is the bot"               '[[ "$(git log -1 --format="%cn")" == "kw-builder[bot]" ]]'
check "owner is co-author"                 'git log -1 --format=%B | grep -qx "Co-authored-by: Knowing Wings <1+knowingwings@users.noreply.github.com>"'
check "gh sees the App token"              '[[ "$("$AS" builder sh -c "echo \$GH_TOKEN")" == "fake-token-123" ]]'
check "ssh remote rewritten to https"      '"$AS" builder git ls-remote --get-url origin | grep -q "^https://github.com/knowingwings/demo"'
cred="$(printf 'protocol=https\nhost=github.com\n\n' | "$AS" builder git credential fill)"
check "push credential is the App token"   'grep -qx "password=fake-token-123" <<< "$cred" && grep -qx "username=x-access-token" <<< "$cred"'
check "whoami"                             '"$AS" whoami builder | grep -q "^kw-builder\[bot\]"'
unknown_out="$("$AS" nobody true 2>&1 || true)"
check "unknown role fails clearly"         '! "$AS" nobody true 2>/dev/null && grep -q "no .*nobody.env" <<< "$unknown_out"'

echo "== Python detection"
STUB="$TMP/stubbin"; mkdir -p "$STUB"
cat > "$STUB/python3" <<'SH'
#!/usr/bin/env bash
echo "Python was not found; run without arguments to install from the Microsoft Store" >&2
exit 9009
SH
cat > "$STUB/python" <<SH
#!/usr/bin/env bash
exec "$PY" "\$@"
SH
cat > "$STUB/curl" <<'SH'
#!/usr/bin/env bash
case "$*" in
  *"/users/"*) echo '{"id": 777}' ;;
  *) echo '{"slug": "kw-stub"}' ;;
esac
SH
chmod +x "$STUB"/*
cp "$DEV_TOOLING_AGENTS_DIR/builder.pem" "$DEV_TOOLING_AGENTS_DIR/stub.pem"
printf 'CLIENT_ID=Iv23.stub\n' > "$DEV_TOOLING_AGENTS_DIR/stub.env"
stub_out="$(PATH="$STUB:$PATH" "$AS" setup stub 2>&1 || true)"
check "skips a python3 that doesn't run"   'grep -q "stub acts as kw-stub\[bot\] (id 777)" <<< "$stub_out"'
exit $fail
