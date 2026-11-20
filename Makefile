COMPOSE := docker compose
TB      := thingsboard-ce
# Set LOAD_DEMO=true to also create tenant@thingsboard.org and demo devices.
LOAD_DEMO ?= false

.PHONY: help env init up down restart logs ps tunnel tunnel-down reset build-vault flash-vault monitor-vault build-badge flash-badge monitor-badge run-gateway

help: ## List commands
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | sed 's/:.*##/ -/'

build-vault: ## Build YoloUNO vault firmware
	pio run -d firmware/vault_yolouno

flash-vault: ## Flash YoloUNO vault firmware (auto-detects port)
	pio run -d firmware/vault_yolouno -t upload

monitor-vault: ## Open serial monitor for YoloUNO (115200 baud)
	pio device monitor -d firmware/vault_yolouno -b 115200

build-badge: ## Build Yolo:Bit badge firmware
	pio run -d firmware/badge_yolobit

flash-badge: ## Flash Yolo:Bit badge firmware (auto-detects port)
	pio run -d firmware/badge_yolobit -t upload

monitor-badge: ## Open serial monitor for Yolo:Bit (115200 baud)
	pio device monitor -d firmware/badge_yolobit -b 115200

run-gateway: ## Start Python Gateway connected to ThingsBoard & YoloUNO
	gateway/.venv/bin/python gateway/gateway.py --host localhost --port 1883 --token 6EzRR6gcTvnOcgVF53hP

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
