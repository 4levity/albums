---
icon: lucide/user
---

# Usage

## Configuration

`albums` needs to know where your albums are. The default is the
operating-system defined user's music directory. When initializing, the
`--library` option allows you to set the location of the library.

## Basic commands

> To see **all** commands and options, run `albums --help` and
> `albums <command> --help`.

`albums scan` will scan the library. This happens automatically the first time
the tool is used, if there is a library in the configured location to scan.

!!!info

    The first time `scan` runs, it reads metadata from every track and image.
    This may take a long time if you have thousands of albums. Subsequent scans
    should only take a few seconds. If you interrupt the scan with ^C, it will
    continue where it left off next time.

Most commands can be filtered. For example, to list albums matching a path
(relative path within the library), run
`albums --regex --path "Freezepop" list`.

Get a list of issues with `albums check`. Learn about using `albums` to fix
problems in [Check and Fix](./check_and_fix.md).

Albums can be in sets called "collections". To create a collection named "DAP"
containing albums to sync to a Digital Audio Player, use for example
`albums -rp "Freezepop" add DAP`. Review the collection with
`albums --collection DAP list`. To copy/sync it to an SD card, see
[Synchronize](./sync.md).

To set up `albums` configuration options interactively, run `albums config`. See
`albums config --help` for other ways to configure.

## Global Settings

In addition to options for individual checks (described in
[Check and Fix](./check_and_fix.md)), there are a few global settings:

- `rescan`: Rescan the library before performing other operations. If the
  operation is filtered then only selected albums will be rescanned. Options:
    - `always`: always scan the library so you never need to run "albums scan"
      but may be slow
    - `never`: never automatically scan the library, you must run "albums scan"
      if it's changed
    - `auto`: scan on first run and before "check" or "sync" operations
- `tagger`: If this option is set, whenever there is an interactive tag fix,
  there will be a menu option to execute this external tagging program. The path
  of the album will be the first parameter.

<!-- pyml disable line-length -->

| Name                  | Default                    | Description                                        |
| --------------------- | -------------------------- | -------------------------------------------------- |
| `library`             | n/a                        | Location of the music library.                     |
| `rescan`              | **auto**                   | When to automatically rescan the library           |
| `tagger`              | **easytag** (if installed) | External tagging program to launch when requested. |
| `open_folder_command` | Use OS default             | Program to open to browse an album folder.         |

<!-- pyml enable line-length -->

## Tag Conversion

`albums` attempts to apply some of the same checks and rules with Vorbis
comments (FLAC, Ogg Vorbis) and ID3 tags (MP3). To enable this, common tags like
track number are converted to the typical Vorbis comment tag names. For example,
the ID3 tags TPE1 "Artist" and TPE2 "Band" are referenced by the standard tag
names "artist" and "albumartist". Or in other words, if `albums` writes a new
"album artist" to your MP3, behind the scenes it's actually writing to the TPE2
tag.

### Track total and disc total

In addition, if track number and track total are combined in the tracknumber (or
ID3 TRCK) with a slash like "04/12" instead of being in separate tags, `albums`
will see that as "tracknumber=04" and "tracktotal=12" and be able to write to
the track number and track total field as if they were separate. The same rule
applies for disc number and disc total if combined in the discnumber (or ID3
TPOS) tag. Storing track total and disc total this way is normal for ID3 tags.
