---
icon: lucide/user
---

# Usage

## Configuration

The tool needs to know where your albums are. The default is the
operating-system defined user's music directory. To use a library in another
location, create a `config.toml` file. See example in
[sample/config.toml](https://github.com/4levity/albums/blob/main/sample/config.toml).

At the bottom of the output from `albums --help` it will show the list of
locations where `albums` will automatically search for the `config.toml` file.

## Getting Started

`albums scan` will scan the library.

> The first time `scan` runs, it will read metadata from every track. This may
> take a long time if you have thousands of albums. Subsequent scans should only
> take a few seconds. If you interrupt the scan with ^C, it will continue where
> it left off next time.

Most commands can be filtered. For example, to list albums matching a path
(relative path within the library), run
`albums --regex --path "Freezepop" list`.

Albums can be in sets called "collections". Create a collection named "DAP" for
albums to sync to a Digital Audio Player and add some albums to it with
`albums -rp "Freezepop" add DAP` and list them with
`albums --collection DAP list`

Get a list of issues with `albums check`. Adjust the settings in `config.toml`
to configure the checks. Learn about using `albums` to fix problems in the next
section, [Check and Fix](./check_and_fix.md).

Sync selected albums to an SD card. Add/update files and **remove all
unrecognized files** in destination folder (**dangerous!**):
`albums -c DAP sync /mnt/sdcard --delete`

There are many other commands and options. Try `albums --help`. To learn more
about a command try e.g. `albums check --help`.
