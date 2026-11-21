"""
Smart Safe Guardian - Local Gateway Operator Interface (T10)
Ultra-lightweight embedded web console for Raspberry Pi Zero 2W.
Zero external dependencies (uses Python standard library).
Features:
- ThreadingHTTPServer (sub-millisecond HTTP response, non-blocking)
- Native Server-Sent Events (SSE) for 0-latency live terminal & telemetry streaming
- 2000-line circular log buffer with smooth DOM append
- Direct hardware serial control (Unlock, Lock, Lockdown, Ack, Custom CLI)
"""

import collections
import html
import json
import os
import queue
import re
import socket
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


# Client queues for active Server-Sent Events (SSE) streams
sse_clients = []
sse_lock = threading.Lock()


def broadcast_sse(event_dict):
    """Broadcasts a JSON event to all connected SSE clients instantly."""
    payload = (f"data: {json.dumps(event_dict)}" + "\n\n").encode("utf-8")
    with sse_lock:
        dead = []
        for q in sse_clients:
            try:
                q.put_nowait(payload)
            except Exception:
                dead.append(q)
        for q in dead:
            if q in sse_clients:
                sse_clients.remove(q)


HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Smart Safe Guardian | Local Gateway Console</title>
  <style>
    :root {
      --bg: #0b0f19;
      --card-bg: #151d30;
      --border: #23314d;
      --text: #e2e8f0;
      --text-muted: #94a3b8;
      --accent: #38bdf8;
      --green: #10b981;
      --red: #ef4444;
      --amber: #f59e0b;
      --purple: #c084fc;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background-color: var(--bg);
      color: var(--text);
      padding: 16px;
      display: flex;
      justify-content: center;
    }
    .container {
      width: 100%;
      max-width: 960px;
      display: flex;
      flex-direction: column;
      gap: 14px;
    }
    header {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 14px 18px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 10px;
    }
    .header-title h1 {
      font-size: 1.15rem;
      font-weight: 700;
      letter-spacing: -0.02em;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .header-title p {
      font-size: 0.8rem;
      color: var(--text-muted);
      margin-top: 2px;
    }
    .badges {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }
    .badge {
      font-size: 0.72rem;
      padding: 3px 8px;
      border-radius: 6px;
      font-weight: 600;
      letter-spacing: 0.03em;
      text-transform: uppercase;
      border: 1px solid transparent;
    }
    .badge-rpi { background: #1e1b4b; color: #a5b4fc; border-color: #3730a3; }
    .badge-t10 { background: #064e3b; color: #6ee7b7; border-color: #047857; }
    .badge-live { background: #0f172a; color: #38bdf8; border-color: #0284c7; }

    /* Telemetry Cards */
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
      gap: 12px;
    }
    .card {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 12px;
      display: flex;
      flex-direction: column;
      gap: 4px;
    }
    .card-label {
      font-size: 0.7rem;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.05em;
      font-weight: 600;
    }
    .card-val {
      font-size: 1.35rem;
      font-weight: 700;
      letter-spacing: -0.03em;
      font-variant-numeric: tabular-nums;
    }
    .card-sub {
      font-size: 0.72rem;
      color: var(--text-muted);
    }
    .pill {
      display: inline-block;
      padding: 3px 8px;
      border-radius: 4px;
      font-size: 0.8rem;
      font-weight: 700;
      text-align: center;
      width: fit-content;
    }
    .pill-locked { background: #064e3b; color: #34d399; }
    .pill-unlocked { background: #78350f; color: #fbbf24; }
    .pill-normal { background: #064e3b; color: #34d399; }
    .pill-breach { background: #7f1d1d; color: #f87171; animation: pulse 1s infinite alternate; }
    .pill-lockdown { background: #581c87; color: #e879f9; }
    .pill-inactive { background: #1e293b; color: #94a3b8; }
    @keyframes pulse { from { opacity: 0.7; } to { opacity: 1; } }

    /* Action Buttons */
    .actions {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 12px 14px;
      display: flex;
      flex-direction: column;
      gap: 8px;
    }
    .section-title {
      font-size: 0.72rem;
      color: var(--text-muted);
      text-transform: uppercase;
      font-weight: 700;
      letter-spacing: 0.05em;
    }
    .btn-group {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }
    button {
      flex: 1;
      min-width: 120px;
      padding: 9px 12px;
      border-radius: 6px;
      font-size: 0.82rem;
      font-weight: 600;
      cursor: pointer;
      border: 1px solid transparent;
      transition: all 0.1s ease-in-out;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
    }
    button:active { transform: scale(0.97); }
    .btn-unlock { background: #065f46; color: #a7f3d0; border-color: #059669; }
    .btn-unlock:hover { background: #047857; }
    .btn-lock { background: #1e293b; color: #cbd5e1; border-color: #334155; }
    .btn-lock:hover { background: #334155; }
    .btn-lockdown { background: #831843; color: #fbcfe8; border-color: #9d174d; }
    .btn-lockdown:hover { background: #9d174d; }
    .btn-unlockdown { background: #0e7490; color: #cffafe; border-color: #0891b2; }
    .btn-unlockdown:hover { background: #0891b2; }
    .btn-ack { background: #854d0e; color: #fef08a; border-color: #a16207; }
    .btn-ack:hover { background: #a16207; }

    /* Terminal Console */
    .terminal-container {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      overflow: hidden;
      display: flex;
      flex-direction: column;
    }
    .terminal-header {
      background: #0d1322;
      padding: 8px 14px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      border-bottom: 1px solid var(--border);
      font-size: 0.72rem;
      color: var(--text-muted);
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    }
    .terminal-controls {
      display: flex;
      gap: 12px;
      align-items: center;
    }
    .terminal-box {
      background: #070a12;
      color: #38bdf8;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 0.78rem;
      line-height: 1.45;
      padding: 12px;
      height: 280px;
      overflow-y: auto;
      white-space: pre-wrap;
      word-break: break-all;
    }
    .terminal-input-bar {
      display: flex;
      border-top: 1px solid var(--border);
      background: #0d1322;
    }
    .terminal-input {
      flex: 1;
      background: transparent;
      border: none;
      color: #f8fafc;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 0.8rem;
      padding: 10px 14px;
      outline: none;
    }
    .terminal-send-btn {
      background: #1e293b;
      color: #94a3b8;
      border: none;
      border-left: 1px solid var(--border);
      padding: 0 18px;
      min-width: auto;
      font-size: 0.8rem;
      border-radius: 0;
    }
    .terminal-send-btn:hover { background: #334155; color: #f8fafc; }
    .status-toast {
      font-size: 0.72rem;
      color: var(--text-muted);
      text-align: right;
    }
    .clear-btn {
      background: none;
      border: none;
      color: var(--text-muted);
      cursor: pointer;
      font-size: 0.7rem;
      padding: 0;
      min-width: auto;
    }
    .clear-btn:hover { color: #f8fafc; }
  </style>
</head>
<body>
  <div class="container">
    <header>
      <div class="header-title">
        <h1>🛡️ Smart Safe Guardian</h1>
        <p>Local Gateway Console & Emergency Maintenance Interface (T10)</p>
      </div>
      <div class="badges">
        <span class="badge badge-rpi">Raspberry Pi Zero 2W</span>
        <span class="badge badge-t10">Rubric T10 Interface</span>
        <span class="badge badge-live" id="connBadge">Connecting...</span>
      </div>
    </header>

    <!-- Telemetry Cards -->
    <div class="grid">
      <div class="card">
        <span class="card-label">Vault State</span>
        <div id="cardState"><span class="pill pill-locked">LOCKED</span></div>
        <span class="card-sub" id="cardBadgeInfo">Authorized Badge</span>
      </div>
      <div class="card">
        <span class="card-label">Tamper Status</span>
        <div id="cardBreach"><span class="pill pill-normal">NORMAL</span></div>
        <span class="card-sub" id="cardBreachSub">Optical & Motion Safe</span>
      </div>
      <div class="card">
        <span class="card-label">Lockdown</span>
        <div id="cardLockdown"><span class="pill pill-inactive">INACTIVE</span></div>
        <span class="card-sub">Bruteforce Defense</span>
      </div>
      <div class="card">
        <span class="card-label">Optical (LDR)</span>
        <div class="card-val" id="valLight">---</div>
        <span class="card-sub">ADC (Dark < 500)</span>
      </div>
      <div class="card">
        <span class="card-label">Climate</span>
        <div class="card-val" id="valClimate">--°C</div>
        <span class="card-sub" id="valHum">Humidity: --%</span>
      </div>
      <div class="card">
        <span class="card-label">Proximity</span>
        <div class="card-val" id="valDist">-- cm</div>
        <span class="card-sub" id="valDistSub">HC-SR04 Sonar</span>
      </div>
      <div class="card">
        <span class="card-label">Edge AI Score</span>
        <div class="card-val" id="valAi">0.00</div>
        <span class="card-sub" id="valAiSub">Isolation Forest</span>
      </div>
    </div>

    <!-- Manual Control Panel -->
    <div class="actions">
      <div style="display:flex; justify-content:space-between; align-items:center;">
        <span class="section-title">Emergency Hardware Override (Direct Serial Relay)</span>
        <span class="status-toast" id="actionToast">Ready</span>
      </div>
      <div class="btn-group">
        <button class="btn-unlock" onclick="sendCmd('unlock')">🔓 Unlock</button>
        <button class="btn-lock" onclick="sendCmd('lock')">🔒 Lock</button>
        <button class="btn-lockdown" onclick="sendCmd('lockdown 1')">🛑 Lockdown</button>
        <button class="btn-unlockdown" onclick="sendCmd('lockdown 0')">🟢 Clear Lockdown</button>
        <button class="btn-ack" onclick="sendCmd('ack')">🔔 Ack Alarm</button>
      </div>
    </div>

    <!-- Live Terminal / Serial Bus Logs -->
    <div class="terminal-container">
      <div class="terminal-header">
        <span>GATEWAY CLI & SERIAL BUS STREAM</span>
        <div class="terminal-controls">
          <button class="clear-btn" onclick="clearTerm()">Clear Terminal</button>
          <span id="logCount">0 events</span>
        </div>
      </div>
      <div class="terminal-box" id="termBox">Connecting to live gateway stream...</div>
      <div class="terminal-input-bar">
        <input type="text" class="terminal-input" id="termInput" placeholder="Type raw serial command (e.g. unlock, lock, ack, pair, reboot)..." onkeydown="if(event.key==='Enter') sendCustomCmd()">
        <button class="terminal-send-btn" onclick="sendCustomCmd()">Send</button>
      </div>
    </div>
  </div>

  <script>
    let isAutoScroll = true;
    let totalLogs = 0;
    const termBox = document.getElementById('termBox');

    termBox.addEventListener('scroll', () => {
      const atBottom = termBox.scrollHeight - termBox.scrollTop <= termBox.clientHeight + 40;
      isAutoScroll = atBottom;
    });

    function clearTerm() {
      termBox.textContent = '';
      totalLogs = 0;
      document.getElementById('logCount').textContent = '0 events';
    }

    function appendLog(line) {
      if (!line) return;
      if (termBox.textContent === 'Connecting to live gateway stream...') {
        termBox.textContent = '';
      }
      const el = document.createElement('div');
      el.textContent = line;
      termBox.appendChild(el);
      totalLogs++;
      document.getElementById('logCount').textContent = totalLogs + ' events';

      // Keep up to 1000 lines in DOM to keep browser memory super low
      if (termBox.childNodes.length > 1000) {
        termBox.removeChild(termBox.firstChild);
      }

      if (isAutoScroll) {
        termBox.scrollTop = termBox.scrollHeight;
      }
    }

    function renderData(d) {
      if (!d) return;

      // 1. Vault State
      const isUnlocked = (d.state === 'UNLOCKED');
      document.getElementById('cardState').innerHTML = isUnlocked
        ? '<span class="pill pill-unlocked">UNLOCKED</span>'
        : '<span class="pill pill-locked">LOCKED</span>';
      document.getElementById('cardBadgeInfo').textContent = d.last_badge || 'Authorized Node';

      // 2. Breach State
      const isBreach = !!d.breach;
      document.getElementById('cardBreach').innerHTML = isBreach
        ? '<span class="pill pill-breach">🚨 BREACH</span>'
        : '<span class="pill pill-normal">NORMAL</span>';
      document.getElementById('cardBreachSub').textContent = isBreach ? 'Tamper alarm active!' : 'Enclosure secure';

      // 3. Lockdown
      const isLockdown = !!d.lockdown;
      document.getElementById('cardLockdown').innerHTML = isLockdown
        ? '<span class="pill pill-lockdown">ARMED</span>'
        : '<span class="pill pill-inactive">INACTIVE</span>';

      // 4. Optical LDR
      const light = (d.light !== undefined) ? d.light : '---';
      document.getElementById('valLight').textContent = light;

      // 5. Climate
      const temp = (d.temp !== undefined && d.temp !== 'N/A') ? d.temp + '°C' : '--°C';
      const hum = (d.hum !== undefined && d.hum !== 'N/A') ? d.hum : '--';
      document.getElementById('valClimate').textContent = temp;
      document.getElementById('valHum').textContent = 'Humidity: ' + hum + '%';

      // 6. Proximity
      const dist = (d.dist !== undefined && d.dist !== 'N/A') ? d.dist + ' cm' : '-- cm';
      document.getElementById('valDist').textContent = dist;
      if (typeof d.dist === 'number') {
        document.getElementById('valDistSub').textContent = (d.dist < 30) ? '👤 User Present (< 30cm)' : 'Clear Zone (> 30cm)';
      }

      // 7. Edge AI Score
      const aiScore = (d.anomaly_score !== undefined) ? Number(d.anomaly_score).toFixed(2) : '0.00';
      document.getElementById('valAi').textContent = aiScore;
      const isAiAnomaly = !!d.anomaly;
      document.getElementById('valAi').style.color = isAiAnomaly ? '#f87171' : (aiScore > 0.4 ? '#fbbf24' : '#e2e8f0');
      document.getElementById('valAiSub').textContent = isAiAnomaly ? ('⚠️ ' + (d.anomaly_reason || 'Outlier')) : 'Baseline Safe';
    }

    // Connect to live native SSE Stream (Zero Latency, Zero Polling)
    let sseSource = null;
    function connectSSE() {
      if (sseSource) sseSource.close();
      sseSource = new EventSource('/api/stream');

      sseSource.onopen = () => {
        const b = document.getElementById('connBadge');
        b.textContent = 'STREAMING (LIVE)';
        b.style.borderColor = '#059669';
        b.style.color = '#34d399';
      };

      sseSource.onmessage = (e) => {
        try {
          const msg = JSON.parse(e.data);
          if (msg.type === 'init') {
            renderData(msg.status);
            if (Array.isArray(msg.logs)) {
              termBox.textContent = '';
              msg.logs.forEach(appendLog);
            }
          } else if (msg.type === 'log') {
            appendLog(msg.line);
          } else if (msg.type === 'status') {
            renderData(msg.data);
          }
        } catch (err) {
          console.error('SSE parse error:', err);
        }
      };

      sseSource.onerror = () => {
        const b = document.getElementById('connBadge');
        b.textContent = 'RECONNECTING...';
        b.style.borderColor = '#dc2626';
        b.style.color = '#f87171';
      };
    }

    async function sendCmd(cmd) {
      const toast = document.getElementById('actionToast');
      toast.textContent = 'Relaying: ' + cmd + '...';
      try {
        const res = await fetch('/api/command', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ cmd: cmd })
        });
        const out = await res.json();
        toast.textContent = 'Command sent: ' + cmd;
        setTimeout(() => { toast.textContent = 'Ready'; }, 1500);
      } catch (err) {
        toast.textContent = 'Relay Error: ' + err.message;
      }
    }

    function sendCustomCmd() {
      const inp = document.getElementById('termInput');
      const val = inp.value.trim();
      if (!val) return;
      sendCmd(val);
      inp.value = '';
    }

    async function fetchInitialStatus() {
      try {
        const res = await fetch('/api/status');
        if (res.ok) {
          const d = await res.json();
          renderData(d);
        }
      } catch (e) {}
    }

    // Load initial values immediately, then establish SSE stream
    fetchInitialStatus();
    connectSSE();
  </script>
</body>
</html>
"""


class LogCaptureTee:
    """Tees stdout so lines are displayed on terminal AND streamed live to connected browsers."""
    def __init__(self, original_stdout, maxlen=2000):
        self.original_stdout = original_stdout
        self.buffer = collections.deque(maxlen=maxlen)

    def write(self, s):
        self.original_stdout.write(s)
        if s.strip():
            # Strip ANSI color codes (both real escape byte and literal escapes)
            clean = re.sub(r'(\x1b|\\033|\\\\033)\[[0-9;]*[a-zA-Z]', '', s).strip()
            if clean:
                for line in clean.splitlines():
                    trimmed = line.strip()
                    if trimmed:
                        self.buffer.append(trimmed)
                        # Push immediately to all SSE clients in real-time
                        broadcast_sse({"type": "log", "line": trimmed})

    def flush(self):
        self.original_stdout.flush()

    def fileno(self):
        return self.original_stdout.fileno()


def make_handler(gateway_instance, log_tee):
    class LocalWebHandler(BaseHTTPRequestHandler):
        # HTTP/1.1 with explicit connection management
        protocol_version = "HTTP/1.1"

        def log_message(self, format, *args):
            # Suppress default HTTP request printing to avoid terminal clutter
            pass

        def do_GET(self):
            if self.path in ("/", "/index.html"):
                body = HTML_PAGE.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(body)

            elif self.path == "/api/stream":
                # Real-Time Server-Sent Events (SSE) Stream
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "keep-alive")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()

                client_q = queue.Queue(maxsize=300)
                with sse_lock:
                    sse_clients.append(client_q)

                # Send initial snapshot (current state + recent log history)
                st = gateway_instance._get_current_vault_state()
                init_data = {
                    "type": "init",
                    "status": {
                        "state": st.get("state", "LOCKED"),
                        "breach": st.get("breach", False),
                        "lockdown": st.get("lockdown", False),
                        "light": st.get("light", 0),
                        "temp": st.get("temp", "N/A"),
                        "hum": st.get("hum", "N/A"),
                        "dist": st.get("dist", "N/A"),
                        "anomaly_score": getattr(gateway_instance, "last_anomaly_score", 0.0),
                        "anomaly": getattr(gateway_instance, "last_anomaly", False),
                        "anomaly_reason": getattr(gateway_instance, "last_anomaly_reason", ""),
                        "last_badge": getattr(gateway_instance, "mock_state", {}).get("last_badge", "Authorized Badge")
                    },
                    "logs": list(log_tee.buffer)[-150:] if log_tee else []
                }
                try:
                    init_payload = (f"data: {json.dumps(init_data)}" + "\n\n").encode("utf-8")
                    self.wfile.write(init_payload)
                    self.wfile.flush()
                except Exception:
                    with sse_lock:
                        if client_q in sse_clients:
                            sse_clients.remove(client_q)
                    return

                # Event streaming loop
                try:
                    while gateway_instance.running:
                        try:
                            msg = client_q.get(timeout=10.0)
                            self.wfile.write(msg)
                            self.wfile.flush()
                        except queue.Empty:
                            # Periodic keep-alive heartbeat ping
                            self.wfile.write(b": ping\n\n")
                            self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError, Exception):
                    pass
                finally:
                    with sse_lock:
                        if client_q in sse_clients:
                            sse_clients.remove(client_q)

            elif self.path == "/api/status":
                st = gateway_instance._get_current_vault_state()
                payload = {
                    "state": st.get("state", "LOCKED"),
                    "breach": st.get("breach", False),
                    "lockdown": st.get("lockdown", False),
                    "light": st.get("light", 0),
                    "temp": st.get("temp", "N/A"),
                    "hum": st.get("hum", "N/A"),
                    "dist": st.get("dist", "N/A"),
                    "anomaly_score": getattr(gateway_instance, "last_anomaly_score", 0.0),
                    "anomaly": getattr(gateway_instance, "last_anomaly", False),
                    "anomaly_reason": getattr(gateway_instance, "last_anomaly_reason", ""),
                    "last_badge": getattr(gateway_instance, "mock_state", {}).get("last_badge", "Authorized Badge"),
                    "logs": list(log_tee.buffer)[-150:] if log_tee else []
                }
                body = json.dumps(payload).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(body)

            else:
                self.send_response(404)
                self.send_header("Content-Length", "0")
                self.send_header("Connection", "close")
                self.end_headers()

        def do_POST(self):
            if self.path == "/api/command":
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length).decode("utf-8")
                cmd = ""
                try:
                    data = json.loads(body)
                    cmd = data.get("cmd", "").strip()
                except Exception:
                    cmd = body.strip()

                if cmd:
                    print(f"[LOCAL WEB T10] Operator command received: '{cmd}'")
                    gateway_instance.write_serial(cmd)
                    # Push instant status update to all connected browsers
                    st = gateway_instance._get_current_vault_state()
                    broadcast_sse({
                        "type": "status",
                        "data": {
                            "state": st.get("state", "LOCKED"),
                            "breach": st.get("breach", False),
                            "lockdown": st.get("lockdown", False),
                            "light": st.get("light", 0),
                            "temp": st.get("temp", "N/A"),
                            "hum": st.get("hum", "N/A"),
                            "dist": st.get("dist", "N/A"),
                            "anomaly_score": getattr(gateway_instance, "last_anomaly_score", 0.0),
                            "anomaly": getattr(gateway_instance, "last_anomaly", False),
                            "anomaly_reason": getattr(gateway_instance, "last_anomaly_reason", ""),
                            "last_badge": getattr(gateway_instance, "mock_state", {}).get("last_badge", "Authorized Badge")
                        }
                    })
                    resp = {"status": "ok", "cmd": cmd}
                else:
                    resp = {"status": "error", "message": "Empty command"}

                res_body = json.dumps(resp).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(res_body)))
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(res_body)
            else:
                self.send_response(404)
                self.send_header("Content-Length", "0")
                self.send_header("Connection", "close")
                self.end_headers()

    return LocalWebHandler


def start_local_web_server(gateway_instance, port=5000):
    """
    Starts the threaded embedded local web server in a background daemon thread.
    Returns (server_thread, log_tee).
    """
    # 2000 lines history buffer
    log_tee = LogCaptureTee(sys.stdout, maxlen=2000)
    sys.stdout = log_tee

    handler_class = make_handler(gateway_instance, log_tee)
    try:
        # Use ThreadingHTTPServer so every request/stream gets its own fast thread
        server = ThreadingHTTPServer(("0.0.0.0", port), handler_class)
    except OSError as e:
        print(f"[LOCAL WEB T10] Warning: Could not bind to port {port} ({e}). Web UI disabled.")
        return None, log_tee

    def _serve():
        try:
            server.serve_forever()
        except Exception:
            pass

    t = threading.Thread(target=_serve, name="local-web-server", daemon=True)
    t.start()
    print(f"\033[92m[LOCAL WEB T10] Live Operator Console running on http://0.0.0.0:{port} (SSE Stream Active)\033[0m")
    return server, log_tee
