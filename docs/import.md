---
icon: lucide/folder-up
---

# Import

After setting up a library and configuring checks, albums can check new albums
and then copy them into the library.

Example: `albums import Downloads --automatic`

## One at a Time

For each album found, `import` will run all enabled checks. If `--automatic` is
specified, apply automatic fixes. Stop for all failed checks.

Every issue found must be resolved, either by fixing it or selecting the option
to ignore it. At the end, the album will be copied to the library.

## Destination Pattern

To determine where to put new albums in your library, define patterns that use
substitution values from tags. The patterns, configured in global settings, are:

- `default_import_path` - path for regular albums associated with an artist
- `default_import_path_various` - path for compilations
- `more_import_paths` - additional choices to display in interactive mode

When importing an album, all of the above folder names are generated, and if any
of them exist, the process will stop and ask for confirmation.

If `--automatic` is specified, albums uses either `default_import_path` or
`default_import_path_various` after looking at the Artist and Album Artist
fields to determine whether it is a compilation. If automatic mode is not
enabled, you are prompted to select from any of the configured path options.

These $variables may be used in the path templates:

| Variable    | Description                                                  |
| ----------- | ------------------------------------------------------------ |
| **$album**  | Album field value                                            |
| **$artist** | Artist or Album Artist field value                           |
| **$A1**     | First letter of artist or "#" for numeric, not including The |
| **$a1**     | Lowercase version of **$A1**                                 |

When there are conflicting values in different tracks, the most frequent value
is used.

## Completing

At the end, the library will be re-scanned.

Currently, if you ignore a check or mark an image file as cover source while
importing an album, those attributes are not imported. So those checks or
unmarked cover source files may flag again next time the library is checked.
