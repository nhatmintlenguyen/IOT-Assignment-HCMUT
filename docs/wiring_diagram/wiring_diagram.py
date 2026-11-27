"""Figure 3.1 - Smart Safe Guardian hardware wiring diagram.

Generates wiring_diagram.svg (and wiring_diagram.png if cairosvg is available):
    uv run --with cairosvg python docs/wiring_diagram/wiring_diagram.py

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
W, H = 1720, 1060

# palette ---------------------------------------------------------------
INK, INK2, INK3 = "#1b1f24", "#56606b", "#8a949e"
LINE, PANEL, BG = "#c9d0d6", "#f6f8fa", "#ffffff"
BOARD, BOARD_EDGE = "#14344f", "#0b2236"          # YoloUNO PCB
BADGE, BADGE_EDGE = "#2b2f36", "#15181c"          # Yolo:Bit PCB
C_I2C, C_ADC, C_DIG = "#7b4fd6", "#d98a00", "#1f78d1"
C_PWM, C_USB, C_RF = "#e0601f", "#4b5563", "#0f9d8a"
GROVE_ROW = {"i2c": "#d9433b", "adc": "#f2c230", "dig": "#f4f4f2"}  # board silk colours

out = []
add = out.append


def text(x, y, s, size=13, color=INK, weight=400, anchor="start", family="body", italic=False):
    fam = "'DejaVu Sans Mono',monospace" if family == "mono" else \
          "Inter,'DejaVu Sans',Arial,sans-serif"
    st = ' font-style="italic"' if italic else ""
    s = escape(s)
    add(f'<text x="{x}" y="{y}" font-family="{fam}" font-size="{size}" fill="{color}" '
        f'font-weight="{weight}" text-anchor="{anchor}"{st}>{s}</text>')


def rect(x, y, w, h, fill, stroke="none", sw=1, r=8, extra=""):
    add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" '
        f'stroke="{stroke}" stroke-width="{sw}" {extra}/>')


def line(x1, y1, x2, y2, color, sw=3, dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    add(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" '
        f'stroke-width="{sw}" stroke-linecap="round"{d}/>')


def path(d, color, sw=3, dash=None):
    ds = f' stroke-dasharray="{dash}"' if dash else ""
    add(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{sw}" '
        f'stroke-linecap="round" stroke-linejoin="round"{ds}/>')


def pill(x, y, s, color, anchor="middle"):
    """Small coloured tag (interface badge) centred on (x, y)."""
    w = 8 * len(s) + 16
    x0 = x - w / 2 if anchor == "middle" else x
    rect(x0, y - 11, w, 22, BG, color, 1.5, 11)
    text(x0 + w / 2, y + 4.5, s, 11.5, color, 600, "middle")


def component(x, y, w, h, title, sub, lines, accent):
    rect(x, y, w, h, BG, LINE, 1.5, 10)
    rect(x, y, 6, h, accent, r=3)
    text(x + 20, y + 26, title, 15, INK, 700)
    text(x + 20, y + 45, sub, 12, INK2)
    for i, s in enumerate(lines):
        text(x + 20, y + 68 + i * 18, s, 12, INK2, family="mono")


# canvas ----------------------------------------------------------------
add(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">')
rect(0, 0, W, H, BG, r=0)
text(40, 52, "Smart Safe Guardian — Hardware Wiring Diagram", 26, INK, 700)
text(40, 80, "Vault node (YoloUNO · ESP32-S3), wearable badge (Yolo:Bit · ESP32) and edge gateway. "
             "All Grove modules run on 3.3 V logic: no level shifter or pull-up needed.", 14, INK2)

# zone labels
text(40, 132, "VAULT PERIPHERALS · GROVE CABLES", 12, INK3, 700)
text(590, 132, "NODE 1 · CENTRAL VAULT CONTROLLER", 12, INK3, 700)
text(1180, 132, "ACTUATOR · GATEWAY · BADGE", 12, INK3, 700)

# =====================================================================
# YoloUNO board
# =====================================================================
BX, BY, BW, BH = 590, 150, 460, 700
rect(BX, BY, BW, BH, BOARD, BOARD_EDGE, 2, 18)
# mounting holes
for hx, hy in [(BX + 22, BY + 22), (BX + BW - 22, BY + 22), (BX + 22, BY + BH - 22), (BX + BW - 22, BY + BH - 22)]:
    add(f'<circle cx="{hx}" cy="{hy}" r="7" fill="{BOARD_EDGE}" stroke="#3a5f80" stroke-width="2"/>')
text(BX + BW / 2, BY + 50, "YoloUNO", 24, "#ffffff", 700, "middle")
text(BX + BW / 2, BY + 72, "ESP32-S3 · 240 MHz dual-core · Wi-Fi + BLE 5", 12.5, "#a9c3da", 400, "middle")

# ESP32-S3 module (with antenna trace)
MX, MY, MW, MH = BX + 150, BY + 260, 160, 150
rect(MX, MY, MW, MH, "#c7ccd1", "#8d959c", 2, 6)
rect(MX + 12, MY + 12, MW - 24, MH - 50, "#9aa2aa", r=4)
text(MX + MW / 2, MY + 58, "ESP32-S3", 15, "#1b1f24", 700, "middle")
text(MX + MW / 2, MY + 76, "WROOM-1", 11, "#1b1f24", 400, "middle")
path(f"M{MX + 20} {MY + MH - 14} h20 v-18 h20 v18 h20 v-18 h20 v18 h20 v-18 h20", "#6b737b", 2.5)
text(MX + MW / 2, MY + MH + 18, "PCB antenna · ESP-NOW ch. 1", 11, "#a9c3da", 400, "middle")

# on-board parts
def onboard(x, y, label, pin, swatch):
    rect(x, y, 170, 40, "#1d4a6e", "#2e6690", 1, 6)
    add(swatch)
    text(x + 44, y + 17, label, 12, "#ffffff", 600)
    text(x + 44, y + 32, pin, 11, "#a9c3da", family="mono")

ox = BX + 270
onboard(ox, BY + 470, "NeoPixel RGB", "GPIO 45 · 1-Wire",
        f'<circle cx="{ox + 22}" cy="{BY + 490}" r="10" fill="#22c55e" stroke="#fff" stroke-width="1.5"/>')
onboard(ox, BY + 520, "Heartbeat LED", "GPIO 48 · 1 Hz",
        f'<circle cx="{ox + 22}" cy="{BY + 540}" r="7" fill="#f59e0b"/>')
onboard(ox, BY + 570, "BOOT button", "GPIO 0 · pair 15 s",
        f'<rect x="{ox + 12}" y="{BY + 580}" width="20" height="20" rx="3" fill="#d1d5db"/>'
        f'<circle cx="{ox + 22}" cy="{BY + 590}" r="5" fill="#4b5563"/>')

# power section
rect(BX + 78, BY + 470, 170, 90, "#1d4a6e", "#2e6690", 1, 6)
text(BX + 94, BY + 492, "Power input", 12, "#ffffff", 600)
text(BX + 94, BY + 512, "USB-C 5 V ≥ 900 mA", 11, "#a9c3da", family="mono")
text(BX + 94, BY + 529, "or DC jack 7–12 V", 11, "#a9c3da", family="mono")
text(BX + 94, BY + 546, "→ GVS 5 V servo rail", 11, "#a9c3da", family="mono")

# ---------------------------------------------------------------------
# Left Grove ports + peripherals
# ---------------------------------------------------------------------
PX, PW, PH = 40, 290, 106
left = [
    # y, row, port label, bus colour, pill, wire labels, comp title, sub, lines
    (190, "i2c", "I2C1", C_I2C, "I²C", ["SDA → GPIO 11", "SCL → GPIO 12"],
     "DHT20", "Temperature & humidity", ["addr 0x38 · every 5 s", "3.3 V · Grove I²C"]),
    (318, "i2c", "I2C2", C_I2C, "I²C", ["same bus (0x21)", "SDA 11 · SCL 12"],
     "LCD 1602 + PCF8574", "Local UI (16 × 2 chars)", ["addr 0x21 · 200 ms refresh", "3.3 V · Grove I²C"]),
    (446, "adc", "A1-A0", C_ADC, "ADC", ["A0 → GPIO 1"],
     "LDR light sensor", "Inside vault: tamper detection", ["12-bit 0–4095 · 200 ms", "breach > 1200 · reset < 800"]),
    (574, "dig", "D4-D3", C_DIG, "GPIO", ["Trig D3 → GPIO 6", "Echo D4 → GPIO 7"],
     "Ultrasonic HC-SR04", "Approach detection", ["pulseIn timeout 25 ms", "near < 30 cm · away > 35 cm"]),
    (702, "dig", "D6-D5", C_DIG, "GPIO", ["D5 → GPIO 8"],
     "IR receiver VS1838B", "Remote PIN keypad", ["NEC protocol · 38 kHz", "C = submit · D = clear"]),
]
for y, row, port, col, tag, wire_lbl, title, sub, lines in left:
    cy = y + PH / 2
    component(PX, y, PW, PH, title, sub, lines, col)
    # Grove socket on board edge (fill = silk colour of the row)
    rect(BX - 14, cy - 18, 70, 36, GROVE_ROW[row], "#0b2236", 2, 4)
    text(BX + 21, cy + 5, port, 12, "#1b1f24", 700, "middle")
    # cable
    line(PX + PW, cy, BX - 14, cy, col, 4)
    add(f'<circle cx="{PX + PW}" cy="{cy}" r="5" fill="{col}"/>')
    pill(PX + PW + 60, cy - 1, tag, col)
    for j, wl in enumerate(wire_lbl):
        text(PX + PW + 14, cy + 24 + j * 15, wl, 11, INK2, family="mono")

# ---------------------------------------------------------------------
# Right: servo on GVS header
# ---------------------------------------------------------------------
SX, SY, SW_, SH = 1180, 170, 270, 150
gy = SY + 75
# GVS header (3 pins)
rect(BX + BW - 56, gy - 36, 70, 72, "#0b2236", "#3a5f80", 2, 4)
text(BX + BW - 64, gy + 4, "GVS D11", 11.5, "#ffffff", 700, "end")
servo_wires = [("G", "GND", "#6b4226", -22), ("V", "+5 V", "#d9433b", 0), ("S", "PWM GPIO 38", C_PWM, 22)]
for k, lbl, col, dy in servo_wires:
    add(f'<rect x="{BX + BW - 34}" y="{gy + dy - 7}" width="14" height="14" fill="#d4af37"/>')
    text(BX + BW - 46, gy + dy + 4, k, 11, "#ffffff", 700, "middle")
    line(BX + BW - 20, gy + dy, SX, gy + dy, col, 3.5)
    text(BX + BW + 30, gy + dy - 5, lbl, 10.5, INK2, family="mono")
component(SX, SY, SW_, SH, "Micro servo SG90 / MG90", "Deadbolt actuator", [
    "PWM 50 Hz · 500–2500 µs", "0° = unlocked · 180° = locked", "peak stall 600–800 mA"], C_PWM)

# ---------------------------------------------------------------------
# Right: gateway over USB
# ---------------------------------------------------------------------
GX, GY, GW, GH = 1180, 400, 270, 170
uy = GY + 70
rect(BX + BW - 40, uy - 16, 54, 32, "#c7ccd1", "#8d959c", 2, 8)
text(BX + BW - 13, uy + 5, "USB-C", 10.5, "#1b1f24", 700, "middle")
line(BX + BW + 14, uy, GX, uy, C_USB, 6)
pill((BX + BW + 14 + GX) / 2, uy - 22, "USB serial", C_USB)
text(BX + BW + 22, uy + 26, "115200 baud", 11, INK2, family="mono")
text(BX + BW + 22, uy + 42, "+5 V supply", 11, INK2, family="mono")
component(GX, GY, GW, GH, "Edge gateway", "Raspberry Pi Zero 2W or PC", [
    "/dev/ttyACM0 (auto-detect)", "gateway.py · Isolation Forest", "web console :5000"], C_USB)
pill(GX + GW - 46, GY + 26, "Linux", C_USB)

# upstream (Wi-Fi)
CX, CY = 1500, 400
rect(CX, CY, 180, 170, PANEL, LINE, 1.5, 10)
text(CX + 18, CY + 28, "Cloud & alerts", 14, INK, 700)
for i, s in enumerate(["CoreIOT MQTT :1883", "ThingsBoard :1883", "Telegram Bot API", "(Wi-Fi / LAN)"]):
    text(CX + 18, CY + 56 + i * 22, s, 11.5, INK2 if i < 3 else INK3, family="mono")
line(GX + GW, uy, CX, uy, C_USB, 2, "2 6")

# ---------------------------------------------------------------------
# Right-bottom: Yolo:Bit badge, ESP-NOW link
# ---------------------------------------------------------------------
YX, YY, YW, YH = 1180, 670, 500, 330
rect(YX, YY, YW, YH, BADGE, BADGE_EDGE, 2, 22)
text(YX + 28, YY + 40, "Yolo:Bit", 22, "#ffffff", 700)
text(YX + 28, YY + 62, "NODE 2 · Wearable badge · ESP32", 12, "#b7bec7")

# 5x5 matrix
mx0, my0, cell = YX + 190, YY + 92, 26
icon = ["00100", "01010", "01010", "11111", "11011"]  # padlock-ish
for r in range(5):
    for c in range(5):
        on = icon[r][c] == "1"
        add(f'<rect x="{mx0 + c * cell}" y="{my0 + r * cell}" width="{cell - 6}" height="{cell - 6}" rx="3" '
            f'fill="{"#22c55e" if on else "#3d434b"}"/>')
text(mx0 + 2.5 * cell - 3, my0 + 5 * cell + 18, "5×5 RGB matrix · GPIO 4", 11.5, "#ffffff", 600, "middle")
text(mx0 + 2.5 * cell - 3, my0 + 5 * cell + 34, "25 × NeoPixel · brightness 40", 10.5, "#b7bec7", family="mono", anchor="middle")

# buttons
def button(x, y, name, pin, mode, role):
    add(f'<circle cx="{x}" cy="{y}" r="22" fill="#111317" stroke="#5b636d" stroke-width="2"/>')
    add(f'<circle cx="{x}" cy="{y}" r="14" fill="#e5e7eb"/>')
    text(x, y + 5, name, 13, "#1b1f24", 700, "middle")
    text(x, y + 44, pin, 11.5, "#ffffff", 600, "middle")
    text(x, y + 60, mode, 10.5, "#b7bec7", family="mono", anchor="middle")
    text(x, y + 76, role, 10.5, "#b7bec7", anchor="middle")

button(YX + 85, YY + 155, "A", "GPIO 35", "INPUT", "Unlock / ack")
button(YX + 420, YY + 155, "B", "GPIO 14", "INPUT_PULLUP", "Manual lock")

# buzzer + ESP32 + USB
add(f'<circle cx="{YX + 85}" cy="{YY + 292}" r="14" fill="#111317" stroke="#5b636d" stroke-width="2"/>')
add(f'<circle cx="{YX + 85}" cy="{YY + 292}" r="4" fill="#5b636d"/>')
text(YX + 108, YY + 289, "Piezo buzzer", 11.5, "#ffffff", 600)
text(YX + 108, YY + 304, "GPIO 25 · tone()", 10.5, "#b7bec7", family="mono")
rect(YX + 355, YY + 268, 120, 44, "#c7ccd1", "#8d959c", 1.5, 4)
text(YX + 415, YY + 288, "ESP32", 12, "#1b1f24", 700, "middle")
text(YX + 415, YY + 303, "USB-C 5 V", 10.5, "#1b1f24", anchor="middle", family="mono")

# ESP-NOW wireless link (no cable)
ly = YY + 50
path(f"M{BX + BW} {ly} L{YX} {ly}", C_RF, 3, "8 7")
add(f'<circle cx="{BX + BW}" cy="{ly}" r="5" fill="{C_RF}"/>')
pill(YX, YY - 76, "ESP-NOW · 2.4 GHz", C_RF, anchor="start")
text(YX, YY - 48, "badge → vault: unlock / lock / ack / pair", 11, INK2, family="mono")
text(YX, YY - 32, "vault → badge: status + icon · channel 1", 11, INK2, family="mono")

# =====================================================================
# Legend
# =====================================================================
LY = 905
text(40, LY, "LEGEND", 12, INK3, 700)
items = [(C_I2C, None, "I²C bus (Grove red row)"), (C_ADC, None, "Analog ADC (Grove yellow row)"),
         (C_DIG, None, "Digital GPIO (Grove white row)"), (C_PWM, None, "PWM servo signal (GVS)"),
         (C_USB, None, "USB-C serial + 5 V power"), (C_RF, "8 7", "ESP-NOW wireless (no cable)")]
for i, (col, dash, lbl) in enumerate(items):
    lx, ly = 40 + (i % 3) * 330, LY + 28 + (i // 3) * 28
    line(lx, ly - 4, lx + 40, ly - 4, col, 4, dash)
    text(lx + 52, ly, lbl, 12.5, INK)
text(40, LY + 104, "Grove cable conductors: red = VCC (3.3 V), black = GND, yellow / white = signal. "
                    "Servo cable: brown = GND, red = +5 V, orange = signal.", 12, INK2)
text(40, LY + 124, "Pin assignments verified against firmware/vault_yolouno and firmware/badge_yolobit sources.",
     12, INK3, italic=True)

add("</svg>")
svg = "\n".join(out)
(HERE / "wiring_diagram.svg").write_text(svg, encoding="utf-8")
print("Saved wiring_diagram.svg")

try:
    import cairosvg
    cairosvg.svg2png(bytestring=svg.encode(), write_to=str(HERE / "wiring_diagram.png"), scale=2)
    print("Saved wiring_diagram.png")
except ImportError:
    print("cairosvg not installed: PNG skipped")
