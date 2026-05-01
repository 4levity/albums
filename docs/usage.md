---
icon: lucide/user
---

# Usage

## Initial Setup

To work with a large music library or use custom configuration settings,
`albums` needs a database which is created by running `albums init`. Some parts
of this documentation assume that `albums init` has been run.

!!!tip

    To get started **without** specifying a library, use the `--dir` option
    with the `check` command to work on a folder instead of a library. When
    `-d`/`--dir` is specified, no information will be stored between runs. Try:
    `albums --dir /path/to/one/album check --fix`

## Options, Command, Args

Usage: **albums** \[**OPTIONS**\] **COMMAND** \[**ARGS**\]

1. **Options** come _before_ the command. Some options are for selecting which
   albums or folders the following command will operate on.
1. **Command** must be specified, like "list" or "check".
1. **Args** some commands take arguments which come _after_ the command.

## Basic Commands

To see **all** options, run `albums --help` and `albums <command> --help`.

`albums scan` scans the library. This happens by default after `init` and when
running some other commands.

!!!info

    The first time `scan` runs, it reads every track and image. This may take a
    long time if you have thousands of albums. Subsequent scans should only
    take a few seconds. If you interrupt the scan with ^C, it will continue
    where it left off next time.

`albums list` lists albums (folders), including total size and play time.

`albums check` finds issues with albums. Learn about using `albums` to review
and fix problems in [Check and Fix](./check_and_fix.md).

## Filtering

Most commands can be filtered with options before the command. For example, to
list albums matching a partial path (relative path within the library), you
could run `albums --regex --path Nirvana list`. See help for options.

### --match

The `--match` / `-m` option provides several ways to filter albums. The same key
may be specified more than once. The parameter to `-m` may be one of these
comparisons:

- `key=value`
- `key!=value` (not equals)
- `key~regex` (matches regular expression)
- `key<value`
- `key<=value`
- `key>value`
- `key>=value`

<!-- pyml disable line-length -->

| Key              | Description                                                     | Example                        |
| ---------------- | --------------------------------------------------------------- | ------------------------------ |
| **path**         | match _any_ of the given paths within the library               | `-m path~Soundtracks`          |
| **tag:XXX**      | _any_ track in the album matches _all_ specified tag conditions | `-m tag:artist=Queen`          |
| **collection**   | be in _any_ of the specified "collections"                      | `-m collection=favorites`      |
| **ignore_check** | ignore _any_ of the given checks                                | `-m ignore_check=cover-unique` |

<!-- pyml enable line-length -->

### --invert

This option inverts the sense of the filter. All albums that **do not** match
the specified conditions will be included.

## More Commands

`add` and `remove` - These commands add or remove associations between the
selected albums and arbitrary named "collections," which can be used to filter
future operations.

`ignore` and `notice` - These commands cause the selected albums to ignore or
stop ignoring certain checks.

`import` - Search a folder outside the library for new albums, check them for
tag/picture/filename/etc issues, fix everything interactively, then add them to
the library - see [Import](./import.md).

`sync` - Copy/sync selected albums to a storage device or player - see
[Synchronize](./sync.md).

### Config

To set up `albums` configuration options interactively, run `albums config`. See
`albums config --help` for other ways to configure. Configuration options for
individual checks are described in [All Checks](./all_checks.md).

#### Global Settings

<!-- pyml disable line-length -->

| Name                          | Default                                      | Description                                       |
| ----------------------------- | -------------------------------------------- | ------------------------------------------------- |
| `library`                     | OS default                                   | Location of the music library                     |
| `open_folder_command`         | OS default                                   | If not blank, program to browse files in an album |
| `path_compatibility`          | `"universal"`                                | Configure what is allowed in filenames            |
| `path_replace_slash`          | `"-"` _(a dash)_                             | Replace a "/" character in path element with this |
| `path_replace_invalid`        | `""` _(nothing)_                             | Replace any other illegal character with this     |
| `rescan`                      | `"auto"`                                     | When to automatically rescan the library          |
| `tagger`                      | `"easytag"` (if installed)                   | External program to view and set tags in an album |
| `id3v1`                       | `"UPDATE"`                                   | Policy for ID3 version 1 tags                     |
| `default_import_path`         | `"$artist/$album"`                           | Import command option - see [Import](./import.md) |
| `default_import_path_various` | `"Compilations/$album"`                      | Import command option                             |
| `more_import_paths`           | `"$A1/$artist/$album", "Soundtracks/$album"` | Import command option                             |
| `import_scan_max_paths`       | **250**                                      | Import command option                             |

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
operation is filtered then only selected albums will be re-scanned. Options:

- `always`: always scan the library so you never need to run "albums scan" but
  may be slow
- `never`: never automatically scan the library, you must run "albums scan" if
  it has changed
- `auto` _(default)_: scan on first run and before "check" or "sync" operations

**`tagger`**: If this option is set or if EasyTAG is installed, the fix menu
will have a menu option to execute an external tagging program. The path of the
album will be the first parameter.

**`id3v1`**: ID3 version 2 tags are always used. This setting describes what to
do with ID3 version 1 tags. Options are **REMOVE** (ID3v1 tags will be removed),
**UPDATE** (ID3v1 tags will be updated but not added), or **CREATE** (ID3v1 tags
will be created and/or updated).
