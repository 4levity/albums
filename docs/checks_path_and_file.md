---
icon: lucide/list-checks
---

# Checks: Path and File

## duplicate-pathname

To prevent issues with case-insensitive file systems (and software designed for
them), filenames should not be "case-insensitive duplicates". For example, an
album should not have two files named `folder.jpg` and `Folder.JPG`.

## illegal-pathname

Filenames should not include invalid characters or be operating system reserved
words. This check flags filenames that might cause a problem. What is allowed
and how illegal filenames are sanitized depends on the `path_compatibility` and
related settings (see [Usage](./usage.md)).

**Automatic fix**: Rename any tracks with illegal names, according to
configuration.

## file-extension

For best compatibility, track filename extensions should be lowercase. For
example, an MP3 file should end with **.mp3** rather than **.MP3**. This check
only examines scanned files with recognized extensions. Files not scanned by
`albums` are ignored.

**Automatic fix**: Rename selected files with all-lowercase file extensions.

| Option          | Default   | Description                                 |
| --------------- | --------- | ------------------------------------------- |
| `lowercase_all` | **false** | If true, check known image/video extensions |

## folder-name

The folder name for each album should indicate the contents. For example, it may
be the name of the album. Folder names should be valid, as described by
`path_compatibility` and related settings in [Usage](./usage.md).

The folder name format is a template string. The template substitutions are:

| Substitution  | Example      | Description  |
| ------------- | ------------ | ------------ |
| **`$album`**  | `Album Name` | Album name   |
| **`$artist`** | `The Artist` | Album artist |

**Automatic fix**: Rename the album folder according to the configured format.

| Option           | Default    | Description                       |
| ---------------- | ---------- | --------------------------------- |
| `format`         | `"$album"` | Template to generate folder names |
| `ignore_folders` | `["misc"]` | Ignore folders with these names   |

## track-filename

Track filenames should match relevant field values. Typically they include the
track number and title. They start with the disc number if part of a set, and
include the artist name if the album is a compilation. Filenames should be
valid, as described by `path_compatibility` and related settings in
[Usage](./usage.md).

The filename format is a template string. The template substitutions are:

<!-- pyml disable line-length -->

| Substitution       | Example                     | Description                                                   |
| ------------------ | --------------------------- | ------------------------------------------------------------- |
| **`$track_auto`**  | `1-02` or `02`              | Disc#-Track# if there is a Disc#, or just Track#              |
| **`$tracknumber`** | `02`                        | Track# only (blank if none)                                   |
| **`$discnumber`**  | `1`                         | Disc# only (blank if none)                                    |
| **`$title_auto`**  | `Artist - Title` or `Title` | "Artist - Title" if artist is not album artist, or just Title |
| **`$artist`**      | `Artist`                    | Track artist                                                  |
| **`$title`**       | `Title`                     | Track title                                                   |

<!-- pyml enable line-length -->

The zero-padding on track number and disc number (if any) normally comes from
formatting applied to the corresponding field. `albums` can format the fields
with the `zero-pad-numbers` check/fix. But in some formats like **M4A**, the
tracknumber and discnumber fields don't support formatting. For such formats, if
the `zero-pad-numbers` check is enabled, the `tracknumber_pad` and
`discnumber_pad` options from _that_ check will be used to generate possibly
zero-padded `$tracknumber` and `$discnumber` substitutions in _this_ check.

The default template `"$track_auto $title_auto"` generates filenames like this:

| Disc   | Track  | Title | Artist | Album Artist    | Filename           |
| ------ | ------ | ----- | ------ | --------------- | ------------------ |
| _none_ | 01     | Foo   | Bar    | _none_          | `01 Foo.mp3`       |
| _none_ | 01     | Foo   | Bar    | Bar             | `01 Foo.mp3`       |
| _none_ | 01     | Foo   | Bar    | Various Artists | `01 Bar - Foo.mp3` |
| 1      | 01     | Foo   | Bar    | _none_          | `1-01 Foo.mp3`     |
| _none_ | _none_ | Foo   | Bar    | _none_          | `Foo.mp3`          |

!!!success "Dependency"

    Requires the `album-artist`, `artist`, `track-numbering`, and
    `track-title` checks to all pass first.

**Automatic fix**: Rename all tracks according to configuration.

| Option   | Default                     | Description                    |
| -------- | --------------------------- | ------------------------------ |
| `format` | `"$track_auto $title_auto"` | Template to generate filenames |

## cover-filename

If the front cover image is in a file with a recognizable name, that file
should have the standard name. For example, `albums` recognizes `.folder.png`
and `AlbumArtSmall.jpg` and other variations as front cover images. This check
flags if one of those files exists, but the "standard" cover image file does
not.

**Automatic fix**: If there is exactly one front cover file, rename or convert
it according to the options.

<!-- pyml disable line-length -->

| Option = default         | Description                                                                  |
| ------------------------ | ---------------------------------------------------------------------------- |
| `filename` = `"cover.*"` | Cover file. `.*` = keep same file type, `.png` or `.jpg` = convert if needed |
| `jpeg_quality` = **90**  | If converting to JPEG, use this quality setting                              |

<!-- pyml enable line-length -->

## album-under-album

This check reports when an album has another album in a subfolder. Maybe they
should be in separate folders or this check should be disabled. No fix offered.

## unreadable-track

This check runs before checking tags and fails if the tagger cannot open or
detect streams in a track. This is probably because the file is corrupt. The fix
offers to rename any unreadable tracks by adding `.unreadable` to the end of the
filename, preserving the file but causing it to be ignored. The fix is **not**
automatic.
