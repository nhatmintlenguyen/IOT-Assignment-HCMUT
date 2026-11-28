"""Figure 3.2 - Smart Safe Guardian hardware wiring diagram (portrait, A4 report width).

Generates wiring_diagram.svg and wiring_diagram.png (PNG needs cairosvg):
    uv run --with cairosvg python docs/wiring_diagram/wiring_diagram.py

The canvas is 1000 px wide so that, printed at 16.5 cm, body text stays around 7 pt.
Pin numbers mirror the firmware:
  firmware/vault_yolouno/src/sensor_monitor.cpp  (I2C 11/12, LDR 1, Trig 6, Echo 7)
  firmware/vault_yolouno/src/ir_reader.cpp       (IR 8)
  firmware/vault_yolouno/src/servo_control.cpp   (servo 38, 500-2500 us)
  firmware/vault_yolouno/src/lcd_display.cpp     (LCD 0x21)
  firmware/vault_yolouno/src/main.cpp            (NeoPixel 45, LED 48, BOOT 0)
  firmware/badge_yolobit/src/main.cpp            (A 35, B 14, buzzer 25, matrix 4)
"""
from pathlib import Path
from xml.sax.saxutils import escape

HERE = Path(__file__).resolve().parent
W, H = 1000, 1540

# palette ---------------------------------------------------------------
INK, INK2, INK3 = "#1b1f24", "#4a545e", "#7d8791"
LINE, PANEL, BG = "#c9d0d6", "#f6f8fa", "#ffffff"
BOARD, BOARD_EDGE = "#14344f", "#0b2236"          # YoloUNO PCB
BADGE, BADGE_EDGE = "#2b2f36", "#15181c"          # Yolo:Bit PCB
C_I2C, C_ADC, C_DIG = "#7b4fd6", "#d98a00", "#1f78d1"
C_PWM, C_USB, C_RF = "#e0601f", "#4b5563", "#0f9d8a"
GROVE_ROW = {"i2c": "#d9433b", "adc": "#f2c230", "dig": "#f4f4f2"}  # board silk colours

out = []
add = out.append


def text(x, y, s, size=15, color=INK, weight=400, anchor="start", family="body", italic=False):
    fam = "'DejaVu Sans Mono',monospace" if family == "mono" else "Inter,'DejaVu Sans',Arial,sans-serif"
    st = ' font-style="italic"' if italic else ""
    add(f'<text x="{x}" y="{y}" font-family="{fam}" font-size="{size}" fill="{color}" '
        f'font-weight="{weight}" text-anchor="{anchor}"{st}>{escape(s)}</text>')


def rect(x, y, w, h, fill, stroke="none", sw=1, r=8):
    add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')


def line(x1, y1, x2, y2, color, sw=3, dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    add(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{sw}" '
        f'stroke-linecap="round"{d}/>')


def pill(x, y, s, color, size=13):
    w = 0.62 * size * len(s) + 18
    rect(x - w / 2, y - 12, w, 24, BG, color, 1.6, 12)
    text(x, y + 5, s, size, color, 700, "middle")


def component(x, y, w, h, title, sub, lines, accent):
    rect(x, y, w, h, BG, LINE, 1.5, 10)
    rect(x, y, 6, h, accent, r=3)
    text(x + 18, y + 27, title, 17, INK, 700)
    text(x + 18, y + 48, sub, 14, INK2)
    for i, s in enumerate(lines):
        text(x + 18, y + 72 + i * 20, s, 13.5, INK2, family="mono")


add(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">')
rect(0, 0, W, H, BG, r=0)
text(20, 40, "Smart Safe Guardian — Hardware Wiring Diagram", 26, INK, 700)
text(20, 68, "Vault node (YoloUNO · ESP32-S3), wearable badge (Yolo:Bit · ESP32) and edge gateway.", 15, INK2)
text(20, 88, "All Grove modules use 3.3 V logic: no level shifter or pull-up resistor is needed.", 15, INK2)

text(20, 132, "VAULT PERIPHERALS · GROVE", 13, INK3, 700)
text(500, 132, "NODE 1 · VAULT CONTROLLER", 13, INK3, 700, "middle")
text(980, 132, "ACTUATOR · GATEWAY", 13, INK3, 700, "end")

# =====================================================================
# YoloUNO board (centre column)
# =====================================================================
BX, BY, BW, BH = 385, 150, 270, 870
rect(BX, BY, BW, BH, BOARD, BOARD_EDGE, 2, 18)
for hx, hy in [(BX + 20, BY + 20), (BX + BW - 20, BY + 20), (BX + 20, BY + BH - 20), (BX + BW - 20, BY + BH - 20)]:
    add(f'<circle cx="{hx}" cy="{hy}" r="7" fill="{BOARD_EDGE}" stroke="#3a5f80" stroke-width="2"/>')
text(BX + BW / 2, BY + 52, "YoloUNO", 28, "#ffffff", 700, "middle")
text(BX + BW / 2, BY + 76, "ESP32-S3 · 240 MHz", 14, "#a9c3da", anchor="middle")
text(BX + BW / 2, BY + 95, "Wi-Fi + BLE 5", 14, "#a9c3da", anchor="middle")

MX, MY, MW, MH = BX + 55, BY + 300, 160, 150
rect(MX, MY, MW, MH, "#c7ccd1", "#8d959c", 2, 6)
rect(MX + 12, MY + 12, MW - 24, MH - 50, "#9aa2aa", r=4)
text(MX + MW / 2, MY + 58, "ESP32-S3", 17, INK, 700, "middle")
text(MX + MW / 2, MY + 78, "WROOM-1", 13, INK, anchor="middle")
add(f'<path d="M{MX + 20} {MY + MH - 14} h20 v-18 h20 v18 h20 v-18 h20 v18 h20 v-18 h20" fill="none" '
    f'stroke="#6b737b" stroke-width="2.5"/>')
text(MX + MW / 2, MY + MH + 22, "PCB antenna · ESP-NOW ch. 1", 13, "#a9c3da", anchor="middle")


def onboard(y, h, label, lines, swatch=None):
    x = BX + 22
    rect(x, y, BW - 44, h, "#1d4a6e", "#2e6690", 1, 6)
    tx = x + 14
    if swatch:
        add(swatch)
        tx = x + 46
    text(tx, y + 21, label, 14, "#ffffff", 700)
    for i, s in enumerate(lines):
        text(tx, y + 40 + i * 18, s, 12.5, "#a9c3da", family="mono")


oy = BY + 520
onboard(oy, 100, "Power input", ["USB-C 5 V (≥ 900 mA)", "or DC jack 7–12 V", "→ GVS 5 V servo rail"])
onboard(oy + 112, 52, "NeoPixel RGB", ["GPIO 45 · 1-Wire"],
        f'<circle cx="{BX + 50}" cy="{oy + 138}" r="11" fill="#22c55e" stroke="#fff" stroke-width="1.5"/>')
onboard(oy + 176, 52, "Heartbeat LED", ["GPIO 48 · 1 Hz"],
        f'<circle cx="{BX + 50}" cy="{oy + 202}" r="8" fill="#f59e0b"/>')
onboard(oy + 240, 52, "BOOT button", ["GPIO 0 · pair 15 s"],
        f'<rect x="{BX + 39}" y="{oy + 255}" width="22" height="22" rx="3" fill="#d1d5db"/>'
        f'<circle cx="{BX + 50}" cy="{oy + 266}" r="5.5" fill="#4b5563"/>')

# =====================================================================
# Left column: Grove peripherals
# =====================================================================
PX, PW, PH = 20, 245, 124
left = [
    (200, "i2c", "I2C1", C_I2C, "I²C", "DHT20", "Temperature & humidity",
     ["SDA GPIO 11 · SCL GPIO 12", "addr 0x38 · every 5 s"]),
    (356, "i2c", "I2C2", C_I2C, "I²C", "LCD 1602 + PCF8574", "Local UI (16 × 2 chars)",
     ["SDA 11 · SCL 12 (shared)", "addr 0x21 · 200 ms refresh"]),
    (512, "adc", "A1-A0", C_ADC, "ADC", "LDR light sensor", "Inside vault: tamper detection",
     ["A0 → GPIO 1 · 0–4095", "breach ≥ 1200 (3 samples)"]),
    (668, "dig", "D4-D3", C_DIG, "GPIO", "Ultrasonic HC-SR04", "Approach detection",
     ["Trig GPIO 6 · Echo GPIO 7", "near < 30 cm · away ≥ 35 cm"]),
    (826, "dig", "D6-D5", C_DIG, "GPIO", "IR receiver VS1838B", "Remote PIN keypad",
     ["D5 → GPIO 8 · NEC 38 kHz", "C submit · B ack · E pair"]),
]
for y, row, port, col, tag, title, sub, lines in left:
    cy = y + PH / 2
    component(PX, y, PW, PH, title, sub, lines, col)
    rect(BX - 46, cy - 18, 62, 36, GROVE_ROW[row], BOARD_EDGE, 2, 4)
    text(BX - 15, cy + 5, port, 13, INK, 700, "middle")
    line(PX + PW, cy, BX - 46, cy, col, 4)
    add(f'<circle cx="{PX + PW}" cy="{cy}" r="5" fill="{col}"/>')
    pill((PX + PW + BX - 46) / 2, cy - 24, tag, col, 12)

# =====================================================================
# Right column: servo (GVS), gateway (USB-C), cloud
# =====================================================================
RX, RW = 715, 265
SY, SH = 290, 150
gy = SY + 80
rect(BX + BW - 50, gy - 38, 64, 76, BOARD_EDGE, "#3a5f80", 2, 4)
text(BX + BW - 58, gy - 46, "GVS D11", 13, "#ffffff", 700, "end")
for k, lbl, col, dy in [("G", "GND", "#6b4226", -24), ("V", "+5 V", "#d9433b", 0), ("S", "PWM", C_PWM, 24)]:
    add(f'<rect x="{BX + BW - 28}" y="{gy + dy - 7}" width="14" height="14" fill="#d4af37"/>')
    text(BX + BW - 40, gy + dy + 5, k, 12, "#ffffff", 700, "middle")
    line(BX + BW - 14, gy + dy, RX, gy + dy, col, 3.5)
    text(BX + BW + 24, gy + dy - 5, lbl, 12, INK2, family="mono")
component(RX, SY, RW, SH, "Micro servo SG90/MG90", "Deadbolt actuator (GPIO 38)",
          ["PWM 50 Hz · 500–2500 µs", "0° unlocked · 180° locked", "stall peak 600–800 mA"], C_PWM)

GY, GH = 480, 160
uy = GY + 80
rect(BX + BW - 36, uy - 17, 56, 34, "#c7ccd1", "#8d959c", 2, 8)
text(BX + BW - 8, uy + 5, "USB-C", 12, INK, 700, "middle")
line(BX + BW + 20, uy, RX, uy, C_USB, 6)
pill((BX + BW + 20 + RX) / 2, uy - 26, "USB", C_USB, 12)
component(RX, GY, RW, GH, "Edge gateway", "Raspberry Pi Zero 2W or PC",
          ["USB CDC · 115200 baud", "/dev/ttyACM0 (auto)", "gateway.py · AI · :5000"], C_USB)

CY, CH = 700, 150
rect(RX, CY, RW, CH, PANEL, LINE, 1.5, 10)
text(RX + 18, CY + 28, "Cloud & alerts (Wi-Fi / LAN)", 15, INK, 700)
for i, s in enumerate(["CoreIOT MQTT :1883", "ThingsBoard MQTT :1883", "Telegram Bot API (HTTPS)", "UDP beacon :50051"]):
    text(RX + 18, CY + 56 + i * 22, s, 13.5, INK2, family="mono")
line(RX + RW / 2, GY + GH, RX + RW / 2, CY, C_USB, 2.5, "3 7")

# =====================================================================
# Bottom: Yolo:Bit badge + ESP-NOW link
# =====================================================================
YX, YY, YW, YH = 20, 1110, 960, 300
lx = BX + BW / 2
line(lx, BY + BH, lx, YY, C_RF, 3.5, "9 8")
add(f'<circle cx="{lx}" cy="{BY + BH}" r="5" fill="{C_RF}"/>')
pill(lx - 110, 1058, "ESP-NOW · 2.4 GHz", C_RF, 13)
text(lx + 20, 1052, "badge → vault: UNLOCK · LOCK · ACK · PAIR", 12.5, INK2, family="mono")
text(lx + 20, 1074, "vault → badge: status (unicast, ch. 1)", 12.5, INK2, family="mono")

rect(YX, YY, YW, YH, BADGE, BADGE_EDGE, 2, 22)
text(YX + 26, YY + 40, "Yolo:Bit", 24, "#ffffff", 700)
text(YX + 26, YY + 63, "NODE 2 · Wearable badge · ESP32", 14, "#b7bec7")

mx0, my0, cell = YX + YW / 2 - 70, YY + 34, 28
icon = ["00100", "01010", "01010", "11111", "11011"]
for r in range(5):
    for c in range(5):
        on = icon[r][c] == "1"
        add(f'<rect x="{mx0 + c * cell}" y="{my0 + r * cell}" width="{cell - 6}" height="{cell - 6}" rx="3" '
            f'fill="{"#22c55e" if on else "#3d434b"}"/>')
text(mx0 + 67, my0 + 5 * cell + 20, "5×5 RGB matrix · GPIO 4", 14, "#ffffff", 700, "middle")
text(mx0 + 67, my0 + 5 * cell + 38, "25 NeoPixels · brightness 40", 12.5, "#b7bec7", family="mono", anchor="middle")


def button(x, y, name, pin, mode, roles):
    add(f'<circle cx="{x}" cy="{y}" r="24" fill="#111317" stroke="#5b636d" stroke-width="2"/>')
    add(f'<circle cx="{x}" cy="{y}" r="15" fill="#e5e7eb"/>')
    text(x, y + 6, name, 15, INK, 700, "middle")
    text(x, y + 48, pin, 14, "#ffffff", 700, "middle")
    text(x, y + 66, mode, 12.5, "#b7bec7", family="mono", anchor="middle")
    for i, s in enumerate(roles):
        text(x, y + 86 + i * 18, s, 13, "#d7dce2", anchor="middle")


button(YX + 140, YY + 120, "A", "GPIO 35", "INPUT", ["short: UNLOCK", "long ≥ 1 s: ACK_BREACH"])
button(YX + YW - 140, YY + 120, "B", "GPIO 14", "INPUT_PULLUP", ["LOCK", "(also acks a breach)"])
text(YX + YW / 2, YY + 248, "A + B: released < 1.5 s → FAKE_BADGE (rogue test) · held ≥ 1.5 s → PAIR_REQ",
     13, "#d7dce2", anchor="middle")
add(f'<circle cx="{YX + 44}" cy="{YY + 276}" r="11" fill="#111317" stroke="#5b636d" stroke-width="2"/>')
text(YX + 64, YY + 281, "Piezo buzzer · GPIO 25 · tone()", 12.5, "#b7bec7", family="mono")
rect(YX + YW - 200, YY + 258, 176, 32, "#c7ccd1", "#8d959c", 1.5, 4)
text(YX + YW - 112, YY + 279, "ESP32 · USB-C 5 V", 12.5, INK, 700, "middle")

# =====================================================================
# Legend
# =====================================================================
LY = 1446
text(20, LY, "LEGEND", 13, INK3, 700)
items = [(C_I2C, None, "I²C bus (Grove red row)"), (C_ADC, None, "Analog ADC (Grove yellow row)"),
         (C_DIG, None, "Digital GPIO (Grove white row)"), (C_PWM, None, "PWM servo signal (GVS)"),
         (C_USB, None, "USB-C serial + 5 V power"), (C_RF, "9 8", "ESP-NOW wireless (no cable)")]
for i, (col, dash, lbl) in enumerate(items):
    lx2, ly2 = 20 + (i % 3) * 330, LY + 26 + (i // 3) * 26
    line(lx2, ly2 - 5, lx2 + 38, ly2 - 5, col, 4, dash)
    text(lx2 + 50, ly2, lbl, 14, INK)

add("</svg>")
svg = "\n".join(out)
(HERE / "wiring_diagram.svg").write_text(svg, encoding="utf-8")
print("Saved wiring_diagram.svg")
try:
    import cairosvg
    cairosvg.svg2png(bytestring=svg.encode(), write_to=str(HERE / "wiring_diagram.png"), scale=2.5)
    print("Saved wiring_diagram.png")
except ImportError:
    print("cairosvg not installed: PNG skipped")
