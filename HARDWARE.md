# Hardware Specification: OhStem AIoT Kit & YoloUNO

This document details all physical hardware components provided in the **OhStem AIoT Kit** (Reference: [OhStem AIoT Kit](https://ohstem.vn/san-pham/aiot-kit-hoc-lap-trinh-iot-va-ai/)), their functional role in the **Smart Safe Guardian** project, and a comprehensive electrical analysis (voltage logic levels, current spikes, and brownout prevention).

---

## 1. Exhaustive Hardware Inventory

### 1.1 Microcontroller Processing Units

| Device | Chipset & Technical Features | Project Functional Role |
| :--- | :--- | :--- |
| **YoloUNO** | **ESP32-S3 Dual-Core Xtensa LX7 @ 240 MHz**<br>• 512 KB SRAM, 8 MB Flash<br>• Wi-Fi 2.4 GHz (802.11 b/g/n) + BLE 5.0<br>• Arduino Uno R3 form factor with **12 onboard Grove connectors**<br>• 4 dedicated GVS servo headers, native USB Type-C, 7–12V DC power jack | **Central Vault Controller (Vault Unit)**: Sensor acquisition, access authentication, deadbolt servo actuation, serial Gateway communication, and embedded emergency Web Server. |
| **Yolo:Bit** | **ESP32 Dual-Core**<br>• 5×5 programmable RGB LED Matrix (25 addressable pixels)<br>• 2 tactile pushbuttons (Button A and B)<br>• Integrated piezoelectric buzzer<br>• 3-axis accelerometer / gyroscope<br>• Powered via 2× AAA battery pack (3V) or USB Type-C | **Wearable Security Badge**: Wireless access requests via ESP-NOW (Button A) or silent duress / panic alarms (Button B), with real-time audio and visual status feedback. |

#### YoloUNO Grove slot rows

The 12 Grove sockets are grouped by interface type. The color identifies the
row's function; it is not a voltage-level indicator:

| Row color | Interface | Board labels | Typical use |
| :---: | :--- | :--- | :--- |
| **Yellow** | Analog | `A6-A3`, `A3-A2`, `A2-A1`, `A1-A0` | Sensors that provide an analog voltage, such as an LDR or soil-moisture sensor. |
| **White** | Digital | `D10-D9`, `D8-D7`, `D6-D5`, `D4-D3` | Digital input/output modules, including the ultrasonic sensor and IR receiver. |
| **Red** | I²C | `I2C4`, `I2C3`, `I2C2`, `I2C1` | Devices sharing the I²C bus, such as the DHT20 and LCD. Multiple devices can share a row when their addresses differ. |

This color coding is specific to the socket group. A Grove cable still uses
the standard four conductors: yellow and white for signals, red for VCC, and
black for GND. The four separate 3-pin GVS headers are intended for servos and
are not part of these three Grove rows.

---

### 1.2 Available Sensors

| Sensor | Interface & Grove Port | Role in Secure Vault | Status |
| :--- | :--- | :--- | :---: |
| **DHT20** | **I2C** (Address `0x38`) — Grove I2C Port | Continuous internal climate telemetry (temperature and humidity monitoring for fire prevention and environmental control). | **Selected** |
| **Light Sensor (LDR)** | **Analog** — Grove Port A1-A0 | Installed inside the vault interior. Detects unauthorized physical breaches by sensing ambient light while in `LOCKED` state. | **Selected** |
| **Ultrasonic Distance Sensor** | **Digital** — Grove Port D6-D5 | Measures technician approach distance (< 30 cm) to wake up the standby LCD screen. | **Selected** |
| **IR Receiver (1838)** | **Digital** — Grove Port D4-D3 | Captures 38 kHz NEC infrared pulses from the remote control for backup 4-digit PIN authentication. | **Selected** |
| **PIR Motion Sensor** | Digital — Grove Port | Passive infrared volumetric human motion detection. | *Spare / Optional* |
| **Soil Moisture Sensor** | Analog — Grove Port | Targeted for smart agriculture projects. | *Not Used* |

---

### 1.3 Actuators, Displays & Control Modules

| Module | Interface | Role in Secure Vault | Status |
| :--- | :--- | :--- | :---: |
| **Servo Motor (MG90 / SG90)** | **PWM (50 Hz)** — Dedicated GVS Port | Mechanical door deadbolt mechanism (0° = Unlocked, 90° = Locked). | **Selected** |
| **1602 LCD Display (PCF8574)** | **I2C** (Address `0x27` / `0x3F`) — Grove I2C Port | Local physical user interface (prompts, masked PIN input `* * * *`, status codes). | **Selected** |
| **Onboard NeoPixel RGB LED** | **GPIO 45** (Internal 1-Wire bus) | Visual status beacon: **Green** (Unlocked), **Blue** (PIN Entry), **Red** (Locked / Alarm). | **Selected** |
| **Onboard Heartbeat LED** | **GPIO 48** (D13 internal line) | 1 Hz periodic toggle indicating FreeRTOS task scheduler health. | **Selected** |
| **IR Remote Control** | Wireless NEC protocol (38 kHz) | Handheld numeric keypad (keys 0–9) for secondary manual PIN entry. | **Selected** |
| **2-Channel Relay Module** | Digital / USB (Optocoupled isolation) | Available to drive external high-voltage electronic maglocks (12V) or sirens. | *Spare / Optional* |
| **4-LED NeoPixel Grove Bar** | 1-Wire Digital | Additional visual lighting strip if auxiliary signaling is needed. | *Spare / Optional* |
| **Mini Fan & Submersible Pump** | PWM / Digital | Active ventilation or liquid dispensing. | *Not Used* |

---

## 2. Electrical Analysis & Hardware Risk Mitigation

### 2.1 Logic Voltage Levels & Level Shifting (3.3V vs. 5V)
* **The Classical Breadboard Issue:** Generic sensors (such as generic HC-SR04 modules) operate on 5V and output 5V on the `Echo` pin directly into the ESP32 GPIO, which risks damaging the 3.3V silicon (ESP32 maximum absolute rating is 3.6V).
* **The OhStem Grove Architecture:**
  * All modules supplied in the OhStem AIoT Kit follow the **4-pin Grove standard**.
  * The YoloUNO Grove ports route power and signal lines with onboard 3.3V logic matching the ESP32-S3.
  * The OhStem ultrasonic distance module includes onboard signal-conditioning circuitry designed specifically for direct connection to ESP32 digital Grove pins.
  * **Conclusion: Zero external level shifters or pull-up resistors are required.** All connections are plug-and-play and electrically safe.

---

### 2.2 Servomotor Peak Current Draw (Brownout Reset Prevention)
* **The Phenomenon:** A micro servomotor (SG90 or MG90) draws 100–250 mA during normal rotation, but can surge to **600–800 mA peak stall current** if the mechanical latch faces physical friction or is jammed against a frame.
* **The Risk:** If the YoloUNO board is powered exclusively from a legacy laptop USB 2.0 port (strictly limited to 500 mA), this transient current spike causes the 5V bus to sag below 4.5V, triggering the ESP32-S3 internal brownout detector (**Brownout Detector: Reset**).
* **Mitigation Strategy:**
  1. **Recommended Demo Power Supply:** Power the YoloUNO via a modern USB 3.0 / USB-C port (delivering 900 mA to 1.5 A), a 5V 2A smartphone wall adapter, or an external power bank.
  2. **External DC Supply via Barrel Jack:** The YoloUNO features an onboard 5521 DC barrel jack accepting 7V to 12V DC. The onboard linear voltage regulator comfortably supplies the high-current GVS servo rail.
  3. **Mechanical Calibration:** Calibrate the PWM sweep angle (e.g., 10° to 80° rather than forcing hard stops at 0° and 90°) to guarantee that the servo horn never stalls against a physical barrier.

---

### 2.3 Role of the 2-Channel Relay Module
* The kit includes an optocoupled **2-channel Relay Module**.
* **Advantage:** Complete galvanic isolation between control signals and power circuits.
* **Alternative Scenario:** If simulating an industrial high-security vault equipped with a 12V electromagnetic lock (*maglock*) or solenoid bolt, the relay can switch this external loop without electrical interference on the microcontroller.
* For the project scope, the **MG90 Servomotor** remains the primary actuator choice because its 90° mechanical rotation provides immediate, undeniable visual evidence in the video demonstration.

---

### 2.4 Peripheral Count Feasibility Evaluation
* **On a Prototype Breadboard:** 8 loose breakout boards would require over 30 Dupont jumper wires, creating an unstable rat's nest prone to loose contacts during transit.
* **On the YoloUNO Board:**
  * The board features **12 keyed Grove connectors** and **4 dedicated 3-pin GVS headers**.
  * Every peripheral utilizes a secure, keyed latching cable.
  * There are **zero pin collisions** (I2C peripherals share the bus under distinct hardware addresses `0x38` and `0x27`, the LDR utilizes the analog `A1-A0` Grove port, the IR receiver utilizes the digital `D4-D3` Grove port, and the servo uses GVS signal `D11`).
* **Verdict:** The planned peripheral count is **fully feasible, stable, and clean**. It provides an impressive physical setup with zero risk of loose wires during presentation.

---

## 3. Recommended YoloUNO Pin & Port Mapping

| Peripheral | YoloUNO Port Type | Physical Connector | Address / Signal Pin |
| :--- | :--- | :--- | :--- |
| **DHT20 Climate Sensor** | Grove I2C | Grove Port I2C #1 | I2C Bus (`0x38`) |
| **1602 LCD Display** | Grove I2C | Grove Port I2C #2 (or daisy-chained) | I2C Bus (`0x27` or `0x3F`) |
| **Light Sensor (LDR)** | Grove Analog | Grove Port A1-A0 | ADC1 Channel (GPIO 1) |
| **Ultrasonic Distance Sensor** | Grove Digital | Grove Port D6-D5 | Dedicated Digital GPIO (Trig/Echo) |
| **IR Receiver (1838)** | Grove Digital | Grove Port D4-D3 | Dedicated Digital GPIO (IR Capture) |
| **MG90 Servomotor** | 3-Pin GVS Header | Servo signal header | D11, dedicated LEDC PWM (50 Hz) |
| **Yolo:Bit** | Wireless | ESP-NOW link | Button and status messages |
| **Onboard NeoPixel** | Internal PCB Circuit | Fixed Internal Route | GPIO 45 |
| **Onboard Heartbeat LED** | Internal PCB Circuit | Fixed Internal Route | GPIO 48 |
| **PC Gateway Bridge** | USB Type-C Cable | USB-C Port | CDC UART @ 115200 baud |
