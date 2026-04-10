# Установка путей по умолчанию
CURRENT_BRANCH := $(shell git rev-parse --abbrev-ref HEAD 2>/dev/null)
BRANCH_FILE := .deploy-branch
BRANCH_FROM_FILE := $(if $(wildcard $(BRANCH_FILE)),$(shell cat $(BRANCH_FILE)),)
DEFAULT_BRANCH = feat/upgrade-openai-4.1-mini
DEPLOY_BRANCH ?= $(if $(BRANCH_FROM_FILE),$(BRANCH_FROM_FILE),$(CURRENT_BRANCH))

# Цель по умолчанию
.PHONY: all
all: update

# Обновление приложения с сервера
.PHONY: update
update:
	@set -e; \
	BRANCH="$(DEPLOY_BRANCH)"; \
	if [ -z "$$BRANCH" ] || [ "$$BRANCH" = "HEAD" ]; then \
		BRANCH="$(DEFAULT_BRANCH)"; \
	fi; \
	echo "Updating deployment branch: $$BRANCH"; \
	git fetch origin --prune --tags; \
	git checkout -f "$$BRANCH"; \
	git reset --hard "origin/$$BRANCH"; \
	echo "Syncing dependencies with uv..."; \
	uv sync --extra webapp --extra ai; \
	echo "Restarting services..."; \
	sudo /bin/systemctl restart tg_bot.service webapp.service; \
	echo "Update complete!"

# Установка зависимостей для разработки
.PHONY: dev
dev:
	uv sync --all-extras

# Запуск тестов
.PHONY: test
test:
	uv run pytest tests/

# Справка
.PHONY: help
help:
	@echo "Доступные цели:"
	@echo "  all      - Цель по умолчанию, запускает 'update'"
	@echo "  update   - Обновление приложения (git pull, uv sync, перезапуск сервисов)"
	@echo "  dev      - Установка всех зависимостей для разработки"
	@echo "  test     - Запуск тестов"
	@echo "  help     - Показать эту справку"
