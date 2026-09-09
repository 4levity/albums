UV := uv
# cSpell, Prettier and Pyright are installed on demand by npx (cached in
# ~/.npm, no npm project files needed). Pinned here so all developers and CI
# use the same version - update with `npm view cspell version` /
# `npm view prettier version` / `npm view pyright version` (requires Node.js
# 22.18+). Pyright runs via `uv run` so VIRTUAL_ENV points at the project
# virtualenv, which pyright needs to resolve the project's packages.
CSPELL := npx --yes cspell@10.3.0
PRETTIER := npx --yes prettier@3.9.6
PYRIGHT := $(UV) run npx --yes pyright@1.1.411

.PHONY: build install static lint lint-markdown typecheck spelling fix test preview docs package pyinstaller clean

build: install static test
	@echo "build complete"

# --locked: fail if uv.lock is out of date with pyproject.toml (run `uv lock` to update it)
install: ## Install project dependencies
	$(UV) sync --locked

# Umbrella for all static checks (no code execution) - the gate for builds, CI
# and the commit hook. Subtargets run in order, cheapest first.
static: lint lint-markdown spelling typecheck ## Run all static checks (lint, markdown, spelling, types)

lint: ## Lint and format-check Python (ruff)
	$(UV) run ruff check .
	$(UV) run ruff format . --check

# glob is quoted so pymarkdown expands it (sh has no globstar)
lint-markdown: ## Lint markdown
	$(UV) run pymarkdown --strict-config scan --respect-gitignore '**/*.md'

spelling: ## Run spell check
	$(CSPELL) lint --gitignore * .github

typecheck: ## Type check (pyright: strict for src, looser for tests)
	$(PYRIGHT)
	$(PYRIGHT) -p tests

fix: install ## Automatically fix lint/format
	$(UV) run ruff format
	$(UV) run ruff check . --fix
	# reflow markdown with the same config the IDE uses (.prettierrc)
	$(PRETTIER) --write '**/*.md'

test: install ## Run all tests with coverage, fail on any warnings
	$(UV) run pytest --max-warnings=0 --cov=src/albums --cov-report=html
	@echo Coverage report in file://$(CURDIR)/htmlcov/index.html

# regenerate sample db if schema or schema-creation code changed
SCHEMA_FILES := $(wildcard src/albums/database/migrations/*.sql) \
	src/albums/database/migrations/migrate.py \
	src/albums/database/migrations/__init__.py \
	src/albums/database/connection.py

sample/albums.db: $(SCHEMA_FILES)
	@rm -rf sample/albums.db
	@mkdir -p sample
	$(UV) run python src/albums/database/connection.py sample/albums.db

docs/database_diagram.png: sample/albums.db
	$(UV) run eralchemy -i sqlite:///sample/albums.db -o docs/database_diagram.png
	@ls -l docs/database_diagram.png

# Render the real `albums --help` output to an image (via ansi2image, bundled JetBrains Mono font).
# FORCE_COLOR=1 forces ANSI color (output is piped, not a tty), COLUMNS=100 fixes rich's wrap width,
# and XDG_CONFIG_HOME='~/.config' (Linux) keeps the epilog's default-db path machine independent.
docs/screenshot_help.png: $(wildcard src/albums/cli/*.py)
	@rm -f $@ $@.tmp $@.txt
	@FORCE_COLOR=1 COLUMNS=100 XDG_CONFIG_HOME='~/.config' $(UV) run albums --help > $@.tmp
	@sed 1d $@.tmp > $@.txt
	@$(UV) run ansi2image $@.txt -o $@
	@rm -f $@.tmp $@.txt
	@test -s $@
	@ls -l $@

# Build a standalone executable for this platform in dist/pyinstaller/<platform>/albums/.
# The version is written to src/albums/_version.py first so the executable
# reports the git-derived version (see scripts/version.py). --collect-data bundles
# the package's non-Python files (the database migration SQL). Note: on Windows
# runners, run these same commands directly (no make available).
pyinstaller: install ## Build standalone pyinstaller executable for this platform
	$(UV) run python scripts/version.py write
	platform=$$($(UV) run python -c "import sysconfig; print(sysconfig.get_platform().replace('-', '_'))") && \
	$(UV) run pyinstaller src/albums/__main__.py --onedir --name albums --noconfirm --clean \
	--collect-data albums \
	--workpath build/$$platform --distpath dist/pyinstaller/$$platform \
	--specpath build/$$platform/.specs --contents-directory _albums_internal && \
	ls -l dist/pyinstaller/$$platform/albums

package: ## Create sdist and wheel in dist/
	$(UV) build

docs: install lint-markdown docs/database_diagram.png docs/screenshot_help.png ## Build docs
	$(UV) run zensical build --clean
	# portable version of sed -i (GNU-only): write to tmp file and move into place
	@version=$$($(UV) run python scripts/version.py) && \
	echo "injecting version $$version" && \
	sed "s/%%version_placeholder%%/$$version/g" site/index.html > site/index.html.tmp && \
	mv site/index.html.tmp site/index.html

preview: docs/database_diagram.png docs/screenshot_help.png ## Preview docs (does not automatically install)
	$(UV) run zensical serve

clean: ## Remove build and test files
	find . -type d -name "__pycache__" -exec rm -rf {} +
	rm -rf dist
	rm -rf build
	rm -rf src/albums/_version.py
	rm -rf tests/fixtures/libraries
	rm -rf docs/database_diagram.png docs/screenshot_help.png docs/screenshot_help.png.tmp docs/screenshot_help.png.txt
	rm -rf site
	rm -rf docs/.cache
	rm -rf htmlcov
	rm -rf .coverage
	rm -rf .pytest_cache
	rm -rf .ruff_cache
	rm -rf sample/albums.db
