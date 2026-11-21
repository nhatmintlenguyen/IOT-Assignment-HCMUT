-include .env
export
MAKEFLAGS += --no-print-directory

COMPOSE := docker compose
TB      := thingsboard-ce
# Set LOAD_DEMO=true to also create tenant@thingsboard.org and demo devices.
LOAD_DEMO ?= false

# PlatformIO binary detection
PIO := $(shell which pio 2>/dev/null || which platformio 2>/dev/null || (test -x $(HOME)/.platformio/penv/bin/pio && echo $(HOME)/.platformio/penv/bin/pio) || (test -x $(HOME)/.local/bin/pio && echo $(HOME)/.local/bin/pio))

# Automatic port discovery
DETECTED_VAULT_PORT := $(shell ls /dev/ttyACM* 2>/dev/null | head -n 1)
DETECTED_BADGE_PORT := $(shell ls /dev/ttyUSB* 2>/dev/null | head -n 1)

# Allow manual override via PORT=/dev/...
VAULT_PORT ?= $(if $(PORT),$(PORT),$(DETECTED_VAULT_PORT))
BADGE_PORT ?= $(if $(PORT),$(PORT),$(DETECTED_BADGE_PORT))

# Detect if 'monitor' is requested in the command line (e.g. make flash-vault monitor)
MONITOR_REQUESTED := $(if $(filter monitor,$(MAKECMDGOALS)),1,$(if $(MONITOR),1,0))
MONITOR_TARGET    := $(if $(filter 1,$(MONITOR_REQUESTED)),-t monitor,)

.PHONY: help env init init-all up down restart logs ps tunnel tunnel-down reset check-pio install-pio ports build-vault flash-vault flash-vault-monitor monitor-vault build-badge flash-badge flash-badge-monitor monitor-badge run-gateway setup-rpi-service setup-thingsboard monitor beacon beacon-bg beacon-stop benchmark

help: ## List commands
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | sed 's/:.*##/ -/'

check-pio:
	@if [ -z "$(PIO)" ]; then \
		echo "\033[91m[ERROR] PlatformIO is not installed or not found in PATH!\033[0m"; \
		echo "Run '\033[92mmake install-pio\033[0m' to install it automatically."; \
		exit 1; \
	fi

install-pio: ## Install PlatformIO Core via official installer script
	@echo "[INFO] Installing PlatformIO Core..."
	curl -fsSL -o /tmp/get-platformio.py https://raw.githubusercontent.com/platformio/platformio-core-installer/master/get-platformio.py
	python3 /tmp/get-platformio.py
	mkdir -p $(HOME)/.local/bin
	ln -sf $(HOME)/.platformio/penv/bin/pio $(HOME)/.local/bin/pio
	ln -sf $(HOME)/.platformio/penv/bin/platformio $(HOME)/.local/bin/platformio
	@echo "\033[92m[SUCCESS] PlatformIO Core installed in ~/.local/bin/pio!\033[0m"

ports: ## List connected microcontroller USB ports (identifies YoloUNO vs Yolo:Bit)
	@echo "=== Connected Microcontroller Ports ==="
	@if [ -d /dev/serial/by-id ] && [ "$$(ls -A /dev/serial/by-id 2>/dev/null)" ]; then \
		ls -l /dev/serial/by-id/ | grep -v '^total' | while read -r line; do \
			dev=$$(echo "$$line" | awk '{print $$NF}' | sed 's|../../||'); \
			id=$$(echo "$$line" | awk '{print $$(NF-2)}'); \
			if echo "$$id" | grep -qiE "espressif|jtag|acm"; then \
				printf "  -> /dev/%-10s [\033[92mYoloUNO Vault Controller\033[0m (ESP32-S3 CDC)]\n" "$$dev"; \
			elif echo "$$id" | grep -qiE "1a86|ch34|cp21|usb_serial"; then \
				printf "  -> /dev/%-10s [\033[94mYolo:Bit Wearable Badge\033[0m (CH340/CP2102)]\n" "$$dev"; \
			else \
				printf "  -> /dev/%-10s [Unknown Serial Device: %s]\n" "$$dev" "$$id"; \
			fi; \
		done; \
	else \
		echo "Scanning raw serial devices:"; \
		ls -l /dev/ttyACM* /dev/ttyUSB* 2>/dev/null || echo "No serial devices detected."; \
	fi
	@echo ""
	@echo "Target for flash-vault : $(if $(VAULT_PORT),\033[92m$(VAULT_PORT)\033[0m,\033[91mNOT DETECTED\033[0m) (override with PORT=/dev/...)"
	@echo "Target for flash-badge : $(if $(BADGE_PORT),\033[94m$(BADGE_PORT)\033[0m,\033[91mNOT DETECTED\033[0m) (override with PORT=/dev/...)"

build-vault: check-pio ## Build YoloUNO vault firmware
	$(PIO) run -d firmware/vault_yolouno

flash-vault: check-pio ## Flash YoloUNO (add 'monitor' to stream serial logs: make flash-vault monitor)
	@if [ -z "$(VAULT_PORT)" ]; then \
		echo "\033[91m[ERROR] No YoloUNO (/dev/ttyACM*) port found. Specify manually with: make flash-vault PORT=/dev/tty...\033[0m"; \
		exit 1; \
	fi
	@echo "\033[92m[FLASH] Flashing YoloUNO Vault on $(VAULT_PORT)$(if $(MONITOR_TARGET), + opening Serial Monitor,)...\033[0m"
	$(PIO) run -d firmware/vault_yolouno -t upload $(MONITOR_TARGET) --upload-port $(VAULT_PORT) $(if $(MONITOR_TARGET),--monitor-port $(VAULT_PORT),)

flash-vault-monitor: ## Flash YoloUNO and open serial monitor
	@$(MAKE) flash-vault monitor

monitor-vault: check-pio ## Open serial monitor for YoloUNO (115200 baud)
	@if [ -z "$(VAULT_PORT)" ]; then \
		echo "\033[91m[ERROR] No YoloUNO port found. Specify with: make monitor-vault PORT=/dev/...\033[0m"; \
		exit 1; \
	fi
	$(PIO) device monitor -d firmware/vault_yolouno -p $(VAULT_PORT) -b 115200

build-badge: check-pio ## Build Yolo:Bit badge firmware
	$(PIO) run -d firmware/badge_yolobit

flash-badge: check-pio ## Flash Yolo:Bit (add 'monitor' to stream serial logs: make flash-badge monitor)
	@if [ -z "$(BADGE_PORT)" ]; then \
		echo "\033[91m[ERROR] No Yolo:Bit (/dev/ttyUSB*) port found. Specify manually with: make flash-badge PORT=/dev/tty...\033[0m"; \
		exit 1; \
	fi
	@echo "\033[94m[FLASH] Flashing Yolo:Bit Badge on $(BADGE_PORT)$(if $(MONITOR_TARGET), + opening Serial Monitor,)...\033[0m"
	$(PIO) run -d firmware/badge_yolobit -t upload $(MONITOR_TARGET) --upload-port $(BADGE_PORT) $(if $(MONITOR_TARGET),--monitor-port $(BADGE_PORT),)

flash-badge-monitor: ## Flash Yolo:Bit and open serial monitor
	@$(MAKE) flash-badge monitor

monitor-badge: check-pio ## Open serial monitor for Yolo:Bit (115200 baud)
	@if [ -z "$(BADGE_PORT)" ]; then \
		echo "\033[91m[ERROR] No Yolo:Bit port found. Specify with: make monitor-badge PORT=/dev/...\033[0m"; \
		exit 1; \
	fi
	$(PIO) device monitor -d firmware/badge_yolobit -p $(BADGE_PORT) -b 115200

reboot-vault: ## Send software reboot command to YoloUNO over serial
	@if [ -z "$(VAULT_PORT)" ]; then \
		echo "\033[91m[ERROR] No YoloUNO port detected.\033[0m"; exit 1; \
	fi
	@gateway/.venv/bin/python -c "import serial, time; s = serial.Serial('$(VAULT_PORT)', 115200, timeout=1); time.sleep(0.1); s.write(b'reboot\n'); s.close(); print('[OK] YoloUNO reboot command sent!')"

reboot-badge: ## Send software reboot command to Yolo:Bit over serial
	@if [ -z "$(BADGE_PORT)" ]; then \
		echo "\033[91m[ERROR] No Yolo:Bit port detected.\033[0m"; exit 1; \
	fi
	@gateway/.venv/bin/python -c "import serial, time; s = serial.Serial('$(BADGE_PORT)', 115200, timeout=1); time.sleep(0.1); s.write(b'reboot\n'); s.close(); print('[OK] Yolo:Bit reboot command sent!')"

monitor: ## Auxiliary target to enable 'make flash-* monitor' chaining
	@:

gateway/.venv/bin/python:
	@echo "[INFO] Creating Python virtual environment in gateway/.venv..."
	python3 -m venv gateway/.venv
	gateway/.venv/bin/pip install --upgrade pip
	gateway/.venv/bin/pip install -r gateway/requirements.txt

HOST ?= $(if $(THINGSBOARD_HOST),$(THINGSBOARD_HOST),auto)
PORT ?= $(if $(THINGSBOARD_MQTT_PORT),$(THINGSBOARD_MQTT_PORT),1883)
TOKEN ?= $(THINGSBOARD_TOKEN)
ARGS ?=

run-gateway: gateway/.venv/bin/python ## Start Python Gateway (auto-discovers ThingsBoard, reads .env)
	gateway/.venv/bin/python gateway/gateway.py --host $(HOST) --port $(PORT) $(if $(TOKEN),--token $(TOKEN),) $(ARGS)

benchmark: gateway/.venv/bin/python ## Run automated system performance, AI accuracy, and latency benchmarks (Chapter 4)
	gateway/.venv/bin/python scripts/system_benchmark.py

beacon: ## Run ThingsBoard UDP discovery beacon in foreground
	python3 scripts/tb_beacon.py

beacon-bg: ## Run ThingsBoard UDP discovery beacon in background
	@if [ -f scripts/.tb_beacon.pid ] && kill -0 $$(cat scripts/.tb_beacon.pid) 2>/dev/null; then \
		echo "[INFO] ThingsBoard beacon is already running (PID: $$(cat scripts/.tb_beacon.pid))."; \
	else \
		python3 scripts/tb_beacon.py --daemon --silent --pid-file scripts/.tb_beacon.pid; \
		sleep 0.2; \
		if [ -f scripts/.tb_beacon.pid ]; then \
			echo "\033[92m[OK] ThingsBoard LAN discovery beacon started in background (PID: $$(cat scripts/.tb_beacon.pid))!\033[0m"; \
		else \
			echo "\033[93m[WARN] Beacon failed to start.\033[0m"; \
		fi; \
	fi

beacon-stop: ## Stop background ThingsBoard UDP discovery beacon
	@if [ -f scripts/.tb_beacon.pid ]; then \
		kill $$(cat scripts/.tb_beacon.pid) 2>/dev/null || true; \
		rm -f scripts/.tb_beacon.pid; \
		echo "[OK] ThingsBoard beacon stopped."; \
	else \
		pkill -f "python3.*tb_beacon.py" 2>/dev/null || true; \
		echo "[OK] No active beacon found."; \
	fi

setup-rpi-service: ## Install and enable systemd gateway and 5-min auto-update timer on Raspberry Pi
	@echo "[INFO] Installing systemd gateway service and auto-update timer..."
	sed "s|%h|$$HOME|g" scripts/smart-safe-gateway.service | sudo tee /etc/systemd/system/smart-safe-gateway.service >/dev/null
	sed "s|%h|$$HOME|g" scripts/smart-safe-autoupdate.service | sudo tee /etc/systemd/system/smart-safe-autoupdate.service >/dev/null
	sudo cp scripts/smart-safe-autoupdate.timer /etc/systemd/system/smart-safe-autoupdate.timer
	sudo systemctl daemon-reload
	sudo systemctl enable --now smart-safe-gateway.service
	sudo systemctl enable --now smart-safe-autoupdate.timer
	@echo "\033[92m[SUCCESS] Gateway and 5-min auto-update timer successfully installed!\033[0m"
	@echo "Check gateway status : sudo systemctl status smart-safe-gateway.service"
	@echo "Check timer status   : sudo systemctl list-timers | grep smart-safe"

env: ## Create .env from .env.example if missing
	@test -f .env || (cp .env.example .env && echo ".env created")

init: env ## Initialize DB schema (first run ONLY), then start
	$(COMPOSE) run --rm -e INSTALL_TB=true -e LOAD_DEMO=$(LOAD_DEMO) $(TB)
	$(COMPOSE) up -d postgres $(TB)
	@$(MAKE) beacon-bg

up: env ## Start ThingsBoard & discovery beacon
	$(COMPOSE) up -d postgres $(TB)
	@$(MAKE) beacon-bg

setup-thingsboard: up ## Start ThingsBoard Docker containers, wait for API readiness, auto-provision in 1 click, and start beacon
	@echo "[INFO] Waiting for ThingsBoard container API to become ready (port 8080)..."
	@until curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/api/auth/login | grep -qE "401|400|200"; do \
		printf "."; \
		sleep 3; \
	done
	@echo ""
	@echo "\033[92m[INFO] ThingsBoard API is UP! Running automated provisioning...\033[0m"
	gateway/.venv/bin/python scripts/setup_thingsboard.py

init-all: init ## First-time full setup: Initialize PostgreSQL schema, start ThingsBoard, auto-provision, and start beacon
	@echo "[INFO] Waiting for ThingsBoard container API to become ready (port 8080)..."
	@until curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/api/auth/login | grep -qE "401|400|200"; do \
		printf "."; \
		sleep 3; \
	done
	@echo ""
	@echo "\033[92m[INFO] ThingsBoard API is UP! Running automated provisioning...\033[0m"
	gateway/.venv/bin/python scripts/setup_thingsboard.py
	@$(MAKE) beacon-bg

down: beacon-stop ## Stop everything (data is kept) and stop beacon
	$(COMPOSE) --profile tunnel down

restart: ## Restart ThingsBoard
	$(COMPOSE) restart $(TB)

logs: ## Tail ThingsBoard logs
	$(COMPOSE) logs -f --tail=100 $(TB)

ps: ## Container status
	$(COMPOSE) --profile tunnel ps

tunnel: env ## Start Cloudflare Tunnel (needs token in .env)
	@grep -qE '^CLOUDFLARE_TUNNEL_TOKEN=.+' .env || (echo "CLOUDFLARE_TUNNEL_TOKEN is missing in .env"; exit 1)
	$(COMPOSE) --profile tunnel up -d cloudflared

tunnel-down: ## Stop the tunnel
	$(COMPOSE) --profile tunnel stop cloudflared

reset: ## DELETE ALL ThingsBoard data (asks for confirmation)
	@printf "Delete all data? Type yes to continue: " && read a && [ "$$a" = yes ]
	$(COMPOSE) --profile tunnel down -v
