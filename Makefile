POETRY := poetry
DOCKER := docker

.PHONY: build install lint lint-markdown spelling fix test integration-test preview docs package clean

build: install lint test
	@echo "build complete"

install: ## Install project dependencies
	$(POETRY) install

lint-markdown: ## Lint markdown
	$(POETRY) run pymarkdown --strict-config scan *.md **/*.md

lint: lint-markdown ## Lint and static analysis
	$(POETRY) run ruff check .
	$(POETRY) run ruff format . --check
	$(POETRY) run pyright
	$(POETRY) run pyright -p tests

spelling: ## Run spell check
	$(DOCKER) run -it -v .:/workdir ghcr.io/streetsidesoftware/cspell:latest lint --gitignore * .github

fix: install ## Automatically fix lint/format
	$(POETRY) run ruff format
	$(POETRY) run ruff check . --fix

test-no-warnings: install ## Run all tests without coverage, fail on any warnings
	$(POETRY) run pytest -v --max-warnings=0

test: test-no-warnings install ## Run all tests with coverage (depends on test-no-warnings)
	# Running tests twice: once without coverage to catch new warnings,
	# and once with coverage for coverage reports (warnings ignored during coverage run)
	$(POETRY) run pytest --cov=src/albums --cov-report=html
	@echo Coverage report in file://$(CURDIR)/htmlcov/index.html

sample/albums.db: src/albums/database/schema.py
	@rm -rf sample/albums.db
	@mkdir -p sample
	$(POETRY) run python src/albums/database/connection.py sample/albums.db

docs/database_diagram.png: sample/albums.db
	$(POETRY) run eralchemy -i sqlite:///sample/albums.db -o docs/database_diagram.png
	@ls -l docs/database_diagram.png

preview: docs/database_diagram.png ## Preview docs (does not automatically install)
	$(POETRY) run zensical serve

docs: install lint-markdown docs/database_diagram.png ## Build docs
	$(POETRY) run zensical build --clean
	@echo injecting version `poetry dynamic-versioning show`
	@sed -i s/%%version_placeholder%%/`poetry dynamic-versioning show`/g site/index.html

package: ## Create distribution
	$(POETRY) build

clean: ## Remove build and test files
	find . -type d -name "__pycache__" -exec rm -rf {} +
	rm -rf dist
	rm -rf tests/fixtures/libraries
	rm -rf docs/database_diagram.png
	rm -rf site
	rm -rf docs/.cache
	rm -rf htmlcov
	rm -rf .coverage
	rm -rf .pytest_cache
	rm -rf .ruff_cache
	rm -rf sample/albums.db
