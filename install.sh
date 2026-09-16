#!/bin/bash
set -euo pipefail

WIFI_IFACE="${WIFI_IFACE:-wlp1s0}"
ETH_IFACE="${ETH_IFACE:-ens1}"
SETUP_SSID="${SETUP_SSID:-IRU317-SETUP}"
SETUP_PASSWORD="${SETUP_PASSWORD:-}"
SETUP_PROFILE="iru-setup"
SETUP_ADDR="10.42.0.1/24"
ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"

if [ "${EUID}" -ne 0 ]; then
    echo "Run as root: sudo SETUP_PASSWORD='...' ./install.sh" >&2
    exit 1
fi

if [ -z "$SETUP_PASSWORD" ]; then
    echo "SETUP_PASSWORD is required and must be at least 8 characters." >&2
    exit 1
fi

if [ "${#SETUP_PASSWORD}" -lt 8 ]; then
    echo "SETUP_PASSWORD must be at least 8 characters." >&2
    exit 1
fi

if ! command -v nmcli >/dev/null 2>&1; then
    echo "NetworkManager/nmcli is required." >&2
    exit 1
fi

if ! ip link show "$WIFI_IFACE" >/dev/null 2>&1; then
    echo "Wi-Fi interface not found: $WIFI_IFACE" >&2
    exit 1
fi

install -m 700 "$ROOT_DIR/scripts/iru-wifi-portal.py" /usr/local/sbin/iru-wifi-portal.py
install -m 700 "$ROOT_DIR/scripts/iru-wifi-scan.py" /usr/local/sbin/iru-wifi-scan.py
install -m 700 "$ROOT_DIR/scripts/iru-wifi-fallback.sh" /usr/local/sbin/iru-wifi-fallback.sh

# Adapt the tested defaults when other interface names are supplied.
sed -i "s/IFACE = \"wlp1s0\"/IFACE = \"$WIFI_IFACE\"/" /usr/local/sbin/iru-wifi-portal.py
sed -i "s/IFACE = \"wlp1s0\"/IFACE = \"$WIFI_IFACE\"/" /usr/local/sbin/iru-wifi-scan.py
sed -i "s/IFACE=\"wlp1s0\"/IFACE=\"$WIFI_IFACE\"/" /usr/local/sbin/iru-wifi-fallback.sh
sed -i "s/ETH=\"ens1\"/ETH=\"$ETH_IFACE\"/" /usr/local/sbin/iru-wifi-fallback.sh

install -m 644 "$ROOT_DIR/systemd/iru-wifi-portal.service" /etc/systemd/system/iru-wifi-portal.service
install -m 644 "$ROOT_DIR/systemd/iru-wifi-fallback.service" /etc/systemd/system/iru-wifi-fallback.service
install -m 644 "$ROOT_DIR/systemd/iru-wifi-fallback.timer" /etc/systemd/system/iru-wifi-fallback.timer
install -m 644 "$ROOT_DIR/systemd/iru-captive-redirect.service" /etc/systemd/system/iru-captive-redirect.service
sed -i "s/-i wlp1s0/-i $WIFI_IFACE/g" /etc/systemd/system/iru-captive-redirect.service

mkdir -p /etc/NetworkManager/dnsmasq-shared.d
install -m 644 "$ROOT_DIR/networkmanager/90-iru-captive.conf" /etc/NetworkManager/dnsmasq-shared.d/90-iru-captive.conf

python3 -m py_compile /usr/local/sbin/iru-wifi-portal.py /usr/local/sbin/iru-wifi-scan.py
bash -n /usr/local/sbin/iru-wifi-fallback.sh

# Recreate only the dedicated setup profile; normal Wi-Fi profiles are untouched.
nmcli connection delete "$SETUP_PROFILE" >/dev/null 2>&1 || true
nmcli connection add \
    type wifi \
    ifname "$WIFI_IFACE" \
    con-name "$SETUP_PROFILE" \
    ssid "$SETUP_SSID"

nmcli connection modify "$SETUP_PROFILE" \
    802-11-wireless.mode ap \
    802-11-wireless.band bg \
    wifi-sec.key-mgmt wpa-psk \
    wifi-sec.psk "$SETUP_PASSWORD" \
    ipv4.method shared \
    ipv4.addresses "$SETUP_ADDR" \
    ipv6.method disabled \
    connection.autoconnect no

systemctl daemon-reload
systemctl enable iru-wifi-portal.service
systemctl enable iru-wifi-fallback.timer
systemctl enable iru-captive-redirect.service

systemctl restart iru-wifi-portal.service
systemctl restart iru-captive-redirect.service
systemctl restart iru-wifi-fallback.timer

echo 0 > /run/iru-wifi-fallback.count

echo
echo "Installed IRU317 Wi-Fi Recovery Portal."
echo "Wi-Fi interface: $WIFI_IFACE"
echo "Setup SSID:       $SETUP_SSID"
echo "Setup portal:     http://10.42.0.1/"
echo
echo "The setup password was applied to NetworkManager and was not written into this repository."
