---
icon: lucide/list-checks
---

# Checks: General Fields

Field checks not related to numbering, pictures or the per-album fields on
the [Album Fields](./checks_fields_per_album.md) page.

## extra-whitespace

None of the basic fields like album, artist, title, track number, etc. should
have extra spaces or other whitespace characters at the beginning or end.

**Automatic fix**: Remove whitespace from the beginning and end of all values
for all supported basic text fields.

## legacy-fields

Some files may contain legacy fields that map to the standard fields. For
example, `album artist` is a legacy name for the standard `albumartist`. And
`label` or `publisher` are legacy names for `organization`, while `totaldiscs`
is a legacy name for `disctotal`.

Some tools may still create these legacy fields. This check reports when any
tracks in an album have legacy fields present so they can be converted to the
standard equivalents.

**Automatic fix**: Remove each legacy field and set the corresponding standard
field. If multiple tracks have values for the same field (from both legacy and
standard sources), the values are merged with duplicates removed.

## album

Tracks should have `album` fields. The fix attempts to guess album name from
fields on other tracks in the folder, and the name of the folder. Choose from
options.

**Automatic fix**: If there is exactly one option for the album name, use it.

<!-- pyml disable line-length -->

| Option = default              | Description                                                          |
| ----------------------------- | -------------------------------------------------------------------- |
| `ignore_folders` = `["misc"]` | a list of folder names (not paths) where this rule should be ignored |

<!-- pyml enable line-length -->

## album-artist

The "album artist" field (e.g. `albumartist`, `TPE2`) allows many media players
to group tracks in the same album when the "artist" is not the same on all the
tracks.

Rules:

- If any tracks have different artists, all tracks should have the same album
  artist.
- If any track has album artist, all tracks should have the same album artist.

The fix offers candidates found in the fields plus the option "Various Artists".
It can also apply a policy from options below.

!!!success "Dependency"

    Requires the `legacy-fields` check to pass first.

**Automatic fix**: If the album artist is or would be redundant, and one of the
optional policies below is enabled, apply the policy.

<!-- pyml disable line-length -->

| Option = default                | Description                                                                      |
| ------------------------------- | -------------------------------------------------------------------------------- |
| `remove_redundant` = **false**  | If **true** album artist should be _removed_ when all artist values are the same |
| `require_redundant` = **false** | If **true** album artist is _required_ even if all artist values are the same    |

<!-- pyml enable line-length -->

## artist

An "artist" should be present on all tracks. If it is _missing_ from any tracks,
candidates to fix include the values for artist and album artist taken from all
tracks in the album.

If the name of the parent folder containing the album folder is not in the
ignore list, the parent folder name is also a candidate. Ignored names can be
configured with an option.

!!!success "Dependency"

    Requires the `album-artist` check to pass first.

**Automatic fix**: If there is exactly one candidate for artist name, apply it
to all tracks that do not have an artist field.

<!-- pyml disable line-length -->

| Option = default                                                                                            |
| ----------------------------------------------------------------------------------------------------------- |
| `ignore_parent_folders` = `["compilation", "compilations", "soundtrack", "soundtracks", "various artists"]` |

<!-- pyml enable line-length -->

## single-value-fields

If present, the specified fields should not have multiple values _in the same
track_. Many multiple-value fields are valid, but they might be unintended, and
might cause unpredictable results with various media players. The fix for this
check provides options to concatenate multiple values into a single value, after
removing duplicates.

Other specific checks may enforce a single value for certain fields such as
track number.

To configure how `albums` will combine multiple values, use the `concatenators`
option. Pay attention to whether or not the separator includes extra spaces -
the first option gives "Alice / Bob" and the second gives "Alice/Bob".

By default, whichever concatenator is first will be used when automatic fix is
requested. To disable this, change the automatic_concatenate option.

**Automatic fix**: If a track has **duplicate** values for the field, the
automatic fix will remove them. And if `automatic_concatenate` is enabled
(default), unique values will be combined into a single value.

<!-- pyml disable line-length -->

| Option                  | Default               | Description                                                     |
| ----------------------- | --------------------- | --------------------------------------------------------------- |
| `fields`                | `["artist", "title"]` | List of fields that should have single values                   |
| `concatenators`         | `[" / ", "/", " - "]` | Separator strings used when combining duplicate values into one |
| `automatic_concatenate` | **true**              | If enabled, automatically concatenate unique values             |

<!-- pyml enable line-length -->

## track-title

Each track should have at least one title field. This check doesn't care if a
track has more than one title. If the track doesn't have a title, it can be
guessed from the filename. A number at the start of the filename is assumed to
be the track number (or a disc number and track number if there are two numbers
separated by a dash), and the title is what follows it, as in these examples:

- `01 the title.flac`
- `01. the title.mp3`
- `01 - the title.mp3`
- `1-03 - the title.flac`
- `the title.flac` _(if nothing else matches)_

Only 1-3 digit numbers are treated as track or disc numbers, and a date at the
start of the filename is ignored entirely. A date is a four-digit year, with an
optional month and day, separated by dashes, dots or underscores (e.g.
`2024-01-05`, `2024-01` or `20240105`), so for example
`2024-01-05 Live show.mp3` gives the title `Live show`.

If the filename looks like a track number only, no title guess will be made.
However, if the filename doesn't match any recognized pattern, the guess will
be the whole filename except for the extension.

**Automatic fix**: If every file that has a missing title also has a filename
from which a title can be guessed, fill in all empty titles.

## genre-present

This check applies a user-defined policy for genre fields. By default, if genre
is present on any track, the same genre must be present on all tracks in the
album. The presence policy options are:

- **"consistent"**: either all tracks have genre, or none do
- **"always"**: all tracks should have genre
- **"never"**: genre should be removed

**Automatic fix**: If the policy is "never", always remove the genre. If the
policy is "always", and a consistent genre is set on some tracks, set the same
genre on the others.

<!-- pyml disable line-length -->

| Option = default                   | Description                                                  |
| ---------------------------------- | ------------------------------------------------------------ |
| `presence` = `"consistent"`        | Set the field presence policy for genre                      |
| `per_track` = **false**            | If **true** genre may be different on each track in an album |
| `select_genres` = `["Blues", ...]` | List of genre options to display - edit to suit preferences  |

<!-- pyml enable line-length -->

## musicbrainz-fields

!!!note

    `albums` reads MusicBrainz fields and checks for consistency, but it doesn't
    use the MusicBrainz API or check whether IDs are correct. Use a tool like
    [MusicBrainz Picard](https://picard.musicbrainz.org/) or
    [beets](https://beets.io/) to create and update MusicBrainz fields.

Whether or not you use MusicBrainz, inconsistencies in MusicBrainz fields within
an album can cause problems for some players. When the `MusicBrainz Album Id` or
`MusicBrainz Album Artist Id` or `MusicBrainz Album Release Country` is not the
same on all tracks in an album (or not set on every track), some music players
interpret this as two separate albums even if all the other (non-MusicBrainz)
fields are the same.
This check reports when those fields are not set consistently across the album.

Other behaviors of this check are controlled by the options. If you don't use
MusicBrainz, you might want to remove all MusicBrainz fields to avoid conflicts
between them and the standard fields. If you do use MusicBrainz, you may want to
remove deprecated MusicBrainz fields (`MusicBrainz TRM Id`).

**Automatic fix**: If `MusicBrainz Album Id` or `MusicBrainz Album Artist Id` is
not the same on all tracks (or not set on every track), remove that field from
every track.

**Automatic fix**: If `remove_all` is enabled, remove all MusicBrainz fields.

**Automatic fix**: If `remove_deprecated` is enabled, remove deprecated
MusicBrainz fields.

<!-- pyml disable line-length -->

| Option = default               | Description                                                             |
| ------------------------------ | ----------------------------------------------------------------------- |
| `remove_all` = **false**       | if enabled, remove all MusicBrainz fields                               |
| `remove_deprecated` = **true** | if enabled, remove deprecated MusicBrainz fields (`MusicBrainz TRM Id`) |

<!-- pyml enable line-length -->
