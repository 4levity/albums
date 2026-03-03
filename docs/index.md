---
icon: lucide/target
---

# Overview

`albums` is an interactive tool to manage music: configurably validate and fix
tags and metadata, rename files, reformat and embed album art, import albums,
and sync parts of the library to digital audio players or portable storage

This documentation is for `albums` version **%%version_placeholder%%**.

![screenshot](screenshot.png)

## License

`albums` is free software, licensed under the terms of the
[GNU General Public License Version 3](https://github.com/4levity/albums/blob/main/COPYING)

## Getting started

Install with `pipx install albums` in an environment with Python 3.12 or newer.

Each album (soundtrack, mixtape...) is expected to be in a folder, or `albums`
won't be helpful.

To immediately start scanning for issues in a single album or a few albums, with
default settings, run: `albums --dir /path/to/an/album check`. Add `--fix` at
the end to see repair options or `--help` for more choices. Using the `--dir`
(or `-d`) option, no data is stored between runs.

Albums can store information about a library of music in its database. Run
`albums scan` (without the `--dir` option) to get started. It will ask you to
confirm whether your music library is in the default user home directory
location (e.g. `~/Music`). It may take several minutes to index a large
collection. Configuration settings are also stored in the database and can be
customized by running `albums config`. See [Usage](./usage.md).

## Supported Formats

**FLAC**, **Ogg Vorbis**, **MP3/ID3** and **M4A** containers are supported.
**WMA** files are read but `albums` doesn't comprehend their tags yet so most
checks are skipped. JPEG, PNG and GIF files in the album folder are loaded as
candidates for cover art.

## System Requirements

Requires Python 3.12+. Primarily tested on Linux and Windows. Should work on
almost any 64-bit x86 or ARM system with Linux, macOS or Windows. (32-bit and
wider OS support possible by dropping `scikit-image` library used for measuring
image similarity.)
