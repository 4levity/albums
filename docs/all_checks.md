---
icon: lucide/list-checks
---

# All Checks

All checks and their configuration options.

## Order

Enabled checks will run in order on each album:

1. `duplicate-pathname` check _("Path and Filename")_
1. `illegal-pathname` check _("Path and Filename")_
1. `extra-whitespace` check _("Other Tags")_
1. All "Numbering" checks
1. Remaining "Other Tags" checks
1. All "Pictures" checks
1. Remaining "Path and Filename" checks

Within each category, the checks run in the order they are listed below.

## Dependencies

Individual checks are mostly independent, but some checks will not run on an
album unless a previous check ran and passed. For example, the specific fix from
the `disc-in-tracknumber` check should be applied before
`invalid-track-or-disc-number` flags the track number as invalid. And, when the
`invalid-image` check doesn't pass, none of the other "Pictures" checks can run.
Other dependencies are listed below.

## Checks: Path and Filename

### duplicate-pathname

To prevent issues with case-insensitive file systems (and software designed for
them), filenames should not be "case-insensitive duplicates". For example, an
album should not have two files named `folder.jpg` and `Folder.JPG`.

### illegal-pathname

Filenames should not include invalid characters or be operating system reserved
words. This check flags filenames that might cause a problem. What is allowed
depends on the `path_compatibility` global configuration setting (see
[Usage](./usage.md)).

### track-filename

Track filenames should match tags. Typically they include the track number and
title. They start with the disc number if part of a set, and include the artist
name if the album is a compilation. Filenames should be valid, as described by
`path_compatibility` and related path settings in [Usage](./usage.md).

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

The zero-padding on track number and disc number (if any) normally comes from
formatting applied to the corresponding tag value. `albums` can format the tags
with the `zero-pad-numbers` check/fix. But in some formats like **M4A**, the
tracknumber and discnumber tags don't support formatting. For such formats, if
the `zero-pad-numbers` check is enabled, the `tracknumber_pad` and
`discnumber_pad` options from _that_ check will be used to generate possibly
zero-padded `$tracknumber` and `$discnumber` substitutions in _this_ check.

<!-- pyml enable line-length -->

The default template `"$track_auto $title_auto"` generates filenames like this:

| Disc   | Track  | Title | Artist | Album Artist    | Filename           |
| ------ | ------ | ----- | ------ | --------------- | ------------------ |
| _none_ | 01     | Foo   | Bar    | _none_          | `01 Foo.mp3`       |
| _none_ | 01     | Foo   | Bar    | Bar             | `01 Foo.mp3`       |
| _none_ | 01     | Foo   | Bar    | Various Artists | `01 Bar - Foo.mp3` |
| 1      | 01     | Foo   | Bar    | _none_          | `1-01 Foo.mp3`     |
| _none_ | _none_ | Foo   | Bar    | _none_          | `Foo.mp3`          |

!!!success "Dependency"

    Requires the `"album-artist`, `artist-tag`, `track-numbering`, and
    `track-title` checks to all pass first.

**Automatic fix**: Rename all tracks according to configuration.

| Option   | Default                     | Description                    |
| -------- | --------------------------- | ------------------------------ |
| `format` | `"$track_auto $title_auto"` | Template to generate filenames |

### cover-filename

If the front cover image is in a file with a recognizable name, it should have a
consistent name. For example, `albums` recognizes `.folder.png` and
`AlbumArtSmall.jpg` and other variations as front cover images. This check flags
if one of those files exists, but the "standard" cover image file does not.

**Automatic fix**: If there is exactly one front cover file, rename or convert
it according to the options.

<!-- pyml disable line-length -->

| Option = default         | Description                                                                  |
| ------------------------ | ---------------------------------------------------------------------------- |
| `filename` = `"cover.*"` | Cover file. `.*` = keep same file type, `.png` or `.jpg` = convert if needed |
| `jpeg_quality` = **90**  | If converting to JPEG, use this quality setting                              |

<!-- pyml enable line-length -->

### album-under-album

This check reports when an album has another album in a subfolder. Maybe they
should be in separate folders or this check should be disabled. No fix offered.

## Checks: Numbering

Track number and disc number tag issues.

### disc-in-track-number

If the disc number and track number are combined in the track number tag with a
dash (i.e. track number="2-03") instead of being in separate tags, this is
treated as an error. Subsequent checks require track numbers to be numeric.

**Automatic fix**: Split the values into track number and disc number tags.

### invalid-track-or-disc-number

This check reports when an album has invalid or ambiguous values for track
number, track total, disc number or disc total. If these fields cannot be
resolved to a single valid number, they are not useful and should be removed.

Rule: for each track, if present, track/disc number/total tags should each have
a single value and that value should be a positive number (0 is not valid).

!!!success "Dependency"

    Requires the `disc-in-track-number` check to pass first.

**Automatic fix**: For each of the noted tags in each track, discard all values
that are non-numeric or 0. If exactly one unique value remains, save it.
Otherwise, delete the tag.

### disc-numbering

Reports on issues with disc number and disc total (`TPOS` in ID3). Optionally,
removes redundant disc number tag for sets of one. See configuration to control
whether multiple disc sets should be required to have all tracks in one folder.

Rules:

- If any track has disc number, all tracks should have disc number
- Disc numbers should start at 1 and be sequential (1, 2, 3...)
- If present, the disc total should be the number of distinct disc number values
  which should be the same as the highest disc number
- All tracks with disc total should also have disc number
- The selected disc total presence policy should apply
    - **"consistent"**: either all tracks have disc total, or none do
    - **"always"**: all tracks should have disc total
    - **"never"**: disc total should be removed

!!!success "Dependency"

    Requires the `invalid-track-or-disc-number` check to pass first.

**Automatic fix** for disc total policy: If the disc total policy is
"consistent" but some tracks are missing disc total, remove it from all tracks.
If the policy is "never", always remove the tag. (There is currently no
automatic fix if the policy is "always".)

<!-- pyml disable line-length -->

| Option = default                          | Description                                                     |
| ----------------------------------------- | --------------------------------------------------------------- |
| `discs_in_separate_folders` = **true**    | if true, discs from one album may be stored in separate folders |
| `remove_redundant_discnumber` = **false** | if true, disc number tag "1" can be removed if no other discs   |
| `disctotal_policy` = `"consistent"`       | Set the tag presence policy for disc total                      |

<!-- pyml enable line-length -->

!!!note

    `discs_in_separate_folders` and `remove_redundant_discnumber` cannot both
    be true. If discs are in separate folders, disc 1 might be part of a set.

> When `discs_in_separate_folders` is enabled (default), this check will
> **ignore** when an album has only one disc of a multiple disc set. But that
> also means it cannot tell whether an album is missing a disc number or whether
> disc total is correct. If you can put multiple-disc albums together in one
> folder, do that and set `discs_in_separate_folders` to **false**. Then, if
> wanted, you can also set `remove_redundant_discnumber` to **true**.

### track-numbering

Reports on several issues with track numbers and track totals, including
apparently missing tracks.

The rules are:

- Every track should have a single decimal track number
- For each disc, track numbers should start at 1 and be sequential
- For each disc, if track total is present, it should be the number of tracks on
  that disc
- All tracks with track total should also have track number
- The selected track total presence policy should apply:
    - **"consistent"**: either all tracks have track total, or none do
    - **"always"**: all tracks should have track total
    - **"never"**: track total should be removed

!!!success "Dependency"

    Requires the `disc-numbering` check to pass first.

**Automatic fix** for missing track numbers: If track number tags are missing
from some tracks but all track numbers can be guessed from the filename,
recreate track number tags from filenames.

**Automatic fix** for track total policy: If the track total policy is
"consistent" but some tracks are missing track total, remove it from all tracks.
If the policy is "never", always remove the tag. (There is currently no
automatic fix if the policy is "always".)

<!-- pyml disable line-length -->

| Option = default                     | Description                                             |
| ------------------------------------ | ------------------------------------------------------- |
| `ignore_folders` = `["misc"]`        | in all folders with these names, ignore track numbering |
| `tracktotal_policy` = `"consistent"` | Set the tag presence policy for track total             |

<!-- pyml enable line-length -->

### zero-pad-numbers

Apply selected policies for zero-padding in the track number/total and disc
number/total tags. Some media players and many file managers do not show tracks
in the correct order unless the track numbers are zero-padded, because for
example "2" comes after "10" when sorted alphabetically.

This check does nothing on **M4A** files because track numbers (and track total,
disc number, disc total) are only stored as plain unformatted numbers.

!!!success "Dependency"

    Requires the `invalid-track-or-disc-number` check to pass first.

**Automatic fix**: If no major problems detected in relevant tags, apply policy.

Choose a policy for each tag. The policy options are:

- **"ignore"**: don't check this tag
- **"never"**: do not use leading zeros
- **"if_needed"**: leading zeros when required for all values to have the same
  number of digits (same as "never" for track/disc totals)
- **"two_digit_minimum"**: all values should be at least two digits (three if
  more than 99 values)

| Option = default                          |
| ----------------------------------------- |
| `tracknumber_pad` = `"two_digit_minimum"` |
| `tracktotal_pad` = `"two_digit_minimum"`  |
| `discnumber_pad` = `"if_needed"`          |
| `disctotal_pad` = `"never"`               |

> The default settings will result in, for example, track **04** of **07** and
> disc **1** of **1**. If you set all policies to "if_needed" instead, you get,
> for example, track **4** of **7** and track **04** of **12**.

## Other Tags

Tag checks that are not related to numbering or pictures.

### extra-whitespace

None of the basic tags like album, artist, title, track number, etc. should have
extra spaces or other whitespace characters at the beginning or end.

**Automatic fix**: Remove whitespace from the beginning and end of all values
for all supported basic text tags.

### album-tag

Tracks should have `album` tags. The fix attempts to guess album name from tags
on other tracks in the folder, and the name of the folder. Choose from options.

**Automatic fix**: If there is exactly one option for the album name, use it.

<!-- pyml disable line-length -->

| Option = default              | Description                                                          |
| ----------------------------- | -------------------------------------------------------------------- |
| `ignore_folders` = `["misc"]` | a list of folder names (not paths) where this rule should be ignored |

<!-- pyml enable line-length -->

### album-artist

The "album artist" tag (e.g. `albumartist`, `TPE2`) allows many media players to
group tracks in the same album when the "artist" is not the same on all the
tracks.

Rules:

- If any tracks have different artists, all tracks should have the same album
  artist.
- If any track has album artist, all tracks should have the same album artist.

The fix offers candidates found in the tags plus the option "Various Artists".
It can also apply a policy from the options below.

**Automatic fix**: If the album artist is or would be redundant, and one of the
optional policies below is enabled, apply the policy.

<!-- pyml disable line-length -->

| Option = default                | Description                                                                      |
| ------------------------------- | -------------------------------------------------------------------------------- |
| `remove_redundant` = **false**  | If **true** album artist should be _removed_ when all artist values are the same |
| `require_redundant` = **false** | If **true** album artist is _required_ even if all artist values are the same    |

<!-- pyml enable line-length -->

### artist-tag

An "artist" should be present on all tracks. If it is _missing_ from any tracks,
candidates to fix include the values for artist and album artist taken from all
tracks in the album.

If the parent folder containing the album folder is not a prohibited name, it is
also a candidate. Prohibited names can be configured with an option.

!!!success "Dependency"

    Requires the `album-artist` check to pass first.

**Automatic fix**: If there is exactly one candidate for artist name, apply it
to all tracks that do not have an artist tag.

<!-- pyml disable line-length -->

| Option = default                                                                                            |
| ----------------------------------------------------------------------------------------------------------- |
| `ignore_parent_folders` = `["compilation", "compilations", "soundtrack", "soundtracks", "various artists"]` |

<!-- pyml enable line-length -->

### single-value-tags

If present, the specified tags should not have multiple values _in the same
track_. Many multiple-value tags are valid, but they might be unintended, and
might cause unpredictable results with various media players. The fix for this
check provides options to concatenate multiple values into a single value, after
removing duplicates.

Other specific checks may enforce a single value for certain tags such as track
number.

To configure how `albums` will combine multiple values, use the `concatenators`
option. Pay attention to whether or not the separator includes extra spaces -
the first option gives "Alice / Bob" and the second is "Alice/Bob".

By default, whichever concatenator is first will be used when automatic fix is
requested. To disable this, change the automatic_concatenate option.

**Automatic fix**: If a track has **duplicate** values for the tag, the
automatic fix will remove them. And if `automatic_concatenate` is enabled
(default), unique values will be combined into a single value.

| Option = default                        |
| --------------------------------------- |
| `tags` = `["artist", "title"]`          |
| `concatenators` = `[" / ", "/", " - "]` |
| `automatic_concatenate` = **true**      |

### track-title

Each track should have at least one title tag. This check doesn't care if a
track has more than one title. If the track doesn't have a title, it can be
guessed from the filename, as long as the filename looks similar to one of these
examples:

- `01 the title.flac`
- `01. the title.mp3`
- `01 - the title.mp3`
- `1-03 - the title.flac`
- `the title.flac` _(if nothing else matches)_

If the filename looks like a track number only, no title guess will be made.
However, if the title doesn't match any recognized pattern, the guess will be
the whole filename except for the extension.

**Automatic fix**: If every tag that has a missing title also has a filename
from which a title can be guessed, fill in all empty titles.

## Pictures

These checks operate on embedded pictures and image files in the album folder.

In some media formats including FLAC files, embedded images are classified with
the "picture type" codes originally defined for ID3v2 `APIC` frames.

When checks refer to the "cover" or "front cover" this means images classified
as `COVER_FRONT` (0x03). If an embedded image does not have a picture type (such
as `covr` atom in M4A files) the image is assumed to be a front cover.

Image files are also considered front covers if they are **png**,
**jpeg**/**jpg** or **gif** and they have the word "folder", "cover",
"thumbnail" or "album" in the filename.

### invalid-image

During the scan, `albums` tries to load every embedded image and supported image
file. If it fails, the image is probably corrupt and a `load_issue error` will
be stored. This check reports on all images that could not be loaded.

!!!tip "Image Loading"

    `albums` does not rely on the file extension or the reported MIME type to
    load images. If the image data is valid, `albums` should be able to load it.
    When the MIME type is wrong, it will be reported (and can be fixed) by the
    `picture-metadata` check.

The fix will list and offer to delete all image files that cannot be loaded, and
remove all embedded images that cannot be loaded.

### duplicate-image

Each of the tracks in an album may have the same images embedded. But other
duplicate image data is not useful. Rules:

- Each of the pictures embedded in a track should be a different image (don't
  have the same image embedded twice)
- Image files should not be exact duplicates of other image files

!!!success "Dependency"

    Requires the `invalid-image` check to pass first.

**Automatic fix**: If several image files (not embedded) contain the exact same
image contents, keep the one with the shortest filename and delete the rest.

<!-- pyml disable line-length -->

| Option = default         | Description                                                            |
| ------------------------ | ---------------------------------------------------------------------- |
| `cover_only` = **false** | if enabled, ignore duplicates for picture types other than COVER_FRONT |

<!-- pyml enable line-length -->

### picture-metadata

FLAC files
[store metadata about embedded pictures](https://www.rfc-editor.org/rfc/rfc9639.html#name-picture)
(MIME type, dimensions). Ogg Vorbis uses a comment with the same structure. ID3
tags include the MIME type of the image in the APIC frame, etc. This check loads
the image data and compares the reported MIME type and dimensions (if present)
to the real image data.

**Automatic fix**: For each file with incorrect metadata, re-embed all the
images with the same image data and correct metadata. Fix not yet available for
other formats.

!!!success "Dependency"

    Requires the `invalid-image` check to pass first.

### album-art

Image files embedded in tracks should be a reasonable size and in a
widely-supported format.

Rules:

- **Embedded** images should not be very large files (see options)
- **Embedded** images should be in PNG or JPEG format (not GIF or other)

!!!success "Dependency"

    Requires the `invalid-image` check to pass first.

**Automatic fix**: For each unique embedded image that is too large or not a
preferred image type, extract the image to a file and un-embed it. If one of the
images un-embedded is cover art, the extracted file can be used by subsequent
checks to re-embed proper cover art.

<!-- pyml disable line-length -->

| Option = default                  | Description                                                         |
| --------------------------------- | ------------------------------------------------------------------- |
| `embedded_size_max` = **4194304** | embedded image data maximum size (not including container encoding) |

<!-- pyml enable line-length -->

### cover-available

If any track has embedded pictures, or if there are any image files in the
folder, the album is expected to have front cover art, meaning one of the
embedded images or filenames should indicate that it's cover art. Optionally,
cover art can be required for all albums (see settings).

If there are any non-cover images available, this check offers a fix to select
one of them as the front cover by renaming or extracting it to an image file
with a standard name.

Rules:

- If there are any embedded images or image files, one or more of them should be
  in a file `cover.jpg` (or similar) to be recognized as the front cover image
- When "cover_required" setting is true, a front cover image **must** be present

!!!success "Dependency"

    Requires the `duplicate-image` check to pass first.

**Automatic fix**: If the album has no front cover art, but there is exactly one
unique image (embedded and/or image file), make that image the cover art by
renaming the image file to `cover.jpg`/`.png`/etc. **or** by extracting the
embedded image from one of the tracks to `cover.jpg` or `.png`.

<!-- pyml disable line-length -->

| Option = default             | Description                                                 |
| ---------------------------- | ----------------------------------------------------------- |
| `cover_required` = **false** | if **true** every album should have correct front cover art |

<!-- pyml enable line-length -->

### cover-unique

Usually, albums should have a single unique image as cover art, or, one cover
image embedded in the tracks plus a higher-resolution image file.

Rules:

- All front cover art associated with the album should be the same image,
  including embedded `COVER_FRONT` as well as image files matching the filenames
  above, **except:**
- There can be two unique cover images, if one of them (like a high-res version
  of the cover) is a file and it is marked in `albums` as "front cover source"

Tracks may have any number of embedded images that are not marked as
`COVER_FRONT`. Other image files in the album folder, where the filename does
not match the expected cover art filenames above, will be treated as picture
type `OTHER`.

!!!success "Dependency"

    Requires the `duplicate-image` check to pass first.

**Automatic fix**: If there are multiple cover images but one of them is a file
that is larger than the other files and/or embedded images, mark that file as
"front cover source" so that file will no longer count as a duplicate. This
might not completely fix the check if there are more front cover images. The
next automatic fix would delete the other image files identified as cover art:

**Automatic fix**: If there are multiple image files (not embedded) recognized
as front cover source by their filenames, and one of them has already been
marked as "front cover source", delete the other front cover art image files.

### conflicting-embedded

Within each track, there should not be more than one picture for a given picture
type (or optionally only for front cover pictures -- see options). For example,
even if tracks have unique "front cover" images, a _single_ track should not
have more than one embedded image marked as "front cover".

No automated fix yet.

!!!success "Dependency"

    Requires the `duplicate-image` check to pass first.

<!-- pyml disable line-length -->

| Option = default         | Description                                                           |
| ------------------------ | --------------------------------------------------------------------- |
| `cover_only` = **false** | if enabled, ignore multiple pictures for types other than COVER_FRONT |

<!-- pyml enable line-length -->

### cover-dimensions

Images treated as picture type COVER_FRONT should be square and within a range
of acceptable sizes.

Rules:

- If an image is marked as front cover source, only that image is evaluated.
  Using the front cover source to fix embedded images is a separate task.
- The width/height of cover art should not be too small or large (see options)
- Cover art should be square (see options)

!!!success "Dependency"

    Requires the `cover-available` check to pass first.

**Automatic fix**: If the front cover image (embedded or in a file) is not as
square as the `squareness` setting but at least as square as the
`fixable_squareness` setting, fix it by cropping first (see options), and if
necessary squashing it the rest of the way. The new square cover image will be
saved as a file with the configured type and marked as "front cover source" for
the album. If the unsquare source was an image file, it will be deleted.

If **embedded** front cover images are present they are **not** changed by this
fix. The new cover image file is set as "front cover source".

<!-- pyml disable line-length -->

| Option = default                   | Description                                                               |
| ---------------------------------- | ------------------------------------------------------------------------- |
| `squareness` = **0.98**            | cover art minimum width/height ratio - **1** for square, **0** to disable |
| `max_pixels` = **2048**            | front cover art should not be larger than this width/height               |
| `min_pixels` = **100**             | front cover art should be at least this width/height                      |
| `fixable_squareness` = **0.8**     | if image is at least this square, offer automatic fix with crop + squash  |
| `max_crop` = **0.03**              | crop at most this much (0.03 = lose max 1.5% of image from two sides)     |
| `create_mime_type` = `"image/png"` | MIME type when creating cover image files, blank to use source type       |
| `create_jpeg_quality` = **80**     | If creating image with MIME type image/jpeg, use this quality (1 - 95)    |

<!-- pyml enable line-length -->

### cover-embedded

If there is any front cover image (file or embedded), all tracks should have
_some_ front cover image embedded. It should not be larger than the maximum size
and should be the required MIME type if set (see `max_height_width` and
`require_mime_type` options).

Furthermore, if there is a front cover image that has been marked as "front
cover source" in `albums`, all tracks should have a front cover image that
exactly matches the specs (dimensions and MIME type) configured in this check
(see `create_*` options).

When there are existing embedded covers that do not meet the above requirements,
the presence of more than one unique front cover image will prevent automatic
fixes by this check, to avoid automatically overwriting per-track cover art.

When the above requirements above **are** met, this check will pass. To cause
`albums` to embed new cover art when there is "good enough" cover art already,
place high resolution cover art in the folder named `cover.jpg` (or another
recognized front cover filename) and run the `cover-unique` check, which should
offer to mark the new art as "front cover source". Subsequently, as long as the
size or MIME type of the previous embedded cover is not exactly the same as what
this check is configured to generate, the new cover can be embedded into tracks
by this check.

!!!success "Dependency"

    Requires the `duplicate-image` check to pass first. For automation,
    `cover-unique` and `cover-dimensions` are recommended.

**Automatic fix**: When there is a front cover source file and there is not more
than one unique front cover image embedded in the tracks, generate a new cover
from the cover source and embed it in every track, replacing any existing cover.

**Automatic fix**: When there is no front cover source, but there is only one
unique cover image, that image can be extracted to a file (if it is not already
a file) and marked as front cover source. Rechecking will then offer the
automatic fix above.

<!-- pyml disable line-length -->

| Option = default                    | Description                                                            |
| ----------------------------------- | ---------------------------------------------------------------------- |
| `max_height_width` = **1000**       | Max height/width of the embedded cover _(see note below)_              |
| `require_mime_type` = _[blank]_     | If not blank, required MIME type for embedded cover _(see note below)_ |
| `create_mime_type` = `"image/jpeg"` | MIME type for embedding cover images (image/jpeg or image/png)         |
| `create_max_height_width` = **600** | Target embedded cover height/width (source can scale down, not up)     |
| `create_jpeg_quality` = **80**      | If `create_mime_type` is image/jpeg, use this quality (1 - 95)         |

<!-- pyml enable line-length -->

Note: The `max_height_width` and `require_mime_type` settings only apply to
albums where no "front cover source" image is defined.
