---
icon: lucide/arrow-big-right-dash
---

# Synchronize

The `albums sync` command will copy some or all of the configured music library
to another location. Only files that have been updated are copied. This enables
updating portable collections and digital audio players as long as they can be
accessed by the operating system like a regular storage device.

> Only music files that `albums` knows about are copied. If there are other
> files in the library album directory, including images, `sync` ignores them!

## Use a collection

`albums` can associate specific albums with "collection" tags (see
[Usage](./usage.md)). A collection could define a subset of the library to copy
to a digital audio player, phone or memory card. The command
`albums --collection top100 sync <destination>` would copy all albums in the
"top100" collection to the destination.

## Sync and delete

If albums are removed from the collection, or folders/files are renamed, running
another sync to the same destination could leave unwanted or duplicate files.
Alternatively, the `--delete` option and `albums` will **delete every file in
the destination that is not being synced!** This is good if the destination is,
for example, a folder on a memory card for a digital audio player, which doesn't
contain any other data, and `albums sync` will manage everything there.

## Sync Destination

Rather than specify the path each time, you can configure one or more "sync
destinations" in the `albums config` menu. This also allows configuring
additional advanced options for the sync:

<!-- pyml disable line-length -->

| Basic Option                   | Description                                         |
| ------------------------------ | --------------------------------------------------- |
| `collection`                   | The albums collection tag to sync                   |
| `path_root`                    | The destination path where files will be copied     |
| `relpath_template_artist`      | Template for album folder name (albums with artist) |
| `relpath_template_compilation` | Template for album folder name (compilations)       |

<!-- pyml enable line-length -->

If `relpath_template_artist` or `relpath_template_compilation` are blank
(default), artist albums and compilations will be organized just the same way
they are in the library.

### Transcoder Options

!!!warning

    If transcoder options are enabled, the transcoder cache created by
    `albums` can consume a very large amount of disk space. See options below.

!!!note

    **ffmpeg** must be installed and available on the PATH to use transcoder options.

By default, sync copies audio files from the library to the destination. But if
it is configured with a sync destination, `albums` can also convert audio files
to a format that is suitable for the destination as needed. Using these options
enables transcoding.

Transcoded files will be tagged with basic tags and pictures as supported by
`albums`. Not all tags from source files are copied to the transcoded files.

<!-- pyml disable line-length -->

| Transcoder Option  | Description                                                  |
| ------------------ | ------------------------------------------------------------ |
| `allow_file_types` | List of allowed audio file types - if other, transcode album |
| `max_kbps`         | Maximum bitrate (album average) - if higher, transcode album |
| `convert_profile`  | Conversion profile including _ffmpeg_ options and file type  |

<!-- pyml enable line-length -->

The convert profile is formatted as `[FFMPEG_OUTPUT_OPTIONS] FILE_TYPE`

Example convert profile for 320kbps MP3: `-b:a 320k mp3`

### Transcoder Cache

When the transcoder is used, all converted files are stored in the "transcoder
cache" before copying. By default this cache is in the user data directory. The
transcoder cache size limit is set to 16 gigabytes by default, and this is a
soft limit: size limits are only applied before and after sync, and while older
caches are removed, the most recently used per-format cache is retained
regardless of size.

The transcoder cache location and soft limit are set in `albums config`.
