---
icon: lucide/user
---

# Usage

## Configuration

`albums` needs to know where your albums are. The default is the
operating-system defined user's music directory. To use a library in another
location, create a `config.toml` file. See example in
[sample/config.toml](https://github.com/4levity/albums/blob/main/sample/config.toml).

At the bottom of the output from `albums --help` it will show the list of
locations where `albums` will automatically search for the `config.toml` file.

## Basic commands

> To see **all** commands and options, run `albums --help` and
> `albums <command> --help`.

`albums scan` will scan the library. This happens automatically the first time
the tool is used, if there is a library in the configured location to scan.

!!!info

    The first time `scan` runs, it will read metadata from every track.
    This may take a long time if you have thousands of albums. Subsequent scans
    should only take a few seconds. If you interrupt the scan with ^C, it will
    continue where it left off next time.

Most commands can be filtered. For example, to list albums matching a path
(relative path within the library), run
`albums --regex --path "Freezepop" list`.

Get a list of issues with `albums check`. Adjust the settings in `config.toml`
to configure the checks. Learn about using `albums` to fix problems in
[Check and Fix](./check_and_fix.md).

Albums can be in sets called "collections". To create a collection named "DAP"
containing albums to sync to a Digital Audio Player, use for example
`albums -rp "Freezepop" add DAP`. Review the collection with
`albums --collection DAP list`. To copy/sync it to an SD card, see
[Synchronize](./sync.md).
