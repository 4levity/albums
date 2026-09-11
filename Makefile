UV := uv
# Lint tools are Node.js dev dependencies, defined in package.json and
# installed by `make install-js` (requires Node.js 22.18+).
CSPELL := npx --no-install cspell
PRETTIER := npx --no-install prettier
# pyright runs via `uv run` for correct project environment
PYRIGHT := $(UV) run npx --no-install pyright
PYRIGHT_TESTS := $(PYRIGHT) -p tests
# shellcheck runs via scripts/shellcheck.py, which on Linux downloads a pinned
# release into .cache/shellcheck/ and elsewhere uses shellcheck from PATH
SHELLCHECK := $(UV) run python scripts/shellcheck.py
RUFF := $(UV) run ruff
RUFF_CHECK := $(RUFF) check .
RUFF_CHECK_FIX := $(RUFF) check . --fix
RUFF_FORMAT := $(RUFF) format
RUFF_FORMAT_CHECK := $(RUFF) format . --check
PRETTIER_WRITE := $(PRETTIER) --write '**/*.md'
SHELLCHECK_CHECK := $(SHELLCHECK) hooks/commit-msg hooks/pre-commit hooks/pre-push $(wildcard hooks/*.sh)
PYMARKDOWN_CHECK := $(UV) run pymarkdown --strict-config scan --respect-gitignore '**/*.md'
CSPELL_CHECK := $(CSPELL) lint --gitignore * .github

# QUIET=1 reduces output for git hooks. Output is still shown on failure.
ifeq ($(QUIET),1)
STEP := @step() { _n=$$1; shift; printf '%s: ' "$$_n"; _o=$$(mktemp); if "$$@" >"$$_o" 2>&1; then rm -f "$$_o"; printf 'OK. '; else printf 'FAILED\n' "$$_n" >&2; cat "$$_o" >&2; rm -f "$$_o"; return 1; fi; }; step
else
STEP := @step() { shift; printf '%s\n' "$$*"; "$$@"; }; step
endif

.PHONY: build install install-js hooks static lint lint-markdown typecheck typecheck-src typecheck-tests spelling fix fix-static test preview docs package pyinstaller clean

build: install static test
	@echo "build complete"

# Git hooks will be enabled when install-js runs (any lint operation)
hooks: ## Enable git hooks (commit-msg, pre-commit, pre-push)
	@if git rev-parse --git-dir >/dev/null 2>&1; then if [ "$$(git config --get core.hooksPath)" != "hooks" ]; then git config core.hooksPath hooks; echo "git hooks enabled (core.hooksPath=hooks)"; fi; else echo "skipping git hooks (not a git repository)"; fi

# --locked: fail if uv.lock is out of date with pyproject.toml (run `uv lock` to update it)
install: ## Install project dependencies
	$(STEP) 'uv sync' $(UV) sync --locked

install-js: node_modules hooks ## Install static-check Node.js dependencies

node_modules: package.json package-lock.json
	npm ci

# cheapest first:
static: lint lint-markdown spelling typecheck ## Run all static checks (lint, markdown, spelling, types)

lint: install-js ## Lint Python (ruff) and shell (shellcheck)
	$(STEP) lint $(RUFF_CHECK)
	$(STEP) format $(RUFF_FORMAT_CHECK)
	$(STEP) shellcheck $(SHELLCHECK_CHECK)

# glob is quoted so pymarkdown expands it (sh has no globstar)
lint-markdown: ## Lint markdown
	$(STEP) markdown $(PYMARKDOWN_CHECK)

spelling: install-js ## Run spell check
	$(STEP) spelling $(CSPELL_CHECK)

typecheck: install-js typecheck-src typecheck-tests ## Type check (pyright: strict for src, looser for tests)

typecheck-src: node_modules
	$(STEP) analyze $(PYRIGHT)

typecheck-tests: node_modules
	$(STEP) 'analyze (tests)' $(PYRIGHT_TESTS)

fix-static: node_modules ## Fix + static checks except pyright (pre-commit path)
	$(STEP) formatter $(RUFF_FORMAT)
	$(STEP) 'lint-fix' $(RUFF_CHECK_FIX)
	$(STEP) 'markdown-fix' $(PRETTIER_WRITE)
	$(STEP) shellcheck $(SHELLCHECK_CHECK)
	$(STEP) markdown $(PYMARKDOWN_CHECK)
	$(STEP) spelling $(CSPELL_CHECK)

fix: install install-js ## Automatically fix lint/format
	$(STEP) formatter $(RUFF_FORMAT)
	$(STEP) 'lint-fix' $(RUFF_CHECK_FIX)
	$(STEP) 'markdown-fix' $(PRETTIER_WRITE)

test: install ## Run all tests, fail on any warnings
	$(UV) run pytest --max-warnings=0

coverage: install ## Run all tests with coverage, fail on any warnings
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
	rm -rf tests/fixtures/libraries tests/tmp
	rm -rf docs/database_diagram.png docs/screenshot_help.png docs/screenshot_help.png.tmp docs/screenshot_help.png.txt
	rm -rf site
	rm -rf docs/.cache
	rm -rf htmlcov
	rm -rf .coverage
	rm -rf .pytest_cache
	rm -rf .ruff_cache
	rm -rf sample/albums.db
