#!/usr/bin/env python3

import json
import os
import subprocess
import time

IFACE = "wlp1s0"
CACHE = "/run/iru-wifi-networks.json"


def nmcli(*args, timeout=30):
    env = os.environ.copy()
    env["LC_ALL"] = "C"

    return subprocess.run(
        ["/usr/bin/nmcli", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env
    )


def parse(text):
    networks = []
    block = {}

    def commit():
        ssid = block.get("SSID", "").strip()

        if not ssid or ssid == "--":
            return

        try:
            signal = int(block.get("SIGNAL", "0"))
        except ValueError:
            signal = 0

        security = block.get("SECURITY", "").strip()

        if not security or security == "--":
            security = "Open"

        networks.append({
            "ssid": ssid,
            "signal": signal,
            "security": security
        })

    for raw in text.splitlines():
        if ":" not in raw:
            continue

        key, value = raw.split(":", 1)
        key = key.strip()
        value = value.strip()

        if key == "SSID" and "SSID" in block:
            commit()
            block = {}

        block[key] = value

    commit()

    unique = {}

    for item in networks:
        ssid = item["ssid"]

        if (
            ssid not in unique
            or item["signal"] > unique[ssid]["signal"]
        ):
            unique[ssid] = item

    return sorted(
        unique.values(),
        key=lambda x: x["signal"],
        reverse=True
    )


networks = []

for attempt in range(1, 4):
    print(f"Wi-Fi scan attempt {attempt}/3...")

    nmcli(
        "device", "wifi", "rescan",
        "ifname", IFACE,
        timeout=20
    )

    time.sleep(4)

    r = nmcli(
        "-m", "multiline",
        "-f", "SSID,SIGNAL,SECURITY",
        "device", "wifi", "list",
        "ifname", IFACE,
        "--rescan", "no",
        timeout=30
    )

    if r.returncode == 0:
        networks = parse(r.stdout)

    if networks:
        break

    time.sleep(3)


tmp = CACHE + ".tmp"

with open(tmp, "w", encoding="utf-8") as f:
    json.dump(
        networks,
        f,
        ensure_ascii=False,
        indent=2
    )

os.chmod(tmp, 0o644)
os.replace(tmp, CACHE)

print(f"Saved {len(networks)} Wi-Fi networks")

for item in networks:
    print(
        f'{item["signal"]:3}%  '
        f'{item["ssid"]:<30} '
        f'{item["security"]}'
    )

raise SystemExit(0 if networks else 1)
