POETRY := poetry

.PHONY: install shell test lint run help

build-all: install lint test build
	@echo "build complete"

build:
	$(POETRY) build

help: ## Display this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: ## Install project dependencies using poetry
	$(POETRY) install

shell: ## Activate the project's virtual environment shell
	$(POETRY) shell

test: ## Run tests using pytest
	$(POETRY) run pytest

lint: ## Run linting checks (e.g., with flake8 or ruff)
	$(POETRY) run ruff check .
	$(POETRY) run ruff format . --check

