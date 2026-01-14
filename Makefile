POETRY := poetry

.PHONY: build install lint fix test integration-test diagram package clean

build: install lint test package
	@echo "build complete"

install: ## Install project dependencies
	$(POETRY) install

lint: ## Lint with ruff
	$(POETRY) run ruff check .
	$(POETRY) run ruff format . --check

fix: ## Automatically fix lint/format
	$(POETRY) run ruff format
	$(POETRY) run ruff check . --fix

test: ## Run all tests
	$(POETRY) run pytest

integration-test: ## Run CLI tests only
	$(POETRY) run pytest tests/test_cli.py

diagram: integration-test ## Create database diagram
	$(POETRY) run eralchemy -i sqlite:///tests/libraries/cli/albums.db -o docs/database_diagram.png

package: ## Create distribution
	$(POETRY) build

clean: ## Remove build and test files
	find . -type d -name "__pycache__" -exec rm -rf {} +
	rm -rf dist
	rm -rf tests/libraries
	rm -rf .pytest_cache
	rm -rf .ruff_cache
	rm docs/database_diagram.png
