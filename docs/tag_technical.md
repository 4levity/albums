---
icon: lucide/wrench
---

# Tag Handling

## Field Conversion

`albums` attempts to apply some of the same checks and rules with Vorbis
comments (FLAC, Ogg Vorbis), ID3 tags (MP3) and MP4 iTunes atoms (M4A). To
enable this, common fields like track number are converted to the typical Vorbis
comment field names. For example, the ID3 frames TPE1 "Artist" and TPE2 "Band"
are referenced by the standard field names "artist" and "albumartist".
In other words, if `albums` writes a new "album artist" to your MP3, behind
the scenes it's actually writing to the TPE2 frame.

The same applies to the release date field: `date` in Vorbis comments (FLAC,
Ogg Vorbis), `TDRC` in ID3 tags (MP3, AIFF), `aard` in MP4 iTunes atoms (M4A)
and `WM/Year` in ASF/WMA tags.

### ID3 release date

In ID3v2.3 the only date frame was `TDRC` ("recording time"), so that is where
tools stored the release date. ID3v2.4 added `TDRL` ("release time") for that
purpose, but by then `TDRC` was already established as the release date frame in
most files and tools, and it remains the de facto standard. The `TDRL` frame is
largely ignored by other software, and when both frames are present they can
disagree and create confusion.

To match what is actually seen in the wild, `albums` writes the release date to
`TDRC` and treats `TDRL` as a deprecated alias for the release date: on read,
non-duplicate values from `TDRL` are merged into the release date field (so a
file that only has `TDRL` still shows its date), and the `legacy-fields` check
reports files with a `TDRL` frame and converts it to `TDRC`.

### Deprecated fields

`albums` also recognizes a number of legacy field names written by other tools
and treats them as aliases of the standard fields. When reading a file, values
from a legacy field are merged into the standard field (skipping duplicates),
and the `legacy-fields` check reports files that still have legacy fields and
converts them to the standard names.

Legacy Vorbis comment names (FLAC, Ogg Vorbis):

| legacy name        | standard field |
| ------------------ | -------------- |
| `album artist`     | `albumartist`  |
| `disc number`      | `discnumber`   |
| `totaldiscs`       | `disctotal`    |
| `label`            | `organization` |
| `publisher`        | `organization` |
| `track number`     | `tracknumber`  |
| `numtracks`        | `tracktotal`   |
| `number_of_tracks` | `tracktotal`   |
| `totaltracks`      | `tracktotal`   |

Deprecated ID3 frames (MP3, AIFF):

| frame  | standard field |
| ------ | -------------- |
| `TDRL` | `date`         |

### Track total and disc total

If track number and track total are combined in the tracknumber field (or ID3
TRCK) with a slash like "04/12" instead of being in separate fields, `albums`
will see that as "tracknumber=04" and "tracktotal=12" and be able to write to
the track number and track total fields as if they were separate. The same rule
applies for disc number and disc total if combined in the discnumber field (or
ID3 TPOS frame).
Storing track total and disc total this way is normal for ID3 tags.
