# albums

> A rich text-based interactive command line tool to help manage a library of
> music, clean up metadata tags and file organization, and sync parts of the
> library to digital audio players

`albums` works with media files and tags, but primarily acts on "albums" rather
than individual files.

## Overview

`albums` scans the library and creates a database. It supports adding albums to
"collections," for example to make a list of albums to sync to a digital audio
player. It can also perform the sync. There are automated checks and interactive
fixes for metadata related issues sich as track numbering (sequence, totals,
disc numbers), album-artist tags, etc.

## Supported Media

Most features require each album (soundtrack, mixtape...) to be in a folder.

Any album with recognized media files can be scanned. However, most of the check
features require `albums` to understand the tags. FLAC, Ogg Vorbis, and other
files with Vorbis comment metadata using standard names are supported. ID3 is
supported but many tags are ignored. Other media files have limited support and
checks may be skipped.

## System Requirements

Requires Python 3.14. Developed/tested only on Linux. Probably works on MacOS.
Interactive features might not work on Windows.

## Getting Started

Builds not yet distributed. See [docs/developing.md](./docs/developing.md).
