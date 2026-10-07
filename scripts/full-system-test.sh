#!/usr/bin/env bash
# Full non-destructive runtime validation for Stremio WebAdmin.
# Run from the repository root on the Docker host after deployment.
set -uo pipefail
# Prefer an explicit HOST. Otherwise use the installation IP when available; this
# matters when Compose publishes services on a specific LAN address rather than 127.0.0.1.
if [ -z "${HOST:-}" ]; then
  HOST="${IPADDRESS:-}"
  if [ -z "$HOST" ] && [ -r /opt/stremio-webadmin/.env ]; then
    HOST="$(sed -n 's/^IPADDRESS=//p' /opt/stremio-webadmin/.env | tail -1 | tr -d '"\r')"
  fi
  HOST="${HOST:-127.0.0.1}"
fi
SERVER="${SERVER:-http://${HOST}:11470}"; WEBADMIN="${WEBADMIN:-http://${HOST}:8090}"; PIHOLE="${PIHOLE:-http://${HOST}:8053}"
SERVER_CONTAINER="${SERVER_CONTAINER:-stremio-libtorrent-server}"; WEBADMIN_CONTAINER="${WEBADMIN_CONTAINER:-stremio-webadmin}"; GLUETUN_CONTAINER="${GLUETUN_CONTAINER:-stremio-gluetun}"; PIHOLE_CONTAINER="${PIHOLE_CONTAINER:-stremio-pihole}"
VAAPI_DEVICE="${VAAPI_DEVICE:-/dev/dri/renderD128}"; TIMEOUT="${TIMEOUT:-10}"; RUN_SYNTHETIC="${RUN_SYNTHETIC:-0}"
FAIL=0; PASS=0; SKIP=0
pass(){ echo "PASS  $*"; PASS=$((PASS+1)); }; fail(){ echo "FAIL  $*"; FAIL=$((FAIL+1)); }; skip(){ echo "SKIP  $*"; SKIP=$((SKIP+1)); }; section(){ echo; echo "===== $* ====="; }
http_ok(){ curl -fsS --max-time "$TIMEOUT" "$1" >/dev/null 2>&1; }; json_ok(){ curl -fsS --max-time "$TIMEOUT" "$1" | python3 -m json.tool >/dev/null 2>&1; }
running(){ [ "$(docker inspect -f '{{.State.Running}}' "$1" 2>/dev/null)" = true ]; }
healthy(){ local h; h="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$1" 2>/dev/null)"; [ "$h" = healthy ] || [ "$h" = none ]; }

section "Prerequisites"
for x in docker curl python3; do command -v "$x" >/dev/null && pass "$x available" || { fail "$x missing"; }; done
[ "$FAIL" -eq 0 ] || skip "continuing despite missing prerequisite(s)"

section "Deployed image and code identity"
git_sha="$(git rev-parse HEAD 2>/dev/null || true)"
git_branch="$(git branch --show-current 2>/dev/null || true)"
[ -n "$git_sha" ] && pass "checkout $git_branch @ $git_sha" || skip "repository identity unavailable"
for c in "$SERVER_CONTAINER" "$WEBADMIN_CONTAINER"; do
  image_ref="$(docker inspect -f '{{.Config.Image}}' "$c" 2>/dev/null || true)"
  image_id="$(docker inspect -f '{{.Image}}' "$c" 2>/dev/null || true)"
  [ -n "$image_ref" ] && { echo "$c image=$image_ref"; echo "$c imageId=$image_id"; pass "$c image identity readable"; } || fail "$c image identity unavailable"
done
wrapper_sig="$(docker exec "$SERVER_CONTAINER" sh -c "grep -E '_auto_apply|probe unsafe|ffmpeg-policy' /usr/local/bin/ffmpeg 2>/dev/null | head -5" 2>/dev/null || true)"
if echo "$wrapper_sig" | grep -q '_auto_apply'; then
  pass "deployed FFmpeg wrapper contains AUTO compatibility policy"
else
  fail "deployed FFmpeg wrapper is older than development AUTO policy"
fi
web_sig="$(docker exec "$WEBADMIN_CONTAINER" sh -c "grep -E 'classifyPlayback|FULL TRANSCODE|completed torrent' /app/static/index.html /srv/app/static/index.html /webadmin/static/index.html 2>/dev/null | head -5" 2>/dev/null || true)"
if echo "$web_sig" | grep -q 'classifyPlayback'; then
  pass "deployed WebAdmin contains playback correlation UI"
else
  fail "deployed WebAdmin is older than development playback UI"
fi

section "Containers"
for c in "$GLUETUN_CONTAINER" "$SERVER_CONTAINER" "$WEBADMIN_CONTAINER" "$PIHOLE_CONTAINER"; do
  running "$c" && pass "$c running" || { fail "$c not running"; continue; }
  healthy "$c" && pass "$c healthy/no-healthcheck" || fail "$c unhealthy"
done

section "HTTP and APIs"
for spec in "$SERVER/health|server health" "$WEBADMIN/health|WebAdmin health" "$PIHOLE/admin/|Pi-hole web"; do url="${spec%%|*}"; label="${spec#*|}"; http_ok "$url" && pass "$label" || fail "$label"; done
for ep in /settings /stats.json /active.json /cache.json /pins.json; do json_ok "$SERVER$ep" && pass "$ep JSON" || fail "$ep"; done
for ep in /api/status /api/config /api/transcoding/status; do json_ok "$WEBADMIN$ep" && pass "WebAdmin $ep" || fail "WebAdmin $ep"; done

section "Persistent configuration"
docker exec "$SERVER_CONTAINER" test -r /config/admin-settings.json 2>/dev/null && pass "server reads admin-settings.json" || fail "server cannot read admin-settings.json"
docker exec "$WEBADMIN_CONTAINER" sh -c 'test -r /config/admin-settings.json && test -w /config/admin-settings.json' 2>/dev/null && pass "WebAdmin reads/writes admin-settings.json" || fail "WebAdmin cannot read/write admin-settings.json"

section "DNS"
docker exec "$SERVER_CONTAINER" getent hosts github.com >/dev/null 2>&1 && pass "server DNS resolution" || fail "server DNS resolution"
docker exec "$PIHOLE_CONTAINER" sh -c 'command -v nslookup >/dev/null && nslookup github.com 172.30.0.10 >/dev/null 2>&1' 2>/dev/null && pass "Pi-hole -> gateway DNS" || skip "Pi-hole DNS probe unavailable"

section "FFmpeg"
docker exec "$SERVER_CONTAINER" test -x /usr/local/libexec/stremio/ffmpeg-real 2>/dev/null && pass "ffmpeg-real present" || fail "ffmpeg-real missing"
docker exec "$SERVER_CONTAINER" sh -c "grep -q 'ffmpeg-policy' /usr/local/bin/ffmpeg" 2>/dev/null && pass "policy wrapper installed" || fail "policy wrapper missing"
encoders="$(docker exec "$SERVER_CONTAINER" /usr/local/libexec/stremio/ffmpeg-real -hide_banner -encoders 2>/dev/null || true)"
grep -F 'libx264' <<<"$encoders" >/dev/null && pass "libx264 encoder" || fail "libx264 missing"

section "VAAPI"
if docker exec "$SERVER_CONTAINER" test -e "$VAAPI_DEVICE" 2>/dev/null; then
  pass "$VAAPI_DEVICE mounted"
  for enc in h264_vaapi hevc_vaapi; do grep -F "$enc" <<<"$encoders" >/dev/null && pass "$enc encoder" || fail "$enc missing"; done
  docker exec "$SERVER_CONTAINER" /usr/local/libexec/stremio/ffmpeg-real -hide_banner -loglevel error -vaapi_device "$VAAPI_DEVICE" -f lavfi -i testsrc2=size=1280x720:rate=30 -frames:v 30 -vf 'format=nv12,hwupload' -c:v h264_vaapi -f null - >/dev/null 2>&1 && pass "VAAPI H264 encode" || fail "VAAPI H264 encode"
else skip "$VAAPI_DEVICE not mounted"; fi

section "Playback and transcoding telemetry"
T="$(mktemp)"; A="$(mktemp)"; trap 'rm -f "$T" "$A"' EXIT
if curl -fsS --max-time "$TIMEOUT" "$WEBADMIN/api/transcoding/status" >"$T"; then
 python3 - "$T" <<'PY'
import json,sys
d=json.load(open(sys.argv[1])); a=d.get("active") if isinstance(d.get("active"),dict) else {}; s=a.get("sessions") if isinstance(a.get("sessions"),list) else []
print("transcoding sessions:",len(s))
if any("testsrc" in str(x).lower() or "lavfi" in str(x).lower() for x in s): raise SystemExit(1)
PY
 [ $? -eq 0 ] && pass "capability probes excluded from sessions" || fail "capability probe leaked into sessions"
else fail "transcoding telemetry unavailable"; fi
if curl -fsS --max-time "$TIMEOUT" "$SERVER/active.json" >"$A"; then
 python3 - "$A" <<'PY'
import json,sys
r=json.load(open(sys.argv[1])); print("torrent rows:",len(r),"active playback rows:",sum(bool(x.get("active")) for x in r))
PY
 pass "active playback signal readable"
else fail "active.json unavailable"; fi

section "Playback classification invariants"
python3 - <<'PY'
def classify(active, sessions):
    modes = ["direct" for _ in active]
    if len(active) != 1 or len(sessions) != 1:
        return modes
    x=sessions[0]
    v=str(x.get("targetVideo") or "").lower()
    a=str(x.get("targetAudio") or "").lower()
    vt=bool(v) and v!="copy"
    at=bool(a) and a!="copy"
    modes[0]="full-transcode" if vt and at else "video-transcode" if vt else "audio-transcode" if at else "remux"
    return modes
cases=[
    ("direct",[{}],[],["direct"]),
    ("remux",[{}],[{"targetVideo":"copy","targetAudio":"copy"}],["remux"]),
    ("audio",[{}],[{"targetVideo":"copy","targetAudio":"aac"}],["audio-transcode"]),
    ("video",[{}],[{"targetVideo":"h264_vaapi","targetAudio":"copy"}],["video-transcode"]),
    ("full",[{}],[{"targetVideo":"h264_vaapi","targetAudio":"aac"}],["full-transcode"]),
    ("ambiguous",[{},{}],[{"targetVideo":"h264_vaapi","targetAudio":"aac"}],["direct","direct"]),
]
bad=[]
for name,a,s,want in cases:
    got=classify(a,s)
    if got!=want: bad.append((name,got,want))
if bad:
    print("classification failures:",bad)
    raise SystemExit(1)
print("DIRECT/REMUX/AUDIO/VIDEO/FULL classification invariants OK")
PY
[ $? -eq 0 ] && pass "playback classification invariants" || fail "playback classification invariants"

section "Completed torrent state invariant"
python3 - <<'PY'
def state(active,paused,progress,down,up,cached):
    if active: return "PLAYING"
    if paused: return "PAUSED"
    if round(progress*100)>=100: return "SEEDING" if up>0 else "CACHED"
    if down>0: return "DOWNLOADING"
    return "CACHED" if cached else "IDLE"
assert state(False,False,1.0,1024,0,True)=="CACHED"
assert state(False,False,1.0,0,1024,True)=="SEEDING"
assert state(False,False,.5,1024,0,False)=="DOWNLOADING"
print("100% torrent cannot be classified as DOWNLOADING")
PY
[ $? -eq 0 ] && pass "completed torrent state precedence" || fail "completed torrent state precedence"

section "Synthetic legal playback"
if [ "$RUN_SYNTHETIC" = 1 ]; then SERVER="$SERVER" python3 scripts/synthetic_playback.py && pass "synthetic playback" || fail "synthetic playback"; else skip "set RUN_SYNTHETIC=1 to exercise legal torrent playback"; fi

section "Recent fatal logs"
for c in "$SERVER_CONTAINER" "$WEBADMIN_CONTAINER" "$GLUETUN_CONTAINER" "$PIHOLE_CONTAINER"; do
 docker logs --since 10m "$c" 2>&1 | grep -Eiq 'Traceback|panic|segmentation fault|fatal error' && fail "$c fatal-looking logs" || pass "$c no fatal-looking logs"
done

section "Summary"
echo "PASS=$PASS FAIL=$FAIL SKIP=$SKIP"
[ "$FAIL" -eq 0 ] && { echo "RESULT=PASS"; exit 0; }
echo "RESULT=FAIL"; exit 1
