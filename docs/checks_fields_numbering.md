---
icon: lucide/list-checks
---

# Checks: Numbering

Track number and disc number field issues.

## disc-in-track-number

If the disc number and track number are combined in the track number field with
a dash (e.g. track number="2-03") instead of being in separate fields, this is
treated as an error. Subsequent checks require track numbers to be numeric.

**Automatic fix**: Split the values into track number and disc number fields.

## invalid-track-or-disc-number

This check reports when an album has invalid or ambiguous values for track
number, track total, disc number or disc total. If these fields cannot be
resolved to a single valid number, they are not useful and should be removed.

Rule: for each track, if present, track/disc number/total fields should each
have a single value and that value should be a positive number (0 is not valid).

!!!success "Dependency"

    Requires the `disc-in-track-number` check to pass first.

**Automatic fix**: For each of the noted fields in each track, discard all
values that are non-numeric or 0. If exactly one unique value remains, save it.
Otherwise, delete the field.

## disc-numbering

Reports on issues with disc number and disc total (`TPOS` in ID3). Optionally,
removes redundant disc number field for sets of one. Use the options below to
control whether multiple disc sets should be required to have all tracks in one
folder. Mismatching disc total values are one reason players incorrectly split
albums.

Rules:

- If any track has disc number, all tracks should have disc number
- Disc numbers should start at 1 and be sequential (1, 2, 3...)
- If present, the disc total should be the number of distinct disc number values
  which should be the same as the highest disc number
- All tracks with disc total should also have disc number
- The selected disc total presence policy should apply
    - **"consistent"**: either all tracks have disc total, or none do
    - **"always"**: all tracks should have disc total
    - **"never"**: disc total should be removed

!!!success "Dependency"

    Requires the `invalid-track-or-disc-number` and `legacy-fields` checks to
    pass first.

**Automatic fix** for disc total policy: If the policy is "never", always remove
the field. If the policy is "always", and a consistent total is set on some
tracks, set the same total on the others.

<!-- pyml disable line-length -->

| Option = default                          | Description                                                     |
| ----------------------------------------- | --------------------------------------------------------------- |
| `discs_in_separate_folders` = **true**    | if true, discs from one album may be stored in separate folders |
| `remove_redundant_discnumber` = **false** | if true, disc number field "1" can be removed if no other discs |
| `disctotal_policy` = `"consistent"`       | Set the field presence policy for disc total                    |

<!-- pyml enable line-length -->

!!!note

    `discs_in_separate_folders` and `remove_redundant_discnumber` cannot both
    be true. If discs are in separate folders, disc 1 might be part of a set.

> When `discs_in_separate_folders` is enabled (default), this check will
> **ignore** albums that have only one disc of a multiple disc set. But that
> also means it cannot tell whether an album is missing a disc number or whether
> disc total is correct. If you can put multiple-disc albums together in one
> folder, do that and set `discs_in_separate_folders` to **false**. Then,
> if desired, you can also set `remove_redundant_discnumber` to **true**.

## track-numbering

Reports on several issues with track numbers and track totals, including
apparently missing tracks.

The rules are:

- Every track should have a single decimal track number
- For each disc, track numbers should start at 1 and be sequential
- For each disc, if track total is present, it should be the number of tracks on
  that disc
- All tracks with track total should also have track number
- The selected track total presence policy should apply:
    - **"consistent"**: either all tracks have track total, or none do
    - **"always"**: all tracks should have track total
    - **"never"**: track total should be removed

!!!success "Dependency"

    Requires the `disc-numbering` check to pass first.

**Automatic fix** for missing track numbers: If track number fields are missing
from some tracks but all track numbers can be guessed from the filename,
recreate track number fields from filenames.

**Automatic fix** for track total policy: If the policy is "never", always
remove the field. If the policy is "always", and a consistent total is set on
some tracks, set the same total on the others.

<!-- pyml disable line-length -->

| Option = default                     | Description                                             |
| ------------------------------------ | ------------------------------------------------------- |
| `ignore_folders` = `["misc"]`        | in all folders with these names, ignore track numbering |
| `tracktotal_policy` = `"consistent"` | Set the field presence policy for track total           |

<!-- pyml enable line-length -->

## zero-pad-numbers

Apply selected policies for zero-padding in the track number/total and disc
number/total fields. Some media players and many file managers do not show
tracks in the correct order unless the track numbers are zero-padded, because
for example "2" comes after "10" when sorted alphabetically.

This check does nothing on **M4A** files because track numbers (and track total,
disc number, disc total) are only stored as plain unformatted numbers.

!!!success "Dependency"

    Requires the `invalid-track-or-disc-number` check to pass first.

**Automatic fix**: If no major problems detected in relevant fields, apply
policy.

Choose a policy for each field. The policy options are:

- **"ignore"**: don't check this field
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
