#!/bin/bash

set -u

IFACE="wlp1s0"
ETH="ens1"
SETUP="iru-setup"

COUNT_FILE="/run/iru-wifi-fallback.count"
LOCK_FILE="/run/iru-wifi-fallback.lock"

exec 9>"$LOCK_FILE"
/usr/bin/flock -n 9 || exit 0


log() {
    /usr/bin/logger -t iru-wifi-fallback "$*"
    echo "$*"
}


reset_count() {
    echo 0 > "$COUNT_FILE"
}


get_count() {
    if [ -r "$COUNT_FILE" ]; then
        cat "$COUNT_FILE" 2>/dev/null || echo 0
    else
        echo 0
    fi
}


# Если NetworkManager сейчас перезапускается - ничего не делаем.
if ! /usr/bin/systemctl is-active --quiet NetworkManager; then
    log "NetworkManager is not ready"
    exit 0
fi


wifi_connection="$(
    /usr/bin/nmcli -g GENERAL.CONNECTION \
    device show "$IFACE" 2>/dev/null || true
)"

wifi_ip="$(
    /usr/bin/nmcli -g IP4.ADDRESS \
    device show "$IFACE" 2>/dev/null \
    | head -1
)"


# Setup mode уже работает.
if [ "$wifi_connection" = "$SETUP" ]; then
    reset_count
    exit 0
fi


# Нормальный Wi-Fi уже есть.
if [ -n "$wifi_connection" ] \
   && [ "$wifi_connection" != "--" ] \
   && [ -n "$wifi_ip" ]; then

    reset_count
    exit 0
fi


# Если есть проводной Ethernet - fallback Wi-Fi не нужен.
eth_ip="$(
    /usr/bin/nmcli -g IP4.ADDRESS \
    device show "$ETH" 2>/dev/null \
    | head -1
)"

if [ -n "$eth_ip" ]; then
    reset_count
    exit 0
fi


count="$(get_count)"

case "$count" in
    ''|*[!0-9]*)
        count=0
        ;;
esac

count=$((count + 1))
echo "$count" > "$COUNT_FILE"

log "No usable network - check $count/3"


# Просто ждём. NetworkManager сам продолжает
# пытаться подключиться к известным профилям.
if [ "$count" -lt 3 ]; then
    exit 0
fi


log "No saved Wi-Fi connected - scanning before setup mode"

/usr/bin/nmcli radio wifi on >/dev/null 2>&1 || true

sleep 2

if /usr/local/sbin/iru-wifi-scan.py; then
    log "Wi-Fi scan completed"
else
    log "Wi-Fi scan returned no networks"
fi


log "Activating IRU317-SETUP"

if /usr/bin/nmcli connection up "$SETUP" \
    >/dev/null 2>&1; then

    log "IRU317-SETUP active on 10.42.0.1"
    reset_count
else
    log "ERROR: failed to activate IRU317-SETUP"
fi
