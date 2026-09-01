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
Ogg Vorbis), `TDRL` in ID3 tags (MP3, AIFF), `aard` in MP4 iTunes atoms (M4A)
and `WM/Year` in ASF/WMA tags.

### Track total and disc total

If track number and track total are combined in the tracknumber field (or ID3
TRCK) with a slash like "04/12" instead of being in separate fields, `albums`
will see that as "tracknumber=04" and "tracktotal=12" and be able to write to
the track number and track total fields as if they were separate. The same rule
applies for disc number and disc total if combined in the discnumber field (or
ID3 TPOS frame).
Storing track total and disc total this way is normal for ID3 tags.
