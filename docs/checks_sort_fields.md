---
icon: lucide/list-checks
---

# Checks: Sort Order Fields

The checks `album-sort`, `album-artist-sort` and `artist-sort` check the sort
order fields `albumsort`, `albumartistsort` and `artistsort`. Each of these
fields is the sort order for a corresponding field: `album` for `albumsort`,
`albumartist` for `albumartistsort` and `artist` for `artistsort`. These checks
apply the presence policy and check that the value is correct.

## Common Behavior

The sort value for each track is generated from the value of the corresponding
field on that track. A leading article is moved to the end: "The Beatles"
becomes "Beatles, The". If a track has several values for the source field, they
are concatenated (with " / ") to make the sort value.

A sort value can't be generated for a track without a source value, so the sort
field must not be present on that track; if it is, it is removed. Any other
value is considered incorrect, and there is no option to keep an alternative
value - if you want to keep a manual sort value, ignore this check for the
album.

The presence policy is applied as follows:

- "always": all tracks should have the generated value. If the generated value
  can't be made for every track (because a track has no source value), the
  policy can't be satisfied, so the issue is reported without an automatic fix.
- "consistent": the field should be on all tracks (each set to the generated
  value) or on none. A fix is offered only if the value needs to be set (e.g.
  the source value has a leading article) or if the value is set incorrectly or
  on some tracks but not others. When the generated value can't be made for
  every track, the only automatic fix is to remove the field from all tracks.
- "never": the field is removed from any track it is present on.

**Automatic fix**: set the generated value on all tracks, or remove the field
from all tracks - never set it on only some tracks.

<!-- pyml disable line-length -->

| Option     | Default        | Description                   |
| ---------- | -------------- | ----------------------------- |
| `presence` | `"consistent"` | Set the field presence policy |

<!-- pyml enable line-length -->

## album-sort

The source field is `album`, which the `album` check ensures has a single value
on all tracks, so the generated sort value is the same on all tracks of an
album.

!!!success "Dependency"

    Requires the `album` check to pass first.

## album-artist-sort

The source field is `albumartist`, which the `album-artist` check ensures has a
single value on all tracks, so the generated sort value is the same on all
tracks of an album. The sort value is generated from `albumartist`, not from
`artist`.

!!!success "Dependency"

    Requires the `album-artist` check to pass first.

## artist-sort

The source field is `artist`. Unlike the album fields, the artist value may
differ on each track (e.g. a guest artist), in which case the sort value may
differ on each track as well.

!!!success "Dependency"

    Requires the `artist` check to pass first.
