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
ambiguous values, then higher level checks.

The checks run in the order they appear in this document.

### disc_in_track_number

If the disc number and track number are combined in the track number tag with a
dash (i.e. track number="2-03") instead of being in separate tags, this is
treated as an error. Later checks may require track numbers to be numeric.

**Automatic fix**: Split the values into track number and disc number tags.

### invalid_track_or_disc_number

This check reports when an album has invalid or ambiguous values for track
number, track total, disc number or disc total. If these fields cannot be
resolved to a single valid number, they are not useful and should be removed.

Rule: for each track, if present, track/disc number/total tags should each have
a single value and that value should be a positive number (0 is not valid).

**Automatic fix**: For each of the noted tags in each track, discard all values
that are non-numeric or 0. If exactly one unique value remains, save it.
Otherwise, delete the tag.

### tracktotal_presence

Apply selected policy for whether or not a track total is present on each track.
Additionally, report if any track has a track total tag without a track number.

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

### required_tags

All tracks should have one or more values for each of these tags.

> Disabled by default, set `enable = true` to use.

| Option      | Default               |
| ----------- | --------------------- |
| `tag_names` | `["artist", "title"]` |

### single_value_tags

If present, the specified tags should not have multiple values _in the same
track_. Many multiple-value tags are valid, but they might be unintended, and
might cause unpredictable results with various media players.

The fix provides options to concatenate multiple values into a single value.

| Option      | Default               |
| ----------- | --------------------- |
| `tag_names` | `["artist", "title"]` |

### track_number

Reports on several issues with track number, track total, disc number and disc
total tags. These are tied together because for example if the disc number isn't
set correctly, we can't tell whether the track total (per disc) is correct or
not.

The rules are:

- If any track has disc number, all tracks should have a single decimal disc
  number
- If present, the disc total should be the number of distinct disc number values
- Disc numbers should start at 1 and be sequential (1, 2, 3...)
- Every track should have a single decimal track number
- For each disc, track numbers should start at 1 and be sequential
- For each disc, if track total is present, it should be the number of tracks on
  that disc

<!-- pyml disable line-length -->

| Option                 | Default    | Description                                                                |
| ---------------------- | ---------- | -------------------------------------------------------------------------- |
| `ignore_folders`       | `["misc"]` | in folders with these names, ignore track/disc numbers                     |
| `warn_disc_per_folder` | `false`    | if an album (folder) has a disc number, there should be more than one disc |

<!-- pyml enable line-length -->

### zero_pad_numbers

Apply selected policies for zero-padding in the track number/total and disc
number/total tags.

> Some media players do not show tracks in the correct order unless they are
> zero-padded, because for example "2" comes after "10" when sorted
> alphabetically.

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
