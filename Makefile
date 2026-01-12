POETRY := poetry

.PHONY: build install lint fix test package

build: install lint test package
	@echo "build complete"

install: ## Install project dependencies using poetry
	$(POETRY) install

lint: ## Lint with ruff
	$(POETRY) run ruff check .
	$(POETRY) run ruff format . --check

fix: ## Automatically fix lint/format
	$(POETRY) run ruff format
	$(POETRY) run ruff check . --fix

test: ## Run tests using pytest
	$(POETRY) run pytest

package:
	$(POETRY) build

