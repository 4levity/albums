---
icon: lucide/computer
---

# Developing

## Prerequisites

- Python 3.12+ available (install with uv or pyenv etc.)
- [poetry](https://python-poetry.org/)
- `make`

## Overview

Run `make` to install dependencies + lint + test. The first time dependencies
are installed, it needs to be running in an environment with Python 3.12+.

### Run

Run the app with `poetry run albums [...]`. The first time you do, you may run
`poetry run albums --db-file albums.db init` in the project directory, which
will create a "local" `albums.db` there for a test environment (separate from
the db used by a regular installation of `albums`).

### Project Files and Folders

| Path                | Description                                          |
| ------------------- | ---------------------------------------------------- |
| `.github/workflows` | Github workflows (build/publish/docs)                |
| `docs/`             | This documentation                                   |
| `src/albums/`       | Python application (structure below)                 |
| `tests/`            | Tests!                                               |
| `Makefile`          | The Makefile                                         |
| `pyproject.toml`    | Project definition, tool configuration, dependencies |
| `zensical.toml`     | Configuration for this documentation                 |

(not all files/folders included)

### Python Project Structure

<!-- pyml disable line-length -->

| Package           | Uses Within Project\*           | Description                                     |
| ----------------- | ------------------------------- | ----------------------------------------------- |
| **`app`**         | -                               | App context type shared across functions        |
| **`config`**      | `database`                      | Types for app configuration                     |
| **`types`**       | `database`, `picture`, `tagger` | Types for app entities and check results        |
| **`checks`**      | everything except `cli`         | Implementations of checks and fixers            |
| **`cli`**         | everything                      | Entry point and command implementations         |
| **`database`**    | `picture`, `tagger`             | Create/update db, store config, build queries   |
| **`interactive`** | `database`, `library`, `tagger` | UI for interacting with checks & configuration  |
| **`library`**     | `picture`, `tagger`, `words`    | Scan library, import album, sync to destination |
| **`picture`**     | _none_                          | Get picture info, caching picture scanner       |
| **`tagger`**      | `picture`                       | Read/write metadata in media files              |
| **`words`**       | _none_                          | Simple text generation e.g. pluralize words     |

<!-- pyml enable line-length -->

\* - not including ubiquitous `app`/`config`/`types`

## Adding Functionality

### Checks

To add a new check, create a class file in `src/albums/checks/<category>/`.
Extend `albums.checks.base_check.Check` and define `name` and `default-config`.
Implement `check(album)`. Add the new class to the list in `albums.checks.all`,
placing it in the ordered list where it should run. Optionally, define
`must_pass_checks` to prevent the check from running when certain earlier checks
were disabled or didn't pass.

`check()` returns `None` to indicate the check passed (including when it isn't
relevant), or a `CheckResult` to indicate a problem. The `CheckResult` has a
message and optionally (hopefully!) a `Fixer` with a solution.

#### Fixers

The `Fixer` object returned in a `CheckResult` has a list of option strings, and
specifies whether a "free text" option should be displayed. It includes a
`fix(option)` function to call once a decision is made. If an automatic fix is
being offered, the fixer sets `option_automatic_index` to point to the option
that is the automatic selection.

The fixer may also optionally define a table (headers and row data) that should
be displayed to the user in interactive modes to help them decide which option
to pick. Generating row data can be deferred until display so the check can be
fast if that is slow.

Tips:

- The `check()` method should avoid slow operations and checks should ideally
  operate only on data loaded during the scan.
- If returning one result is limiting, maybe the check should be two checks.
- Consider checking for "pass" conditions first in some cases.

### Music File Tag Support

An `AlbumTaggerProvider` instance provides configured `AlbumTagger` instances.
`AlbumTagger.open()` selects a `FileTagger` implementation class based on the
file extension.

Support for different file types is provided by `FileTagger` implementations in
`albums.tagger.file_types`. The mapping from file extensions to tagger
capabilities and implementation classes is in `albums.tagger.folder`.

`FileTagger` implementations for music files all extend `AbstractMutagenTagger`.
File types that use ID3 extend `AbstractId3Tagger`.

### Common Tags

The tagger in `albums` only uses the values in `albums.tagger.types.BasicTag`.
In general, all files that advertise basic tag capability are expected to be
able to read and write values corresponding to each of these.

To add support for a new tag:

- Add the new common tag to `BasicTag`.
- For FLAC and Ogg Vorbis support, simply use the same name as the Vorbis
  Comment, or edit `vorbis_comment_tags()` and `vorbis_comment_set_tag()`.
- For MP3 and AIFF support, add to `AbstractId3Tagger`.
- Add to all other implementations in `albums.tagger.file_types`

## Tips

### Lint, format and static analysis

No warnings, only pass/fail. Some lint/format problems can be automatically
fixed with `make fix`.

- lint/format with [ruff](https://docs.astral.sh/ruff/) (static format same as
  [Black](https://black.readthedocs.io/en/stable/)) - all defaults except 150
  character line limit
- static type checking with [pyright](https://microsoft.github.io/pyright/) -
  strict mode for main project, looser rules for tests
- markdown lint with [PyMarkdown](https://pymarkdown.readthedocs.io/en/latest/)

### Spell check

CI builds require [cSpell](https://cspell.org/) spell check to pass. The
`make spelling` target is separate from `lint` because it requires Docker to be
installed. Add valid words and relevant technical terms to `cspell.json`.

### IDE

Use an IDE like [Visual Studio Code](https://code.visualstudio.com/) that
supports ruff/Black formatting and a
[pyright](https://microsoft.github.io/pyright/) language server and
[cSpell](https://cspell.org/). [Prettier](https://prettier.io/) can reflow
Markdown text.

### Other Tips

- `make preview` to preview these docs (requires
  [GraphViz](https://graphviz.org/))
- Query `albums.db` directly with `albums sql "SELECT * FROM album LIMIT 10;"`
  or try `albums list --json`

### Database Schema

![albums database schema diagram](./database_diagram.png)
