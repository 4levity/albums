---
icon: lucide/rocket
---

# Overview

`albums` is a rich text-based interactive tool to help manage a library of
music, clean up metadata tags and file organization, and sync parts of the
library to digital audio players

## Project home

**[https://github.com/4levity/albums/](https://github.com/4levity/albums/)**

## License

`albums` is free software, licensed under the terms of the
[GNU General Public License Version 3](https://github.com/4levity/albums/blob/main/sample/config.toml)

## Installation

Install with `pip install albums` in an environment with Python 3.12 or newer.

## Minimum setup

If your music library happens to be in the operating system reported default
user music directory (e.g. `~/Music`) and you don't mind the `albums.db`
database file being created in the default user config directory (e.g.
`home/ivan/.config/albums/`), you can start immediately by running
`albums scan`. Otherwise, you need a configuration file. See [Usage](./usage.md)

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
  computer via hypothetical vulnerabilities in Mutagen.
