# ĐỀ XUẤT ĐỀ TÀI (PROJECT PROPOSAL)

# SMART SAFE GUARDIAN — Hệ thống tủ an toàn IoT đa nút với xác thực kép, giám sát môi trường và phát hiện bất thường tại biên


| Mục               | Nội dung                                                                      |
| :----------------- | :----------------------------------------------------------------------------- |
| Môn học           | Internet of Things (IoT) — Học kỳ 7                                           |
| Nhóm / Thành viên | `[điền: họ tên – MSSV – vai trò]` (tối đa 3 sinh viên/nhóm)                   |
| Giảng viên        | TS. Nguyễn Hòa Hưng (theo thông báo đồ án IoT, học kỳ 261, năm học 2026–2027) |
| Nền tảng bắt buộc | CoreIOT server và board ESP32-S3 (YoloUNO)                                    |
| Ngày lập          | 13/11/2026                                                                    |
| Phiên bản         | 1.0 (bản đề xuất)                                                             |


---

## 1. Tóm tắt (Executive Summary)

**Smart Safe Guardian** là hệ thống tủ/két an toàn thông minh dùng để bảo vệ tài sản nhạy cảm (hóa chất nguy hiểm, thiết bị phòng lab đắt tiền, máy chủ). Hệ thống gồm ba lớp thiết bị và hai lớp nền tảng:

1. **Thẻ đeo (Yolo:Bit)** gửi yêu cầu mở khóa qua **ESP-NOW**.
2. **Bộ điều khiển tủ (YoloUNO, ESP32-S3)** đọc cảm biến, xác thực, điều khiển khóa servo và hiển thị trạng thái.
3. **Gateway cục bộ (PC / Pi Zero 2 W)** nhận dữ liệu qua UART, chạy mô hình **Isolation Forest** phát hiện bất thường, hiển thị dashboard cục bộ, và đẩy dữ liệu MQTT đồng thời lên **CoreIOT** (đám mây chính) và **ThingsBoard tự triển khai bằng Docker** (dự phòng ngoại tuyến).

Điểm khác biệt của đề tài so với một "khóa cửa thông minh" thông thường:

- Hai kênh xác thực độc lập (thẻ không dây + PIN hồng ngoại), có chế độ xác thực kép tùy chọn.
- Phát hiện đột nhập vật lý bằng cảm biến ánh sáng bên trong tủ, kết hợp cảnh báo Telegram qua RuleChain.
- Phát hiện bất thường đa biến tại biên (không phụ thuộc Internet).
- Dự phòng kép cloud + local, vẫn vận hành và ghi log khi mất mạng.

---

## 2. Bối cảnh, vấn đề và mục tiêu

### 2.1 Vấn đề

- Khóa cơ hoặc khóa PIN đơn lẻ dễ bị sao chép, dò mã hoặc quên đóng; không có nhật ký truy cập truy vết được.
- Nơi lưu trữ hóa chất, thiết bị đắt tiền cần theo dõi **nhiệt độ/độ ẩm** (nguy cơ cháy, hỏng thiết bị) cùng lúc với **an ninh**.
- Hệ thống phụ thuộc hoàn toàn vào cloud sẽ mất giám sát khi mạng gián đoạn.

### 2.2 Mục tiêu


| Mã  | Mục tiêu                                                            | Tiêu chí đo được                                                        |
| :--- | :------------------------------------------------------------------- | :----------------------------------------------------------------------- |
| O1  | Mở khóa không tiếp xúc bằng thẻ đeo (ESP-NOW), PIN IR làm dự phòng  | Mở khóa thành công khi token/PIN hợp lệ; từ chối khi không hợp lệ       |
| O2  | Giám sát nhiệt độ/độ ẩm (DHT20) và phát hiện mở cửa trái phép (LDR) | Telemetry định kỳ; cảnh báo khi LDR vượt ngưỡng lúc trạng thái `LOCKED` |
| O3  | Phát hiện bất thường tại biên bằng Isolation Forest                 | Xuất `anomaly_score` và cờ cảnh báo sớm theo cửa sổ trượt               |
| O4  | Dự phòng kép CoreIOT + ThingsBoard cục bộ                           | Rút mạng Internet: dữ liệu vẫn vào ThingsBoard cục bộ, không mất khung  |
| O5  | Giám sát/điều khiển từ xa an toàn                                   | Dashboard + RPC; RPC mở khóa có cơ chế xác nhận (mục 8.4)               |
| O6  | Cập nhật firmware từ xa (OTA)                                       | Cập nhật firmware YoloUNO qua Wi-Fi từ CoreIOT                          |


> Lưu ý về thuật ngữ: blueprint gọi hệ thống là "dual-authentication" nhưng luồng hiện tại là **thẻ HOẶC PIN**. Đề xuất định nghĩa rõ: *chế độ thường* = một trong hai kênh; *chế độ bảo mật cao* (tùy chọn, bật qua RPC/dashboard) = **cần cả thẻ VÀ PIN**. Nếu muốn giữ đúng tên "dual-authentication", chế độ bảo mật cao nên được cài đặt (xem mục 6.3).

---

## 3. Phạm vi và yêu cầu

### 3.1 Yêu cầu chức năng

- **FR1** Phát hiện người đến gần (&lt; 30 cm) để đánh thức giao diện LCD.
- **FR2** Xác thực bằng thẻ đeo (ESP-NOW) hoặc PIN 4 số qua remote IR.
- **FR3** Điều khiển servo khóa/mở; tự khóa lại sau 10 s.
- **FR4** Sai PIN 3 lần liên tiếp → khóa phạt 60 s và gửi cảnh báo.
- **FR5** Nút B trên thẻ gửi báo động cưỡng bức (duress) im lặng.
- **FR6** Phát hiện đột nhập vật lý bằng LDR khi đang `LOCKED`.
- **FR7** Gửi telemetry và sự kiện qua UART (JSON) lên Gateway.
- **FR8** Gateway: phát hiện bất thường, dashboard cục bộ, publish MQTT kép, nhận RPC.
- **FR9** CoreIOT: dashboard, RuleChain, thông báo Telegram/Email, OTA.

### 3.2 Yêu cầu phi chức năng

- **Độ trễ**: từ lúc bấm nút thẻ đến lúc servo chuyển động nên đủ thấp để người dùng không nhận thấy trễ (mục tiêu nội bộ ≤ 1 s; sẽ đo và báo cáo giá trị thực trong phần kiểm thử, không tuyên bố trước).
- **Độ sẵn sàng**: hoạt động độc lập khi mất Wi-Fi/Internet (khóa vẫn chạy hoàn toàn trên YoloUNO; Gateway vẫn ghi log và local TB vẫn nhận dữ liệu).
- **An toàn (fail-safe/secure)**: mất nguồn hoặc mất Gateway **không** được làm tủ tự mở (xem 8.4).
- **Bảo mật**: chống phát lại (replay) token, không để lộ khóa/mật khẩu trong mã nguồn công khai (mục 9).

### 3.3 Ngoài phạm vi

Khóa cơ khí thực tế chịu lực; chứng nhận an toàn; quản lý nhiều người dùng quy mô lớn (chỉ làm tối đa vài thẻ/PIN trong demo).

---

## 4. Kiến trúc hệ thống (mô hình 5 lớp)

```
 [Yolo:Bit - Thẻ đeo]
   Nút A: yêu cầu mở | Nút B: duress | LED 5x5 + loa: phản hồi
          │  ESP-NOW (2.4 GHz, P2P)
          ▼
 [YoloUNO - Bộ điều khiển tủ (ESP32-S3), FreeRTOS]
   DHT20 + LCD1602 (I2C) | LDR (ADC) | Siêu âm | IR 1838
   Servo (khóa) | NeoPixel | LED heartbeat
          │  USB-UART 115200, JSON Lines
          ▼
 [Gateway PC / Pi Zero 2 W]
   pyserial → Isolation Forest → Streamlit → paho-mqtt
          │                                   │
          ▼ MQTT                              ▼ MQTT
 [CoreIOT (chính)]               [ThingsBoard CE trong Docker (dự phòng)]
   Dashboard, RuleChain, Telegram, RPC, OTA
```


| Lớp               | Thành phần                                                   |
| :----------------- | :------------------------------------------------------------ |
| Perception        | DHT20, LDR, siêu âm, IR, nút/IMU trên Yolo:Bit               |
| Transport/Network | ESP-NOW (cục bộ), UART JSON (controller–gateway), MQTT (WAN) |
| Gateway/Edge      | Daemon Python, Isolation Forest, dashboard Streamlit         |
| Cloud/Middleware  | CoreIOT, ThingsBoard CE (Docker)                             |
| Application       | Kiểm toán truy cập, cảnh báo đột nhập, nhật ký tuân thủ      |


---

## 5. Thiết kế phần cứng

### 5.1 Đối chiếu với bộ kit trong ảnh (hardware1.jpeg, hardware2.jpeg)


| Thành phần blueprint                                                 | Có trong kit (theo ảnh)              | Ghi chú                                                                                                                              |
| :-------------------------------------------------------------------- | :------------------------------------ | :------------------------------------------------------------------------------------------------------------------------------------ |
| Yolo:Bit (ESP32, nút A/B, LED 5x5 màu, loa, cổng pin 3.7–6 V)        | Có                                   | Ảnh 1 xác nhận nút A, B, LED 5x5, loa, cảm biến ánh sáng/nhiệt độ/gia tốc, mạch sạc Li-ion/LiPo 3.7 V → phù hợp làm thẻ đeo chạy pin |
| DHT20                                                                | Có                                   | Cảm biến nhiệt độ – độ ẩm                                                                                                            |
| LCD 16x2                                                             | Có                                   | Cần xác nhận có mạch I2C PCF8574 và địa chỉ (0x27 hay 0x3F)                                                                          |
| Cảm biến khoảng cách (siêu âm)                                       | Có                                   |                                                                                                                                      |
| Cảm biến ánh sáng (LDR)                                              | Có                                   | Dạng module; xác nhận ngõ ra analog                                                                                                  |
| Mắt đọc hồng ngoại + remote                                          | Có                                   | Remote có bàn phím số 0–9                                                                                                            |
| Servo                                                                | Có                                   | Ảnh là loại servo nhỏ kiểu SG90 (xanh dương); blueprint ghi MG90 → **ghi đúng model thực tế trong báo cáo**                          |
| Đèn LED RGB (module)                                                 | Có                                   | Có thể dùng làm đèn phụ nếu NeoPixel onboard khó dùng                                                                                |
| Mạch mở rộng, dây tín hiệu x9, cáp USB                               | Có                                   | Mạch mở rộng trong ảnh dành cho Yolo:Bit                                                                                             |
| **YoloUNO (ESP32-S3)**                                               | Có (đây là thiết bị trường cho mượn) | Phải chuẩn bị riêng; xác nhận cách đấu cảm biến Grove vào YoloUNO                                                                    |
| Cảm biến chuyển động, relay, quạt mini, bơm, độ ẩm đất, công tắc USB | Có, chưa dùng                        | Tùy chọn mở rộng (5.3)                                                                                                               |


Số cổng/dây: hệ thống dùng 6 module (DHT20, LCD, LDR, siêu âm, IR, servo) so với 9 dây tín hiệu có sẵn → đủ, nhưng I2C (DHT20 + LCD) cần chia sẻ bus.

### 5.2 Bảng chức năng và chân


| Thiết bị | Linh kiện | Giao tiếp                | Vai trò                                             |
| :-------- | :--------- | :------------------------ | :--------------------------------------------------- |
| Yolo:Bit | Nút A     | GPIO nội                 | Gửi gói mở khóa ESP-NOW                             |
|          | Nút B     | GPIO nội                 | Báo động duress                                     |
|          | LED 5x5   | nội                      | ✔ / ✖ / biểu tượng khóa                             |
|          | Loa       | nội                      | Chuông xác nhận, bíp cảnh báo                       |
| YoloUNO  | DHT20     | I2C 0x38                 | Nhiệt độ, độ ẩm                                     |
|          | LCD1602   | I2C 0x27/0x3F            | Giao diện cục bộ                                    |
|          | LDR       | ADC                      | Phát hiện mở cửa trái phép                          |
|          | Siêu âm   | 2 GPIO (Trig/Echo)       | Đo khoảng cách; &lt; 30 cm thì đánh thức UI         |
|          | IR 1838   | 1 GPIO                   | Giải mã NEC cho PIN                                 |
|          | Servo     | PWM 50 Hz                | 0° = mở, 90° = khóa                                 |
|          | NeoPixel  | GPIO 45 (theo blueprint) | Xanh lá = mở, xanh dương = nhập, đỏ = khóa/báo động |
|          | LED       | GPIO 48 (theo blueprint) | Heartbeat 1 Hz                                      |


> **Cần kiểm chứng trên board thực tế:** số chân GPIO 45/48 và các chân Trig/Echo/IR/ADC/PWM chưa có trong tài liệu nào đính kèm. Phải đối chiếu với sơ đồ chân chính thức của YoloUNO trước khi chốt (chưa điền chân cụ thể để tránh sai). Đồng thời ESP32-S3 có một số chân strapping/đặc biệt cần tránh.

### 5.3 Mở rộng tùy chọn (dùng linh kiện sẵn có trong kit)

- **Quạt mini + relay**: RuleChain/Gateway bật quạt thông gió khi nhiệt độ vượt ngưỡng (thể hiện vòng điều khiển khép kín).
- **Gia tốc kế trên Yolo:Bit**: lắc mạnh để kích hoạt duress thay cho nút B.
- **Cảm biến chuyển động (PIR)**: bổ sung tín hiệu cho mô hình bất thường (có chuyển động nhưng không có xác thực).

### 5.4 Điểm kỹ thuật cần lưu ý

- **LDR không đo trực tiếp lux.** Blueprint ghi ngưỡng "&gt; 80 lux", nhưng module LDR chỉ cho giá trị ADC. Cần hiệu chuẩn: đo giá trị ADC khi tủ đóng và khi mở trong điều kiện sáng thực tế, rồi đặt ngưỡng theo ADC (hoặc báo cáo là "đơn vị tương đối"), kèm trễ (hysteresis) và lọc trung bình để tránh báo giả.
- **Nguồn servo**: servo khởi động có thể gây sụt áp làm reset MCU/nhiễu ADC; cần tụ lọc hoặc cấp nguồn phù hợp.
- **Yolo:Bit chạy pin**: chỉ dùng pin Li-ion/LiPo 3.7 V theo hướng dẫn trong ảnh.

---

## 6. Thiết kế phần mềm nhúng

### 6.1 Kiến trúc FreeRTOS trên YoloUNO


| Task              | Nhiệm vụ                              | Giao tiếp           |
| :----------------- | :------------------------------------- | :------------------- |
| T1 `ultrasonic`   | Đo khoảng cách định kỳ                | queue → state       |
| T2 `sensors`      | Đọc DHT20 (I2C), LDR (ADC), lọc       | queue → state, UART |
| T3 `ir_rx`        | Giải mã NEC, ghép PIN                 | queue → state       |
| T4 `espnow_rx`    | Callback nhận gói, kiểm tra token     | queue → state       |
| T5 `actuator_fsm` | Máy trạng thái, servo/NeoPixel/LCD    | —                   |
| T6 `uart_bridge`  | Xuất JSON Lines, nhận lệnh từ Gateway | UART                |
| T7 `heartbeat`    | LED 1 Hz                              | —                   |


Dùng queue/mutex cho dữ liệu dùng chung; bus I2C được bảo vệ bằng mutex vì DHT20 và LCD dùng chung.

### 6.2 Máy trạng thái

`IDLE (khóa, đỏ)` → (khoảng cách &lt; 30 cm) → `STANDBY` → (thẻ hoặc PIN hợp lệ) → `UNLOCKED (xanh, 10 s)` → hết giờ → `IDLE`.
Nhánh phụ: không hợp lệ → `DENIED` (đỏ chớp, strike +1) → 3 strike → `LOCKOUT 60 s`.
Nhánh cảnh báo: `LOCKED` + LDR vượt ngưỡng → `BREACH` (đỏ strobe, LCD "SECURITY BREACH", gửi cảnh báo nghiêm trọng).
Nhánh duress: nhận cờ duress → hành xử như bình thường ở cục bộ (không phát tín hiệu rõ ràng) nhưng gửi sự kiện `duress` lên Gateway.

### 6.3 Chế độ xác thực

- `mode = normal`: thẻ HOẶC PIN.
- `mode = high_security`: cần thẻ rồi PIN trong cửa sổ thời gian (ví dụ 15 s; giá trị là tham số cấu hình).

### 6.4 Giao thức ESP-NOW (thẻ → tủ)

Blueprint dùng "token tĩnh". Token tĩnh bị bắt gói rồi phát lại (replay) được, nên đề xuất:

- Mỗi gói gồm `device_id`, `counter` (tăng đơn điệu, lưu NVS), `cmd` (UNLOCK / DURESS), `mac` = HMAC-SHA256 cắt ngắn của (`device_id`‖`counter`‖`cmd`) bằng khóa chung.
- Tủ chỉ chấp nhận khi MAC đúng và `counter` &gt; counter đã thấy.
- Có thể dùng thêm mã hóa ESP-NOW (PMK/LMK) của chính ESP-NOW như lớp bổ sung; nhóm cần đọc tài liệu Espressif để xác nhận giới hạn (số peer mã hóa, v.v.).

### 6.5 Giao thức UART (YoloUNO ↔ Gateway)

JSON Lines, một đối tượng mỗi dòng, 115200 baud. Ví dụ (giá trị minh họa, không phải số đo thật):

```json
{"t":"telemetry","ts":0,"temp":0.0,"hum":0.0,"ldr":0,"dist":0,"state":"LOCKED"}
{"t":"event","ts":0,"type":"access","method":"badge","result":"granted"}
{"t":"event","ts":0,"type":"tamper","detail":"ldr_breach"}
{"t":"cmd","action":"unlock","nonce":"..."}   // Gateway -> YoloUNO
```

Gateway cần xử lý dòng hỏng, mất kết nối cổng serial và tự kết nối lại.

### 6.6 Wi-Fi và ESP-NOW cùng lúc (rủi ro)

OTA (T14) cần YoloUNO kết nối Wi-Fi, trong khi ESP-NOW phải chạy cùng kênh vô tuyến với Wi-Fi STA. Thẻ đeo cần khóa cùng kênh với router của phòng lab. Đây là rủi ro tích hợp cần thử sớm (mục 12).

---

## 7. Gateway và Edge AI

### 7.1 Gateway (T08)

- Daemon Python: `pyserial` đọc khung, kiểm tra hợp lệ, gắn dấu thời gian.
- Publish MQTT đồng thời tới CoreIOT và ThingsBoard cục bộ; hàng đợi đệm khi một đích mất kết nối, gửi lại khi có mạng.
- Nhận RPC từ cả hai nền tảng và chuyển thành lệnh UART.

### 7.2 Phát hiện bất thường (T09)

- **Mô hình**: Isolation Forest (scikit-learn); One-Class SVM là phương án so sánh. Tham khảo Liu, Ting, Zhou (2008).
- **Đặc trưng theo cửa sổ trượt**: xu hướng nhiệt độ (độ dốc), độ biến thiên LDR, số lần kích hoạt siêu âm, số lần truy cập thất bại, giờ trong ngày (ngoài giờ làm việc).
- **Dữ liệu huấn luyện**: không có dữ liệu có nhãn sẵn. Kế hoạch: thu dữ liệu "bình thường" trong vài ngày thử nghiệm thật, rồi tạo kịch bản bất thường có chủ đích (làm nóng DHT20 bằng nguồn nhiệt an toàn, mở cửa, nhập sai PIN liên tiếp) để đánh giá. Nếu dữ liệu thật ít, bổ sung dữ liệu mô phỏng và **ghi rõ trong báo cáo là dữ liệu mô phỏng**.
- **Đánh giá**: báo cáo precision/recall trên các kịch bản có nhãn do nhóm tự dựng; số liệu sẽ lấy từ thực nghiệm, không đặt trước.
- **Đầu ra**: `anomaly_score` và cờ `early_warning` đẩy lên cả hai nền tảng.
- Phương án "SLM cục bộ" trong blueprint **không** thuộc phạm vi chính; chỉ giữ scikit-learn để đáp ứng rubric T09 và giảm rủi ro.

### 7.3 Dashboard cục bộ (T10)

Streamlit: trạng thái khóa, nhiệt độ/độ ẩm, LDR, biểu đồ `anomaly_score`, nhật ký truy cập/sự kiện, chỉ báo kết nối (serial, CoreIOT, local TB).

---

## 8. Đám mây và dự phòng

### 8.1 CoreIOT (T11, T12, T13, T14)

- **Telemetry** qua MQTT topic `v1/devices/me/telemetry`; **RPC** qua `v1/devices/me/rpc/request/+` và phản hồi `.../response/{id}` (API MQTT kiểu ThingsBoard; nhóm xác nhận lại với tài liệu của CoreIOT).
- **Dashboard (T11)**: biểu đồ nhiệt độ/độ ẩm/LDR/`anomaly_score`, thẻ trạng thái khóa, nút RPC (khóa/mở, bật chế độ bảo mật cao).
- **RuleChain (T12)**: ngưỡng nhiệt độ/độ ẩm, sự kiện `tamper`/`duress`, `anomaly_score` vượt ngưỡng → tạo cảnh báo.
- **Thông báo (T13)**: Telegram bot (và/hoặc Email).
- **OTA (T14)**: cập nhật firmware YoloUNO qua Wi-Fi; cần quy trình xác minh toàn vẹn firmware và kế hoạch quay lui nếu cập nhật lỗi (partition OTA kép).
- Địa chỉ máy chủ `app.coreiot.io` lấy theo blueprint; cần xác nhận lại với hướng dẫn môn học trước khi đưa vào báo cáo.

### 8.2 ThingsBoard cục bộ bằng Docker (N07)

- **Vai trò:** thông báo đồ án quy định CoreIOT là nền tảng bắt buộc; ThingsBoard cục bộ **không thay thế** CoreIOT mà là điểm cộng N07 (1.0 điểm, trần điểm cộng là 1). Mọi mục T11–T15 vẫn thực hiện trên CoreIOT.
- **Bằng chứng cho N07:** thông báo yêu cầu có bằng chứng (ảnh chụp, log, video, mã nguồn) mới được tính điểm, và không nêu mức độ tối thiểu. Vì vậy ThingsBoard cục bộ phải nhận telemetry thật từ Gateway và có dashboard hiển thị, không chỉ cài đặt. Mức độ cần đạt sẽ hỏi giảng viên (Phụ lục A).
- Ngoài ra nhóm dùng ThingsBoard cục bộ (kèm Cloudflare Tunnel + Access) để các thành viên cùng xem dashboard khi phát triển; đây là công cụ phối hợp, không phải một phần của kiến trúc.
- `docker-compose.yml` chạy ThingsBoard CE, mở 8080 (UI) và 1883 (MQTT), volume lưu dữ liệu bền vững.
- Cấu hình thiết bị/dashboard tương tự CoreIOT để chứng minh hoạt động độc lập.
- Kiểm thử: ngắt Internet, xác nhận dữ liệu vẫn vào local TB.

### 8.3 Thông số bảo mật truyền tải

Blueprint ghi MQTT over TLS ở sơ đồ nhưng dùng cổng 1883 (không mã hóa) ở mục 4.5. Cần thống nhất: dùng cổng TLS cho CoreIOT nếu được hỗ trợ (nhóm tra tài liệu), còn local TB trong mạng nội bộ có thể dùng 1883 và ghi rõ là chấp nhận rủi ro.

### 8.4 An toàn cho RPC mở khóa từ xa

Cho phép mở khóa qua internet là rủi ro lớn nhất. Đề xuất:

- RPC mở khóa yêu cầu **nonce dùng một lần + thời hạn hiệu lực ngắn**, và chỉ chấp nhận khi chế độ "cho phép mở từ xa" được bật tại chỗ hoặc bởi quản trị viên.
- Ghi nhật ký mọi RPC.
- **Fail-secure**: mất kết nối/mất Gateway → tủ giữ nguyên trạng thái khóa.
- Có thể giới hạn RPC từ xa chỉ ở lệnh **khóa** và **bật/tắt chế độ**, còn **mở** chỉ dùng trong demo (quyết định của nhóm).

---

## 9. Bảo mật (tổng hợp)


| Mối đe dọa                      | Biện pháp                                                    |
| :------------------------------- | :------------------------------------------------------------ |
| Phát lại gói ESP-NOW            | Counter + HMAC (6.4)                                         |
| Dò PIN                          | Giới hạn 3 lần, khóa phạt 60 s, ghi log, cảnh báo            |
| Lộ khóa/token/mật khẩu trong mã | Để trong tệp cấu hình/ biến môi trường, không commit lên git |
| Mở khóa từ xa trái phép         | Cơ chế mục 8.4, xác thực thiết bị bằng access token          |
| Nghe lén MQTT                   | TLS với CoreIOT khi khả dụng                                 |
| Cưỡng ép người dùng             | Duress im lặng (nút B)                                       |
| Mất điện/ngắt Gateway           | Fail-secure, khóa chạy độc lập trên YoloUNO                  |


---

## 10. Kế hoạch kiểm thử và nghiệm thu


| Mã   | Kịch bản                         | Kết quả mong đợi                                                    |
| :---- | :-------------------------------- | :------------------------------------------------------------------- |
| TC1  | Bấm nút A với token hợp lệ       | Servo mở, NeoPixel xanh, thẻ hiện ✔, log gửi lên Gateway            |
| TC2  | Phát lại gói đã bắt              | Bị từ chối                                                          |
| TC3  | PIN đúng / sai / sai 3 lần       | Mở / từ chối / khóa phạt 60 s + cảnh báo                            |
| TC4  | Mở cửa khi `LOCKED` (che/mở LDR) | Strobe đỏ, LCD cảnh báo, Telegram nhận tin                          |
| TC5  | Nút B duress                     | Sự kiện duress lên cloud, hành vi cục bộ không lộ                   |
| TC6  | Làm nóng DHT20 an toàn           | RuleChain tạo cảnh báo nhiệt                                        |
| TC7  | Kịch bản bất thường đa biến      | `anomaly_score` vượt ngưỡng, cờ cảnh báo sớm                        |
| TC8  | Ngắt Internet                    | Local TB vẫn nhận dữ liệu; sau khi có mạng, dữ liệu đệm được gửi bù |
| TC9  | RPC mở/khóa từ dashboard         | Chỉ chấp nhận theo quy tắc 8.4                                      |
| TC10 | OTA                              | Firmware mới chạy; lỗi → quay lui                                   |
| TC11 | Rút cáp Gateway                  | Khóa vẫn vận hành, trạng thái giữ an toàn                           |
| TC12 | Chế độ bảo mật cao               | Chỉ mở khi có cả thẻ và PIN trong cửa sổ thời gian                  |


Các số liệu đo (độ trễ, tỷ lệ báo giả, độ chính xác mô hình) sẽ được thu thập khi thực nghiệm và đưa vào báo cáo.

---

## 11. Ánh xạ sang thang điểm môn học


| Hạng mục         | Mã  | Nội dung đề xuất đáp ứng                                                                                                                                      | Điểm (theo blueprint) |
| :---------------- | :--- | :------------------------------------------------------------------------------------------------------------------------------------------------------------- | :---------------------: |
| Cảm biến         | T01 | Cảm biến I2C **trên Tasmota** (theo thông báo). DHT20 trên firmware tự viết có thể **không** đủ điều kiện; chỉ tính nếu dùng Tasmota hoặc giảng viên xác nhận | 0.5 (chưa chắc)       |
| Giao tiếp cục bộ | T06 | ESP-NOW Yolo:Bit ↔ YoloUNO                                                                                                                                    | 1.5                   |
| Gateway          | T08 | Gateway PC/Pi, UART + RPC                                                                                                                                     | 1.0                   |
|                  | T09 | Isolation Forest                                                                                                                                              | 1.0                   |
|                  | T10 | Dashboard Streamlit/Tkinter                                                                                                                                   | 1.0                   |
| CoreIOT          | T11 | Dashboard + nút RPC                                                                                                                                           | 1.0                   |
|                  | T12 | RuleChain ngưỡng                                                                                                                                              | 1.0                   |
|                  | T13 | Telegram/Email                                                                                                                                                | 0.5                   |
|                  | T14 | OTA qua Wi-Fi                                                                                                                                                 | 2.0                   |
|                  | T15 | Gateway trên CoreIOT đồng bộ với Gateway cục bộ — thiết kế dual-publish có thể liên quan nhưng **chưa chắc đủ điều kiện**; cần hỏi giảng viên cách hiểu       | 2.0 (chưa chắc)       |
| Tổng công nghệ   |     | Thô: 9.5 (T01, T06, T08–T14) hoặc 11.5 nếu T15 được công nhận; tối đa tính 8.0                                                                                | 8.0                   |
| Báo cáo          |     | 6 chương theo mẫu báo cáo của môn, ≥ 5 tài liệu tham khảo, kèm bảng tự đánh giá và bảng phân công                                                             | 2.0                   |
| Nâng cao         | N07 | ThingsBoard CE tự triển khai trên máy cục bộ (Docker)                                                                                                         | 1.0                   |
| **Tổng**         |     | min(8; Σ công nghệ) + báo cáo (≤ 2) + min(1; Σ nâng cao)                                                                                                      | **10.0**              |


Điểm số các mục lấy từ thông báo đồ án (học kỳ 261, ngày 27/10/2026). Mã nhóm điểm và nội dung T08–T15 trong thông báo là: T08 gateway tổng hợp dữ liệu, gửi lên CoreIOT và nhận lệnh điều khiển; T09 AI chạy trên gateway; T10 giao diện giám sát/điều khiển trên gateway; T11 template/dashboard/điều khiển từ xa; T12 RuleChain; T13 cảnh báo khi vượt ngưỡng; T14 OTA.

Điểm công nghệ thô vượt trần 8.0 nên còn dư địa: nếu phải cắt giảm khi thiếu thời gian thì ưu tiên giữ các mục trọng số cao và chắc chắn đủ điều kiện (T06, T08, T09, T10, T11, T12). T14 (2.0 điểm) có rủi ro tích hợp cao nhất (mục 6.6), nên làm sớm. Một phần được làm dở vẫn được giảng viên chấm theo mức độ hoàn thành, nhưng chỉ khi có bằng chứng trong báo cáo.

---

## 12. Kế hoạch thực hiện

**Mốc của môn học (theo thông báo đồ án):**


| Việc                                                                  | Thời hạn   | Hình thức                     |
| :--------------------------------------------------------------------- | :---------- | :----------------------------- |
| Đăng ký nhóm và đề tài                                                | Tuần 10–11 | Sinh viên tự lập nhóm         |
| Trình bày proposal (mô tả tính năng, danh sách mục công nghệ dự kiến) | Tuần 12–13 | Trực tiếp trên lớp (tùy chọn) |
| Demo và thảo luận                                                     | Tuần 10–15 | Trực tiếp trên lớp (tùy chọn) |
| Nộp báo cáo, mã nguồn, video demo                                     | Tuần 16    | LMS                           |


Nộp trễ có thể bị trừ điểm theo số ngày trễ. Thông báo không nêu ngày cụ thể của từng tuần nên nhóm cần đối chiếu với lịch học kỳ.

Kế hoạch bên dưới tính theo tuần tương đối (10 tuần) và cần điều chỉnh cho khớp mốc trên.


| Giai đoạn    | Nội dung                                                                                                                           | Sản phẩm                         |
| :------------ | :---------------------------------------------------------------------------------------------------------------------------------- | :-------------------------------- |
| 1 (tuần 1–2) | Xác nhận phần cứng (pinout YoloUNO, địa chỉ I2C, model servo); đọc cảm biến; ESP-NOW cơ bản; **thử sớm Wi-Fi + ESP-NOW cùng kênh** | Firmware nhận gói, đọc DHT20/LDR |
| 2 (tuần 3–4) | FreeRTOS đầy đủ, máy trạng thái, IR PIN, servo, LCD, NeoPixel; giao thức UART                                                      | Tủ chạy độc lập                  |
| 3 (tuần 5–6) | Gateway, ThingsBoard Docker, MQTT kép, dashboard cục bộ; thu dữ liệu; huấn luyện Isolation Forest                                  | Gateway + local TB               |
| 4 (tuần 7–8) | CoreIOT: dashboard, RuleChain, Telegram, RPC, OTA                                                                                  | Hệ thống tích hợp                |
| 5 (tuần 9)   | Kiểm thử TC1–TC12, đo số liệu, sửa lỗi                                                                                             | Bảng kết quả                     |
| 6 (tuần 10)  | Báo cáo 6 chương, video demo                                                                                                       | Báo cáo + demo                   |


**Phân công**: `[điền theo thành viên: firmware / gateway+AI / cloud+OTA / báo cáo]`.

### Rủi ro chính


| Rủi ro                                        | Mức        | Giảm thiểu                               |
| :--------------------------------------------- | :----------: | :---------------------------------------- |
| ESP-NOW và Wi-Fi xung đột kênh, ảnh hưởng OTA | Cao        | Thử tích hợp ngay giai đoạn 1; khóa kênh |
| Không có YoloUNO hoặc sai sơ đồ chân          | Cao        | Xác nhận phần cứng trong tuần 1          |
| LDR báo giả do ánh sáng môi trường            | Trung bình | Hiệu chuẩn, hysteresis, lọc              |
| Thiếu dữ liệu huấn luyện                      | Trung bình | Kịch bản thu thập + mô phỏng ghi rõ      |
| Mất kết nối CoreIOT khi demo                  | Trung bình | Local TB làm dự phòng, quay video        |
| Sụt áp khi servo chạy                         | Thấp       | Tụ lọc, nguồn riêng                      |


### 12.1 Sản phẩm bàn giao và quy định môn học

Theo thông báo đồ án:

1. **Báo cáo PDF** theo mẫu, tên file `[ClassCode]_[GroupCode]_IoTReport.pdf`, gồm 6 phần (Giới thiệu, Phân tích hệ thống, Triển khai, Đo lường và kiểm thử, Kết luận, Hướng dẫn mã nguồn), kèm **bảng tự đánh giá các mục công nghệ** và **bảng phân công**. Phần giới thiệu cần ≥ 5 tài liệu tham khảo; phần phân tích phải ánh xạ từng tính năng sang mã T/N.
2. **Mã nguồn trên GitHub** (công khai hoặc cấp quyền cho giảng viên), có `README.md` hướng dẫn sử dụng; **lịch sử commit phải phản ánh công việc của từng thành viên** (mỗi người tự commit phần mình).
3. **Video demo** (khuyến nghị 5–10 phút) trình diễn từng tính năng đăng ký chấm điểm, kèm link trong báo cáo.

Các quy định cần tuân thủ:

- Phần tái sử dụng từ dự án mẫu trên CoreIOT hoặc nguồn khác phải ghi rõ, tách biệt với phần nhóm tự phát triển; mọi tài liệu, mã nguồn, dự án mẫu tham khảo đều phải trích dẫn.
- Được dùng công cụ AI hỗ trợ lập trình và viết báo cáo, nhưng **phải nêu rõ mức độ sử dụng trong báo cáo**, và mỗi thành viên phải giải thích được phần việc của mình khi vấn đáp.
- Điểm cá nhân có thể được điều chỉnh theo bảng phân công, đóng góp thực tế và buổi vấn đáp.
- Một mục chỉ được điểm khi có bằng chứng (ảnh chụp, log, video, mã nguồn).

---

## 13. Tài liệu tham khảo (dự kiến)

> Danh sách này gợi ý theo hiểu biết, chưa kiểm tra lại URL/phiên bản; cần xác nhận và bổ sung ngày truy cập trước khi đưa vào báo cáo chính thức.

1. F. T. Liu, K. M. Ting, Z.-H. Zhou, "Isolation Forest," *Proc. IEEE International Conference on Data Mining (ICDM)*, 2008.
2. Espressif Systems, *ESP-IDF Programming Guide — ESP-NOW* (tài liệu chính thức trên docs.espressif.com).
3. ThingsBoard, tài liệu *MQTT Device API*, *Rule Engine* và *OTA firmware updates* (thingsboard.io/docs).
4. OASIS, *MQTT Version 3.1.1* (tiêu chuẩn OASIS, 2014).
5. scikit-learn, tài liệu *IsolationForest* và *Novelty and Outlier Detection* (scikit-learn.org).
6. FreeRTOS, *Mastering the FreeRTOS Real Time Kernel* (freertos.org).
7. Tài liệu kit Yolo:Bit / YoloUNO của nhà sản xuất (Yolo:Bit hướng dẫn trong ảnh hardware1.jpeg; sơ đồ chân YoloUNO cần lấy từ tài liệu chính thức).
8. Tài liệu hướng dẫn CoreIOT do giảng viên/nhà cung cấp cung cấp.

---

## Phụ lục A — Việc cần xác nhận trước khi chốt

1. Sơ đồ chân YoloUNO: Trig/Echo, IR, ADC (LDR), PWM (servo), GPIO 45/48 có đúng NeoPixel/LED không.
2. YoloUNO có được cấp riêng không, và cách đấu Grove/cảm biến.
3. Model servo thực tế (ảnh trông như SG90, blueprint ghi MG90) và địa chỉ I2C của LCD.
4. Máy chủ/cổng CoreIOT (có TLS không), cách tạo thiết bị Gateway và cơ chế OTA mà CoreIOT hỗ trợ.
5. Ngày cụ thể của các tuần mốc (tuần 10–16) theo lịch học kỳ 261, số thành viên nhóm (≤ 3) và phân công.
6. Quyết định: có cài chế độ bảo mật cao (xác thực kép đúng nghĩa) hay đổi tên thành "dual-channel".
7. Quyết định: có cho phép RPC **mở khóa** từ xa hay chỉ cho phép khóa/đổi chế độ.
8. **Câu hỏi gửi giảng viên** (email hoặc forum LMS):
   - T01 yêu cầu "I2C trên Tasmota": DHT20 trên firmware tự viết có được tính không?
   - T15 "Gateway trên CoreIOT đồng bộ với Gateway cục bộ": thiết kế Gateway publish đồng thời lên CoreIOT và ThingsBoard cục bộ có đáp ứng không, và cần chứng minh "đồng bộ" thế nào?
   - N07: mức độ sử dụng ThingsBoard cục bộ tối thiểu để được điểm (chỉ nhận telemetry và dashboard, hay phải có RPC/RuleChain)?
   - Dùng Yolo:Bit làm thiết bị thứ hai ngoài YoloUNO có phù hợp với yêu cầu nền tảng không (T06 cần hai thiết bị ESP-NOW)?
   - Yêu cầu và định dạng cụ thể của bảng tự đánh giá, bảng phân công, và mẫu báo cáo.

## Phụ lục B — Những chỗ đã chỉnh so với blueprint

- Token tĩnh → counter + HMAC (chống phát lại).
- "&gt; 80 lux" → ngưỡng ADC đã hiệu chuẩn (LDR không cho lux).
- Làm rõ "dual-authentication" (thẻ HOẶC PIN vs thẻ VÀ PIN).
- Bổ sung rủi ro chung kênh Wi-Fi/ESP-NOW cho OTA, và cơ chế an toàn cho RPC mở khóa.
- Thống nhất TLS vs cổng 1883.
- Gỡ phương án SLM khỏi phạm vi chính.

## Phụ lục C — Những chỗ đã chỉnh sau khi đối chiếu thông báo đồ án

- Làm rõ CoreIOT là nền tảng bắt buộc; ThingsBoard cục bộ chỉ là điểm cộng N07, không thay thế CoreIOT.
- T01 gắn với Tasmota nên không còn ghi chắc chắn 0.5 điểm.
- Bổ sung T15 (2.0 điểm) ở trạng thái "chưa chắc", cần xác nhận.
- Bổ sung mốc thời gian chính thức, giới hạn 3 sinh viên/nhóm, các sản phẩm bàn giao, yêu cầu về lịch sử commit và nêu rõ việc dùng AI.
- Danh sách câu hỏi gửi giảng viên (Phụ lục A, mục 8).