"""Figure 2.1 (a)(b)(c) - Smart Safe Guardian overall system architecture, split in three readable parts.

Generates figure_2_1a_device_tier, figure_2_1b_gateway_tier and figure_2_1c_cloud_user_tiers
(.svg, and .png when cairosvg is available):
    uv run --with cairosvg python docs/system_architecture_diagram/architecture_diagram.py

Same visual language as docs/wiring_diagram/wiring_diagram.py (Inter / DejaVu Sans Mono, 1000 px wide
so that text stays around 7 pt once printed at 16.5 cm). Content mirrors the current repository.
"""
from pathlib import Path
from xml.sax.saxutils import escape

HERE = Path(__file__).resolve().parent
W = 1000

INK, INK2, INK3 = "#1b1f24", "#4a545e", "#7d8791"
LINE, BG = "#c9d0d6", "#ffffff"
DEV, DEV_EDGE, DEV_SUB = "#14344f", "#0b2236", "#a9c3da"          # hardware nodes (as in wiring diagram)
T1 = ("#1f78d1", "#f2f7fd")   # tier accent, tier fill
T2 = ("#0f9d74", "#effaf5")
T4 = ("#6d5bd0", "#f4f2fd")
T5 = ("#b04fc0", "#fbf1fc")
C_RF, C_USB, C_NET = "#0f9d8a", "#4b5563", "#1f78d1"
C_I2C, C_ADC, C_DIG, C_PWM = "#7b4fd6", "#d98a00", "#1f78d1", "#e0601f"


class Svg:
    def __init__(self, h):
        self.h = h
        self.o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{h}" viewBox="0 0 {W} {h}">',
                  '<defs>' + ''.join(
                      f'<marker id="a{c[1:]}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5.5" markerHeight="5.5" '
                      f'orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 z" fill="{c}"/></marker>'
                      for c in (C_RF, C_USB, C_NET, C_I2C, C_ADC, C_DIG, C_PWM, T2[0], T4[0], T5[0], INK3)) + '</defs>',
                  f'<rect x="0" y="0" width="{W}" height="{h}" fill="{BG}"/>']

    def add(self, s):
        self.o.append(s)

    def text(self, x, y, s, size=14, color=INK, weight=400, anchor="start", mono=False, italic=False):
        fam = "'DejaVu Sans Mono',monospace" if mono else "Inter,'DejaVu Sans',Arial,sans-serif"
        st = ' font-style="italic"' if italic else ""
        self.add(f'<text x="{x}" y="{y}" font-family="{fam}" font-size="{size}" fill="{color}" '
                 f'font-weight="{weight}" text-anchor="{anchor}"{st}>{escape(s)}</text>')

    def rect(self, x, y, w, h, fill, stroke="none", sw=1, r=10, dash=None):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" stroke="{stroke}" '
                 f'stroke-width="{sw}"{d}/>')

    def path(self, pts, color, sw=2.5, start=False, end=True, dash=None):
        d = "M" + " L".join(f"{x} {y}" for x, y in pts)
        m = f'marker-id'
        ms = f' marker-start="url(#a{color[1:]})"' if start else ""
        me = f' marker-end="url(#a{color[1:]})"' if end else ""
        ds = f' stroke-dasharray="{dash}"' if dash else ""
        self.add(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{sw}" stroke-linejoin="round"{ms}{me}{ds}/>')

    def pill(self, x, y, s, color, size=12.5, fill=BG):
        w = 0.6 * size * len(s) + 20
        self.rect(x - w / 2, y - 12, w, 24, fill, color, 1.6, 12)
        self.text(x, y + 4.5, s, size, color, 700, "middle")

    def vband(self, x, y, w, h, title, tier):
        acc, fill = tier
        self.rect(x, y, w, h, fill, acc, 1.5, 16)
        self.rect(x, y, 38, h, acc, r=16)
        self.rect(x + 22, y, 16, h, acc, r=0)
        cx, cy = x + 25, y + h / 2
        self.add(f'<text x="{cx}" y="{cy}" transform="rotate(-90 {cx} {cy})" font-family="Inter,\'DejaVu Sans\',sans-serif" '
                 f'font-size="14" font-weight="700" fill="#ffffff" text-anchor="middle">{escape(title)}</text>')

    def band(self, x, y, w, h, title, tier):
        acc, fill = tier
        self.rect(x, y, w, h, fill, acc, 1.5, 16)
        self.rect(x, y, w, 36, acc, r=16)
        self.rect(x, y + 20, w, 16, acc, r=0)
        self.text(x + 18, y + 24, title, 15, "#ffffff", 700)

    def device(self, x, y, w, h, title, sub, lines):
        self.rect(x, y, w, h, DEV, DEV_EDGE, 2, 14)
        self.text(x + 18, y + 30, title, 18, "#ffffff", 700)
        self.text(x + 18, y + 51, sub, 13.5, DEV_SUB)
        for i, s in enumerate(lines):
            self.text(x + 18, y + 80 + i * 21, s, 14, "#e6edf3")

    def box(self, x, y, w, h, title, sub, lines, accent, mono_lines=False, dash=None, fill=BG):
        self.rect(x, y, w, h, fill, LINE if not dash else accent, 1.5, 10, dash)
        if not dash:
            self.rect(x, y, 6, h, accent, r=3)
        self.text(x + 18, y + 27, title, 16, INK, 700)
        yy = y + 27
        if sub:
            self.text(x + 18, y + 47, sub, 13.5, INK2)
            yy = y + 47
        for i, s in enumerate(lines):
            self.text(x + 18, yy + 23 + i * 20, s, 13.5 if mono_lines else 14, INK2, mono=mono_lines)

    def save(self, name):
        svg = "\n".join(self.o + ["</svg>"])
        (HERE / f"{name}.svg").write_text(svg, encoding="utf-8")
        try:
            import cairosvg
            cairosvg.svg2png(bytestring=svg.encode(), write_to=str(HERE / f"{name}.png"), scale=2.5)
            print("Saved", name + ".png/.svg")
        except ImportError:
            print("Saved", name + ".svg (cairosvg missing: PNG skipped)")


# ============================================================== (a) device tier
s = Svg(640)
s.band(20, 20, 960, 600, "TIER 1 · EMBEDDED DEVICE TIER — perception & actuation", T1)
s.device(45, 75, 330, 175, "Yolo:Bit (ESP32)", "Wearable badge · node 2", [
    "• A short: UNLOCK · A long: ACK_BREACH",
    "• B: LOCK (also acks a breach)",
    "• A+B: FAKE_BADGE (< 1.5 s) / PAIR_REQ",
    "• 5×5 RGB matrix + buzzer feedback"])
s.device(565, 75, 390, 175, "YoloUNO (ESP32-S3)", "Central vault controller · node 1", [
    "• FreeRTOS tasks: sensors, LED, telemetry",
    "• 3-strike anti-bruteforce lockdown",
    "• Badge MAC whitelist (paired at boot)",
    "• NeoPixel status + 30 s auto-relock"])
s.path([(382, 165), (558, 165)], C_RF, 3, start=True, end=True, dash="9 7")
s.pill(470, 140, "ESP-NOW · 2.4 GHz", C_RF, fill=T1[1])
s.text(470, 193, "▲ requests", 12.5, INK2, anchor="middle", mono=True)
s.text(470, 211, "▼ status (ch. 1)", 12.5, INK2, anchor="middle", mono=True)

bus_y = 300
s.path([(700, 250), (700, bus_y)], INK3, 2.5, end=False)
s.path([(105, bus_y), (875, bus_y)], INK3, 2.5, end=False)
s.text(105, bus_y - 10, "Vault peripherals (Grove cables · 3.3 V logic)", 13, INK3, 700)
periph = [
    ("DHT20", "Temp & humidity", "I²C · 0x38", C_I2C, "in"),
    ("LCD 1602", "Status display", "I²C · 0x21", C_I2C, "out"),
    ("LDR", "Optical tamper", "ADC · GPIO 1", C_ADC, "in"),
    ("HC-SR04", "Presence < 30 cm", "GPIO 6 / 7", C_DIG, "in"),
    ("IR VS1838B", "PIN keypad", "NEC · GPIO 8", C_DIG, "in"),
    ("SG90 / MG90", "Deadbolt servo", "PWM · GPIO 38", C_PWM, "out"),
]
PWB, GAP, X0, PY = 140, 11, 35, 350
for i, (name, role, itf, col, d) in enumerate(periph):
    x = X0 + i * (PWB + GAP)
    cx = x + PWB / 2
    if d == "in":
        s.path([(cx, PY), (cx, bus_y + 3)], col, 3)
    else:
        s.path([(cx, bus_y), (cx, PY - 2)], col, 3)
    s.rect(x, PY, PWB, 104, BG, LINE, 1.5, 10)
    s.rect(x, PY, PWB, 6, col, r=3)
    s.text(cx, PY + 33, name, 15, INK, 700, "middle")
    s.text(cx, PY + 56, role, 13, INK2, anchor="middle")
    s.text(cx, PY + 84, itf, 12.5, col, 700, "middle", mono=True)

s.path([(945, 250), (945, 540), (905, 540)], C_USB, 4)
s.rect(300, 492, 600, 98, BG, C_USB, 1.8, 10, "7 6")
s.text(320, 520, "USB CDC serial · 115 200 baud  →  Local IoT Gateway (Figure 2.1 (b))", 14.5, INK, 700)
s.text(320, 547, "▲ telemetry JSON every 2 s + immediate event frames", 13.5, INK2, mono=True)
s.text(320, 569, "▼ unlock · lock · lockdown 1/0 · ack · pair", 13.5, INK2, mono=True)
s.text(45, 478, "Sensors feed the vault controller;", 13, INK3, italic=True)
s.text(45, 496, "the LCD and the servo are driven by it.", 13, INK3, italic=True)
s.save("figure_2_1a_device_tier")

# ============================================================== (b) gateway tier
s = Svg(640)
s.band(20, 20, 960, 605, "TIERS 2–3 · LOCAL COMMUNICATION & EDGE GATEWAY TIER", T2)
s.rect(250, 65, 500, 70, BG, C_USB, 1.8, 10, "7 6")
s.text(500, 92, "From the YoloUNO vault (Figure 2.1 (a))", 14.5, INK, 700, anchor="middle")
s.text(500, 117, "USB CDC serial · 115 200 baud · newline JSON", 13.5, INK2, anchor="middle", mono=True)
s.path([(500, 137), (500, 203)], C_USB, 4, start=True, end=True)
s.text(514, 176, "▲ telemetry / events   ▼ commands", 12.5, INK2, mono=True)

s.box(270, 205, 460, 205, "Local IoT Gateway daemon", "gateway/gateway.py · PC or Raspberry Pi Zero 2W", [
    "• Serial JSON parser + 1.5 s event dedup",
    "• Dual MQTT clients: CoreIOT + local TB",
    "• CoreIOT offline buffer (5,000 frames)",
    "• Telegram bot: alerts + RBAC commands",
    "• UDP beacon discovery · systemd service"], T2[0])
s.box(30, 225, 210, 165, "Edge AI (T09)", "anomaly_detector.py", [
    "2 Isolation Forest", "models + rule flags", "anomaly ⇔ score ≥ 0.50"], T2[0])
s.box(760, 225, 210, 165, "Web console (T10)", "web_server.py", [
    "HTTP :5000 · SSE", "7 KPI cards · 5 buttons", "serial CLI"], T2[0])
s.path([(242, 308), (268, 308)], T2[0], 2.5, start=True)
s.path([(732, 308), (758, 308)], T2[0], 2.5, start=True)

TY, TW = 480, 210
targets = [  # x, name, proto, flow, source x on the daemon / console
    (35, "HCMUT CoreIOT", "MQTT :1883", "▲ telemetry ▼ RPC", 300),
    (275, "Local ThingsBoard CE", "MQTT :1883", "▲ telemetry ▼ RPC", 400),
    (515, "Telegram Bot API", "HTTPS", "▲ alerts ▼ commands", 640),
    (760, "Field technician", "HTTP / SSE :5000", "browser on the LAN", 865),
]
for x, name, proto, flow, sx in targets:
    cx = x + TW / 2
    sy = 412 if sx < 760 else 392
    pts = [(sx, sy), (cx, TY - 2)] if sx == cx else [(sx, sy), (sx, 445), (cx, 445), (cx, TY - 2)]
    s.path(pts, C_NET, 2.5, start=True)
    s.rect(x, TY, TW, 100, BG, C_NET, 1.8, 10, "7 6")
    s.text(cx, TY + 30, name, 15, INK, 700, "middle")
    s.text(cx, TY + 55, proto, 13.5, C_NET, 700, "middle", mono=True)
    s.text(cx, TY + 79, flow, 13, INK2, anchor="middle", mono=True)
s.path([(460, TY), (460, 414)], INK3, 2, dash="4 5")
s.text(468, 468, "UDP beacon", 11.5, INK3)
s.text(45, 600, "Store-and-forward: CoreIOT telemetry produced while the cloud link is down is buffered with its "
                "original", 13, INK3, italic=True)
s.text(45, 618, "timestamp and replayed in order on reconnection. Targets continue in Figure 2.1 (c).", 13, INK3,
       italic=True)
s.save("figure_2_1b_gateway_tier")

# ============================================================== (c) cloud + users
s = Svg(700)
s.rect(150, 15, 700, 70, BG, C_NET, 1.8, 10, "7 6")
s.text(500, 43, "From the Local IoT Gateway (Figure 2.1 (b))", 14.5, INK, 700, anchor="middle")
s.text(500, 67, "MQTT telemetry / RPC · Telegram HTTPS · HTTP/SSE :5000", 13.5, INK2, anchor="middle", mono=True)

s.vband(20, 110, 960, 220, "TIER 4 · CLOUD", T4)
s.box(75, 130, 240, 180, "HCMUT CoreIOT", "Cloud platform", [
    "• MQTT broker :1883", "• Dashboard (T11)", "• RuleChain alarms (T12)", "• Public dashboard link"], T4[0])
s.box(330, 130, 320, 180, "Local ThingsBoard (N07)", "Docker Compose · self-hosted", [
    "• tb-node 4.3.1.8 :8080 / :1883", "• PostgreSQL 18 persistence", "• Same dashboard + RuleChain",
    "• UDP beacon :50051"], T4[0])
s.box(690, 130, 275, 180, "Telegram Bot API", "api.telegram.org (HTTPS)", [
    "• Breach, thermal and", "  bruteforce alerts", "• Admin chat-ID whitelist",
    "• /status /unlock /lock …"], T4[0])
for x in (195, 490, 827):
    s.path([(x, 87), (x, 128)], C_NET, 2.5, start=True)

s.vband(20, 390, 960, 250, "TIER 5 · USERS", T5)
s.path([(670, 87), (670, 438)], C_NET, 2.5, start=True, dash="7 6")
s.box(75, 440, 400, 150, "SOC operator (T11, N06)", "Browser · CoreIOT or local ThingsBoard", [
    "• Dashboard: KPIs, multi-axis chart, alarms", "• Access & Security Audit Log (N06)",
    "• 5 remote RPC buttons"], T5[0])
s.box(495, 440, 190, 150, "Field technician", "(T10) on the LAN", [
    "Gateway console", "http://<gw>:5000"], T5[0])
s.box(705, 440, 260, 150, "Mobile responder", "(T13) Telegram app", [
    "• Real-time alerts", "• RBAC commands", "• Breach-cleared notice"], T5[0])
for x in (195, 400, 835):
    s.path([(x, 312), (x, 438)], T5[0], 2.5, start=True)
s.pill(298, 360, "HTTPS / WebSocket", T5[0])
s.pill(835, 360, "HTTPS", T5[0])
s.pill(670, 360, "HTTP / SSE", C_NET)
s.text(30, 668, "Both platforms receive the same telemetry and audit events and accept RPCs; "
                "the ThingsBoard Gateway API (v1/gateway/*) is not used.", 13, INK3, italic=True)
s.save("figure_2_1c_cloud_user_tiers")
