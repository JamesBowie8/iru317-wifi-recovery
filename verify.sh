#!/bin/bash
set -u

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
FAIL=0

ok()   { printf 'OK   %s\n' "$*"; }
warn() { printf 'WARN %s\n' "$*"; }
fail() { printf 'FAIL %s\n' "$*"; FAIL=1; }

compare_file() {
    local repo_file="$1"
    local installed_file="$2"

    if [ ! -f "$installed_file" ]; then
        fail "$installed_file is missing"
        return
    fi

    if cmp -s "$ROOT_DIR/$repo_file" "$installed_file"; then
        ok "$installed_file matches GitHub copy"
    else
        fail "$installed_file differs from $repo_file"
        diff -u "$ROOT_DIR/$repo_file" "$installed_file" || true
    fi
}

echo '=== FILES ==='
compare_file scripts/iru-wifi-portal.py /usr/local/sbin/iru-wifi-portal.py
compare_file scripts/iru-wifi-scan.py /usr/local/sbin/iru-wifi-scan.py
compare_file scripts/iru-wifi-fallback.sh /usr/local/sbin/iru-wifi-fallback.sh
compare_file systemd/iru-wifi-portal.service /etc/systemd/system/iru-wifi-portal.service
compare_file systemd/iru-wifi-fallback.service /etc/systemd/system/iru-wifi-fallback.service
compare_file systemd/iru-wifi-fallback.timer /etc/systemd/system/iru-wifi-fallback.timer
compare_file systemd/iru-captive-redirect.service /etc/systemd/system/iru-captive-redirect.service
compare_file networkmanager/90-iru-captive.conf /etc/NetworkManager/dnsmasq-shared.d/90-iru-captive.conf

echo
echo '=== SYNTAX ==='
if python3 -m py_compile /usr/local/sbin/iru-wifi-portal.py /usr/local/sbin/iru-wifi-scan.py; then
    ok 'Python syntax'
else
    fail 'Python syntax'
fi

if bash -n /usr/local/sbin/iru-wifi-fallback.sh; then
    ok 'fallback shell syntax'
else
    fail 'fallback shell syntax'
fi

echo
echo '=== SERVICES ==='
for unit in iru-wifi-portal.service iru-wifi-fallback.timer iru-captive-redirect.service NetworkManager.service; do
    state="$(systemctl is-active "$unit" 2>/dev/null || true)"
    if [ "$state" = active ]; then
        ok "$unit active"
    else
        fail "$unit state=$state"
    fi
done

echo
echo '=== SETUP PROFILE (NO SECRET OUTPUT) ==='
PROFILE=iru-setup
if nmcli -g NAME connection show "$PROFILE" >/dev/null 2>&1; then
    ok "$PROFILE exists"

    mode="$(nmcli -g 802-11-wireless.mode connection show "$PROFILE" 2>/dev/null || true)"
    band="$(nmcli -g 802-11-wireless.band connection show "$PROFILE" 2>/dev/null || true)"
    ipv4="$(nmcli -g ipv4.method connection show "$PROFILE" 2>/dev/null || true)"
    addr="$(nmcli -g ipv4.addresses connection show "$PROFILE" 2>/dev/null || true)"
    auto="$(nmcli -g connection.autoconnect connection show "$PROFILE" 2>/dev/null || true)"

    [ "$mode" = ap ] && ok 'setup mode=ap' || fail "setup mode=$mode"
    [ "$band" = bg ] && ok 'setup band=bg' || warn "setup band=$band"
    [ "$ipv4" = shared ] && ok 'setup ipv4.method=shared' || fail "setup ipv4.method=$ipv4"
    printf '%s\n' "$addr" | grep -q '^10\.42\.0\.1/24' && ok 'setup address=10.42.0.1/24' || fail "setup address=$addr"
    [ "$auto" = no ] && ok 'setup autoconnect=no' || fail "setup autoconnect=$auto"
else
    fail "$PROFILE is missing"
fi

echo
echo '=== RUNTIME ==='
active_wifi="$(nmcli -g GENERAL.CONNECTION device show wlp1s0 2>/dev/null || true)"
printf 'Active Wi-Fi connection: %s\n' "${active_wifi:-(none)}"

if pgrep -af 'dnsmasq.*--listen-address=10\.42\.0\.1' >/dev/null 2>&1; then
    if [ "$active_wifi" = iru-setup ]; then
        ok 'setup dnsmasq is running while AP is active'
    else
        fail 'stale setup dnsmasq is running outside setup mode'
    fi
else
    if [ "$active_wifi" = iru-setup ]; then
        warn 'setup AP active but setup dnsmasq was not found'
    else
        ok 'no stale setup dnsmasq'
    fi
fi

if iptables -t nat -C PREROUTING -i wlp1s0 -s 10.42.0.0/24 -p tcp --dport 80 -j REDIRECT --to-ports 80 2>/dev/null; then
    ok 'captive HTTP redirect rule installed'
else
    fail 'captive HTTP redirect rule missing'
fi

echo
echo '=== REPOSITORY SECRET SANITY CHECK ==='
if grep -RInE --exclude-dir=.git --exclude='verify.sh' '(wifi-sec\.psk[[:space:]]+[^$]|psk=[^A-Z]|BEGIN (RSA|OPENSSH|EC) PRIVATE KEY|api[_-]?key[[:space:]]*=|token[[:space:]]*=)' "$ROOT_DIR" >/tmp/iru-repo-secret-check.$$ 2>/dev/null; then
    warn 'possible secret-like strings found; review manually:'
    cat /tmp/iru-repo-secret-check.$$
else
    ok 'no obvious committed secrets detected'
fi
rm -f /tmp/iru-repo-secret-check.$$

echo
echo '=== RESULT ==='
if [ "$FAIL" -eq 0 ]; then
    echo 'PASS - installed system matches the repository checks.'
else
    echo 'FAIL - see differences above.'
fi

exit "$FAIL"
