POETRY := poetry
DOCKER := docker

.PHONY: build install lint lint-markdown spelling fix test preview docs package clean

build: install lint test
	@echo "build complete"

install: ## Install project dependencies
	$(POETRY) install

# glob is quoted so pymarkdown expands it (sh has no globstar)
lint-markdown: ## Lint markdown
	$(POETRY) run pymarkdown --strict-config scan --respect-gitignore '**/*.md'

lint: lint-markdown ## Lint and static analysis
	$(POETRY) run ruff check .
	$(POETRY) run ruff format . --check
	$(POETRY) run pyright
	$(POETRY) run pyright -p tests

spelling: ## Run spell check
	$(DOCKER) run -i -v .:/workdir ghcr.io/streetsidesoftware/cspell:latest lint --gitignore * .github

fix: install ## Automatically fix lint/format
	$(POETRY) run ruff format
	$(POETRY) run ruff check . --fix

test: install ## Run all tests with coverage, fail on any warnings
	$(POETRY) run pytest --max-warnings=0 --cov=src/albums --cov-report=html
	@echo Coverage report in file://$(CURDIR)/htmlcov/index.html

# regenerate sample db if schema or schema-creation code changed
SCHEMA_FILES := $(wildcard src/albums/database/migrations/*.sql) \
	src/albums/database/migrations/migrate.py \
	src/albums/database/migrations/__init__.py \
	src/albums/database/connection.py

sample/albums.db: $(SCHEMA_FILES)
	@rm -rf sample/albums.db
	@mkdir -p sample
	$(POETRY) run python src/albums/database/connection.py sample/albums.db

docs/database_diagram.png: sample/albums.db
	$(POETRY) run eralchemy -i sqlite:///sample/albums.db -o docs/database_diagram.png
	@ls -l docs/database_diagram.png

# Render the real `albums --help` output to an image (via ansi2image, bundled JetBrains Mono font).
# FORCE_COLOR=1 forces ANSI color (output is piped, not a tty), COLUMNS=100 fixes rich's wrap width,
# and XDG_CONFIG_HOME='~/.config' (Linux) keeps the epilog's default-db path machine independent.
docs/screenshot_help.png: $(wildcard src/albums/cli/*.py)
	@rm -f $@ $@.tmp $@.txt
	@FORCE_COLOR=1 COLUMNS=100 XDG_CONFIG_HOME='~/.config' $(POETRY) run albums --help > $@.tmp
	@sed 1d $@.tmp > $@.txt
	@$(POETRY) run ansi2image $@.txt -o $@
	@rm -f $@.tmp $@.txt
	@test -s $@
	@ls -l $@

preview: docs/database_diagram.png docs/screenshot_help.png ## Preview docs (does not automatically install)
	$(POETRY) run zensical serve

docs: install lint-markdown docs/database_diagram.png docs/screenshot_help.png ## Build docs
	$(POETRY) run zensical build --clean
	# portable version of sed -i (GNU-only): write to tmp file and move into place
	@version=$$($(POETRY) dynamic-versioning show) && \
	echo "injecting version $$version" && \
	sed "s/%%version_placeholder%%/$$version/g" site/index.html > site/index.html.tmp && \
	mv site/index.html.tmp site/index.html

package: ## Create distribution
	$(POETRY) build

clean: ## Remove build and test files
	find . -type d -name "__pycache__" -exec rm -rf {} +
	rm -rf dist
	rm -rf tests/fixtures/libraries
	rm -rf docs/database_diagram.png docs/screenshot_help.png docs/screenshot_help.png.tmp docs/screenshot_help.png.txt
	rm -rf site
	rm -rf docs/.cache
	rm -rf htmlcov
	rm -rf .coverage
	rm -rf .pytest_cache
	rm -rf .ruff_cache
	rm -rf sample/albums.db
