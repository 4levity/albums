POETRY := poetry

.PHONY: build install lint fix test integration-test diagram package clean

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

integration-test: ## Only run CLI tests
	$(POETRY) run pytest tests/test_cli.py

diagram: integration-test ## creates diagram using integration test database
	$(POETRY) run eralchemy -i sqlite:///tests/libraries/cli/albums.db -o docs/database_diagram.png

package:
	$(POETRY) build

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	rm -rf dist
	rm -rf tests/libraries
	rm -rf .pytest_cache
	rm -rf .ruff_cache
	rm docs/database_diagram.png
