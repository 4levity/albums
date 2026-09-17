UV := uv
# Lint tools are Node.js dev dependencies, defined in package.json and
# installed by `make install-js` (requires Node.js 22.18+).
CSPELL := npx --no-install cspell
RUMDL := npx --no-install rumdl
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
# rumdl scans . for markdown files and respects .gitignore
RUMDL_CHECK := $(RUMDL) check .
RUMDL_CHECK_FIX := $(RUMDL) check --fix .
# all shell scripts in the project, excluding VCS, dependency and generated
# folders (add exclusions here if a new generated folder contains *.sh)
SHELL_FILES := $(shell find . -name '*.sh' \
	-not -path './.git/*' -not -path './node_modules/*' \
	-not -path './.venv/*' -not -path './.cache/*' \
	-not -path './build/*' -not -path './dist/*' \
	-not -path './site/*')
SHELLCHECK_CHECK := $(SHELLCHECK) hooks/commit-msg hooks/pre-commit hooks/pre-push $(SHELL_FILES)
# syntax checks for the config files that have no dedicated linter:
# node --check for commitlint.config.js and jsonc-parser for .vscode/*.json
# (JSONC with comments, which strict JSON parsers reject)
JSONC_CHECK := node scripts/check_jsonc.js .vscode/*.json
JS_CHECK := node --check commitlint.config.js
# cspell skips hidden (dot) files and dirs when walking, so besides `.`
# (everything else; gitignored paths skipped by --gitignore) the root dot
# entries are passed explicitly. .git is not listed in .gitignore, so it is
# excluded explicitly (its objects would otherwise be spell-checked).
CSPELL_CHECK := $(CSPELL) lint --gitignore --exclude .git . .[!.]*
# actionlint runs via scripts/actionlint.py, which on Linux downloads a
# pinned release into .cache/actionlint/ and elsewhere uses actionlint from
# PATH; it also ensures the pinned shellcheck (importing scripts/shellcheck.py)
# is on its PATH, since actionlint shellchecks the workflows' run: blocks
ACTIONLINT := $(UV) run python scripts/actionlint.py
ACTIONLINT_CHECK := $(ACTIONLINT) .github/workflows/*.yml

# QUIET=1 reduces output for git hooks. Output is still shown on failure.
ifeq ($(QUIET),1)
STEP := @step() { _n=$$1; shift; printf '%s: ' "$$_n"; _o=$$(mktemp); if "$$@" >"$$_o" 2>&1; then rm -f "$$_o"; printf 'OK. '; else printf 'FAILED\n' "$$_n" >&2; cat "$$_o" >&2; rm -f "$$_o"; return 1; fi; }; step
else
STEP := @step() { shift; printf '%s\n' "$$*"; "$$@"; }; step
endif

.PHONY: build install install-js hooks static lint lint-python lint-markdown shellcheck actionlint jsonc js typecheck typecheck-src typecheck-tests spelling fix fix-python fix-markdown test preview docs package pyinstaller wine-setup wine-build wine-pytest wine-e2e clean extraclean

build: install static test
	@echo "build complete"

# Git hooks will be enabled when install-js runs (any lint operation)
hooks: ## Enable git hooks (commit-msg, pre-commit, pre-push)
	@if git rev-parse --git-dir >/dev/null 2>&1; then if [ "$$(git config --get core.hooksPath)" != "hooks" ]; then git config core.hooksPath hooks; echo "git hooks enabled (core.hooksPath=hooks)"; fi; else echo "skipping git hooks (not a git repository)"; fi

install: ## Install project dependencies
	$(STEP) 'uv sync' $(UV) sync --locked

install-js: node_modules hooks ## Install static-check Node.js dependencies

node_modules: package.json package-lock.json
	npm ci

# cheapest first:
static: lint spelling typecheck ## Run all static checks (lint, spelling, types)

# one target per tool (fix-python/fix-markdown auto-fix), so callers such as
# the pre-commit hook can run only the tools a change can affect
lint: install-js lint-python lint-markdown shellcheck actionlint jsonc js ## Lint Python, shell, markdown and config files

lint-python: ## Lint and format-check Python (ruff)
	$(STEP) lint $(RUFF_CHECK)
	$(STEP) format $(RUFF_FORMAT_CHECK)

fix-python: ## Format and fix Python (ruff)
	$(STEP) formatter $(RUFF_FORMAT)
	$(STEP) 'lint-fix' $(RUFF_CHECK_FIX)

lint-markdown: install-js ## Lint markdown (rumdl)
	$(STEP) markdown $(RUMDL_CHECK)

fix-markdown: install-js ## Fix markdown (rumdl)
	$(STEP) 'markdown-fix' $(RUMDL_CHECK_FIX)

shellcheck: ## Shellcheck all shell scripts (hooks/ + *.sh)
	$(STEP) shellcheck $(SHELLCHECK_CHECK)

actionlint: ## Lint the GitHub workflows (actionlint)
	$(STEP) actionlint $(ACTIONLINT_CHECK)

jsonc: install-js ## Check the JSONC config syntax (.vscode/*.json)
	$(STEP) jsonc $(JSONC_CHECK)

js: ## Syntax-check commitlint.config.js (node --check)
	$(STEP) js $(JS_CHECK)

spelling: install-js ## Run spell check
	$(STEP) spelling $(CSPELL_CHECK)

typecheck: install-js typecheck-src typecheck-tests ## Type check (pyright: strict for src, looser for tests)

typecheck-src: node_modules
	$(STEP) analyze $(PYRIGHT)

typecheck-tests: node_modules
	$(STEP) 'analyze (tests)' $(PYRIGHT_TESTS)

fix: install fix-python fix-markdown ## Automatically fix lint/format

test: install ## Run all tests, fail on any warnings
	$(UV) run pytest --max-warnings=0

coverage: install ## Run all tests with coverage, fail on any warnings
	$(UV) run pytest --max-warnings=0 --cov=src/albums --cov-report=xml
	@echo Coverage XML in $(CURDIR)/coverage.xml

# regenerate sample db if schema or schema-creation code changed
SCHEMA_FILES := $(wildcard src/albums/database/migrations/*.sql) \
	src/albums/database/migrations/migrate.py \
	src/albums/database/migrations/__init__.py \
	src/albums/database/connection.py

sample/albums.db: $(SCHEMA_FILES)
	@rm -rf sample/albums.db
	@mkdir -p sample
	$(UV) run python src/albums/database/connection.py sample/albums.db

docs/images/database_diagram.png: sample/albums.db
	@mkdir -p docs/images
	$(UV) run eralchemy -i sqlite:///sample/albums.db -o docs/images/database_diagram.png
	@ls -l docs/images/database_diagram.png

# Render the real `albums --help` output to an image (via ansi2image, bundled JetBrains Mono font).
# FORCE_COLOR=1 forces ANSI color (output is piped, not a tty), COLUMNS=100 fixes rich's wrap width,
# and XDG_CONFIG_HOME='~/.config' (Linux) keeps the epilog's default-db path machine independent.
docs/images/screenshot_help.png: $(wildcard src/albums/cli/*.py)
	@mkdir -p docs/images
	@rm -f $@ $@.tmp $@.txt
	@FORCE_COLOR=1 COLUMNS=100 XDG_CONFIG_HOME='~/.config' $(UV) run albums --help > $@.tmp
	@sed 1d $@.tmp > $@.txt
	@$(UV) run ansi2image $@.txt -o $@
	@rm -f $@.tmp $@.txt
	@test -s $@
	@ls -l $@

# Render derived images from the committed master icon (docs/art/icon.png):
# the docs site favicon and header logo (docs/images/) and the Windows icon
# (build/icon.ico) for the PyInstaller executable and Inno Setup installer.
docs/images/favicon.png docs/images/logo.png build/icon.ico &: docs/art/icon.png scripts/render_icon.py
	$(UV) run python scripts/render_icon.py

# Build a standalone executable for this platform in dist/pyinstaller/<platform>/albums/.
pyinstaller: install build/icon.ico ## Build standalone pyinstaller executable for this platform
	$(UV) run python scripts/version.py write
	platform=$$($(UV) run python -c "import sysconfig; print(sysconfig.get_platform().replace('-', '_'))") && \
	case $$platform in win*) iconopt="--icon $$(pwd)/build/icon.ico" ;; *) iconopt="" ;; esac && \
	$(UV) run pyinstaller src/albums/__main__.py --onedir --name albums --noconfirm --clean \
	--collect-data albums $$iconopt \
	--workpath build/$$platform --distpath dist/pyinstaller/$$platform \
	--specpath build/$$platform/.specs --contents-directory _albums_internal && \
	ls -l dist/pyinstaller/$$platform/albums

# Windows installer on Linux via wine: wine_setup.py idempotently creates the
# wine environment (prefix, uv + Windows Python, Inno Setup) in gitignored
# .cache/wine/, wine_build.py builds dist/installer/ like the Windows CI job.
# wine-pytest needs the wine environment (hence depends on wine-setup);
# wine-e2e tests the existing installer, or builds a fresh one first with
# --build (which also creates the wine environment).
wine-setup: ## Create the wine environment for Windows installer builds
	$(UV) run python scripts/wine_setup.py

wine-build: ## Build the Windows installer on Linux via wine (dist/installer/)
	$(UV) run python scripts/wine_build.py

wine-pytest: wine-setup ## Run the test suite under wine
	$(UV) run python scripts/wine_pytest.py

wine-e2e: ## Install, run and uninstall the installer in a temporary wine prefix
	$(UV) run python scripts/wine_e2e.py

package: ## Create sdist and wheel in dist/
	$(UV) build

docs: install lint-markdown docs/images/favicon.png docs/images/logo.png docs/images/database_diagram.png docs/images/screenshot_help.png ## Build docs
	$(UV) run zensical build --clean
	# portable version of sed -i (GNU-only): write to tmp file and move into place
	@version=$$($(UV) run python scripts/version.py) && \
	echo "injecting version $$version" && \
	sed "s/%%version_placeholder%%/$$version/g" site/index.html > site/index.html.tmp && \
	mv site/index.html.tmp site/index.html

preview: docs/images/favicon.png docs/images/logo.png docs/images/database_diagram.png docs/images/screenshot_help.png ## Preview docs (does not automatically install)
	$(UV) run zensical serve

clean: ## Remove build and test files
	find . -type d -name "__pycache__" -exec rm -rf {} +
	rm -rf dist
	rm -rf build
	rm -rf src/albums/_version.py
	rm -rf tests/fixtures/libraries tests/tmp
	rm -rf docs/images
	rm -rf site
	rm -rf docs/.cache
	rm -rf .coverage
	rm -rf .pytest_cache
	rm -rf .ruff_cache
	rm -rf .rumdl_cache
	rm -rf sample/albums.db

extraclean: clean ## Remove build/test files, caches and installed dependencies
	rm -rf .cache .venv node_modules
