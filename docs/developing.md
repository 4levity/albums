---
icon: lucide/computer
---

# Developing

## Prerequisites

- Python 3.12+ available (install with uv or pyenv etc.)
- [poetry](https://python-poetry.org/)
- `make` (recommended)

## Building

Run `make` to install dependencies + lint + test + package. Or use `poetry` -
see Makefile.

The first time dependencies are installed, it needs to be in an environment with
Python 3.12+. Run the local app with `poetry run albums`.

## Lint, format and static analysis

All checks must pass for a successful build.

- lint and formatting with [ruff](https://docs.astral.sh/ruff/)
    - all default settings except for 150 character line limit
    - formats the same as [Black](https://black.readthedocs.io/en/stable/)
      static
- static type checking with [pyright](https://microsoft.github.io/pyright/)
    - **strict** mode for main project
    - looser rules for tests (separate rules in
      [tests/pyrightconfig.json](https://github.com/4levity/albums/blob/main/tests/pyrightconfig.json))
- markdown lint with [PyMarkdown](https://pymarkdown.readthedocs.io/en/latest/)

Some lint/format problems can be automatically fixed with `make fix`.

Developing in VSCode with Pylance is helpful. Pylance version 2025.12.101 or
later is required for Pylance to utilize the separate configuration in the tests
folder. Also, Prettier is useful to automatically reflow Markdown text.

## Tips

- Create an `albums.db` file in the project root for a local test environment
  (if there is an `albums.db` file in the working directory it will be used)
- `make fix` to automatically fix lint and format errors
- `make preview` to preview these docs (requires
  [GraphViz](https://graphviz.org/))
- Query albums.db with e.g. `albums sql "SELECT * FROM album LIMIT 10;"` or try
  `albums list --json`

## Database Schema

![albums database schema diagram](./database_diagram.png)
