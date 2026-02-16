# albums

A rich text-based interactive tool to help manage a library of music, clean up
metadata tags and file organization, and sync parts of the library to digital
audio players

- [Read the documentation here](https://4levity.github.io/albums/)

## Overview

`albums` works with media files and tags, but primarily acts on "albums" rather
than individual files.

It scans the media library and creates a database. It supports adding albums to
"collections," for example to make a list of albums to sync to a digital audio
player. It can also perform the sync. There are automated checks and interactive
fixes for metadata related issues such as track numbering (sequence, totals,
disc numbers), album-artist tags, etc.

## Supported Media

Most features require each album (soundtrack, mixtape...) to be in a folder.

Any album with recognized media files can be scanned. However, most of the check
features require `albums` to understand the tags. FLAC, Ogg Vorbis, and other
files with Vorbis comment metadata using standard names are supported. ID3 is
supported. JPEG, PNG and GIF files in the album folder are scanned. Other media
files have limited support and checks may be skipped.

## System Requirements

Requires Python 3.12+. Primarily tested on Linux and Windows. Should work on any
64-bit x86 or ARM system with Linux, macOS or Windows. (For wider support, one
could remove the dependency on non-essential library `scikit-image`.)
