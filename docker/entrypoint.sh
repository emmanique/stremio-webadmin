#!/bin/sh
# All-in-one: the bundled Stremio web player + our libtorrent streaming server on one origin —
# HTTP :8080 (LAN) and HTTPS :12470 (cert). uvicorn (API) stays internal on :11470.
set -e

CACHE="${STREMIOSRV_CACHE_ROOT:-/root/.stremio-server}"
CERT="$CACHE/${CERT_FILE:-certificates.pem}"

# In VPN mode the container shares Gluetun's network namespace. Docker rejects
# the Compose `dns:` option with network_mode: service:gluetun, so set the
# resolver here before any Stremio/Node/Python process starts. This preserves
# the intended path Stremio -> Pi-hole -> Gluetun DNS -> VPN without a WAN DNS
# bypass. Outside VPN mode STREMIOSRV_DNS_SERVER is unset and Docker DNS remains
# untouched.
if [ -n "${STREMIOSRV_DNS_SERVER:-}" ]; then
    case "$STREMIOSRV_DNS_SERVER" in
        *[!0-9.]*|'')
            echo "[entrypoint] invalid STREMIOSRV_DNS_SERVER=$STREMIOSRV_DNS_SERVER" >&2
            exit 1
            ;;
    esac
    printf 'nameserver %s\noptions ndots:0\n' "$STREMIOSRV_DNS_SERVER" > /etc/resolv.conf
    echo "[entrypoint] DNS resolver -> $STREMIOSRV_DNS_SERVER"
fi

# 1) TLS cert for HTTPS :12470. TVs require a TRUSTED cert. In VPN mode the
# trusted stremio.rocks certificate is bootstrapped outside the tunnel by
# start-vpn.sh and persisted in the shared cache volume. Reuse it first so LAN
# clients are not coupled to VPN/DNS readiness. If it is missing/expired, a
# direct-mode runtime may still fetch it here; otherwise we fall back to an
# existing/self-signed certificate so the service can at least start.
mkdir -p "$CACHE"
if [ -n "${IPADDRESS:-}" ]; then
    IPD=$(echo "$IPADDRESS" | sed "s/[.]/-/g")
    SROCKS_DOMAIN="${IPD}.519b6502d940.stremio.rocks"
    TRUSTED_JSON="$CACHE/httpsCert.json"

    if [ -s "$CERT" ] \
        && openssl x509 -checkend 86400 -noout -in "$CERT" >/dev/null 2>&1 \
        && [ -s "$TRUSTED_JSON" ] \
        && grep -q "$SROCKS_DOMAIN" "$TRUSTED_JSON"; then
        grep -q "$SROCKS_DOMAIN" /etc/hosts 2>/dev/null || echo "${IPADDRESS} ${SROCKS_DOMAIN}" >> /etc/hosts
        [ -n "${SERVER_URL:-}" ] || SERVER_URL="https://${SROCKS_DOMAIN}:12470/"
        echo "[entrypoint] trusted cert reused for $SROCKS_DOMAIN"
    else
        echo "[entrypoint] IPADDRESS=$IPADDRESS -> fetching trusted stremio.rocks cert"
        FETCH_OK=""
        if (cd /srv/stremio-server && timeout 30 node certificate.js --action fetch); then
            if [ -s /srv/stremio-server/certificates.pem ]; then
                cp /srv/stremio-server/certificates.pem "$CERT"
                grep -q "$SROCKS_DOMAIN" /etc/hosts 2>/dev/null || echo "${IPADDRESS} ${SROCKS_DOMAIN}" >> /etc/hosts
                if (cd /srv/stremio-server && node certificate.js --action load \
                    --pem-path "$CERT" --domain "$SROCKS_DOMAIN" --json-path "$TRUSTED_JSON"); then
                    FETCH_OK=yes
                    [ -n "${SERVER_URL:-}" ] || SERVER_URL="https://${SROCKS_DOMAIN}:12470/"
                    echo "[entrypoint] trusted cert for $SROCKS_DOMAIN"
                fi
            fi
        fi
        if [ -z "$FETCH_OK" ]; then
            echo "[entrypoint] stremio.rocks fetch failed -> falling back to existing/self-signed cert"
        fi
    fi
fi
if [ -f "$CERT" ]; then
    [ -n "${IPADDRESS:-}" ] || echo "[entrypoint] using existing cert $CERT (bring-your-own)"
else
    echo "[entrypoint] no trusted cert -> self-signed (CN=${DOMAIN:-localhost}); TVs may reject it"
    openssl req -x509 -newkey rsa:2048 -nodes -days 3650 \
        -keyout "${CERT}.key" -out "${CERT}.crt" -subj "/CN=${DOMAIN:-localhost}" >/dev/null 2>&1
    cat "${CERT}.crt" "${CERT}.key" > "$CERT"
    rm -f "${CERT}.key" "${CERT}.crt"
fi

# 2) Point the bundled web player at the streaming server (stock localStorage mechanism).
SEED_SRC="/srv/stremio-server/localStorage.json"
SEED_DST="/srv/stremio-server/build/localStorage.json"
if [ -f "$SEED_SRC" ]; then
    cp "$SEED_SRC" "$SEED_DST"
    # The player's loader.js HEADs server_url.env and applies the server URL seeded below only when
    # that answers 2xx; otherwise it ignores SERVER_URL and uses the page's own origin. The file was
    # never shipped -- the HEAD succeeded only because nginx used to answer every unknown path with
    # index.html. Written here so the seed no longer rides on that fallback. Its content is unused.
    : > /srv/stremio-server/build/server_url.env
    if [ -n "${SERVER_URL:-}" ]; then
        case "$SERVER_URL" in */) ;; *) SERVER_URL="$SERVER_URL/" ;; esac
        sed -i "s|http://127.0.0.1:11470/|${SERVER_URL}|g" "$SEED_DST"
        echo "[entrypoint] web player -> $SERVER_URL"
        # The v6 desktop app re-points itself at its bundled 127.0.0.1 server on every launch, so the
        # Streaming Server URL won't stick. Launching it with a non-default --webui-url skips that
        # injection; --development also stops the bundled server. Trusted (:12470) URL only.
        echo "[entrypoint] desktop app -> add launch flags: --development --webui-url=$SERVER_URL"
    else
        echo "[entrypoint] web player -> default 127.0.0.1:11470 (set SERVER_URL for remote clients)"
    fi
fi

# /proxy counts a web page on SERVER_URL's host as this server's own (1.6.9). The IPADDRESS branch
# sets SERVER_URL inside this script, and uvicorn sees only what is exported.
export SERVER_URL

# 3) Run uvicorn (API, internal :11470) + nginx (web player + API proxy on :8080 and :12470).
mkdir -p /tmp/nx-proxy /tmp/nx-body
# Render the cert path into the nginx config (honors a custom STREMIOSRV_CACHE_ROOT).
sed "s#/root/.stremio-server/certificates.pem#${CERT}#g" \
    /srv/app/docker/nginx-allinone.conf > /tmp/nginx-allinone.conf
# --no-access-log: don't log every request — those lines include infohash/stream paths (a
# content-neutrality + privacy concern, like nginx's access_log off) and would otherwise bury real
# warnings/errors so the admin Logs card surfaces nothing.
/srv/app/.venv/bin/uvicorn stremiosrv.app:build_app --factory --host 0.0.0.0 --port 11470 \
  --no-access-log &
APP_PID=$!
nginx -c /tmp/nginx-allinone.conf -g 'daemon off;' &
wait "$APP_PID"
