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

.PHONY: help env init up down restart logs ps tunnel tunnel-down reset check-pio install-pio ports build-vault flash-vault monitor-vault build-badge flash-badge monitor-badge run-gateway

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

flash-vault: check-pio ## Flash YoloUNO vault firmware (target: VAULT_PORT or PORT=...)
	@if [ -z "$(VAULT_PORT)" ]; then \
		echo "\033[91m[ERROR] No YoloUNO (/dev/ttyACM*) port found. Specify manually with: make flash-vault PORT=/dev/tty...\033[0m"; \
		exit 1; \
	fi
	@echo "\033[92m[FLASH] Flashing YoloUNO Vault on $(VAULT_PORT)...\033[0m"
	$(PIO) run -d firmware/vault_yolouno -t upload --upload-port $(VAULT_PORT)

monitor-vault: check-pio ## Open serial monitor for YoloUNO (115200 baud)
	@if [ -z "$(VAULT_PORT)" ]; then \
		echo "\033[91m[ERROR] No YoloUNO port found. Specify with: make monitor-vault PORT=/dev/...\033[0m"; \
		exit 1; \
	fi
	$(PIO) device monitor -d firmware/vault_yolouno -p $(VAULT_PORT) -b 115200

build-badge: check-pio ## Build Yolo:Bit badge firmware
	$(PIO) run -d firmware/badge_yolobit

flash-badge: check-pio ## Flash Yolo:Bit badge firmware (target: BADGE_PORT or PORT=...)
	@if [ -z "$(BADGE_PORT)" ]; then \
		echo "\033[91m[ERROR] No Yolo:Bit (/dev/ttyUSB*) port found. Specify manually with: make flash-badge PORT=/dev/tty...\033[0m"; \
		exit 1; \
	fi
	@echo "\033[94m[FLASH] Flashing Yolo:Bit Badge on $(BADGE_PORT)...\033[0m"
	$(PIO) run -d firmware/badge_yolobit -t upload --upload-port $(BADGE_PORT)

monitor-badge: check-pio ## Open serial monitor for Yolo:Bit (115200 baud)
	@if [ -z "$(BADGE_PORT)" ]; then \
		echo "\033[91m[ERROR] No Yolo:Bit port found. Specify with: make monitor-badge PORT=/dev/...\033[0m"; \
		exit 1; \
	fi
	$(PIO) device monitor -d firmware/badge_yolobit -p $(BADGE_PORT) -b 115200

run-gateway: ## Start Python Gateway connected to ThingsBoard & YoloUNO
	gateway/.venv/bin/python gateway/gateway.py --host localhost --port 1883 --token 6EzRR6gcTvnOcgVF53hP

setup-rpi-service: ## Install and enable systemd auto-update service on Raspberry Pi
	@echo "[INFO] Installing systemd service on Raspberry Pi..."
	sed "s|%h|$$HOME|g" scripts/smart-safe-gateway.service | sudo tee /etc/systemd/system/smart-safe-gateway.service >/dev/null
	sudo systemctl daemon-reload
	sudo systemctl enable --now smart-safe-gateway.service
	@echo "\033[92m[SUCCESS] smart-safe-gateway.service installed and started!\033[0m"
	@echo "Check status with: sudo systemctl status smart-safe-gateway.service"

env: ## Create .env from .env.example if missing
	@test -f .env || (cp .env.example .env && echo ".env created")

init: env ## Initialize DB schema (first run ONLY), then start
	$(COMPOSE) run --rm -e INSTALL_TB=true -e LOAD_DEMO=$(LOAD_DEMO) $(TB)
	$(COMPOSE) up -d postgres $(TB)

up: env ## Start ThingsBoard
	$(COMPOSE) up -d postgres $(TB)

down: ## Stop everything (data is kept)
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
