#!/bin/sh
# Isolated, non-root regression test: mocked iptables, no live firewall changes.
set -eu
# Validate the complete VPN entrypoint, not just extracted helper functions.
/bin/sh -n "${1:-vpn/entrypoint.sh}"
ENTRYPOINT="${1:-vpn/entrypoint.sh}"
TEMP="$(mktemp -d)"
trap 'rm -rf "$TEMP"' EXIT
export MOCK_STATE="$TEMP/state"
cat > "$MOCK_STATE" <<'EOF'
-P INPUT DROP
-A INPUT -i lo -j ACCEPT
-A INPUT -i lo -j ACCEPT
-P OUTPUT DROP
-A OUTPUT -o tun0 -j ACCEPT
-A OUTPUT -o tun0 -j ACCEPT
-A OUTPUT -o tun0 -j ACCEPT
-A OUTPUT -o lo -j ACCEPT
EOF
cat > "$TEMP/iptables" <<'EOF'
#!/bin/sh
set -eu
if [ "${1:-}" = "-S" ]; then
    awk -v chain="$2" '$2 == chain {print}' "$MOCK_STATE"
elif [ "${1:-}" = "-w" ]; then
    shift 2
    [ "$1" = "-D" ] || exit 3
    shift
    chain="$1"
    shift
    target="-A $chain $*"
    awk -v target="$target" '{
        if (!removed && $0 == target) {removed=1; next}
        print
    }' "$MOCK_STATE" > "$MOCK_STATE.tmp"
    mv "$MOCK_STATE.tmp" "$MOCK_STATE"
else
    exit 4
fi
EOF
chmod +x "$TEMP/iptables"
PATH="$TEMP:$PATH"
export PATH
function_text="$(sed -n '/^deduplicate_firewall_rules() {/,/^}/p' "$ENTRYPOINT")"
[ -n "$function_text" ] || { echo MISSING_FUNCTION; exit 1; }
eval "$function_text"
deduplicate_firewall_rules
deduplicate_firewall_rules
[ "$(grep -c '^-A OUTPUT -o tun0 -j ACCEPT$' "$MOCK_STATE")" -eq 1 ]
[ "$(grep -c '^-A INPUT -i lo -j ACCEPT$' "$MOCK_STATE")" -eq 1 ]
[ "$(grep -c '^-A OUTPUT -o lo -j ACCEPT$' "$MOCK_STATE")" -eq 1 ]
grep -q '^-P OUTPUT DROP$' "$MOCK_STATE"
grep -q '^-P INPUT DROP$' "$MOCK_STATE"
echo FIREWALL_DEDUP_MOCK_PASS
