#!/usr/bin/env bash
set -euo pipefail
root=$(git rev-parse --show-toplevel)
cd "$root"
[[ "$(uname -s)" == Linux ]] || { echo 'HTTP contract tests require Linux.' >&2; exit 1; }
# Only this disposable directory contains test keys and application settings.
fixture=$(mktemp -d "${RUNNER_TEMP:-${TMPDIR:-/tmp}}/viper-http.XXXXXXXX")
trap 'rm -rf -- "$fixture"' EXIT
mkdir -p "$fixture/home" "$fixture/empty-certs" tools/.reports
openssl req -x509 -newkey rsa:2048 -nodes -keyout "$fixture/ca.key" \
  -out "$fixture/ca.pem" -subj '/CN=Viper ephemeral test CA' -days 2 \
  -addext 'basicConstraints=critical,CA:TRUE' -addext 'keyUsage=critical,keyCertSign,cRLSign' \
  > "$fixture/certificate.log" 2>&1
openssl req -new -newkey rsa:2048 -nodes -keyout "$fixture/server.key" \
  -out "$fixture/server.csr" -subj '/CN=localhost' >> "$fixture/certificate.log" 2>&1
for name in trusted wrong-host; do
  san='DNS:localhost,IP:127.0.0.1'
  [[ "$name" != wrong-host ]] || san='DNS:wrong.invalid'
  printf 'basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth\nsubjectAltName=%s\n' "$san" > "$fixture/$name.ext"
  openssl x509 -req -in "$fixture/server.csr" -CA "$fixture/ca.pem" -CAkey "$fixture/ca.key" \
    -set_serial "$( [[ "$name" == trusted ]] && echo 2 || echo 3 )" -days 2 \
    -extfile "$fixture/$name.ext" -out "$fixture/$name.pem" >> "$fixture/certificate.log" 2>&1
done
openssl req -x509 -key "$fixture/server.key" -out "$fixture/untrusted.pem" \
  -subj '/CN=localhost' -days 2 -addext 'subjectAltName=DNS:localhost,IP:127.0.0.1' \
  >> "$fixture/certificate.log" 2>&1
python - "$fixture/body.gz" <<'PYCODE'
import gzip, pathlib, sys
pathlib.Path(sys.argv[1]).write_bytes(gzip.compress(b'{"message":"http-contract"}', mtime=0))
PYCODE
# Compile before changing HOME: rustup/cargo keep their real, pinned locations.
cargo test --locked --test http_dependency_contract --features flutter,linux-pkg-config,http-contract-tests --no-run \
  > tools/.reports/http-contract-build.log 2>&1 || { tail -100 tools/.reports/http-contract-build.log; exit 1; }
# cargo emits the executable path in JSON; never pick an old target/debug binary.
cargo test --locked --test http_dependency_contract --features flutter,linux-pkg-config,http-contract-tests \
  --no-run --message-format=json > "$fixture/build.json" 2> "$fixture/build.stderr"
executable=$(python - "$fixture/build.json" <<'PY'
import json, sys
paths = [r['executable'] for line in open(sys.argv[1]) if (r := json.loads(line)).get('reason') == 'compiler-artifact' and r.get('target', {}).get('name') == 'http_dependency_contract' and r.get('executable')]
if len(paths) != 1:
    raise SystemExit('Expected exactly one freshly checked HTTP test executable')
print(paths[0])
PY
)
timeout --kill-after=5s 180s env HOME="$fixture/home" XDG_CONFIG_HOME="$fixture/home" \
  SSL_CERT_FILE="$fixture/ca.pem" SSL_CERT_DIR="$fixture/empty-certs" \
  VIPER_HTTP_TEST_DIR="$fixture" \
  HTTP_PROXY=http://127.0.0.1:9 HTTPS_PROXY=http://127.0.0.1:9 ALL_PROXY=http://127.0.0.1:9 \
  http_proxy=http://127.0.0.1:9 https_proxy=http://127.0.0.1:9 all_proxy=http://127.0.0.1:9 \
  NO_PROXY= no_proxy= \
  "$executable" --test-threads=1 --nocapture > tools/.reports/http-contract-tests.log 2>&1 \
  || { cat tools/.reports/http-contract-tests.log; exit 1; }
cat tools/.reports/http-contract-tests.log
