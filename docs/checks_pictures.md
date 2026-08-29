---
icon: lucide/list-checks
---

# Checks: Pictures

These checks operate on embedded pictures and image files in the album folder.

In some media formats including FLAC files, embedded images are classified with
the "picture type" codes originally defined for ID3v2 `APIC` frames.

When checks refer to the "cover" or "front cover" this means images classified
as `COVER_FRONT` (0x03). If an embedded image does not have an explicit picture
type (such as `covr` atom in M4A files), the type `COVER_FRONT` is assumed.

Image files are also considered front covers if they have the word "folder",
"cover", "thumbnail" or "album" in the filename.

## invalid-image

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

## duplicate-image

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

## picture-metadata

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

## album-art

Embedded images should be a reasonable size and in a
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

## cover-available

If any track has embedded pictures, or if there are any image files in the
folder, the album is expected to have front cover art, meaning one of the
embedded images or image files should be recognizable as cover art. Optionally,
cover art can be required for all albums (see settings).

If there are any non-cover images available, this check offers a fix to select
one of them as the front cover by renaming or extracting it to an image file
with a standard name.

Rules:

- If there are any embedded images or image files, one or more of them should be
  in a file `cover.jpg` (or similar) to be recognized as the front cover image.
- When "cover_required" setting is true, a front cover image **must** be
  present. If a download tool is available, it can be tried (see below).

!!!success "Dependency"

    Requires the `duplicate-image` check to pass first.

**Automatic fix**: If the album has no front cover art, but there is exactly one
unique image (embedded and/or image file), make that image the cover art by
renaming the image file to `cover.jpg`/`.png`/etc. **or** by extracting the
embedded image from one of the tracks to `cover.jpg` or `.png`.

**Automatic fix**: If the album has no front cover art, **and** there is no
other art embedded or in the folder that can be used as cover art, **and**
`cover_required` is enabled, **and** `get_cover_command` is set or the default
tool [SACAD](https://github.com/desbma/sacad) is found: run the external tool to
try to download cover art.

!!!warning

    If you use the automatic fix with `cover_required` enabled, and a tool is
    available but the tool fails to download an image, the fix will keep trying
    every time you run the check again.

The `get_cover_command` option is a template. The template substitutions are:

| Substitution    | Example             | Description                 |
| --------------- | ------------------- | --------------------------- |
| **`$album`**    | `Album Name`        | Album name                  |
| **`$artist`**   | `The Artist`        | Album artist                |
| **`$filename`** | `cover.jpg`         | The cover filename to use\* |
| **`$path`**     | `/library/foo/bar/` | Path to album               |

\* - Cover filename is taken from \*_cover-filename_ configuration

If [SACAD](https://github.com/desbma/sacad) is installed (assumed if the command
`sacad` and `sacad_r` are both found on the path), the default
`get_cover_command` will be set to:

    sacad --preserve-format --size-tolerance 60 $artist $album 1200 $filename

<!-- pyml disable line-length -->

| Option = default             | Description                                                 |
| ---------------------------- | ----------------------------------------------------------- |
| `cover_required` = **false** | if **true** every album should have correct front cover art |
| `get_cover_command`          | template for command/script that retrieves cover art        |

<!-- pyml enable line-length -->

## cover-unique

Usually, albums should have a single unique image as cover art, or one cover
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

## conflicting-embedded

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

## cover-dimensions

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
the album. If the unsquare source is an image file, it will be deleted.

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

## cover-embedded

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

When the above requirements **are** met, this check will pass. To cause
`albums` to embed new cover art when there is "good enough" cover art already,
place high resolution cover art in the folder named `cover.jpg` (or another
recognized front cover filename) and run the `cover-unique` check, which should
offer to mark the new art as "front cover source". Afterwards, this check will
embed the new cover into the tracks, as long as the previously embedded
cover's size or MIME type differs from what this check is configured to
generate.

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
