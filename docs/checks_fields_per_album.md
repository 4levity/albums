---
icon: lucide/list-checks
---

# Checks: Album Fields

This section is only for "generic" per-album fields that should be the same on
all tracks, or not present. There are more checks for fields that need to be the
same per album (e.g. "album" and "album-artist"), but those are not generic.

Per-album field checks all share a purpose: if one of these fields is set
inconsistently on tracks in an album, some players treat this as distinct
albums. So each of these fields should be set to the same value, or not set.

## Common Behavior

Each check applies a user-defined policy for the corresponding field. The
"presence" policy options are:

- **"consistent"**: either all tracks have the field, or none do
- **"always"**: all tracks should have the field
- **"never"**: the field should be removed

If any track has a value, then all values must be the same.

**Automatic fix**: If the policy is "never", always remove the field. If the
policy is "consistent" or "always", and a consistent value is set but only on
some tracks, set that value on the tracks which have no value. And if the policy
is "consistent" but no single value is identified, remove the field from all
tracks.

| Option     | Default        | Description                   |
| ---------- | -------------- | ----------------------------- |
| `presence` | `"consistent"` | Set the field presence policy |

## album-sort, album-artist-sort, barcode, compilation

See above for details on these per-album field checks.

## publisher

See above for common behavior of this check.

!!!success "Dependency"

    Requires the `legacy-fields` check to pass first.

## release-country, release-type

See above for common behavior of this check.

!!!warning

    The `release country` and `release type` fields are only mapped for files
    that use Vorbis Comment tags (e.g. FLAC, Ogg). So if one album has a mix of
    track types where some use Vorbis Comment and others don't, the `presence`
    setting will be ignored for that album and the field will be **removed** if
    present.
