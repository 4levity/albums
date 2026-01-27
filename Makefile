POETRY := poetry

.PHONY: build install lint fix test integration-test diagram preview docs package clean

build: install lint test package
	@echo "build complete"

install: ## Install project dependencies
	$(POETRY) install

lint: ## Lint and static analysis
	$(POETRY) run ruff check .
	$(POETRY) run ruff format . --check
	$(POETRY) run pyright
	$(POETRY) run pyright -p tests
	$(POETRY) run pymarkdown --strict-config scan *.md **/*.md

fix: ## Automatically fix lint/format
	$(POETRY) run ruff format
	$(POETRY) run ruff check . --fix

test: ## Run all tests
	$(POETRY) run pytest --cov=src/albums --cov-report=html
	@echo Coverage report in file://$(CURDIR)/htmlcov/index.html

build/albums.db: src/albums/database/schema.py
	@mkdir -p build
	$(POETRY) run python src/albums/database/connection.py build/albums.db

docs/database_diagram.png: build/albums.db
	$(POETRY) run eralchemy -i sqlite:///build/albums.db --title "Albums Database Schema" -o docs/database_diagram.png
	@ls -l docs/database_diagram.png

diagram: docs/database_diagram.png ## Generate database diagram

preview: diagram ## Preview docs
	$(POETRY) run zensical serve

docs: diagram ## Build docs
	$(POETRY) run zensical build --clean

package: ## Create distribution
	$(POETRY) build

clean: ## Remove build and test files
	find . -type d -name "__pycache__" -exec rm -rf {} +
	rm -rf build
	rm -rf dist
	rm -rf tests/fixtures/libraries
	rm -rf docs/database_diagram.png
	rm -rf site
	rm -rf docs/.cache
	rm -rf htmlcov
	rm -rf .coverage
	rm -rf .pytest_cache
	rm -rf .ruff_cache
