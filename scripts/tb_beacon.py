#!/usr/bin/env python3
"""
Smart Safe Guardian - ThingsBoard LAN Beacon Broadcaster
Broadcasts UDP discovery beacons on the local network so that the Raspberry Pi Zero 2W
(or any other gateway instance) can automatically discover the ThingsBoard server IP
without requiring manual network configuration.
"""

import argparse
import atexit
import json
import os
import re
import signal
import socket
import subprocess
import sys
import time

def load_dotenv_fallback():
    """Loads environment variables from .env if present in root or search paths."""
    search_dirs = [
        os.getcwd(),
        os.path.dirname(os.path.abspath(__file__)),
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ]
    seen_files = set()
    for d in search_dirs:
        env_file = os.path.abspath(os.path.join(d, ".env"))
        if env_file in seen_files or not os.path.isfile(env_file):
            continue
        seen_files.add(env_file)
        try:
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip("'\"")
                    if k and k not in os.environ:
                        os.environ[k] = v
        except Exception:
            pass

load_dotenv_fallback()


def get_local_ip():
    """Returns the primary non-loopback LAN IP address of this machine."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Does not send real packets; triggers OS routing table lookup
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception:
        try:
            ip = socket.gethostbyname(socket.gethostname())
        except Exception:
            ip = "127.0.0.1"
    finally:
        s.close()
    return ip


def get_broadcast_addresses():
    """Finds all active subnet broadcast addresses on this machine."""
    broadcasts = set()
    broadcasts.add('<broadcast>')
    broadcasts.add('255.255.255.255')

    # Query Linux `ip addr`
    try:
        out = subprocess.check_output(['ip', '-o', '-4', 'addr', 'show'], text=True, stderr=subprocess.DEVNULL)
        for line in out.splitlines():
            m = re.search(r'brd\s+([0-9.]+)', line)
            if m:
                broadcasts.add(m.group(1))
    except Exception:
        pass

    # Query macOS / BSD / legacy Linux `ifconfig`
    try:
        out = subprocess.check_output(['ifconfig'], text=True, stderr=subprocess.DEVNULL)
        for line in out.splitlines():
            m = re.search(r'broadcast\s+([0-9.]+)', line)
            if m:
                broadcasts.add(m.group(1))
    except Exception:
        pass

    return sorted(list(broadcasts))


def daemonize():
    """Double-fork daemonization to detach cleanly from terminal and process group."""
    try:
        pid = os.fork()
        if pid > 0:
            sys.exit(0)
    except OSError as err:
        sys.stderr.write(f"Fork #1 failed: {err}\n")
        sys.exit(1)

    os.setsid()
    os.umask(0)

    try:
        pid = os.fork()
        if pid > 0:
            sys.exit(0)
    except OSError as err:
        sys.stderr.write(f"Fork #2 failed: {err}\n")
        sys.exit(1)

    sys.stdout.flush()
    sys.stderr.flush()
    si = open(os.devnull, 'r')
    so = open(os.devnull, 'a+')
    se = open(os.devnull, 'a+')
    os.dup2(si.fileno(), sys.stdin.fileno())
    os.dup2(so.fileno(), sys.stdout.fileno())
    os.dup2(se.fileno(), sys.stderr.fileno())


def main():
    parser = argparse.ArgumentParser(description="Smart Safe Guardian - ThingsBoard UDP Beacon Broadcaster")
    parser.add_argument("--port", type=int, default=int(os.getenv("BEACON_PORT", "50051")),
                        help="UDP Broadcast destination port (default: 50051)")
    parser.add_argument("--interval", type=float, default=float(os.getenv("BEACON_INTERVAL", "2.0")),
                        help="Broadcast interval in seconds (default: 2.0)")
    parser.add_argument("--mqtt-port", type=int, default=int(os.getenv("THINGSBOARD_PORT", "1883")),
                        help="ThingsBoard MQTT Broker port (default: 1883)")
    parser.add_argument("--http-port", type=int, default=8080,
                        help="ThingsBoard Web UI port (default: 8080)")
    parser.add_argument("--token", default=os.getenv("THINGSBOARD_TOKEN", "6EzRR6gcTvnOcgVF53hP"),
                        help="ThingsBoard Device Access Token (default: 6EzRR6gcTvnOcgVF53hP)")
    parser.add_argument("--gateway-token", default=os.getenv("GATEWAY_TOKEN", "GATEWAY_SECRET_TOKEN"),
                        help="ThingsBoard Gateway Access Token (default: GATEWAY_SECRET_TOKEN)")
    parser.add_argument("--pid-file", default=None,
                        help="Path to write PID file for process management")
    parser.add_argument("--daemon", action="store_true",
                        help="Run as background daemon (double-fork)")
    parser.add_argument("--silent", action="store_true",
                        help="Suppress periodic log output (for daemon mode)")

    args = parser.parse_args()

    # Daemonize if requested
    if args.daemon:
        daemonize()

    # PID file handling (writes daemonized PID)
    if args.pid_file:
        try:
            with open(args.pid_file, "w") as f:
                f.write(str(os.getpid()))
            atexit.register(lambda: os.path.exists(args.pid_file) and os.remove(args.pid_file))
        except Exception as e:
            print(f"[WARN] Failed to write PID file: {e}")

    local_ip = get_local_ip()
    broadcast_addrs = get_broadcast_addresses()

    if not args.silent:
        print("===================================================================")
        print("   Smart Safe Guardian - ThingsBoard LAN Beacon Broadcaster       ")
        print("===================================================================")
        print(f"  Service          : SMART_SAFE_THINGSBOARD")
        print(f"  Server LAN IP    : {local_ip}")
        print(f"  MQTT Port        : {args.mqtt_port}")
        print(f"  HTTP Dashboard   : http://{local_ip}:{args.http_port}")
        print(f"  Device Token     : {args.token}")
        print(f"  Broadcast Addrs  : {broadcast_addrs}")
        print(f"  UDP Beacon Port  : {args.port}")
        print(f"  Interval         : Every {args.interval}s")
        print("===================================================================")
        print("[BEACON] Broadcasting presence... (Press Ctrl+C to stop)\n")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    payload = {
        "service": "SMART_SAFE_THINGSBOARD",
        "version": "1.0",
        "name": "ThingsBoard-CE",
        "ip": local_ip,
        "mqtt_port": args.mqtt_port,
        "http_port": args.http_port,
        "device_token": args.token,
        "gateway_token": args.gateway_token
    }

    # Graceful shutdown handler
    running = True

    def sig_handler(sig, frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    seq = 0
    try:
        while running:
            seq += 1
            payload["timestamp"] = int(time.time())
            payload["seq"] = seq
            data_bytes = json.dumps(payload).encode("utf-8")

            for b_addr in broadcast_addrs:
                try:
                    sock.sendto(data_bytes, (b_addr, args.port))
                except Exception:
                    pass

            if not args.silent and (seq == 1 or seq % 10 == 0):
                print(f"[BEACON] Broadcast #{seq} sent to {len(broadcast_addrs)} addrs ({time.strftime('%H:%M:%S')}) -> IP {local_ip}:{args.mqtt_port}")

            time.sleep(args.interval)
    finally:
        sock.close()
        if not args.silent:
            print("\n[BEACON] ThingsBoard beacon stopped.")


if __name__ == "__main__":
    main()
