---
icon: lucide/target
---

# Overview

`albums` is a rich text-based interactive tool to help manage a library of
music, clean up metadata tags and file organization, and sync parts of the
library to digital audio players.

This documentation is for `albums` version **%%version_placeholder%%**.

## License

`albums` is free software, licensed under the terms of the
[GNU General Public License Version 3](https://github.com/4levity/albums/blob/main/COPYING)

## Installation

Install with `pipx install albums` in an environment with Python 3.12 or newer.

## Getting started

Run `albums scan` to get started. It will ask you to confirm whether your music
library is in the default user home directory location (e.g. `~/Music`). If it
isn't, run `albums --library "/path/to/library" scan` instead. It may take
several minutes to index a large collection. See [Usage](./usage.md).
