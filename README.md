# albums

Manage a library of music: configurably validate and fix tags and metadata,
rename files, format and embed album art, and sync parts of the library to
digital audio players or portable storage

- [Read the documentation here](https://4levity.github.io/albums/)

## Overview

`albums` works with media files and tags, but primarily acts on "albums" rather
than individual files. Everything is done locally and an Internet connection is
not required. It's a command-line application that runs in a terminal, but it is
designed to be user friendly, with interactive menus, rich text formatting,
tables and even blocky graphics.

It scans the media library and creates a database to make subsequent operations
fast. It supports adding albums to "collections," for example to make a list of
albums to sync to a digital audio player. It can also perform the sync. It has
[many automated checks and fixes](https://4levity.github.io/albums/all_checks/)
for metadata related issues such as track numbering (sequence, totals, disc
numbers), album-artist tags, embedding cover art, etc.

## Why use `albums` instead of other music library tools?

Use them all, you don't have to decide. If you have missing metadata or
unidentified recordings and you want to use online databases to fill in the
blanks, [MusicBrainz Picard](https://picard.musicbrainz.org/) is good for that.
For editing tags with some fancy features and automation,
[puddletag](https://docs.puddletag.net/#) and
[MP3TAG](https://www.mp3tag.de/en/index.html) (proprietary but no cost for
Windows version) are nice, while [EasyTAG](https://wiki.gnome.org/Apps/EasyTAG)
is simple and quick.

`albums` has some functionality related to these tools, but a different focus.
Its main use is to find and fix metadata issues and apply tag/filename policies
one album at a time across a large collection that's mostly organized (or at
least in folders by albums). It does this with many individually-configurable
"checks" which are mostly independent, letting the user decide which issues to
address. And its DAP/external storage sync feature may prove useful.

## Supported Media

**FLAC**, **Ogg Vorbis** and **MP3/ID3** are supported. **M4A** and **WMA**
files are read but `albums` doesn't comprehend their tags yet so most checks
are skipped. JPEG, PNG and GIF files in the album folder are loaded as
candidates for cover art.

More formats and tag comprehension will likely be added if requested.

## System Requirements

Requires Python 3.12+. Primarily tested on Linux and Windows. Should work on
almost any 64-bit x86 or ARM system with Linux, macOS or Windows. (32-bit and
wider OS support possible by dropping `scikit-image` library used for measuring
image similarity.)
