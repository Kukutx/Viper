#!/usr/bin/env bash
set -euo pipefail
root=$(git rev-parse --show-toplevel)
cd "$root"
[[ "$(uname -s)" == Linux ]] || { echo 'PulseAudio validation requires Linux.' >&2; exit 1; }
for tool in pulseaudio pactl cargo timeout; do
  command -v "$tool" >/dev/null || { echo "Missing required tool: $tool" >&2; exit 1; }
done
python tools/verify_pulse_vendor.py
mkdir -p tools/.reports
runtime=$(mktemp -d "${RUNNER_TEMP:-${TMPDIR:-/tmp}}/viper-pulse.XXXXXX")
chmod 700 "$runtime"
pid=''
cleanup() {
  if [[ -n "$pid" ]]; then
    kill "$pid" 2>/dev/null || true
    wait "$pid" 2>/dev/null || true
  fi
  rm -rf -- "$runtime"
}
trap cleanup EXIT
export PULSE_SERVER="unix:$runtime/native"
export PULSE_COOKIE="$runtime/cookie"
export VIPER_PULSE_TEST=1
cat > "$runtime/server.pa" <<EOF
load-module module-native-protocol-unix socket=$runtime/native auth-cookie=$runtime/cookie
load-module module-null-sink sink_name=viper_ci channels=2 rate=48000
set-default-sink viper_ci
set-default-source viper_ci.monitor
EOF
PULSE_RUNTIME_PATH="$runtime" XDG_RUNTIME_DIR="$runtime" XDG_CONFIG_HOME="$runtime/config" \
  pulseaudio --daemonize=no --exit-idle-time=-1 --use-pid-file=no -nF "$runtime/server.pa" \
  > tools/.reports/pulse-server.log 2>&1 &
pid=$!
ready=false
for _ in {1..100}; do
  if pactl info > tools/.reports/pulse-server-info.log 2>&1; then ready=true; break; fi
  kill -0 "$pid" 2>/dev/null || { cat tools/.reports/pulse-server.log >&2; exit 1; }
  sleep 0.1
done
[[ "$ready" == true ]] || { cat tools/.reports/pulse-server.log >&2; echo 'Private audio server did not become ready.' >&2; exit 1; }
timeout 300 cargo test --locked -p rust-pulsectl --test pulse_smoke --features private-server-tests -- --nocapture --test-threads=1 \
  > tools/.reports/pulse-smoke.log 2>&1 || { cat tools/.reports/pulse-smoke.log >&2; exit 1; }
cat tools/.reports/pulse-smoke.log
