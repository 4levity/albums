# albums

`albums` is a rich interactive command line tool to help manage a library of
music. Works with FLAC/ID3/etc tags, but acts primarily on "albums" rather than
individual files.

> Most of the features of this tool require each album (soundtrack, mixtape,
> etc) to be in a folder.

## Overview

`albums` scans the library and creates a database. It supports tagging albums
with "collections," for example to make a list of albums to sync to a digital
audio player. It can also do the sync. There are checks and interactive fixes
for metadata related issues like track numbering (sequence, totals, disc
numbers), album-artist tags, etc.

## Requirements

Developed/tested only on Linux. Probably works on MacOS. Interactive fixer may
not work on Windows.

With [poetry](https://python-poetry.org/) installed and Python 3.14 available,
run `make` to install Python dependencies, lint, test and build. Or use `poetry`
directly.

## Configuration

The tool needs to know where your albums are. The default is the
operating-system defined user's music directory. To use a library in another
location, create a `config.toml` file. See example in
[sample/config.toml](sample/config.toml).

## Usage

`albums scan` will create the database and scan the library. The first time it
runs, it will read metadata from every track which may take a long time.
Subsequent scans should take seconds.

Most commands can be filtered. For example, to list albums matching a path
(relative path within the library), run
`albums --regex --path "Freezepop" list`.

Albums can be in sets called "collections". Create a collection named "DAP" for
albums to sync to a Digital Audio Player and add some albums to it with
`albums -rp "Freezepop" add DAP` and list them with
`albums --collection DAP list`

Get a list of issues albums knows about with `albums check`. Adjust the settings
in `config.toml` to control how checks work. Run `albums check --interactive` to
interactively fix some problems.

Sync selected albums to an SD card. Update and **remove** files in destination
folder (dangerous!): `albums -c DAP sync /mnt/sdcard --delete`

Try `albums --help` or e.g. `albums sync --help`.

## Developing

Refer to [Makefile](./Makefile). Install [GraphViz](https://graphviz.org/) and
`make diagram` for a database reference diagram. See [docs](./docs).
