---
icon: lucide/search-check
---

# Check and Fix

A _check_ is a module that can report on problems with albums, such as tags,
filenames or directory structure. Some checks provide options to fix the problem
that must be selected by a user. And some checks provide a high-confidence fully
automatic fix. See below for how to use these.

Using a tool that can modify your music files automatically might have
unintended results. If it goes very badly, simply restore your backup.

!!!note

    Check configuration is stored in the `albums` database. Every check may be
    enabled or disabled. Some checks have other settings, described in
    [All Checks](./all_checks.md). To enable, disable or configure checks, run
    `albums config`.

## Check Command

To list (and optionally fix) issues, use the `albums check` command. This will
run all enabled checks, unless some check names are provided, in which case it
will run those only. No changes will be applied unless one of the fix options is
specified. You can filter what albums are examined. See `albums --help` and
`albums check --help`.

Run checks on any directory (outside the library) with the `--dir` option, which
can fix files but will not store data (such as ignoring certain checks or
marking front cover image files) Otherwise, checks will run against the most
recent scan of the library.

!!!tip

    By default `albums` automatically scans when using `check` on the library.
    You can disable this with the `rescan` setting (see [Usage](./usage.md)),
    but if you do, make sure to run `albums scan` manually whenever any changes
    are made to the library outside of `albums`.

### How to Check and Fix

These example commands demonstrate how you can use `albums` in different ways to
look for and/or fix issues.

<!-- pyml disable line-length -->

| Task                                                   | Example Command                                    |
| ------------------------------------------------------ | -------------------------------------------------- |
| Run all enabled checks on the library (no fixing)      | `albums check`                                     |
| Run all enabled checks on any folder                   | `albums --dir /path/to/an/album check`             |
| Run enabled checks in matching folders                 | `albums -m path~Foo check`                         |
| Run a specific check (and checks it requires)          | `albums check duplicate-image`                     |
| When there is a quick fix, stop and ask what to do     | `albums check --fix`                               |
| Check for fully automatic fixes but don't run them     | `albums check --preview`                           |
| Run automatic fixes on one album (exact path)          | `albums -m path="Artist/Album/" check --automatic` |
| Run automatic fixes, ask what to do for manual fixes   | `albums check --automatic --fix`                   |
| For every issue, ask what to do (even if no quick fix) | `albums check --interactive`                       |

<!-- pyml enable line-length -->

_Most parameters have abbreviations._ `-ia` _is the same as_
`--interactive --automatic`.
