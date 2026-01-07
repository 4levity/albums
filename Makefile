POETRY := poetry

.PHONY: build install lint test package

build: install lint test package
	@echo "build complete"

install: ## Install project dependencies using poetry
	$(POETRY) install

lint: ## Run linting checks (e.g., with flake8 or ruff)
	$(POETRY) run ruff check .
	$(POETRY) run ruff format . --check

test: ## Run tests using pytest
	$(POETRY) run pytest

package:
	$(POETRY) build

