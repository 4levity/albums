POETRY := poetry

.PHONY: build install lint format test package

build: install lint test package
	@echo "build complete"

install: ## Install project dependencies using poetry
	$(POETRY) install

lint: ## Lint with ruff
	$(POETRY) run ruff check .
	$(POETRY) run ruff format . --check

format: ## AUtomatically fix formatting
	$(POETRY) run ruff format

test: ## Run tests using pytest
	$(POETRY) run pytest

package:
	$(POETRY) build

