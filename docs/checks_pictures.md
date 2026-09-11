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

**Automatic fix**: If the same image is embedded more than once in a single
track, remove the duplicate embedded images (keep the first). This is lossless
because the image data is identical. (WMA/ASF embedded images are read-only, so
duplicates there are reported but not removed.) If several image files (not
embedded) contain the exact same image contents, keep the one with the shortest
filename and delete the rest.

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

Embedded images should be a reasonable size and in a widely-supported format.

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

If any track has embedded pictures or image files exist in the folder, the album
is expected to have front cover art — one of the embedded images or image files
should be recognizable as cover art. Optionally, cover art can be required for
all albums (see settings).

If non-cover images are available, this check offers a fix to select one as the
front cover by renaming or extracting it to an image file with a standard name.

### Rules

- If there are any embedded images or image files, one or more should be in a
  file `cover.jpg` (or similar) to be recognized as the front cover image.
- When the `cover_required` setting is true, a front cover image **must** be
  present. If a download tool is available, it can be tried.

!!!success "Dependency"

    Requires the `duplicate-image` check to pass first.

### Automatic fixes

**Single unique image**: If the album has no front cover art but there is
exactly one unique image (embedded and/or image file), make that image the cover
art by renaming the image file to `cover.jpg`/`.png`/etc. **or** by extracting
the embedded image from one of the tracks.

**Download cover art**: If the album has no front cover art, **and** there is no
other art embedded or in the folder that can be used as cover art, **and**
`cover_required` is enabled, **and** `get_cover_command` is set or the default
tool [SACAD](https://github.com/desbma/sacad) is found: run the external tool to
try to download cover art.

!!!warning

    If you use the automatic fix with `cover_required` enabled, and a tool is
    available but fails to download an image, the fix will keep trying every
    time you run the check again.

### Cover download command

The `get_cover_command` option is a template. The template substitutions are:

| Substitution    | Example             | Description                 |
| --------------- | ------------------- | --------------------------- |
| **`$album`**    | `Album Name`        | Album name                  |
| **`$artist`**   | `The Artist`        | Album artist                |
| **`$filename`** | `cover.jpg`         | The cover filename to use\* |
| **`$path`**     | `/library/foo/bar/` | Path to album               |

\* - Cover filename is taken from the `cover-filename` configuration.

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

Albums should have a single unique image as cover art, or one cover image
embedded in the tracks plus a higher-resolution image file.

### Rules (cover-unique)

- All front cover art associated with the album should be the same image,
  including embedded `COVER_FRONT` and image files matching the expected cover
  filenames.
- **Exception**: there can be two unique cover images if one of them (e.g. a
  high-res version) is a file marked in `albums` as "front cover source".

Non-cover image files (not matching expected cover filenames) are treated as
picture type `OTHER`. Tracks may have any number of non-cover embedded images.

!!!success "Dependency"

    Requires the `duplicate-image` check to pass first.

### Automatic fixes (cover-unique)

**Mark high-res file**: If there are multiple cover images but one is a file
larger than the others, mark that file as "front cover source" so it no longer
counts as a duplicate.

**Delete extras**: If there are multiple image files recognized as front cover
source by their filenames, and one has already been marked as "front cover
source", delete the others.

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

Cover art images should be square and within a range of acceptable sizes.

### Rules (cover-dimensions)

- If an image is marked as front cover source, only that image is evaluated.
  Using the front cover source to fix embedded images is a separate task.
- Width/height should not be too small or large (see options below).
- Cover art should be square (see options below).

!!!success "Dependency"

    Requires the `cover-available` check to pass first.

### Automatic fix (cover-dimensions)

If the front cover image (embedded or in a file) is not as square as the
`squareness` setting but at least as square as the `fixable_squareness` setting,
fix it by cropping first, then squashing the rest of the way. The new square
cover image is saved as a file and marked as "front cover source". If the
unsquare source is an image file, it is deleted.

**Embedded** front cover images are **not** changed by this fix — only the file
source is modified.

<!-- pyml disable line-length -->

| Option = default                   | Description                                                               |
| ---------------------------------- | ------------------------------------------------------------------------- |
| `squareness` = **0.98**            | cover art minimum width/height ratio — **1** for square, **0** to disable |
| `max_pixels` = **2048**            | front cover art should not be larger than this width/height               |
| `min_pixels` = **100**             | front cover art should be at least this width/height                      |
| `fixable_squareness` = **0.8**     | if image is at least this square, offer automatic fix with crop + squash  |
| `max_crop` = **0.03**              | crop at most this much (0.03 = lose max 1.5% of image from two sides)     |
| `create_mime_type` = `"image/png"` | MIME type when creating cover image files, blank to use source type       |
| `create_jpeg_quality` = **80**     | If creating image with MIME type image/jpeg, use this quality (1 - 95)    |

<!-- pyml enable line-length -->

## cover-embedded

If any front cover image exists (file or embedded), all tracks should have it
embedded. The embedded cover should not exceed the maximum size and should use
the required MIME type if set (see `max_height_width` and `require_mime_type`).

If a "front cover source" image has been marked in `albums`, all tracks should
have a front cover image matching the specs (dimensions and MIME type)
configured here (see `create_*` options).

### How it works

When existing embedded covers don't meet requirements, the presence of more than
one unique front cover image will **prevent** automatic fixes — this avoids
overwriting per-track cover art. When requirements **are** met, the check
passes.

To embed new cover art when "good enough" cover already exists:

1. Place high-resolution cover art as `cover.jpg` (or another recognized name)
2. Run the `cover-unique` check to mark it as "front cover source"
3. Re-run `cover-embedded` — it will embed the new cover if the existing one's
   size or MIME type differs from the configured specs.

!!!success "Dependency"

    Requires the `duplicate-image` check to pass first. For full automation,
    `cover-unique` and `cover-dimensions` are recommended.

### Automatic fixes (cover-embedded)

**From cover source**: When there is a front cover source file and no more than
one unique front cover image embedded, generate a new cover from the source and
embed it in every track, replacing any existing cover.

**Create cover source**: When there is no front cover source but only one unique
cover image, extract it to a file and mark it as front cover source. Rechecking
will then offer the fix above.

<!-- pyml disable line-length -->

| Option = default                    | Description                                                            |
| ----------------------------------- | ---------------------------------------------------------------------- |
| `max_height_width` = **1000**       | Max height/width of the embedded cover _(see note below)_              |
| `require_mime_type` = _[blank]_     | If not blank, required MIME type for embedded cover _(see note below)_ |
| `create_mime_type` = `"image/jpeg"` | MIME type for embedding cover images (image/jpeg or image/png)         |
| `create_max_height_width` = **600** | Target embedded cover height/width (source can scale down, not up)     |
| `create_jpeg_quality` = **80**      | If `create_mime_type` is image/jpeg, use this quality (1 - 95)         |

<!-- pyml enable line-length -->

> **Note**: The `max_height_width` and `require_mime_type` settings only apply
> to albums where no "front cover source" image is defined.
