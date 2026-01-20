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
lint, test and build. Or use `poetry` directly.

Developed/tested only on Linux. Probably works on MacOS. Interactive fixer may not work on Windows.

## Configuration

The tool needs to know where your albums are. The default is the operating-system defined user's
music directory. To use a library in another location, create a `config.toml` file with `[library]`
section specifying where to find albums. See example in [sample/config.toml](sample/config.toml).

In the `[checks]` sections, you may configure options to check albums for issues with tags.

## Usage

Scan the library and create the album database with `albums scan`. The first time it runs, it will
read metadata from every track which may take a long time. When the library is changed, you should
run `albums scan` again.

List albums matching a path with a command like `albums --regex --path "Freezepop" list`.

Albums can be in sets called "collections". You could create a collection named "DAP" for albums to
sync to a Digital Audio Player: `albums -r -p "Freezepop" add DAP`

List the albums in the collection with `albums --collection DAP list`

Sync selected albums to an SD card. Add, update or remove files under destination folder:
`albums -c DAP sync /mnt/sdcard --delete`

Check and report on possible issues with `albums check` and filter with `-c` or `-p` options.

Try `albums --help` or e.g. `albums sync --help`.

## Developing

Refer to [Makefile](./Makefile).

After scanning a collection, use the `sqlite3` command line tool with the database file to explore
via SQL. Install [GraphViz](https://graphviz.org/) and `make diagram` for a reference diagram. 

## Future

 - Select albums based on track tags, recently accessed, other
 - Support additional file formats
   - Comprehend standard tags (artist, album, title. track)
   - For MP4 (M4A, M4B, M4P) and other files
   - Add other extensions to scan
 - Interactively fix metadata problems detected by checks with suggested solutions
 - More checks/fixes:
   - album art (missing, not in desired format, not the same on all tracks, too small/too large)
   - track numbering issues (missing tag, missing track, filename doesn't start with track number, etc)
   - missing track-total
   - low bitrate or suboptimal codec
   - not all tracks encoded the same (file type or kbps target)
   - track filename doesn't match title
   - album folder doesn't match album name  
   - parent folder doesn't match artist if using artist/album