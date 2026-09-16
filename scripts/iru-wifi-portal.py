#!/usr/bin/env python3

import hashlib
import html
import json
import os
import subprocess
import threading
import time

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

IFACE = "wlp1s0"
SETUP = "iru-setup"
CACHE = "/run/iru-wifi-networks.json"

LOCK = threading.Lock()
STATE = {
    "busy": False,
    "message": "Выберите Wi-Fi сеть.",
}


def nmcli(*args, timeout=30):
    env = os.environ.copy()
    env["LC_ALL"] = "C"
    return subprocess.run(
        ["/usr/bin/nmcli", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )


def allowed_client(ip):
    return ip.startswith("10.42.0.") or ip in ("127.0.0.1", "::1")


def load_networks():
    try:
        with open(CACHE, "r", encoding="utf-8") as f:
            data = json.load(f)
        result = []
        for item in data:
            ssid = str(item.get("ssid", "")).strip()
            if not ssid or ssid == "--":
                continue
            result.append({
                "ssid": ssid,
                "signal": int(item.get("signal", 0)),
                "security": str(item.get("security", "Open")),
            })
        return result
    except Exception:
        return []


def saved_wifi_profiles():
    result = {}
    r = nmcli("-t", "-f", "NAME,TYPE", "connection", "show")
    if r.returncode != 0:
        return result

    for raw in r.stdout.splitlines():
        if ":" not in raw:
            continue
        name, typ = raw.rsplit(":", 1)
        if typ not in ("wifi", "802-11-wireless") or name == SETUP:
            continue
        s = nmcli("-g", "802-11-wireless.ssid", "connection", "show", name)
        ssid = s.stdout.strip()
        if ssid:
            result.setdefault(ssid, name)
    return result


def signal_bars(signal):
    if signal >= 75:
        level = 4
    elif signal >= 55:
        level = 3
    elif signal >= 35:
        level = 2
    else:
        level = 1

    bars = []
    for i in range(1, 5):
        cls = "on" if i <= level else ""
        bars.append(f'<span class="{cls} b{i}"></span>')
    return "".join(bars)


def render_page():
    networks = load_networks()
    saved = saved_wifi_profiles()

    with LOCK:
        message = STATE["message"]
        busy = STATE["busy"]

    disabled = "disabled" if busy else ""
    rows = []

    for net in networks:
        ssid = net["ssid"]
        signal = net["signal"]
        security = net["security"]
        badge = '<span class="known">✓ сохранена</span>' if ssid in saved else ""

        rows.append(f'''
<label class="network">
  <input type="radio" name="ssid" value="{html.escape(ssid, quote=True)}" {disabled}>
  <div class="network-main">
    <div class="ssid-row"><span class="ssid">{html.escape(ssid)}</span>{badge}</div>
    <div class="meta">
      <span>{html.escape(security)}</span>
      <span class="signal"><span class="bars">{signal_bars(signal)}</span>{signal}%</span>
    </div>
  </div>
</label>
''')

    if not rows:
        rows.append('<div class="empty">Список сетей пуст. Можно ввести SSID вручную.</div>')

    return f'''<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>IRU317 Wi-Fi</title>
<style>
*{{box-sizing:border-box}}body{{margin:0;min-height:100vh;background:linear-gradient(180deg,#f2f5f8,#e9eef3);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif;color:#18202a}}.wrap{{width:min(620px,calc(100% - 28px));margin:30px auto}}.card{{background:#fff;border-radius:26px;padding:26px;box-shadow:0 20px 60px rgba(20,40,60,.10)}}.logo{{width:54px;height:54px;border-radius:17px;display:grid;place-items:center;font-weight:800;background:#18202a;color:#fff;margin-bottom:18px}}h1{{margin:0;font-size:27px}}.subtitle{{margin-top:7px;color:#66717f;line-height:1.45}}.status{{margin:20px 0;padding:14px 16px;border-radius:15px;background:#f4f7f9;color:#46515d;font-size:14px}}.section-title{{margin:22px 0 10px;font-size:13px;font-weight:700;color:#7b8590;text-transform:uppercase;letter-spacing:.06em}}.network{{display:flex;align-items:center;gap:13px;padding:14px 13px;margin-bottom:8px;border:1px solid #e6eaf0;border-radius:16px;cursor:pointer}}.network:has(input:checked){{border-color:#536170;background:#f5f7f9}}.network input{{width:20px;height:20px}}.network-main{{min-width:0;flex:1}}.ssid-row{{display:flex;align-items:center;gap:8px}}.ssid{{font-weight:650;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}.known{{font-size:11px;padding:4px 7px;border-radius:20px;background:#e8f5eb;color:#26763b;font-weight:700}}.meta{{margin-top:6px;display:flex;justify-content:space-between;color:#87919b;font-size:12px}}.signal{{display:flex;align-items:center;gap:6px}}.bars{{height:15px;display:flex;align-items:end;gap:2px}}.bars span{{display:block;width:3px;border-radius:2px;background:#d7dce1}}.bars .b1{{height:4px}}.bars .b2{{height:7px}}.bars .b3{{height:10px}}.bars .b4{{height:14px}}.bars span.on{{background:#344252}}input[type=text],input[type=password]{{width:100%;border:1px solid #dfe4e9;border-radius:14px;padding:14px 15px;font-size:16px}}.password-wrap{{position:relative}}.password-wrap input{{padding-right:72px}}.show-password{{position:absolute;right:9px;top:50%;transform:translateY(-50%);border:0;background:transparent;font-weight:650;color:#596776;cursor:pointer}}.connect{{width:100%;margin-top:18px;padding:15px;border:0;border-radius:15px;background:#18202a;color:#fff;font-weight:750;font-size:16px;cursor:pointer}}.connect:disabled{{opacity:.45}}.note{{margin-top:15px;color:#88929d;font-size:12px;line-height:1.5;text-align:center}}.empty{{padding:18px;border-radius:15px;background:#f5f7f9;color:#697580;font-size:14px}}.footer{{margin-top:16px;text-align:center;color:#9aa3ac;font-size:11px}}@media(max-width:520px){{.wrap{{margin:14px auto}}.card{{padding:20px;border-radius:22px}}}}
</style>
</head>
<body>
<div class="wrap"><div class="card">
<div class="logo">IRU</div>
<h1>Настройка Wi-Fi</h1>
<div class="subtitle">Выберите сеть для IRU317. После успешного подключения она будет сохранена автоматически.</div>
<div class="status">{html.escape(message)}</div>
<form method="post" action="/connect">
<div class="section-title">Доступные сети</div>
{''.join(rows)}
<div class="section-title">Другая сеть</div>
<input type="text" name="manual_ssid" placeholder="Имя сети (SSID)" autocomplete="off" {disabled}>
<div class="section-title">Пароль</div>
<div class="password-wrap">
<input id="wifi-password" type="password" name="password" placeholder="Пароль Wi-Fi" autocomplete="current-password" {disabled}>
<button type="button" class="show-password" onclick="togglePassword()">Показать</button>
</div>
<button class="connect" type="submit" {disabled}>Подключиться</button>
</form>
<div class="note">Для сети с отметкой «✓ сохранена» пароль можно оставить пустым.<br>Если подключение не удастся, IRU317-SETUP появится снова.</div>
</div><div class="footer">IRU317 · Wi-Fi Recovery Portal</div></div>
<script>
function togglePassword(){{const i=document.getElementById('wifi-password');const b=document.querySelector('.show-password');if(i.type==='password'){{i.type='text';b.textContent='Скрыть'}}else{{i.type='password';b.textContent='Показать'}}}}
</script>
</body></html>'''


def normal_connection_ready():
    for _ in range(40):
        c = nmcli("-g", "GENERAL.CONNECTION", "device", "show", IFACE).stdout.strip()
        ip = nmcli("-g", "IP4.ADDRESS", "device", "show", IFACE).stdout.strip()
        if c and c != "--" and c != SETUP and ip:
            return True
        time.sleep(1)
    return False


def connect_worker(ssid, password, hidden):
    generated = False
    try:
        with LOCK:
            STATE["message"] = f"Подключаемся к {ssid}..."

        saved = saved_wifi_profiles()

        if ssid in saved and not password:
            profile = saved[ssid]
            nmcli("connection", "down", SETUP, timeout=15)
            time.sleep(2)
            r = nmcli("connection", "up", profile, "ifname", IFACE, timeout=45)
        else:
            profile = "iru-wifi-" + hashlib.sha256(ssid.encode("utf-8")).hexdigest()[:10]
            generated = True
            nmcli("connection", "delete", profile, timeout=10)
            nmcli("connection", "down", SETUP, timeout=15)
            time.sleep(2)

            args = ["device", "wifi", "connect", ssid, "ifname", IFACE, "name", profile]
            if password:
                args += ["password", password]
            if hidden:
                args += ["hidden", "yes"]

            r = nmcli(*args, timeout=50)
            if r.returncode == 0:
                nmcli(
                    "connection", "modify", profile,
                    "connection.autoconnect", "yes",
                    "connection.autoconnect-priority", "80",
                )

        if r.returncode == 0 and normal_connection_ready():
            with LOCK:
                STATE["message"] = f"Подключено к {ssid}."
                STATE["busy"] = False
            return

        if generated:
            nmcli("connection", "delete", profile, timeout=10)

        nmcli("connection", "up", SETUP, timeout=30)
        with LOCK:
            STATE["message"] = "Не удалось подключиться. Проверьте пароль и попробуйте ещё раз."
            STATE["busy"] = False

    except Exception:
        nmcli("connection", "up", SETUP, timeout=30)
        with LOCK:
            STATE["message"] = "Ошибка подключения. Режим настройки восстановлен."
            STATE["busy"] = False


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f'{self.client_address[0]} - {fmt % args}', flush=True)

    def send_html(self, body, code=200):
        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if not allowed_client(self.client_address[0]):
            self.send_html("<h1>403</h1>", 403)
            return
        self.send_html(render_page())

    def do_POST(self):
        if not allowed_client(self.client_address[0]):
            self.send_html("<h1>403</h1>", 403)
            return

        if self.path != "/connect":
            self.send_html("<h1>404</h1>", 404)
            return

        length = int(self.headers.get("Content-Length", "0"))
        data = parse_qs(self.rfile.read(length).decode("utf-8", errors="replace"))
        selected = data.get("ssid", [""])[0].strip()
        manual = data.get("manual_ssid", [""])[0].strip()
        password = data.get("password", [""])[0]
        ssid = manual or selected
        hidden = bool(manual)

        if not ssid:
            with LOCK:
                STATE["message"] = "Сначала выберите сеть."
            self.send_html(render_page())
            return

        with LOCK:
            if STATE["busy"]:
                self.send_html(render_page())
                return
            STATE["busy"] = True
            STATE["message"] = f"Готовимся подключиться к {ssid}..."

        threading.Timer(1.0, connect_worker, args=(ssid, password, hidden)).start()
        self.send_html('''<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>IRU317</title></head><body style="font-family:sans-serif;background:#f0f3f6;display:grid;place-items:center;min-height:100vh"><div style="background:white;padding:30px;border-radius:24px;text-align:center"><h2>Подключаем IRU317</h2><p>Точка IRU317-SETUP сейчас исчезнет.<br>После подключения сервера вернитесь в обычную Wi-Fi сеть.</p></div></body></html>''')


if __name__ == "__main__":
    server = ThreadingHTTPServer(("0.0.0.0", 80), Handler)
    print("IRU317 Wi-Fi portal listening on port 80", flush=True)
    server.serve_forever()
