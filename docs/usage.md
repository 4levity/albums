---
icon: lucide/user
---

# Usage

## Configuration

To work with a large music library and use custom configuration settings
`albums` needs a database which it will create automatically after asking. When
initializing, you will be asked if you want to use the operating-system defined
user's music directory as your library. Or the `--library` option can specify
another location.

!!!tip

    To get started **without** specifying a library, use the `--dir` option
    with the `check` command (or `list` or `sql`) to work on one album instead
    of a library. When `-d`/`--dir` is specified, no information will be stored
    between runs, and `albums` will not ask for a library location or prompt to
    create a database. Try: `albums --dir /path/to/one/album check --fix`

## Basic commands

To see **all** options, run `albums --help` and `albums <command> --help`.

`albums scan` will scan the library. This happens automatically the first time
the tool is used, if there is a library in the configured location to scan.

!!!info

    The first time `scan` runs, it reads every track and image. This may take a
    long time if you have thousands of albums. Subsequent scans should only
    take a few seconds. If you interrupt the scan with ^C, it will continue
    where it left off next time.

Get a list of issues with `albums check`. Learn about using `albums` to fix
problems in [Check and Fix](./check_and_fix.md).

Most commands can be filtered. For example, to list albums matching a path
(relative path within the library), run
`albums --regex --path "Freezepop" list`.

Within a library, albums can be in sets called "collections". To create a
collection named "DAP" containing albums to sync to a Digital Audio Player, use
for example `albums -rp "Freezepop" add DAP`. Review the collection with
`albums --collection DAP list`. To copy/sync it to an SD card, see
[Synchronize](./sync.md).

You can scan a new album for tag/picture/filename/etc issues, fix them all
interactively, then add the album to your library with one command. For example:
`albums import "temp/new album 1"`.

To set up `albums` configuration options interactively, run `albums config`. See
`albums config --help` for other ways to configure.

## Global Settings

In addition to check configurations (see [Check and Fix](./check_and_fix.md)),
there are some global settings:

<!-- pyml disable line-length -->

| Name                          | Default                                      | Description                                       |
| ----------------------------- | -------------------------------------------- | ------------------------------------------------- |
| `library`                     | OS default                                   | Location of the music library                     |
| `open_folder_command`         | OS default                                   | If not blank, program to browse files in an album |
| `path_compatibility`          | `"universal"`                                | Configure what is allowed in filenames            |
| `rescan`                      | `"auto"`                                     | When to automatically rescan the library          |
| `tagger`                      | `"easytag"` (if installed)                   | External program to view and set tags in an album |
| `default_import_path`         | `"$artist/$album"`                           | Import: default path for new albums in library    |
| `default_import_path_various` | `"Compilations/$album"`                      | Import: default path for new compilation albums   |
| `more_import_paths`           | `"$A1/$artist/$album", "Soundtracks/$album"` | Import: other selectable paths for new albums     |

!!!note

    The import paths can use substitution values determined from the tags on
    the new album. Available substitutions are: `$album`, `$artist` (which may
    be the "album artist" value), `$A1` (first letter of artist name not
    including "The", or `#` for numeric), and `$a1` (lowercase version of `$A1`)

<!-- pyml enable line-length -->

**`open_folder_command`**: If this option is set, the _"Open folder..."_ menu
option runs this command. The path of the album will be the first parameter.

**`path_compatibility`**: Determines what special characters and reserved words
are allowed in filenames, whenever a check is validating or generating
filenames. The compatibility options come from
[pathvalidate](https://pathvalidate.readthedocs.io/en/latest/pages/introduction/index.html#summary):

- `"Linux"`: fewest restrictions
- `"Windows"`
- `"macOS"`
- `"POSIX"`
- `"universal"` _(default)_: most restrictions and most compatible

**`rescan`**: Rescan the library before performing other operations. If the
operation is filtered then only selected albums will be rescanned. Options:

- `always`: always scan the library so you never need to run "albums scan" but
  may be slow
- `never`: never automatically scan the library, you must run "albums scan" if
  it has changed
- `auto` _(default)_: scan on first run and before "check" or "sync" operations

**`tagger`**: If this option is set or if EasyTAG is installed, the fix menu
will have a menu option to execute an external tagging program. The path of the
album will be the first parameter.

## Tag Conversion

`albums` attempts to apply some of the same checks and rules with Vorbis
comments (FLAC, Ogg Vorbis), ID3 tags (MP3) and MP4 iTunes atoms (M4A). To
enable this, common tags like track number are converted to the typical Vorbis
comment tag names. For example, the ID3 tags TPE1 "Artist" and TPE2 "Band" are
referenced by the standard tag names "artist" and "albumartist". Or in other
words, if `albums` writes a new "album artist" to your MP3, behind the scenes
it's actually writing to the TPE2 tag.

### Track total and disc total

If track number and track total are combined in the tracknumber (or ID3 TRCK)
with a slash like "04/12" instead of being in separate tags, `albums` will see
that as "tracknumber=04" and "tracktotal=12" and be able to write to the track
number and track total field as if they were separate. The same rule applies for
disc number and disc total if combined in the discnumber (or ID3 TPOS) tag.
Storing track total and disc total this way is normal for ID3 tags.

## Risks

This software has no warranty and I am not claiming it is safe or fit for any
purpose. But if something goes very wrong, you can simply restore your backups.
If you don't have backups, maybe this tool isn't for you.

More specifically, here are some of the actual risks:

- Could overwrite correct tags with incorrect info, or rename files incorrectly,
  etc, depending on configuration, use or bugs.
- If you set a bad `sync` destination **and** use `--delete` **and** confirm or
  use `--force`, it will delete everything at the specified path.
    - Even if you set the correct `sync` location, the `--delete` option could
      delete files from your digital audio player that you wanted to keep.
- Might corrupt your music files while editing their tags due to hypothetical
  bugs in Mutagen.
- Might make corrupt copies of albums if there are bugs in the sync code.
- Might create a vector for malware living in media file metadata to attack your
  computer via hypothetical vulnerabilities in libraries or your OS.
