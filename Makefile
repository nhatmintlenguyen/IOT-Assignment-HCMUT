COMPOSE := docker compose
TB      := thingsboard-ce
# Set LOAD_DEMO=true to also create tenant@thingsboard.org and demo devices.
LOAD_DEMO ?= false

.PHONY: help env init up down restart logs ps tunnel tunnel-down reset

help: ## List commands
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | sed 's/:.*##/ -/'

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
