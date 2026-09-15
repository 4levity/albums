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
`albums -m collection=top100 sync <destination>` would copy all albums in the
"top100" collection to the destination.

## Sync and delete

If albums are removed from the collection, or folders/files are renamed, running
another sync to the same destination could leave unwanted or duplicate files.
Alternatively, with the `--delete` option, `albums` will **delete every file in
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
| `collection`                   | The albums collection to filter by for sync         |
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

By default, sync copies audio files from the library to the destination. But if
it is configured with a sync destination, `albums` can also convert audio files
to a format that is suitable for the destination as needed. Using these options
enables transcoding.

Transcoded files will be tagged with basic tags and pictures as supported by
`albums`. Not all tags from source files are copied to the transcoded files.

<!-- pyml disable line-length -->

| Transcoder Option     | Description                                                        |
| --------------------- | ------------------------------------------------------------------ |
| `allow_file_types`    | List of allowed audio file types - if other, transcode album       |
| `max_kbps`            | Maximum bitrate, kbps - if higher (album average), transcode album |
| `max_sample_rate`     | Maximum sample rate, Hz - if higher (any track), transcode album   |
| `max_bits_per_sample` | Maximum bits per sample - if higher (any track), transcode album   |
| `convert_file_type`   | Transcode output file type: `mp3`, `m4a` (aac) or `flac`           |
| `convert_bitrate`     | Transcode output bitrate: `vbr` or a fixed kbps (`flac` has none)  |

<!-- pyml enable line-length -->

`vbr` is only offered for `mp3` (~192 kbps); `m4a` uses fixed bitrates.
Transcoded output is at most 16-bit and stereo, and the sample rate is capped at
`max_sample_rate` if set. All supported source formats can be transcoded, but
only `mp3`, `m4a` and `flac` are output types - for example, ogg vorbis albums
can be transcoded to mp3, but ogg output is not available.

### Transcoder Cache

When the transcoder is used, all converted files are stored in the "transcoder
cache" before copying. By default this cache is in the user data directory. The
transcoder cache size limit is set to 16 gigabytes by default. This is a soft
limit, applied only before and after sync. Older caches are removed, but the
most recently used per-format cache is retained regardless of size.

The transcoder cache location and soft limit are set in `albums config`.
