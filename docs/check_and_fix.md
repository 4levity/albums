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
| `--fix` / `-f`         | If the check provides a menu of fixes, you will be shown details and prompted to select an option. |
| `--interactive` / `-i` | For every issue, you will be asked what to do, even if the only options are ignore or manual fix.  |

<!-- pyml enable line-length -->

> Before running checks, ensure the database is up to date by running
> `albums scan`.

See `albums --help` and `albums check --help` for more.

## Checks

### album_artist

The "album artist" tag (e.g. `albumartist`, `TPE2`) groups tracks in the same
album when the "artist" tag is not the same on all the tracks.

- If any tracks in an album have different artist tags, all tracks should have
  the same album artist tag.
- If any track has an album artist tag, all tracks should have the same album
  artist tag.

<!-- pyml disable line-length -->

| Option              | Default   | Description                                                                                              |
| ------------------- | --------- | -------------------------------------------------------------------------------------------------------- |
| `remove_redundant`  | **false** | The album artist tag should be removed if all the artist tags are the same.                              |
| `require_redundant` | **false** | There should always be an album artist tag even if all the artist tags are the same. (default **false**) |

<!-- pyml enable line-length -->

### album_tag

Tracks should have `album` tags. The fix attempts to guess album name from tags
on other tracks in the folder, and the name of the folder. Choose from options.

**Automatic fix**: If there is exactly one option for the album name, use it.

<!-- pyml disable line-length -->

| Option           | Default    | Description                                                          |
| ---------------- | ---------- | -------------------------------------------------------------------- |
| `ignore_folders` | `["misc"]` | a list of folder names (not paths) where this rule should be ignored |

<!-- pyml enable line-length -->

### album_under_album

This check reports when an album has another album in a subfolder. Maybe they
should be in separate folders. No fix provided.

### required_tags

All tracks should have one or more values for each of these tags.

> Disabled by default, set `enable = true` to use.

| Option      | Default               |
| ----------- | --------------------- |
| `tag_names` | `["artist", "title"]` |

### single_value_tags

If present, the specified tags should usually not have multiple values within
the same track. It is valid for a track to have more than one title, but
multiple-value tags may have unpredictable results in some media players.

<!-- pyml disable line-length -->

| Option      | Default                                                             |
| ----------- | ------------------------------------------------------------------- |
| `tag_names` | `["discnumber", "disctotal", "title", "tracknumber", "tracktotal"]` |

<!-- pyml enable line-length -->

### track_number

Reports on several issues with tracknumber, tracktotal, discnumber and disctotal
tags. These are tied together because for example if the disc number isn't set
correctly, we can't tell whether the track total (per disc) is correct or not.

If tracknumber and tracktotal are combined in the tracknumber tag with a slash
(i.e. tracknumber="04/12") instead of separate tags, they will be treated as
separate values. Same for discnumber and disctotal if combined in the discnumber
tag.

- if any track has disc number, all should have a single decimal disc number
- if any track has disc total, all should have a single decimal disc total
- if present, the disc total should be the number of distinct disc number values
- discnumbers should start at 1 and be sequential (1, 2, 3...)
- every track should have a single decimal tracknumber tag
- for each discnumber, tracks should start at 1 and be sequential
- for each discumber, if any track has track total, all should have a single
  decimal track total
- for each discnumber, if track total is present, it should be the number of
  tracks on that disc

<!-- pyml disable line-length -->

| Option                 | Default    | Description                                                                |
| ---------------------- | ---------- | -------------------------------------------------------------------------- |
| `ignore_folders`       | `["misc"]` | in folders with these names, ignore track/disc numbers                     |
| `warn_disc_per_folder` | `false`    | if an album (folder) has a disc number, there should be more than one disc |

<!-- pyml enable line-length -->

### zero_pad_numbers

Enforce a policy for zero-padding in the track number/total and disc
number/total tags. Some devices may not show tracks in the correct order unless
they are zero-padded, because for example "2" comes after "10" if you sort
alphabetically.

**Automatic fix**: If no major problems detected in existing tags, apply policy

Set a policy for each tag. The policy options are:

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

> The default settings will result in, for example, track 04/07 and disc 1/1. Or
> setting all policies to "if_needed" will result in, for example, track 4/7 and
> track 04/12
