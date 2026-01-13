# albums

A command line tool to help manage a library of music albums. Focuses on albums, not individual
tracks. To this tool, an album is a folder with music files whhich are either by the same artist
or a compilation.

This tool can:
 - Mark a subset of a music library to be copied to a digital audio player or phone
 - Sync selected albums with destination (add, update if changed, remove)
 - Report on problems with tags and organization in the library

See section below for future ideas.

`albums` makes a database of album folders, tracks and metadata. It can quickly rescan the library
to detect changes and update the database. Other operations can be performed without rescanning the
library every time. In addition to data gathered from the scan, albums may be tagged with arbitrary
"collection" names.

## Requirements

With [poetry](https://python-poetry.org/) installed, run `make` to install Python dependencies,
lint, test and build. Or use `poetry` directly (refer to [Makefile](./Makefile) to see commands).

Developed and tested only on Linux. Probably works on MacOS and Windows.

## Configuration

The tool needs to know where your albums are stored.

Create a `config.ini` file with `[library]` section specifying where to find albums. See example in
[sample/config.ini](sample/config.ini).

In the `[checks]` section, you may configure options to check albums for issues with tags.

## Usage

Scan the library and create the album database with `albums scan`. The first time it runs, it will
read metadata from every track which may take a long time. When the library is changed, you should
run `albums scan` again.

List albums matching a path with a command like `albums --regex --path "Freezepop" list`.

Albums can be in sets called "collections". You could create a collection named "DAP" for albums to
sync to a Digital Audio Player: `albums --regex --p "Freezepop" add DAP`

List the albums in the collection with `albums --collection DAP list`

Sync selected albums to an SD card. Add, update or remove files under destination folder:
`albums -c DAP sync /mnt/sdcard --delete`

Check and report on possible issues with `albums check` and filter with `-c` or `-p` options.

Try `albums --help` or e.g. `albums sync --help`.

## Future

 - Select albums based on track tags, recently accessed, other
 - Support additional file formats
 - Interactively fix metadata problems detected by checks with suggested solutions
 - More checks/fixes:
   - album art (missing, not in desired format, not the same on all tracks, too small/too large)
   - track numbering issues (missing tag, missing track, filename doesn't start with track number, etc)
   - missing track-total
   - not all tracks encoded the same (file type or kbps target)
   - track filename doesn't match title
   - album folder doesn't match album name
   - parent folder doesn't match artist if using artist/album