---
icon: lucide/search-check
---

# Check and Fix

A _check_ is a module that can report on problems with albums, such as tags,
filenames or directory structure. Some checks provide options to fix the
problem, or a single automatic option.

Using a tool to automatically repair your music files in bulk might have
unintended results. If it goes very badly, simply restore your backup.

## Configuration

Each check can be configured in the `[checks.<check name>]` section of
config.toml. See
[sample/config.toml](https://github.com/4levity/albums/blob/main/sample/config.toml)
for examples. Every check has an `enabled` setting which may be `true` or
`false`. It may have other settings, described below.

## Check Command

To report on and optionally fix issues in the library, use the `albums check`
command. This will run all enabled checks, unless some check names are provided,
in which case it will run those only. To also apply fixes, see options below.

<!-- pyml disable line-length -->

| Option                 | Description                                                                                        |
| ---------------------- | -------------------------------------------------------------------------------------------------- |
| `--automatic` / `-a`   | If the check has an automatic option, it will be applied without asking.                           |
| `--preview` / `-p`     | Preview the changes that would be made if you use the -a option.                                   |
| `--fix` / `-f`         | If the check provides a menu of fixes, you will be shown details and prompted to select an option. |
| `--interactive` / `-i` | For every issue, you will be asked what to do, even if the only options are ignore or manual fix.  |

<!-- pyml enable line-length -->

> Before running checks, ensure the database is up to date by running
> `albums scan`.

See `albums --help` and `albums check --help` for more.

## Checks

Checks run in a particular order. First basic tag issues like non-numeric or
ambiguous values, then higher level checks. Some checks require specific prior
checks to pass first.

The checks run in the order they appear in this document.

### disc_in_track_number

If the disc number and track number are combined in the track number tag with a
dash (i.e. track number="2-03") instead of being in separate tags, this is
treated as an error. Subsequent checks require track numbers to be numeric.

**Automatic fix**: Split the values into track number and disc number tags.

### invalid_track_or_disc_number

This check reports when an album has invalid or ambiguous values for track
number, track total, disc number or disc total. If these fields cannot be
resolved to a single valid number, they are not useful and should be removed.

Rule: for each track, if present, track/disc number/total tags should each have
a single value and that value should be a positive number (0 is not valid).

!!!note

    Requires the `disc_in_track_number` check to pass first.

**Automatic fix**: For each of the noted tags in each track, discard all values
that are non-numeric or 0. If exactly one unique value remains, save it.
Otherwise, delete the tag.

### tracktotal_presence

Apply selected policy for whether or not a track total is present on each track.
Additionally, report if any track has a track total tag without a track number.
This check does not check whether the track total is correct.

Policies:

- **"consistent"**: either all tracks on an album have track total, or none do
- **"always"**: all tracks should have track total
- **"never"**: track total should be removed

**Automatic fix**: If the policy is "consistent" but some tracks are missing
track total, remove it from all tracks. If the policy is "never", always remove
the tag. (There is currently no automatic fix if the policy is "always".)

| Option   | Default        | Description                                 |
| -------- | -------------- | ------------------------------------------- |
| `policy` | `"consistent"` | Set the tag presence policy for track total |

### disctotal_presence

Exactly the same as `tracktotal_presence` except it is for the disc total.

### album_tag

Tracks should have `album` tags. The fix attempts to guess album name from tags
on other tracks in the folder, and the name of the folder. Choose from options.

**Automatic fix**: If there is exactly one option for the album name, use it.

<!-- pyml disable line-length -->

| Option           | Default    | Description                                                          |
| ---------------- | ---------- | -------------------------------------------------------------------- |
| `ignore_folders` | `["misc"]` | a list of folder names (not paths) where this rule should be ignored |

<!-- pyml enable line-length -->

### album_artist

The "album artist" tag (e.g. `albumartist`, `TPE2`) allows many media players to
group tracks in the same album when the "artist" tag is not the same on all the
tracks.

- If any tracks in an album have different artist tags, all tracks should have
  the same album artist tag.
- If any track has an album artist tag, all tracks should have the same album
  artist tag.

The fix gathers candidates from tags plus "Various Artists". It may also apply a
policy from the options below.

**Automatic fix**: If a policy is enabled to set or remove redundant album
artist, it can be applied automatically when no other problems are detected.

<!-- pyml disable line-length -->

| Option              | Default   | Description                                                                          |
| ------------------- | --------- | ------------------------------------------------------------------------------------ |
| `remove_redundant`  | **false** | The album artist tag should be removed if all the artist tags are the same.          |
| `require_redundant` | **false** | There should always be an album artist tag even if all the artist tags are the same. |

<!-- pyml enable line-length -->

### artist_tag

The "artist" tag should be present on all tracks. If it is missing from any
track, candidates include values for artist and album artist for all tracks.

If the parent folder containing the album folder is not a prohibited name, it is
also a candidate. Prohibited names can be configured with an option.

!!!note

    Requires the `album_artist` check to pass first.

**Automatic fix**: If there is exactly one candidate for artist name, apply it
to all tracks that do not have an artist tag.

<!-- pyml disable line-length -->

| Option                  | Default                                                                           |
| ----------------------- | --------------------------------------------------------------------------------- |
| `ignore_parent_folders` | `["compilation", "compilations", "soundtrack", "soundtracks", "various artists"]` |

<!-- pyml enable line-length -->

### required_tags

All tracks should have one or more values for each of these tags.

> Disabled by default, set `enable = true` to use.

| Option | Default               |
| ------ | --------------------- |
| `tags` | `["artist", "title"]` |

### single_value_tags

If present, the specified tags should not have multiple values _in the same
track_. Many multiple-value tags are valid, but they might be unintended, and
might cause unpredictable results with various media players.

Other checks also enforce a single value for specific tags such as track number.

The fix provides options to concatenate multiple values into a single value,
after removing duplicates.

**Automatic fix**: When a track has **duplicate** values for the tag, an
automatic fix is available that only removes the duplicates. If there are
multiple unique values, they will be kept and still flagged by this check.

| Option | Default               |
| ------ | --------------------- |
| `tags` | `["artist", "title"]` |

### disc_numbering

Reports on issues with disc number and disc total. This high level check
requires that the individual tag values are valid. In other words,
`disc_in_track_number` and `invalid_track_or_disc_number` must pass, or this
check will just fail saying "couldn't arrange tracks by disc".

Rules:

- If any track has disc number, all tracks should have disc number
- Disc numbers should start at 1 and be sequential (1, 2, 3...)
- If present, the disc total should be the number of distinct disc number values
  which should be the same as the highest disc number

!!!note

    Requires the `invalid_track_or_disc_number` check to pass first.

<!-- pyml disable line-length -->

| Option                      | Default  | Description                                                  |
| --------------------------- | -------- | ------------------------------------------------------------ |
| `discs_in_separate_folders` | **true** | albums with multiple discs may be stored in separate folders |

<!-- pyml enable line-length -->

> When `discs_in_separate_folders` is enabled (default), this check will ignore
> when an album is only one disc of a multiple disc set. But then it cannot tell
> whether an album is missing a disc number or if disc total is correct. If you
> can put multiple-disc albums together in one folder, set this to **false**.

### track_numbering

Reports on several issues with track numbers and track totals, including
apparently missing tracks.

The rules are:

- Every track should have a single decimal track number
- For each disc, track numbers should start at 1 and be sequential
- For each disc, if track total is present, it should be the number of tracks on
  that disc

!!!note

    Requires the `invalid_track_or_disc_number` check to pass first.

<!-- pyml disable line-length -->

| Option           | Default    | Description                                                |
| ---------------- | ---------- | ---------------------------------------------------------- |
| `ignore_folders` | `["misc"]` | in all folders with these names, ignore track/disc numbers |

<!-- pyml enable line-length -->

### track_title

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

### zero_pad_numbers

Apply selected policies for zero-padding in the track number/total and disc
number/total tags.

> Some media players and many file managers do not show tracks in the correct
> order unless the track numbers are zero-padded, because for example "2" comes
> after "10" when sorted alphabetically.

!!!note

    Requires the `invalid_track_or_disc_number` check to pass first.

**Automatic fix**: If no major problems detected in relevant tags, apply policy.

Choose a policy for each tag. The policy options are:

- **"ignore"**: don't check this tag
- **"never"**: do not use leading zeros
- **"if_needed"**: leading zeros when required for all values to have the same
  number of digits (same as "never" for track/disc totals)
- **"two_digit_minimum"**: all values should be at least two digits (three if
  more than 99 values)

| Option            | Default               |
| ----------------- | --------------------- |
| `tracknumber_pad` | `"two_digit_minimum"` |
| `tracktotal_pad`  | `"two_digit_minimum"` |
| `discnumber_pad`  | `"if_needed"`         |
| `disctotal_pad`   | `"never"`             |

> The default settings will result in, for example, track **04** of **07** and
> disc **1** of **1**. If you set all policies to "if_needed" instead, you get,
> for example, track **4** of **7** and track **04** of **12**.

### album_under_album

This check reports when an album has another album in a subfolder. Maybe they
should be in separate folders. No fix offered.
