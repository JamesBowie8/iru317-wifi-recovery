# IRU317 Wi-Fi Recovery Portal

[Русский](README.md) | **English**

A lightweight headless Wi-Fi recovery/setup portal for Ubuntu Server + NetworkManager on a machine with **a single Wi-Fi adapter**.

The project was built for an iRU 317 mini PC that needs to move between networks without a monitor or keyboard. If a known Wi-Fi network is available, NetworkManager connects normally. If no usable saved network is available, a watchdog scans nearby Wi-Fi networks while the adapter is still in client mode, caches the results, and then starts a temporary access point called `IRU317-SETUP`. A phone detects the captive portal, opens the setup page, the user selects a Wi-Fi network and enters its password, and the new NetworkManager profile is saved for future use.

## How it works

```text
boot
  |
  +-- saved Wi-Fi is available --> normal operation
  |
  +-- no usable network
        |
        +-- watchdog waits through several checks
        +-- scan Wi-Fi while still in client mode
        +-- cache networks in /run/iru-wifi-networks.json
        +-- start IRU317-SETUP (10.42.0.1/24)
        +-- captive portal at http://10.42.0.1/
        +-- select network + enter password
        +-- save NetworkManager profile
        +-- connect to the new network
```

The important detail is that with a single radio, scanning is done **before** switching the adapter into AP mode. This keeps the setup access point stable while the user is viewing the page and allows the portal to show a ready-made list of nearby networks.

## Project layout

- `scripts/iru-wifi-portal.py` - setup portal implemented with the Python standard library, no Flask required.
- `scripts/iru-wifi-scan.py` - scans and caches nearby SSIDs.
- `scripts/iru-wifi-fallback.sh` - watchdog that activates setup mode when normal networking is unavailable.
- `systemd/iru-wifi-portal.service` - portal service.
- `systemd/iru-wifi-fallback.service` + `.timer` - periodic network checks.
- `systemd/iru-captive-redirect.service` - redirects HTTP captive-portal probes to the local portal.
- `networkmanager/90-iru-captive.conf` - DNS redirection inside the setup network.
- `install.sh` - installs the project and creates the dedicated AP profile.
- `verify.sh` - non-destructive verification that an installed system matches the repository baseline.

## Requirements

Verified environment: Ubuntu Server 24.04, NetworkManager 1.46.x, Python 3.12, `iptables`, `dnsmasq`, and a Wi-Fi adapter with AP mode support. The tested interface names are Wi-Fi `wlp1s0` and Ethernet `ens1`.

Check AP support with:

```bash
sudo iw list | sed -n '/Supported interface modes:/,/Band/p'
```

The list should contain `AP`.

## Installation

> Do not commit real `.nmconnection` files. They may contain Wi-Fi PSKs.

Clone the repository and run the installer as root. The setup-network password is provided locally and is **not written to Git**:

```bash
git clone https://github.com/JamesBowie8/iru317-wifi-recovery.git
cd iru317-wifi-recovery
sudo SETUP_PASSWORD='CHANGE-ME-1234' ./install.sh
```

Default values:

```text
Wi-Fi interface: wlp1s0
Ethernet:         ens1
Setup SSID:       IRU317-SETUP
Setup address:    10.42.0.1/24
Portal:           http://10.42.0.1/
```

These can be overridden with environment variables.

## Verify an installed system against the repository

On a running server with this repository cloned:

```bash
cd iru317-wifi-recovery
git pull
chmod +x verify.sh
sudo ./verify.sh
```

The verifier does not modify the system. It compares the installed scripts, systemd units and dnsmasq configuration with the repository, checks syntax, service state, the `iru-setup` profile, the captive HTTP redirect rule, and stale setup dnsmasq processes. It does not print the saved Wi-Fi PSK.

A clean result ends with:

```text
PASS - installed system matches the repository checks.
```

If a live server intentionally differs from the repository, inspect the displayed diff before copying anything back into Git.

## Manual diagnostics

```bash
systemctl status iru-wifi-portal --no-pager
systemctl status iru-wifi-fallback.timer --no-pager
systemctl status iru-captive-redirect.service --no-pager
nmcli -f NAME,TYPE,DEVICE connection show --active
sudo /usr/local/sbin/iru-wifi-scan.py
python3 -m json.tool /run/iru-wifi-networks.json
```

## Security and privacy

- Real Wi-Fi passwords should never be committed to the repository.
- `IRU317-SETUP` is protected with WPA-PSK.
- The portal accepts clients only from `10.42.0.0/24` and localhost.
- New Wi-Fi profiles are created locally by NetworkManager.
- `.gitignore` excludes `.nmconnection` files, secrets, runtime cache files and local backups.
- `verify.sh` checks the project without reading or printing saved Wi-Fi PSKs.
- The project does not require publishing home SSIDs, public IP addresses, passwords, or real NetworkManager connection files.

If UFW is enabled, allow HTTP, DNS and optionally emergency SSH from the setup subnet.

## Recovery access

While setup mode is active, the server address is `10.42.0.1`.

## License

Licensed under the [MIT License](LICENSE).
