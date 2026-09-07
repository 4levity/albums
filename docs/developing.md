---
icon: lucide/computer
---

# Developing

## Prerequisites

- Python 3.12+ available (install with uv or pyenv etc.)
- [poetry](https://python-poetry.org/)
- `make`

## Overview

Run `make` to install dependencies + lint + test. The first run requires
Python 3.12+.

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

| Package       | Description                                               |
| ------------- | --------------------------------------------------------- |
| `app`         | App context (db, config, console) shared across functions |
| `config`      | Configuration types, defaults, serialization              |
| `entities`    | ORM models (Album, Track, PictureFile, OtherFile)         |
| `checks`      | Check/fixer implementations and orchestration             |
| `cli`         | Entry point and command implementations                   |
| `database`    | DB creation, migrations, queries                          |
| `interactive` | UI for interacting with checks \u0026 configuration       |
| `library`     | Scan library, import album, sync to destination           |
| `picture`     | Get picture info, caching picture scanner                 |
| `tagger`      | Read/write metadata in media files                        |
| `words`       | Simple text generation e.g. pluralize words               |

### Key Types to Know

- **`Context`** (`app.py`) - Carries shared state (db engine, config, console)
  across invocation.
- **`Album`/`Track`/`PictureFile`/`OtherFile`** (`entities.py`) - SQLAlchemy ORM
  models representing the data model.
- **`CheckConfiguration`** (`checks/check_types.py`) - Per-check config dict
  type.
- **`Fixer`/`CheckResult`** (`checks/check_types.py`) - Problem reporting and
  fix contracts.

## Adding Functionality

### Checks

Checks are grouped into categories under `src/albums/checks/`:

- **`fields/`** - Metadata field presence and consistency checks
- **`numbering/`** - Track/disc numbering validation
- **`path/`** - Filename and path structure checks
- **`picture/`** - Album art embedding, dimensions, duplicates

Each check file defines one class. Extend `base_check.Check` for general checks
or `base_check_field_per_album` for field-consistency checks.

To add a new check:

1. Create a class in the appropriate `checks/<category>/` subdirectory
2. Define `name`, `default_config` (dict with `"enabled": True` plus any custom
   options)
3. Implement `check(album: Album) -> CheckResult | None`
4. Add to `ALL_CHECKS` tuple in [`checks/all.py`](src/albums/checks/all.py)
5. Optionally define `must_pass_checks` to depend on earlier checks

The `check()` method gets an ORM `Album` with loaded tracks. Check and fix via
`self.session`, `self.tagger`, and `self.ctx`. Return `None` if passed, or a
`CheckResult` with a message and optional `Fixer`.

#### Check guidelines: fast and stateless

Two rules keep checks repeatable and fast (a million checks should run in a
few seconds):

1. **`check()` should rely on data in the database.** It should not read tags
   from files, or perform file system or network operations, or anything
   "slow". Tag data (fields, pictures, stream info) is loaded during the scan
   and available on the ORM entities, and additional queries via
   `self.session` are fine. Any exception must be defensible and commented,
   e.g. `folder-name` does a single `exists()` stat - and only for an album
   that has already failed the check - because a rename collision depends on
   disk state that is not in the database.
2. **Checks should be stateless, holding only configuration.** Instance
   attributes should be set in `init()` from the check configuration (or be
   the injected `ctx`/`tagger`/`session`), and `check()` must not set any
   state on the Check object. The one exception is `duplicate-album`, which
   holds an in-memory index of the library built in `__init__` to compare
   albums across the whole library; see its docstring for the justification.

Related guidance:

- Slow work belongs in the **fix phase**: the fixer's `fix(option)` callback
  may read/write files, rename, or download (e.g. `cover-available` runs an
  external download command).
- Table row data for interactive display can be **deferred** by passing a row
  factory callable instead of rows (`Fixer.get_table()` resolves it only when
  the table is actually displayed). This keeps slow work such as image
  decoding (picture checks) or reading the album folder for proposed
  filenames (`unreadable-track`) out of `check()`.

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

- The `check()` method should avoid slow operations - see the check guidelines
  above.
- If returning one result is limiting, maybe the check should be two checks.
- Consider checking for "pass" conditions first in some cases.

### Writing Tests

Tests live in `tests/`, mirroring `src/albums/`. Use `pytest` with class-based
tests. Construct Albums and Tracks directly; use `Context()` for app state.
Example:

```python
from albums.app import Context
from albums.entities import Album, Track
from albums.tagger import AlbumTagger
from albums.tagger import BasicField

class TestMyCheck:
    def test_missing_field(self, mocker):
        album = Album(
            path="foo/",
            tracks=[
                Track(filename="1.flac", tag={BasicField.ALBUM: "Foo"}),
                Track(filename="2.flac"),  # missing album field
            ],
        )
        result = MyCheck(Context()).check(album)
        assert result.fixer
        mock_set_basic_fields = mocker.patch.object(AlbumTagger, "set_basic_fields")
        result.fixer.fix(result.fixer.options[0])
        assert mock_set_basic_fields.call_count == 1
```

Library fixture data is in `tests/fixtures/libraries/`. Run `make test` for full
suite, or `poetry run pytest tests/path/to/test.py -v` for targeted runs.

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

The tagger only uses values in [`BasicField`](src/albums/tagger/types.py). All
files with basic fields must read/write each one. Add a tag field by:

1. Add to the `BasicField` enum with comments showing ID3/vorbis/M4A equivalents
2. For FLAC/Ogg Vorbis, use same name or edit functions in
   [`tagger/vorbis.py`](src/albums/tagger/vorbis.py)
3. For MP3/AIFF: add to [`tagger/base_id3.py`](src/albums/tagger/base_id3.py)
   `AbstractId3Tagger`
4. For other types: implement in
   [`tagger/file_types/`](src/albums/tagger/file_types/)
5. Add a test case in the appropriate `tests/checks/fields/` test file

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

### Database Schema

Database migrations are SQL files in
[`database/migrations/`](src/albums/database/migrations/). Scanner version
(`SCANNER_VERSION` in `app.py`) tracks changes. To refresh the ER diagram run:

```bash
make docs/database_diagram.png
```

![albums database schema diagram](./database_diagram.png)

### Querying the Database

Use `albums sql "SELECT * FROM album LIMIT 10;"` or `albums list --json` to
inspect library data.

### Previewing Docs

`make preview` requires [GraphViz](https://graphviz.org/).
